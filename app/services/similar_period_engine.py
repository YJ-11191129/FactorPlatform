from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class SimilarPeriodParams:
    eps: float = 1.5
    min_samples: int = 10
    topk: int = 20
    lookback_exclude: int = 40
    sequence_window: int = 5
    pca_dim: int = 6
    w_level1: float = 0.35
    w_level2: float = 0.30
    w_sequence: float = 0.35
    model_version: str = "similar_period_dbscan_v1"


L1_COLS = [
    "rv_20",
    "tailloss_5_20",
    "illiq_20",
    "vix_z",
    "vrp_z",
    "breadth_stress",
]


def _safe_log_illiq(s: pd.Series) -> pd.Series:
    return np.log1p(pd.to_numeric(s, errors="coerce").fillna(0.0) * 1e12)


def load_snapshot(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def build_feature_stack(snapshot: pd.DataFrame, sequence_window: int = 5) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = snapshot.copy()
    for c in L1_COLS:
        work[c] = pd.to_numeric(work[c], errors="coerce")
    work["log_illiq_20"] = _safe_log_illiq(work["illiq_20"])

    l1 = pd.DataFrame({"date": work["date"]})
    l1["rv_20"] = work["rv_20"]
    l1["tailloss_5_20"] = work["tailloss_5_20"]
    l1["log_illiq_20"] = work["log_illiq_20"]
    l1["vix_z"] = work["vix_z"]
    l1["vrp_z"] = work["vrp_z"]
    l1["breadth_stress"] = work["breadth_stress"]

    l2 = pd.DataFrame({"date": work["date"]})
    for c in l1.columns:
        if c == "date":
            continue
        s = l1[c]
        l2[f"{c}_ma5"] = s.rolling(5, min_periods=5).mean()
        l2[f"{c}_chg3"] = s - s.shift(3)
        l2[f"{c}_slope5"] = s.diff(5)
        l2[f"{c}_vol5"] = s.rolling(5, min_periods=5).std()

    seq = pd.DataFrame({"date": work["date"]})
    for c in ["rv_20", "tailloss_5_20", "log_illiq_20", "vix_z", "vrp_z", "breadth_stress"]:
        for lag in range(sequence_window):
            seq[f"{c}_lag{lag}"] = l1[c].shift(lag)

    valid = (
        l1.drop(columns=["date"]).notna().all(axis=1)
        & l2.drop(columns=["date"]).notna().all(axis=1)
        & seq.drop(columns=["date"]).notna().all(axis=1)
    )
    dates = work.loc[valid, "date"].reset_index(drop=True)
    l1f = l1.loc[valid].drop(columns=["date"]).reset_index(drop=True)
    l2f = l2.loc[valid].drop(columns=["date"]).reset_index(drop=True)
    seqf = seq.loc[valid].drop(columns=["date"]).reset_index(drop=True)
    return dates, l1f, l2f, seqf


def fit_dbscan_for_state_space(l1: pd.DataFrame, l2: pd.DataFrame, seq: pd.DataFrame, eps: float, min_samples: int, pca_dim: int) -> tuple[np.ndarray, np.ndarray]:
    feature_all = pd.concat([l1, l2, seq], axis=1)
    scaler = StandardScaler()
    x = scaler.fit_transform(feature_all)
    dim = max(1, min(pca_dim, x.shape[0] - 1, x.shape[1]))
    xp = PCA(n_components=dim, random_state=42).fit_transform(x)
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(xp)
    return xp, labels


def _forward_return(ret: np.ndarray, idx: int, horizon: int) -> float | None:
    if idx + horizon >= len(ret):
        return None
    return float(np.prod(1.0 + ret[idx + 1 : idx + 1 + horizon]) - 1.0)


def _forward_es05(ret: np.ndarray, idx: int, horizon: int = 10) -> float | None:
    if idx + horizon >= len(ret):
        return None
    val = ret[idx + 1 : idx + 1 + horizon]
    if len(val) < 3:
        return None
    q = np.quantile(val, 0.05)
    tail = val[val <= q]
    if len(tail) == 0:
        return None
    return float(np.mean(tail))


def _as_label(snapshot_row: pd.Series) -> str:
    if "cluster_label" in snapshot_row and pd.notna(snapshot_row["cluster_label"]):
        return str(snapshot_row["cluster_label"])
    return str(snapshot_row.get("regime_label", "UNKNOWN"))


def find_similar_periods(
    snapshot: pd.DataFrame,
    dates: pd.Series,
    l1: pd.DataFrame,
    l2: pd.DataFrame,
    seq: pd.DataFrame,
    labels: np.ndarray,
    params: SimilarPeriodParams,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(dates)
    if n == 0:
        return pd.DataFrame(), pd.DataFrame()

    cur_idx = n - 1
    candidate_idx = np.arange(max(0, cur_idx - params.lookback_exclude))
    if len(candidate_idx) == 0:
        return pd.DataFrame(), pd.DataFrame()

    cur_label = int(labels[cur_idx])
    is_noise = cur_label == -1
    if not is_noise:
        same = candidate_idx[labels[candidate_idx] == cur_label]
        if len(same) >= max(5, min(10, params.topk)):
            candidate_idx = same

    x1 = StandardScaler().fit_transform(l1)
    x2 = StandardScaler().fit_transform(l2)
    x3 = StandardScaler().fit_transform(seq)

    d1 = np.linalg.norm(x1[candidate_idx] - x1[cur_idx], axis=1)
    d2 = np.linalg.norm(x2[candidate_idx] - x2[cur_idx], axis=1)
    d3 = np.linalg.norm(x3[candidate_idx] - x3[cur_idx], axis=1)
    d_all = params.w_level1 * d1 + params.w_level2 * d2 + params.w_sequence * d3

    order = np.argsort(d_all)[: params.topk]
    nearest = candidate_idx[order]

    valid_snapshot = snapshot[snapshot["date"].isin(dates)].sort_values("date").reset_index(drop=True)
    valid_snapshot = valid_snapshot.set_index("date")
    ret_arr = pd.to_numeric(valid_snapshot["mkt_ret"], errors="coerce").fillna(0.0).to_numpy(dtype=float)

    rows: list[dict[str, Any]] = []
    for rank, idx_in_valid in enumerate(nearest, start=1):
        d = dates.iloc[idx_in_valid]
        row = valid_snapshot.loc[d]
        rows.append(
            {
                "asof_date": dates.iloc[cur_idx].strftime("%Y-%m-%d"),
                "current_cluster_label": int(cur_label),
                "current_is_noise": bool(is_noise),
                "match_rank": rank,
                "matched_date": d.strftime("%Y-%m-%d"),
                "distance_total": float(d_all[order[rank - 1]]),
                "distance_level1": float(d1[order[rank - 1]]),
                "distance_level2": float(d2[order[rank - 1]]),
                "distance_sequence": float(d3[order[rank - 1]]),
                "matched_risk_regime": str(row.get("risk_regime", row.get("regime_label", "UNKNOWN"))),
                "matched_market_state": str(row.get("market_state", "RANGE_BOUND")),
                "matched_event_context": str(row.get("event_context", "NONE")),
                "matched_fwd5_return": _forward_return(ret_arr, int(idx_in_valid), 5),
                "matched_fwd10_return": _forward_return(ret_arr, int(idx_in_valid), 10),
                "matched_fwd10_es05": _forward_es05(ret_arr, int(idx_in_valid), 10),
                "model_version": params.model_version,
            }
        )
    lookup = pd.DataFrame(rows)

    cur_row = valid_snapshot.loc[dates.iloc[cur_idx]]
    mean_dist = float(lookup["distance_total"].mean()) if not lookup.empty else np.nan
    conf = 1.0 / (1.0 + max(0.0, mean_dist)) if np.isfinite(mean_dist) else 0.0
    profile = pd.DataFrame(
        [
            {
                "asof_date": dates.iloc[cur_idx].strftime("%Y-%m-%d"),
                "risk_regime": str(cur_row.get("risk_regime", cur_row.get("regime_label", "UNKNOWN"))),
                "market_state": str(cur_row.get("market_state", "RANGE_BOUND")),
                "event_context": str(cur_row.get("event_context", "NONE")),
                "trend_strength": str(cur_row.get("trend_strength", "WEAK")),
                "market_risk_level": str(cur_row.get("market_risk_level", "MEDIUM")),
                "dbscan_label": int(cur_label),
                "is_noise": bool(is_noise),
                "nearest_cluster_label": _as_label(valid_snapshot.loc[pd.to_datetime(lookup.iloc[0]["matched_date"])]) if not lookup.empty else "UNKNOWN",
                "similar_period_count": int(len(lookup)),
                "similarity_confidence": float(conf),
                "model_version": params.model_version,
                "computed_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            }
        ]
    )
    return lookup, profile


def run_similar_period_lookup(snapshot_path: str, params: SimilarPeriodParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshot = load_snapshot(snapshot_path)
    dates, l1, l2, seq = build_feature_stack(snapshot, sequence_window=params.sequence_window)
    _, labels = fit_dbscan_for_state_space(l1, l2, seq, eps=params.eps, min_samples=params.min_samples, pca_dim=params.pca_dim)
    lookup, profile = find_similar_periods(snapshot, dates, l1, l2, seq, labels, params=params)
    return lookup, profile


def persist_similar_outputs(lookup: pd.DataFrame, profile: pd.DataFrame, out_dir: str) -> dict[str, str]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    lookup_csv = root / "similar_period_lookup.csv"
    lookup_parquet = root / "similar_period_lookup.parquet"
    profile_csv = root / "current_state_profile.csv"
    profile_parquet = root / "current_state_profile.parquet"
    lookup.to_csv(lookup_csv, index=False, encoding="utf-8-sig")
    lookup.to_parquet(lookup_parquet, index=False)
    profile.to_csv(profile_csv, index=False, encoding="utf-8-sig")
    profile.to_parquet(profile_parquet, index=False)
    return {
        "lookup_csv": str(lookup_csv),
        "lookup_parquet": str(lookup_parquet),
        "profile_csv": str(profile_csv),
        "profile_parquet": str(profile_parquet),
    }

