from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler

from app.datahub.loaders.qlib_bin import load_daily_bar

try:
    import ruptures as rpt  # type: ignore
except Exception:  # pragma: no cover
    rpt = None


STATE_COLS = [
    "rv_20",
    "semivol_20_minus",
    "tailloss_5_20",
    "illiq_20",
    "turnover_z_20",
    "volume_z_20",
    "dispersion_20",
    "breadth_stress",
    "vix_z",
    "vrp_z",
    "oil_shock_z",
    "usd_cny_z",
    "energy_sector_outperf_5",
]


@dataclass(frozen=True)
class RegimeParams:
    min_size: int = 20
    jump: int = 1
    penalty: float = 12.0
    eps: float = 1.0
    min_samples: int = 10
    pca_dim: int = 5
    scope: str = "A_SHARE_ALL"
    model_version: str = "regime_v1_gaussian_cpd"
    left_window: int = 10
    right_window: int = 10
    cov_epsilon: float = 1e-6
    shock_hit_window_days: int = 3
    transition_hit_start_days: int = 4
    transition_hit_end_days: int = 30
    secondary_hit_window_days: int = 3
    policy_hit_window_days: int = 3
    primary_window_days: int = 20
    post_window_start_days: int = 21
    post_window_end_days: int = 60
    geo_primary_hit_window_days: int = 3
    geo_secondary_hit_window_days: int = 3


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _artifact_root() -> Path:
    override = os.getenv("FACTOR_PLATFORM_REGIME_DIR")
    root = Path(override) if override else (_project_root() / "data" / "exports" / "regime_engine")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _provider_uri() -> str | None:
    return os.getenv("FACTOR_PLATFORM_PROVIDER_URI")


def _real_ohlcv_path() -> str | None:
    env_path = os.getenv("FACTOR_PLATFORM_REAL_OHLCV_PATH")
    if env_path:
        return env_path
    default_path = Path("D:/Kaggle/data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet")
    if default_path.exists():
        return str(default_path)
    return None


def _force_real_daily_mode() -> bool:
    # Default to true after regime hardening: never silently fall back to synthetic in production-like runs.
    raw = os.getenv("FACTOR_PLATFORM_FORCE_REAL_DAILY", "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _universe() -> str:
    return os.getenv("FACTOR_PLATFORM_REGIME_UNIVERSE", "csi300")


def _instrument_limit() -> int:
    raw = os.getenv("FACTOR_PLATFORM_REGIME_INSTRUMENT_LIMIT", "200")
    try:
        v = int(raw)
    except Exception:
        v = 200
    return max(v, 10)


def _rolling_z(s: pd.Series, win: int = 20) -> pd.Series:
    mu = s.rolling(win, min_periods=win).mean()
    sd = s.rolling(win, min_periods=win).std()
    z = (s - mu) / sd.replace(0.0, np.nan)
    return z


def _winsorize_series(s: pd.Series, low: float = 0.01, high: float = 0.99) -> pd.Series:
    ql, qh = s.quantile(low), s.quantile(high)
    return s.clip(lower=ql, upper=qh)


def _severity_weights() -> dict[str, float]:
    return {
        "rv_20": 1.0,
        "semivol_20_minus": 1.0,
        "tailloss_5_20": 1.2,
        "illiq_20": 1.1,
        "turnover_z_20": 0.8,
        "volume_z_20": 0.8,
        "dispersion_20": 1.0,
        "breadth_stress": 1.0,
        "vix_z": 1.2,
        "vrp_z": 1.0,
        "oil_shock_z": 1.2,
        "usd_cny_z": 0.8,
        "energy_sector_outperf_5": 0.9,
    }


def _shock_dates() -> list[date]:
    raw = os.getenv("FACTOR_PLATFORM_SHOCK_DATES", "2020-02-03,2022-04-25,2024-10-09,2025-04-07")
    out: list[date] = []
    for s in raw.split(","):
        s = s.strip()
        if not s:
            continue
        try:
            out.append(date.fromisoformat(s))
        except Exception:
            continue
    return sorted(set(out))


def _secondary_transition_dates() -> list[date]:
    # Can be maintained by research review and passed by env.
    raw = os.getenv(
        "FACTOR_PLATFORM_SECONDARY_DATES",
        "2020-03-02,2020-07-16,2022-05-26,2024-02-05,2024-03-12,2024-05-17,2024-11-06,2025-05-08",
    )
    out: list[date] = []
    for s in raw.split(","):
        s = s.strip()
        if not s:
            continue
        try:
            out.append(date.fromisoformat(s))
        except Exception:
            continue
    return sorted(set(out))


def _policy_regime_dates() -> list[date]:
    raw = os.getenv("FACTOR_PLATFORM_POLICY_DATES", "2024-09-24")
    out: list[date] = []
    for s in raw.split(","):
        s = s.strip()
        if not s:
            continue
        try:
            out.append(date.fromisoformat(s))
        except Exception:
            continue
    return sorted(set(out))


def _geo_event_dates() -> dict[str, date]:
    def _d(env_key: str, default: str) -> date:
        raw = os.getenv(env_key, default).strip()
        try:
            return date.fromisoformat(raw)
        except Exception:
            return date.fromisoformat(default)

    return {
        "primary": _d("FACTOR_PLATFORM_GEO_PRIMARY_DATE", "2026-02-28"),
        "secondary": _d("FACTOR_PLATFORM_GEO_SECONDARY_DATE", "2026-03-12"),
        "persistent_start": _d("FACTOR_PLATFORM_GEO_PERSISTENT_START", "2026-03-23"),
        "persistent_end": _d("FACTOR_PLATFORM_GEO_PERSISTENT_END", "2026-03-29"),
    }


def get_event_library() -> dict[str, list[str]]:
    geo = _geo_event_dates()
    return {
        "primary_shocks": [d.isoformat() for d in _shock_dates()],
        "secondary_transitions": [d.isoformat() for d in _secondary_transition_dates()],
        "primary_policy_dates": [d.isoformat() for d in _policy_regime_dates()],
        "primary_geo_energy_shock_dates": [geo["primary"].isoformat()],
        "secondary_geo_energy_escalation_dates": [geo["secondary"].isoformat()],
        "persistent_energy_crisis_windows": [f"{geo['persistent_start'].isoformat()}~{geo['persistent_end'].isoformat()}"],
    }


def _load_market_frame_from_qlib() -> pd.DataFrame | None:
    provider = _provider_uri()
    if not provider:
        return None

    try:
        df = load_daily_bar(
            provider_uri=provider,
            universe=_universe(),
            instrument_limit=_instrument_limit(),
        )
    except Exception:
        return None

    if df.empty:
        return None

    if "trade_date" not in df.columns:
        return None

    m = df.copy()
    m["trade_date"] = pd.to_datetime(m["trade_date"])
    m = m.sort_values(["asset_code", "trade_date"])
    m["ret"] = m.groupby("asset_code")["close"].pct_change(fill_method=None)
    if "adj_factor" in m.columns:
        m["turnover_proxy"] = m["volume"] * m["adj_factor"].fillna(1.0)
    else:
        m["turnover_proxy"] = m["volume"]
    if "amount" in m.columns:
        m["amount_proxy"] = m["amount"]
    else:
        m["amount_proxy"] = m["close"] * m["volume"].replace(0.0, np.nan)

    def _breadth_stress(g: pd.DataFrame) -> float:
        ret = g["ret"].dropna()
        if ret.empty:
            return np.nan
        neg_ratio = float((ret < 0).mean())
        median_ret = float(ret.median())
        return neg_ratio - median_ret

    agg = (
        m.groupby("trade_date")
        .apply(
            lambda g: pd.Series(
                {
                    "mkt_ret": float(g["ret"].mean(skipna=True)),
                    "mkt_close": float(g["close"].mean(skipna=True)),
                    "mkt_volume": float(g["volume"].sum(skipna=True)),
                    "mkt_turnover": float(g["turnover_proxy"].sum(skipna=True)),
                    "dispersion": float(g["ret"].std(skipna=True)),
                    "breadth_stress_raw": _breadth_stress(g),
                    "illiq_raw": float((g["ret"].abs() / g["amount_proxy"]).replace([np.inf, -np.inf], np.nan).mean(skipna=True)),
                }
            )
        )
        .reset_index()
        .sort_values("trade_date")
    )
    return agg


def _load_market_frame_from_local_ohlcv() -> pd.DataFrame | None:
    p = _real_ohlcv_path()
    if not p:
        return None
    path = Path(p)
    if not path.exists():
        return None

    try:
        df = pd.read_parquet(path, columns=["date", "wind_code", "close", "volume", "amt"])
    except Exception:
        return None

    if df.empty:
        return None

    m = df.copy()
    m["trade_date"] = pd.to_datetime(m["date"])
    m = m.sort_values(["wind_code", "trade_date"])
    m["ret"] = m.groupby("wind_code")["close"].pct_change(fill_method=None)

    agg = (
        m.groupby("trade_date")
        .apply(
            lambda g: pd.Series(
                {
                    "mkt_ret": float(g["ret"].mean(skipna=True)),
                    "mkt_close": float(g["close"].mean(skipna=True)),
                    "mkt_volume": float(g["volume"].sum(skipna=True)),
                    "mkt_turnover": float(g["amt"].sum(skipna=True)),
                    "dispersion": float(g["ret"].std(skipna=True)),
                    "breadth_stress_raw": float((g["ret"] < 0).mean() - g["ret"].median(skipna=True)),
                    "illiq_raw": float((g["ret"].abs() / g["amt"].replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).mean(skipna=True)),
                }
            )
        )
        .reset_index()
        .dropna(subset=["mkt_ret"])
        .sort_values("trade_date")
    )
    return agg


def _load_macro_cross_asset_wide() -> pd.DataFrame | None:
    base = Path("D:/Kaggle/Data/wind_data/03_market_state/macro_cross_asset_daily.parquet")
    p = Path(os.getenv("FACTOR_PLATFORM_MACRO_CROSS_ASSET_PATH", str(base)))
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p, columns=["date", "value", "wind_code"])
    except Exception:
        return None
    if df.empty:
        return None

    x = df.copy()
    x["trade_date"] = pd.to_datetime(x["date"])
    x["wind_code"] = x["wind_code"].astype(str)
    wide = x.pivot_table(index="trade_date", columns="wind_code", values="value", aggfunc="last").sort_index()
    wide = wide.rename(
        columns={
            "CL00.NYM": "wti",
            "USDX.FX": "dxy",
            "VIX.GI": "vix_idx",
            "GC00.CMX": "gold",
            "SPX.GI": "spx",
            "IXIC.GI": "ixic",
        }
    )
    out = wide.reset_index()
    for col in ["wti", "dxy", "vix_idx", "gold", "spx", "ixic"]:
        if col not in out.columns:
            out[col] = np.nan
    return out


def _synthetic_market_frame(periods: int = 420) -> pd.DataFrame:
    rng = np.random.default_rng(20260329)
    end = pd.Timestamp.today().normalize()
    if end.dayofweek >= 5:
        end = end - pd.offsets.BDay(1)
    dates = pd.bdate_range(end=end, periods=periods)
    ret = rng.normal(0.0002, 0.007, periods)

    # Inject two shock windows to make CPD meaningful and reproducible.
    if periods > 260:
        ret[160:180] += rng.normal(-0.0018, 0.020, 20)
        ret[300:315] += rng.normal(-0.0010, 0.016, 15)

    close = 100 * np.cumprod(1 + ret)
    volume = np.exp(rng.normal(16.2, 0.35, periods))
    turnover = volume * close
    dispersion = np.abs(rng.normal(0.012, 0.004, periods)) + np.abs(ret) * 0.8
    breadth_stress_raw = np.clip(0.55 - ret * 15 + rng.normal(0, 0.08, periods), 0, 1.2)
    illiq_raw = np.clip(np.abs(ret) / np.maximum(turnover, 1.0), 0, None)

    return pd.DataFrame(
        {
            "trade_date": dates,
            "mkt_ret": ret,
            "mkt_close": close,
            "mkt_volume": volume,
            "mkt_turnover": turnover,
            "dispersion": dispersion,
            "breadth_stress_raw": breadth_stress_raw,
            "illiq_raw": illiq_raw,
        }
    )


def _build_state_vector(mkt: pd.DataFrame) -> pd.DataFrame:
    df = mkt.copy().sort_values("trade_date").reset_index(drop=True)
    r = df["mkt_ret"].fillna(0.0)
    neg_r = r.where(r < 0.0, 0.0)

    df["rv_20"] = np.sqrt(252.0) * r.rolling(20, min_periods=20).std()
    df["semivol_20_minus"] = np.sqrt(252.0) * neg_r.rolling(20, min_periods=20).std()
    df["tailloss_5_20"] = (
        r.rolling(20, min_periods=20)
        .apply(lambda x: float(np.mean(np.sort(x)[: max(1, int(np.ceil(len(x) * 0.05)))])), raw=True)
        .abs()
    )
    df["illiq_20"] = df["illiq_raw"].rolling(20, min_periods=20).mean()
    df["volume_z_20"] = _rolling_z(np.log1p(df["mkt_volume"]), 20)
    df["turnover_z_20"] = _rolling_z(np.log1p(df["mkt_turnover"]), 20)
    df["dispersion_20"] = df["dispersion"].rolling(20, min_periods=20).mean()
    df["breadth_stress"] = df["breadth_stress_raw"].rolling(5, min_periods=5).mean()

    # v1 proxy: vix_z from rv itself, vrp_z from semivol-rv spread.
    df["vix_proxy"] = df["rv_20"].rolling(5, min_periods=5).mean()
    df["vrp_proxy"] = (df["semivol_20_minus"] - df["rv_20"]).rolling(5, min_periods=5).mean()
    df["vix_z"] = _rolling_z(df["vix_proxy"], 20)
    df["vrp_z"] = _rolling_z(df["vrp_proxy"], 20)

    macro = _load_macro_cross_asset_wide()
    if macro is not None and not macro.empty:
        df = df.merge(macro, on="trade_date", how="left")
    else:
        for col in ["wti", "dxy", "vix_idx", "gold", "spx", "ixic"]:
            df[col] = np.nan

    df["wti_ret_1"] = pd.to_numeric(df["wti"], errors="coerce").pct_change(fill_method=None)
    df["wti_ret_5"] = pd.to_numeric(df["wti"], errors="coerce").pct_change(5, fill_method=None)
    df["wti_z_20"] = _rolling_z(pd.to_numeric(df["wti"], errors="coerce"), 20)
    df["oil_realized_vol_20"] = np.sqrt(252.0) * df["wti_ret_1"].rolling(20, min_periods=20).std()
    df["oil_vol_z_20"] = _rolling_z(df["oil_realized_vol_20"], 20)
    df["oil_shock_z"] = 0.7 * df["wti_z_20"].fillna(0.0) + 0.3 * df["oil_vol_z_20"].fillna(0.0)
    df["dxy_z_20"] = _rolling_z(pd.to_numeric(df["dxy"], errors="coerce"), 20)
    df["usd_cny_z"] = df["dxy_z_20"]  # data proxy: DXY z-score
    df["energy_sector_outperf_5"] = df["wti_ret_5"].fillna(0.0) - df["mkt_close"].pct_change(5).fillna(0.0)

    out = df[["trade_date", *STATE_COLS]].copy()
    for c in ["oil_shock_z", "usd_cny_z", "energy_sector_outperf_5"]:
        out[c] = out[c].fillna(float(out[c].median()) if out[c].notna().any() else 0.0)
    out = out.dropna().reset_index(drop=True)
    for c in STATE_COLS:
        out[c] = _winsorize_series(out[c].astype(float))
    return out


def _scale_and_embed(state: pd.DataFrame, pca_dim: int) -> tuple[np.ndarray, np.ndarray]:
    x = state[STATE_COLS].to_numpy(dtype=float)
    x_scaled = RobustScaler().fit_transform(x)
    dim = max(1, min(pca_dim, x_scaled.shape[1], x_scaled.shape[0] - 1))
    if dim >= x_scaled.shape[1]:
        return x_scaled, x_scaled
    x_emb = PCA(n_components=dim, random_state=42).fit_transform(x_scaled)
    return x_scaled, x_emb


def _candidate_endpoints(n: int, jump: int) -> list[int]:
    if n <= 0:
        return [0]
    step = max(1, int(jump))
    pts = {0, n}
    for t in range(step, n, step):
        pts.add(t)
    return sorted(pts)


def _gaussian_segment_cost_builder(x: np.ndarray, cov_eps: float) -> Any:
    # Segment cost is proportional to negative log-likelihood under multivariate Gaussian:
    # cost(s,t) = m * logdet(Sigma_hat + eps*I), where m=t-s and Sigma_hat is segment covariance.
    n, d = x.shape
    csum = np.zeros((n + 1, d), dtype=float)
    csum[1:] = np.cumsum(x, axis=0)

    outer = np.einsum("ni,nj->nij", x, x, optimize=True)
    csum_outer = np.zeros((n + 1, d, d), dtype=float)
    csum_outer[1:] = np.cumsum(outer, axis=0)
    eye = np.eye(d, dtype=float)

    @lru_cache(maxsize=None)
    def seg_cost(s: int, t: int) -> float:
        m = t - s
        if m <= 1:
            return 0.0
        sx = csum[t] - csum[s]
        sxx = csum_outer[t] - csum_outer[s]
        mean = sx / m
        scatter = sxx - m * np.outer(mean, mean)
        cov = (scatter / m) + cov_eps * eye
        sign, logdet = np.linalg.slogdet(cov)
        if sign <= 0 or not np.isfinite(logdet):
            return 1e12
        return float(m * logdet)

    return seg_cost


def _dp_gaussian_breakpoints(x: np.ndarray, params: RegimeParams) -> list[int]:
    n = len(x)
    if n <= params.min_size * 2:
        return [n]

    candidates = _candidate_endpoints(n, params.jump)
    idx_of = {t: i for i, t in enumerate(candidates)}
    seg_cost = _gaussian_segment_cost_builder(x, cov_eps=max(params.cov_epsilon, 1e-12))

    inf = float("inf")
    best = [inf] * len(candidates)
    prev = [-1] * len(candidates)
    best[0] = -float(params.penalty)

    for i in range(1, len(candidates)):
        t = candidates[i]
        best_val = inf
        best_prev = -1
        for j in range(i):
            s = candidates[j]
            if t - s < params.min_size:
                continue
            prev_cost = best[j]
            if not np.isfinite(prev_cost):
                continue
            val = prev_cost + seg_cost(s, t) + float(params.penalty)
            if val < best_val:
                best_val = val
                best_prev = j
        best[i] = best_val
        prev[i] = best_prev

    end_i = idx_of[n]
    if prev[end_i] == -1:
        return [n]

    bkps: list[int] = []
    cur = end_i
    while cur > 0:
        t = candidates[cur]
        bkps.append(t)
        cur = prev[cur]
        if cur < 0:
            break
    bkps = sorted(set(b for b in bkps if b > 0))
    if not bkps or bkps[-1] != n:
        bkps.append(n)
    return bkps


def _detect_breakpoints(x_emb: np.ndarray, params: RegimeParams) -> list[int]:
    if len(x_emb) <= params.min_size * 2:
        return [len(x_emb)]

    if rpt is None:
        return _dp_gaussian_breakpoints(x_emb, params)

    cost = rpt.costs.CostNormal()
    algo = rpt.Pelt(custom_cost=cost, min_size=params.min_size, jump=params.jump).fit(x_emb)
    bkps = algo.predict(pen=params.penalty)
    bkps = sorted(set(int(b) for b in bkps if b > 0))
    if not bkps or bkps[-1] != len(x_emb):
        bkps.append(len(x_emb))
    return bkps


def _compute_severity(state_scaled: pd.DataFrame, bkps: list[int], params: RegimeParams) -> dict[int, float]:
    weights = _severity_weights()
    sev: dict[int, float] = {}
    n = len(state_scaled)

    for b in bkps:
        if b >= n:
            continue
        l0 = max(0, b - params.left_window)
        l1 = b
        r0 = b
        r1 = min(n, b + params.right_window)
        if l1 - l0 < 3 or r1 - r0 < 3:
            continue

        left = state_scaled.iloc[l0:l1]
        right = state_scaled.iloc[r0:r1]
        score = 0.0
        for c in STATE_COLS:
            score += weights.get(c, 1.0) * abs(float(right[c].mean() - left[c].mean()))
        sev[b] = float(score)
    return sev


def _map_risk_regime(raw: pd.DataFrame) -> list[str]:
    labels: list[str] = []
    for _, r in raw.iterrows():
        rv = float(r["rv_20"])
        tail = float(r["tailloss_5_20"])
        illiq = float(r["illiq_20"])
        bs = float(r["breadth_stress"])
        vix = float(r["vix_z"])
        vrp = float(r["vrp_z"])
        oil = float(r.get("oil_shock_z", 0.0))
        mret = float(r["mkt_ret"])
        cluster_id = int(r["cluster_id"])
        is_boundary = bool(r.get("cpd_boundary_flag", False))
        cpd_score = float(r.get("cpd_score", 0.0))

        if (rv > 0.25 and tail > 0.015 and illiq > np.nanmedian(raw["illiq_20"])) or (cluster_id == -1 and bs > 0.7):
            labels.append("LIQUIDITY_SHOCK")
        elif oil > 1.6 and vix > 1.2 and bs > 0.70:
            labels.append("FRAGILE_HIGH_VOL")
        elif is_boundary and cpd_score >= 0.45:
            labels.append("TRANSITION")
        elif rv > 0.20 and (tail > 0.010 or vix > 1.0):
            labels.append("FRAGILE_HIGH_VOL")
        elif rv < 0.20 and tail < 0.010 and abs(mret) < 0.01 and bs < 0.68:
            labels.append("NORMAL_VOL_STABLE")
        elif mret > 0 and rv < 0.22 and bs < 0.65 and vrp < 0.8:
            labels.append("TREND_RISK_ON")
        elif rv < 0.16 and tail < 0.008 and bs < 0.55:
            labels.append("CALM_LOW_VOL")
        else:
            labels.append("POST_SHOCK_REBOUND")
    return labels


def _segment_ranges(dates: pd.Series, bkps: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    prev = 0
    for b in bkps:
        out.append((prev, b))
        prev = b
    return out


def _compute_shock_proximity(snapshot: pd.DataFrame, breakpoints: pd.DataFrame) -> pd.Series:
    if breakpoints.empty:
        return pd.Series(["OUTSIDE_EVENT_WINDOW"] * len(snapshot), index=snapshot.index)
    bp_dates = pd.to_datetime(breakpoints["breakpoint_date"]).sort_values()
    out = []
    for d in pd.to_datetime(snapshot["date"]):
        dist = int(np.min(np.abs((bp_dates - d).dt.days)))
        if dist <= 5:
            out.append("WITHIN_5_BARS")
        elif dist <= 20:
            out.append("WITHIN_20_BARS")
        else:
            out.append("OUTSIDE_EVENT_WINDOW")
    return pd.Series(out, index=snapshot.index)


def _market_risk_level_rules(snapshot: pd.DataFrame) -> pd.Series:
    out: list[str] = []
    bq = float(snapshot["breadth_stress"].quantile(0.65))
    for _, r in snapshot.iterrows():
        rr = str(r.get("risk_regime", ""))
        vol = str(r["volatility_state"])
        tail = str(r["tail_risk_state"])
        liq = str(r["liquidity_state"])
        vix_z = float(r["vix_z"])
        breadth = float(r["breadth_stress"])

        if rr == "LIQUIDITY_SHOCK":
            out.append("EXTREME")
            continue
        if vol == "EXTREME_VOL" or tail == "EXTREME":
            out.append("EXTREME")
            continue
        if rr == "FRAGILE_HIGH_VOL":
            out.append("HIGH")
            continue
        if vol == "HIGH_VOL" and (tail in {"STRESSED", "EXTREME"} or breadth >= bq or vix_z >= 2.0 or liq == "STRESSED"):
            out.append("HIGH")
            continue
        if vol in {"HIGH_VOL", "NORMAL_VOL"} and (tail in {"ELEVATED", "STRESSED"} or abs(vix_z) >= 1.2 or breadth >= bq):
            out.append("MEDIUM")
            continue
        out.append("LOW")
    return pd.Series(out, index=snapshot.index)


def _build_market_state_features(mkt: pd.DataFrame) -> pd.DataFrame:
    df = mkt[["trade_date", "mkt_close", "mkt_ret", "mkt_turnover", "breadth_stress_raw", "dispersion"]].copy()
    df = df.sort_values("trade_date").reset_index(drop=True)
    c = df["mkt_close"]
    r = df["mkt_ret"]

    ma20 = c.rolling(20, min_periods=20).mean()
    ma60 = c.rolling(60, min_periods=60).mean()

    df["ret_5"] = c.pct_change(5)
    df["ret_20"] = c.pct_change(20)
    df["ret_60"] = c.pct_change(60)
    df["price_to_ma20"] = c / ma20 - 1.0
    df["ma20_to_ma60"] = ma20 / ma60 - 1.0
    df["ma20_slope"] = ma20.diff(5)
    df["ma60_slope"] = ma60.diff(10)
    df["breadth_trend_10"] = (-df["breadth_stress_raw"]).rolling(10, min_periods=10).mean().diff(3)
    df["new_high_ratio_20"] = (c >= c.rolling(20, min_periods=20).max()).astype(float).rolling(20, min_periods=20).mean()

    upv = (df["mkt_turnover"] * (r > 0).astype(float)).rolling(10, min_periods=10).sum()
    tov = df["mkt_turnover"].rolling(10, min_periods=10).sum().replace(0.0, np.nan)
    df["up_volume_ratio_10"] = upv / tov
    df["turnover_trend_10"] = _rolling_z(np.log1p(df["mkt_turnover"]), 20)
    df["leadership_strength"] = df["ret_20"] - df["dispersion"].rolling(20, min_periods=20).mean()

    return df


def _trend_strength_from_score(ts: float) -> str:
    a = abs(ts)
    if a >= 2.0:
        return "EXTREME"
    if a >= 1.0:
        return "STRONG"
    if a >= 0.4:
        return "MODERATE"
    return "WEAK"


def _market_state_from_row(r: pd.Series) -> str:
    rr = str(r.get("risk_regime", "TRANSITION"))
    ret20 = float(r.get("ret_20", 0.0))
    ret60 = float(r.get("ret_60", 0.0))
    ma = float(r.get("ma20_to_ma60", 0.0))
    breadth = float(r.get("breadth_trend_10", 0.0))
    new_high = float(r.get("new_high_ratio_20", 0.0))
    ev = str(r.get("event_context", "NONE"))
    cl = str(r.get("cluster_label", "UNKNOWN"))
    ts = float(r.get("trend_score", 0.0))

    if ev == "SECONDARY_GEO_ENERGY_ESCALATION_HIT":
        if ret20 < 0 and ma < 0:
            return "BEAR_DOWNTREND"
        return "RANGE_BOUND_WEAK"
    if ev == "PERSISTENT_ENERGY_CRISIS_WINDOW_HIT" and ret20 < 0:
        return "RISK_OFF_DERISKING"
    if cl == "GEO_ENERGY_SHOCK":
        if ret20 < 0:
            return "BEAR_DOWNTREND"
        return "RANGE_BOUND_WEAK"
    if rr == "POST_SHOCK_REBOUND" and ev in {"GEO_ENERGY_CLUSTER_HIT", "SECONDARY_GEO_ENERGY_ESCALATION_HIT"}:
        return "POST_GEO_SHOCK_REBOUND"
    if ev in {"PRIMARY_POLICY_REGIME_HIT", "PRIMARY_POLICY_REGIME_WINDOW"} and ret20 > 0 and breadth > 0:
        return "POLICY_RISK_ON"
    if ret20 > 0.08 and ret60 > 0.12 and new_high > 0.45 and ts > 1.5:
        return "BLOWOFF_EUPHORIA"
    if ma > 0 and ret20 > 0 and breadth > 0 and rr in {"NORMAL_VOL_STABLE", "POST_SHOCK_REBOUND", "FRAGILE_HIGH_VOL"}:
        if rr == "FRAGILE_HIGH_VOL":
            return "BULL_UPTREND_CORRECTION"
        return "BULL_UPTREND"
    if ma < 0 and ret20 < 0 and breadth < 0:
        return "BEAR_DOWNTREND"
    if rr in {"POST_SHOCK_REBOUND", "TRANSITION"} and ret20 > -0.03 and ret20 < 0.08 and ret60 < 0:
        return "RELIEF_REBOUND"
    if ma <= 0 and ret20 > 0:
        return "BEAR_MARKET_RALLY"
    if abs(ret20) < 0.03 and abs(ma) < 0.03:
        if rr == "FRAGILE_HIGH_VOL":
            return "RANGE_BOUND_WEAK"
        return "RANGE_BOUND"
    return "RANGE_BOUND"


def _event_context_for_date(d: date, bp_hit_map: dict[date, str], params: RegimeParams) -> str:
    if d in bp_hit_map:
        return bp_hit_map[d]

    geo = _geo_event_dates()
    if geo["persistent_start"] <= d <= geo["persistent_end"]:
        return "PERSISTENT_ENERGY_CRISIS_WINDOW_HIT"
    if abs((d - geo["primary"]).days) <= params.geo_primary_hit_window_days:
        return "PRIMARY_GEO_ENERGY_SHOCK_HIT"
    if abs((d - geo["secondary"]).days) <= params.geo_secondary_hit_window_days:
        return "SECONDARY_GEO_ENERGY_ESCALATION_HIT"

    for sd in _shock_dates():
        delta = (d - sd).days
        if 0 <= delta <= params.primary_window_days:
            return "PRIMARY_SHOCK_WINDOW"
        if params.post_window_start_days <= delta <= params.post_window_end_days:
            return "POST_SHOCK_WINDOW"
    for pd0 in _policy_regime_dates():
        delta = (d - pd0).days
        if 0 <= delta <= params.primary_window_days:
            return "PRIMARY_POLICY_REGIME_WINDOW"
        if params.post_window_start_days <= delta <= params.post_window_end_days:
            return "POST_POLICY_WINDOW"
    return "NONE"


def _breakpoint_event_tag(bp_date: date, params: RegimeParams) -> tuple[bool, str]:
    geo = _geo_event_dates()
    if abs((bp_date - geo["primary"]).days) <= params.geo_primary_hit_window_days:
        return True, "PRIMARY_GEO_ENERGY_SHOCK_HIT"
    if abs((bp_date - geo["secondary"]).days) <= params.geo_secondary_hit_window_days:
        return True, "SECONDARY_GEO_ENERGY_ESCALATION_HIT"
    if geo["persistent_start"] <= bp_date <= geo["persistent_end"]:
        return True, "PERSISTENT_ENERGY_CRISIS_WINDOW_HIT"

    # PRIMARY_SHOCK_HIT: near known primary shock day.
    for sd in _shock_dates():
        d = (bp_date - sd).days
        if abs(d) <= params.shock_hit_window_days:
            return True, "PRIMARY_SHOCK_HIT"
    # PRIMARY_POLICY_REGIME_HIT: near known policy regime day.
    for pd0 in _policy_regime_dates():
        if abs((bp_date - pd0).days) <= params.policy_hit_window_days:
            return True, "PRIMARY_POLICY_REGIME_HIT"
    # SECONDARY_TRANSITION_HIT: near known secondary transition library dates.
    for td in _secondary_transition_dates():
        if abs((bp_date - td).days) <= params.secondary_hit_window_days:
            return True, "SECONDARY_TRANSITION_HIT"
    # Fallback inferred transition: lag window after primary shocks.
    for sd in _shock_dates():
        d = (bp_date - sd).days
        if params.transition_hit_start_days <= d <= params.transition_hit_end_days:
            return True, "SECONDARY_TRANSITION_HIT"
    for pd0 in _policy_regime_dates():
        d = (bp_date - pd0).days
        if params.transition_hit_start_days <= d <= params.transition_hit_end_days:
            return True, "SECONDARY_TRANSITION_HIT"
    return False, "NONE"


def _map_cluster_labels(snapshot: pd.DataFrame) -> dict[int, str]:
    q = {
        "oil80": float(snapshot["oil_shock_z"].quantile(0.80)),
        "vix75": float(snapshot["vix_z"].quantile(0.75)),
        "bs75": float(snapshot["breadth_stress"].quantile(0.75)),
        "vrp75": float(snapshot["vrp_z"].quantile(0.75)),
        "rv75": float(snapshot["rv_20"].quantile(0.75)),
        "rv25": float(snapshot["rv_20"].quantile(0.25)),
        "tail25": float(snapshot["tailloss_5_20"].quantile(0.25)),
        "illiq80": float(snapshot["illiq_20"].quantile(0.80)),
    }
    out: dict[int, str] = {}
    for cid, g in snapshot.groupby("cluster_id", dropna=False):
        cid_int = int(cid)
        if cid_int == -1:
            out[cid_int] = "TRANSITION"
            continue
        oil = float(g["oil_shock_z"].median())
        vix = float(g["vix_z"].median())
        bs = float(g["breadth_stress"].median())
        vrp = float(g["vrp_z"].median())
        eo = float(g["energy_sector_outperf_5"].median())
        rv = float(g["rv_20"].median())
        tail = float(g["tailloss_5_20"].median())
        illiq = float(g["illiq_20"].median())
        if sum([oil >= q["oil80"], vix >= q["vix75"], bs >= q["bs75"], vrp >= q["vrp75"], eo > 0.0]) >= 4:
            out[cid_int] = "GEO_ENERGY_SHOCK"
        elif illiq >= q["illiq80"] and bs >= q["bs75"]:
            out[cid_int] = "LIQUIDITY_SHOCK"
        elif rv <= q["rv25"] and tail <= q["tail25"]:
            out[cid_int] = "CALM_LOW_VOL"
        elif rv >= q["rv75"]:
            out[cid_int] = "FRAGILE_HIGH_VOL"
        else:
            out[cid_int] = "POST_SHOCK_REBOUND"
    return out


def _forward_returns(s: pd.Series, horizon: int) -> pd.Series:
    vals = []
    arr = s.to_numpy(dtype=float)
    n = len(arr)
    for i in range(n):
        if i + horizon >= n:
            vals.append(np.nan)
            continue
        vals.append(float(np.prod(1.0 + arr[i + 1 : i + 1 + horizon]) - 1.0))
    return pd.Series(vals, index=s.index)


def _future_vol(s: pd.Series, horizon: int) -> pd.Series:
    vals = []
    arr = s.to_numpy(dtype=float)
    n = len(arr)
    for i in range(n):
        if i + horizon >= n:
            vals.append(np.nan)
            continue
        win = arr[i + 1 : i + 1 + horizon]
        vals.append(float(np.sqrt(252.0) * np.std(win, ddof=1)) if len(win) > 1 else np.nan)
    return pd.Series(vals, index=s.index)


def _cluster_forecast_profile(snapshot: pd.DataFrame, params: RegimeParams) -> pd.DataFrame:
    s = snapshot.sort_values("date").reset_index(drop=True).copy()
    s["fwd5_ret"] = _forward_returns(s["mkt_ret"], 5)
    s["fwd10_ret"] = _forward_returns(s["mkt_ret"], 10)
    s["fwd5_rv"] = _future_vol(s["mkt_ret"], 5)
    s["fwd10_rv"] = _future_vol(s["mkt_ret"], 10)
    s["next_cluster_label"] = s["cluster_label"].shift(-1)

    rows: list[dict[str, Any]] = []
    for label, g in s.groupby("cluster_label", dropna=False):
        g = g.copy()
        q05 = float(g["fwd10_ret"].quantile(0.05)) if g["fwd10_ret"].notna().any() else np.nan
        tail = g.loc[g["fwd10_ret"] <= q05, "fwd10_ret"] if np.isfinite(q05) else pd.Series(dtype=float)
        rows.append(
            {
                "cluster_label": str(label),
                "sample_size": int(len(g)),
                "fwd5_down_prob": float((g["fwd5_ret"] < 0).mean()),
                "fwd10_down_prob": float((g["fwd10_ret"] < 0).mean()),
                "fwd10_q05": q05,
                "fwd10_es05": float(tail.mean()) if not tail.empty else np.nan,
                "fwd5_rv_median": float(g["fwd5_rv"].median()) if g["fwd5_rv"].notna().any() else np.nan,
                "fwd10_rv_median": float(g["fwd10_rv"].median()) if g["fwd10_rv"].notna().any() else np.nan,
                "cluster_persist_prob": float((g["next_cluster_label"] == label).mean()),
                "to_liquidity_shock_prob": float((g["next_cluster_label"] == "LIQUIDITY_SHOCK").mean()),
                "to_post_shock_rebound_prob": float((g["next_cluster_label"] == "POST_SHOCK_REBOUND").mean()),
                "to_extreme_risk_prob": float((g["next_cluster_label"].isin(["LIQUIDITY_SHOCK", "FRAGILE_HIGH_VOL"])).mean()),
                "computed_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "model_version": params.model_version,
            }
        )
    return pd.DataFrame(rows)


def _build_geo_event_evaluation(breakpoints: pd.DataFrame, params: RegimeParams) -> pd.DataFrame:
    if breakpoints is None or breakpoints.empty:
        return pd.DataFrame()
    b = breakpoints.copy()
    b["breakpoint_date"] = pd.to_datetime(b["breakpoint_date"]).dt.date
    geo = _geo_event_dates()
    events = [
        {"event_id": "geo_primary_2026_02_28", "event_date": geo["primary"], "event_name": "Primary Geo-Energy Shock", "event_type": "PRIMARY"},
        {"event_id": "geo_secondary_2026_03_12", "event_date": geo["secondary"], "event_name": "Secondary Geo-Energy Escalation", "event_type": "SECONDARY"},
        {
            "event_id": "geo_persistent_2026_03_23_2026_03_29",
            "event_date": geo["persistent_start"],
            "event_name": "Persistent Energy Crisis Window",
            "event_type": "PERSISTENT_WINDOW",
        },
    ]
    rows: list[dict[str, Any]] = []
    for ev in events:
        d0 = ev["event_date"]
        distances = b["breakpoint_date"].apply(lambda d: abs((d - d0).days))
        i = int(distances.idxmin())
        nearest = b.loc[i]
        dist = int(distances.loc[i])
        window = 5 if ev["event_type"] != "PERSISTENT_WINDOW" else 7
        rows.append(
            {
                "event_id": ev["event_id"],
                "event_date": d0,
                "event_name": ev["event_name"],
                "event_type": ev["event_type"],
                "nearest_breakpoint_date": nearest["breakpoint_date"],
                "breakpoint_distance_days": dist,
                "breakpoint_hit_flag": bool(dist <= 3),
                "window_hit_flag": bool(dist <= window),
                "cluster_hit_flag": bool(
                    dist <= window
                    and str(nearest.get("event_hit_type", "")).startswith(
                        ("PRIMARY_GEO_ENERGY", "SECONDARY_GEO_ENERGY", "PERSISTENT_ENERGY")
                    )
                ),
                "event_hit_type": str(nearest.get("event_hit_type", "NONE")),
                "policy_or_geo_score": float(nearest.get("severity_score", 0.0)),
                "review_note": f"nearest breakpoint distance={dist}d",
                "model_version": params.model_version,
            }
        )
    return pd.DataFrame(rows)


def _build_outputs(params: RegimeParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    force_real = _force_real_daily_mode()
    mkt: pd.DataFrame | None = None
    data_source = "unknown"

    if force_real:
        mkt = _load_market_frame_from_local_ohlcv()
        data_source = "local_ohlcv"
        if mkt is None or mkt.empty:
            p = _real_ohlcv_path()
            raise RuntimeError(
                f"FORCE_REAL_DAILY enabled but failed to load local OHLCV data. "
                f"Please set FACTOR_PLATFORM_REAL_OHLCV_PATH to a valid parquet path. current={p!r}"
            )
    else:
        mkt = _load_market_frame_from_qlib()
        data_source = "qlib"
        if mkt is None or mkt.empty:
            mkt = _load_market_frame_from_local_ohlcv()
            data_source = "local_ohlcv"
        if mkt is None or mkt.empty:
            mkt = _synthetic_market_frame()
            data_source = "synthetic"

    state = _build_state_vector(mkt)
    merged = state.merge(mkt[["trade_date", "mkt_ret"]], on="trade_date", how="left")
    mkt_state_feat = _build_market_state_features(mkt)

    x_scaled, x_emb = _scale_and_embed(state, params.pca_dim)
    bkps = _detect_breakpoints(x_emb, params)

    state_scaled = state.copy()
    state_scaled[STATE_COLS] = x_scaled
    sev = _compute_severity(state_scaled, bkps, params)
    max_sev = max(sev.values()) if sev else 1.0

    cluster = DBSCAN(eps=params.eps, min_samples=params.min_samples)
    cids = cluster.fit_predict(x_emb)

    snapshot = merged.copy()
    snapshot["date"] = pd.to_datetime(snapshot["trade_date"]).dt.date
    snapshot["scope"] = params.scope
    snapshot["cluster_id"] = cids.astype(int)
    snapshot["cpd_boundary_flag"] = False
    snapshot["severity_score"] = 0.0

    for b in bkps:
        if b >= len(snapshot):
            continue
        snapshot.loc[b, "cpd_boundary_flag"] = True
        snapshot.loc[b, "severity_score"] = float(sev.get(b, 0.0))

    snapshot["severity_score"] = snapshot["severity_score"].astype(float)
    snapshot["cpd_score"] = snapshot["severity_score"] / max(1e-6, max_sev)
    snapshot["risk_regime"] = _map_risk_regime(snapshot)
    snapshot["regime_label"] = snapshot["risk_regime"]  # backward compatibility
    snapshot["shock_proximity"] = _compute_shock_proximity(
        snapshot,
        pd.DataFrame({"breakpoint_date": [snapshot.loc[b, "date"] for b in bkps if b < len(snapshot)]}),
    )
    snapshot["computed_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    snapshot["model_version"] = params.model_version
    snapshot["data_source"] = data_source
    cid_map = _map_cluster_labels(snapshot)
    snapshot["cluster_label"] = snapshot["cluster_id"].map(cid_map).fillna("UNKNOWN")
    geo = _geo_event_dates()
    q_oil = float(snapshot["oil_shock_z"].quantile(0.80))
    q_vix = float(snapshot["vix_z"].quantile(0.75))
    q_bs = float(snapshot["breadth_stress"].quantile(0.75))
    geo_window = (
        (pd.to_datetime(snapshot["date"]) >= pd.Timestamp(geo["primary"]))
        & (pd.to_datetime(snapshot["date"]) <= pd.Timestamp(geo["persistent_end"]))
    )
    geo_mask = (
        (snapshot["oil_shock_z"] >= q_oil)
        & (snapshot["vix_z"] >= q_vix)
        & (snapshot["breadth_stress"] >= q_bs)
        & geo_window
    )
    snapshot.loc[geo_mask, "cluster_label"] = "GEO_ENERGY_SHOCK"
    snapshot["geo_energy_flag"] = snapshot["cluster_label"].eq("GEO_ENERGY_SHOCK")
    snapshot["volatility_state"] = pd.cut(
        snapshot["rv_20"],
        bins=[-np.inf, 0.15, 0.22, 0.30, np.inf],
        labels=["LOW_VOL", "NORMAL_VOL", "HIGH_VOL", "EXTREME_VOL"],
    ).astype(str)
    snapshot["tail_risk_state"] = pd.cut(
        snapshot["tailloss_5_20"],
        bins=[-np.inf, 0.006, 0.012, 0.020, np.inf],
        labels=["NORMAL", "ELEVATED", "STRESSED", "EXTREME"],
    ).astype(str)
    snapshot["liquidity_state"] = pd.cut(
        snapshot["illiq_20"],
        bins=[-np.inf, snapshot["illiq_20"].quantile(0.5), snapshot["illiq_20"].quantile(0.8), np.inf],
        labels=["EASY", "TIGHT", "STRESSED"],
        include_lowest=True,
    ).astype(str)
    snapshot = snapshot.merge(
        mkt_state_feat[
            [
                "trade_date",
                "ret_5",
                "ret_20",
                "ret_60",
                "price_to_ma20",
                "ma20_to_ma60",
                "ma20_slope",
                "ma60_slope",
                "breadth_trend_10",
                "new_high_ratio_20",
                "up_volume_ratio_10",
                "turnover_trend_10",
                "leadership_strength",
            ]
        ],
        on="trade_date",
        how="left",
    )
    snapshot["direction_score"] = (
        snapshot["ret_20"].fillna(0.0) * 1.5
        + snapshot["ret_60"].fillna(0.0) * 1.2
        + snapshot["ma20_to_ma60"].fillna(0.0) * 2.0
        + snapshot["breadth_trend_10"].fillna(0.0) * 1.2
    )
    snapshot["trend_score"] = (
        snapshot["direction_score"]
        + snapshot["new_high_ratio_20"].fillna(0.0)
        + snapshot["up_volume_ratio_10"].fillna(0.0)
        + snapshot["turnover_trend_10"].fillna(0.0) * 0.5
        + snapshot["leadership_strength"].fillna(0.0) * 0.5
    )
    snapshot["trend_strength"] = snapshot["trend_score"].apply(_trend_strength_from_score)

    # Breakpoint hit map for event context.
    bp_hit_map: dict[date, str] = {}
    for b in bkps:
        if b >= len(snapshot):
            continue
        bp_date = snapshot.loc[b, "date"]
        _, bp_type = _breakpoint_event_tag(bp_date, params)
        if bp_type != "NONE":
            bp_hit_map[bp_date] = bp_type
    snapshot["event_context"] = snapshot["date"].apply(lambda d: _event_context_for_date(d, bp_hit_map, params))
    geo_secondary = _geo_event_dates()["secondary"]
    geo_secondary_end = geo_secondary + pd.Timedelta(days=8)
    idx_geo_cluster_hit = (
        snapshot["event_context"].isin(["NONE", "POST_SHOCK_WINDOW", "PRIMARY_SHOCK_WINDOW", "SECONDARY_TRANSITION_HIT"])
        & snapshot["geo_energy_flag"]
        & (pd.to_datetime(snapshot["date"]) >= pd.Timestamp(geo_secondary))
        & (pd.to_datetime(snapshot["date"]) <= pd.Timestamp(geo_secondary_end))
    )
    snapshot.loc[idx_geo_cluster_hit, "event_context"] = "GEO_ENERGY_CLUSTER_HIT"
    snapshot["policy_regime_flag"] = snapshot["event_context"].isin({"PRIMARY_POLICY_REGIME_HIT", "PRIMARY_POLICY_REGIME_WINDOW", "POST_POLICY_WINDOW"})
    snapshot["market_state"] = snapshot.apply(_market_state_from_row, axis=1)
    snapshot["bull_phase_flag"] = snapshot["market_state"].isin({"BULL_UPTREND", "POLICY_RISK_ON", "BLOWOFF_EUPHORIA"})
    snapshot["market_risk_level"] = _market_risk_level_rules(snapshot).astype(str)
    profile = _cluster_forecast_profile(snapshot, params)
    if not profile.empty:
        prof_map = profile.set_index("cluster_label")
        snapshot["fwd5_down_prob"] = snapshot["cluster_label"].map(prof_map["fwd5_down_prob"].to_dict())
        snapshot["fwd10_es05"] = snapshot["cluster_label"].map(prof_map["fwd10_es05"].to_dict())
        snapshot["cluster_persist_prob"] = snapshot["cluster_label"].map(prof_map["cluster_persist_prob"].to_dict())
    else:
        snapshot["fwd5_down_prob"] = np.nan
        snapshot["fwd10_es05"] = np.nan
        snapshot["cluster_persist_prob"] = np.nan

    snapshot_out = snapshot[
        [
            "date",
            "scope",
            "regime_label",
            "risk_regime",
            "market_state",
            "event_context",
            "trend_strength",
            "policy_regime_flag",
            "bull_phase_flag",
            "direction_score",
            "trend_score",
            "cluster_id",
            "cluster_label",
            "geo_energy_flag",
            "cpd_boundary_flag",
            "cpd_score",
            "severity_score",
            "rv_20",
            "tailloss_5_20",
            "illiq_20",
            "vix_z",
            "vrp_z",
            "oil_shock_z",
            "breadth_stress",
            "fwd5_down_prob",
            "fwd10_es05",
            "cluster_persist_prob",
            "volatility_state",
            "tail_risk_state",
            "liquidity_state",
            "shock_proximity",
            "market_risk_level",
            "mkt_ret",
            "data_source",
            "computed_at",
            "model_version",
        ]
    ].copy()
    snapshot_out = snapshot_out.sort_values("date").reset_index(drop=True)

    ranges = _segment_ranges(snapshot_out["date"], bkps)
    b_rows: list[dict[str, Any]] = []
    for idx, (l, r) in enumerate(ranges):
        if r >= len(snapshot_out):
            continue
        bp_date = snapshot_out.loc[r, "date"]
        event_hit_flag, event_hit_type = _breakpoint_event_tag(bp_date, params)
        b_rows.append(
            {
                "breakpoint_date": bp_date,
                "segment_left_start": snapshot_out.loc[l, "date"],
                "segment_left_end": snapshot_out.loc[r - 1, "date"] if r - 1 >= l else snapshot_out.loc[l, "date"],
                "segment_right_start": snapshot_out.loc[r, "date"],
                "segment_right_end": snapshot_out.loc[min(len(snapshot_out) - 1, ranges[idx + 1][1] - 1), "date"]
                if idx + 1 < len(ranges)
                else snapshot_out.loc[len(snapshot_out) - 1, "date"],
                "penalty": params.penalty,
                "min_size": params.min_size,
                "jump": params.jump,
                "severity_score": float(sev.get(r, 0.0)),
                "event_hit_flag": bool(event_hit_flag),
                "event_hit_type": event_hit_type,
                "model_version": params.model_version,
            }
        )
    breakpoints = pd.DataFrame(b_rows)

    return snapshot_out, breakpoints


def _persist_outputs(snapshot: pd.DataFrame, breakpoints: pd.DataFrame, params: RegimeParams) -> None:
    root = _artifact_root()
    snapshot.to_parquet(root / "regime_snapshot_daily.parquet", index=False)
    breakpoints.to_parquet(root / "regime_breakpoints.parquet", index=False)
    if {"date", "mkt_ret", "cluster_label"}.issubset(snapshot.columns):
        cluster_profile = _cluster_forecast_profile(snapshot, params)
        if not cluster_profile.empty:
            cluster_profile.to_parquet(root / "cluster_forecast_profile.parquet", index=False)
    geo_eval = _build_geo_event_evaluation(breakpoints, params)
    if not geo_eval.empty:
        geo_eval.to_parquet(root / "geo_energy_event_evaluation.parquet", index=False)
    meta = {
        "model_version": params.model_version,
        "computed_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "rows_snapshot": int(snapshot.shape[0]),
        "rows_breakpoints": int(breakpoints.shape[0]),
        "force_real_daily": _force_real_daily_mode(),
        "real_ohlcv_path": _real_ohlcv_path(),
        "data_source": str(snapshot.iloc[-1]["data_source"]) if (not snapshot.empty and "data_source" in snapshot.columns) else "unknown",
        "provider_uri": _provider_uri(),
        "universe": _universe(),
        "params": params.__dict__,
    }
    (root / "regime_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _params_from_env() -> RegimeParams:
    return RegimeParams(
        min_size=int(os.getenv("FACTOR_PLATFORM_REGIME_MIN_SIZE", "20")),
        jump=int(os.getenv("FACTOR_PLATFORM_REGIME_JUMP", "1")),
        penalty=float(os.getenv("FACTOR_PLATFORM_REGIME_PENALTY", "12")),
        eps=float(os.getenv("FACTOR_PLATFORM_REGIME_DBSCAN_EPS", "1.0")),
        min_samples=int(os.getenv("FACTOR_PLATFORM_REGIME_DBSCAN_MIN_SAMPLES", "10")),
        pca_dim=int(os.getenv("FACTOR_PLATFORM_REGIME_PCA_DIM", "5")),
        cov_epsilon=float(os.getenv("FACTOR_PLATFORM_REGIME_COV_EPSILON", "1e-6")),
        shock_hit_window_days=int(os.getenv("FACTOR_PLATFORM_SHOCK_HIT_WINDOW_DAYS", "3")),
        transition_hit_start_days=int(os.getenv("FACTOR_PLATFORM_TRANSITION_HIT_START_DAYS", "4")),
        transition_hit_end_days=int(os.getenv("FACTOR_PLATFORM_TRANSITION_HIT_END_DAYS", "30")),
        secondary_hit_window_days=int(os.getenv("FACTOR_PLATFORM_SECONDARY_HIT_WINDOW_DAYS", "3")),
        geo_primary_hit_window_days=int(os.getenv("FACTOR_PLATFORM_GEO_PRIMARY_HIT_WINDOW_DAYS", "3")),
        geo_secondary_hit_window_days=int(os.getenv("FACTOR_PLATFORM_GEO_SECONDARY_HIT_WINDOW_DAYS", "3")),
        scope=os.getenv("FACTOR_PLATFORM_REGIME_SCOPE", "A_SHARE_ALL"),
        model_version=os.getenv("FACTOR_PLATFORM_REGIME_MODEL_VERSION", "regime_v1_gaussian_cpd"),
    )


@lru_cache(maxsize=1)
def get_regime_artifacts() -> tuple[pd.DataFrame, pd.DataFrame]:
    params = _params_from_env()
    snapshot, breakpoints = _build_outputs(params)
    _persist_outputs(snapshot, breakpoints, params)
    return snapshot, breakpoints


def refresh_regime_artifacts() -> tuple[pd.DataFrame, pd.DataFrame]:
    get_regime_artifacts.cache_clear()
    return get_regime_artifacts()


def get_latest_regime_snapshot() -> dict[str, Any]:
    snapshot, _ = get_regime_artifacts()
    if snapshot.empty:
        return {}
    row = snapshot.iloc[-1]
    row_date = pd.Timestamp(row["date"]).date()
    row_scope = row.get("scope", "A_SHARE_ALL")
    row_model_version = row.get("model_version", _params_from_env().model_version)
    force_real = _force_real_daily_mode()
    shock_proximity = row.get("shock_proximity", "OUTSIDE_EVENT_WINDOW")
    if shock_proximity in {"INSIDE_WINDOW", "WITHIN_3D"}:
        primary_window_label = "PRIMARY_WINDOW"
    elif shock_proximity in {"POST_WINDOW", "OUTSIDE_EVENT_WINDOW"}:
        primary_window_label = "POST_WINDOW"
    else:
        primary_window_label = "NORMAL_WINDOW"
    return {
        "date": row_date.isoformat(),
        "scope": str(row_scope),
        "model_version": str(row_model_version),
        "force_real_daily_mode": force_real,
        "primary_window_label": primary_window_label,
        "snapshot_time": str(pd.Timestamp(row["date"]).strftime("%Y-%m-%dT15:00:00+08:00")),
        "regime_label": row["regime_label"],
        "risk_regime": row.get("risk_regime", row["regime_label"]),
        "market_state": row.get("market_state", "RANGE_BOUND"),
        "event_context": row.get("event_context", "NONE"),
        "trend_strength": row.get("trend_strength", "WEAK"),
        "cluster_label": row.get("cluster_label", "UNKNOWN"),
        "geo_energy_flag": bool(row.get("geo_energy_flag", False)),
        "cpd_score": float(row["cpd_score"]),
        "cluster_id": int(row["cluster_id"]),
        "severity_score": float(row["severity_score"]),
        "volatility_state": row["volatility_state"],
        "liquidity_state": row["liquidity_state"],
        "tail_risk_state": row["tail_risk_state"],
        "market_risk_level": row["market_risk_level"],
        "shock_proximity": shock_proximity,
        "data_source": row.get("data_source", "unknown"),
        "fwd5_down_prob": float(row["fwd5_down_prob"]) if pd.notna(row.get("fwd5_down_prob")) else None,
        "fwd10_es05": float(row["fwd10_es05"]) if pd.notna(row.get("fwd10_es05")) else None,
        "cluster_persist_prob": float(row["cluster_persist_prob"]) if pd.notna(row.get("cluster_persist_prob")) else None,
    }


def get_regime_snapshot_at(target_dt: datetime) -> dict[str, Any]:
    snapshot, _ = get_regime_artifacts()
    if snapshot.empty:
        return {}
    s = snapshot.copy()
    s["dt"] = pd.to_datetime(s["date"])
    t = pd.Timestamp(target_dt.date())
    subset = s[s["dt"] <= t]
    row = subset.iloc[-1] if not subset.empty else s.iloc[-1]
    return {
        "snapshot_time": str(pd.Timestamp(row["date"]).strftime("%Y-%m-%dT15:00:00+08:00")),
        "regime_label": row["regime_label"],
        "risk_regime": row.get("risk_regime", row["regime_label"]),
        "market_state": row.get("market_state", "RANGE_BOUND"),
        "event_context": row.get("event_context", "NONE"),
        "trend_strength": row.get("trend_strength", "WEAK"),
        "cluster_label": row.get("cluster_label", "UNKNOWN"),
        "geo_energy_flag": bool(row.get("geo_energy_flag", False)),
        "cpd_score": float(row["cpd_score"]),
        "cluster_id": int(row["cluster_id"]),
        "severity_score": float(row["severity_score"]),
        "volatility_state": row["volatility_state"],
        "liquidity_state": row["liquidity_state"],
        "tail_risk_state": row["tail_risk_state"],
        "shock_proximity": row["shock_proximity"],
        "data_source": row.get("data_source", "unknown"),
        "fwd5_down_prob": float(row["fwd5_down_prob"]) if pd.notna(row.get("fwd5_down_prob")) else None,
        "fwd10_es05": float(row["fwd10_es05"]) if pd.notna(row.get("fwd10_es05")) else None,
        "cluster_persist_prob": float(row["cluster_persist_prob"]) if pd.notna(row.get("cluster_persist_prob")) else None,
    }


def get_regime_history_items(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    snapshot, _ = get_regime_artifacts()
    if snapshot.empty:
        return []
    s = snapshot.copy()
    if from_date is not None:
        s = s[s["date"] >= from_date]
    if to_date is not None:
        s = s[s["date"] <= to_date]
    s = s.sort_values("date")
    return [
        {
            "time": str(pd.Timestamp(r["date"]).strftime("%Y-%m-%dT15:00:00+08:00")),
            "regime_label": r["regime_label"],
            "risk_regime": r.get("risk_regime", r["regime_label"]),
            "market_state": r.get("market_state", "RANGE_BOUND"),
            "event_context": r.get("event_context", "NONE"),
            "trend_strength": r.get("trend_strength", "WEAK"),
            "cluster_label": r.get("cluster_label", "UNKNOWN"),
            "geo_energy_flag": bool(r.get("geo_energy_flag", False)),
            "cpd_score": float(r["cpd_score"]),
            "severity_score": float(r["severity_score"]),
            "cluster_id": int(r["cluster_id"]),
            "vix": float(r["vix_z"]),
            "vrp": float(r["vrp_z"]),
            "illiq": float(r["illiq_20"]),
            "fwd5_down_prob": float(r["fwd5_down_prob"]) if pd.notna(r.get("fwd5_down_prob")) else None,
            "fwd10_es05": float(r["fwd10_es05"]) if pd.notna(r.get("fwd10_es05")) else None,
            "cluster_persist_prob": float(r["cluster_persist_prob"]) if pd.notna(r.get("cluster_persist_prob")) else None,
        }
        for _, r in s.iterrows()
    ]


def get_regime_timeline_items(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    snapshot, _ = get_regime_artifacts()
    if snapshot.empty:
        return []
    s = snapshot.copy().sort_values("date")
    if from_date is not None:
        s = s[s["date"] >= from_date]
    if to_date is not None:
        s = s[s["date"] <= to_date]
    if s.empty:
        return []

    items: list[dict[str, Any]] = []
    start = s.iloc[0]["date"]
    curr = s.iloc[0]["regime_label"]
    prev_date = s.iloc[0]["date"]
    for _, r in s.iloc[1:].iterrows():
        if r["regime_label"] != curr:
            items.append(
                {
                    "start": str(pd.Timestamp(start).strftime("%Y-%m-%dT15:00:00+08:00")),
                    "end": str(pd.Timestamp(prev_date).strftime("%Y-%m-%dT15:00:00+08:00")),
                    "regime_label": curr,
                }
            )
            start = r["date"]
            curr = r["regime_label"]
        prev_date = r["date"]
    items.append(
        {
            "start": str(pd.Timestamp(start).strftime("%Y-%m-%dT15:00:00+08:00")),
            "end": str(pd.Timestamp(prev_date).strftime("%Y-%m-%dT15:00:00+08:00")),
            "regime_label": curr,
        }
    )
    return items


def get_breakpoints_items() -> list[dict[str, Any]]:
    _, breakpoints = get_regime_artifacts()
    if breakpoints.empty:
        return []
    return breakpoints.sort_values("breakpoint_date").to_dict(orient="records")
