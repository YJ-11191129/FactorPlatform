from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from app.factors.registry import ensure_registered, list_factors
from app.services.factor_service import DEFAULT_FACTOR_MODULES


DEFAULT_PROVIDER_URI = r"D:\mcQlib\data\qlib_bin\cn_data"
DEFAULT_UNIVERSE = "csi300"
DEFAULT_FREQ = "day"


@dataclass(frozen=True)
class QlibResearchError(Exception):
    status: str
    message: str
    readiness: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _new_id(prefix: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{ts}_{secrets.token_hex(4)}"


def _research_root() -> Path:
    override = os.getenv("FACTOR_PLATFORM_QLIB_RESEARCH_DIR")
    root = Path(override) if override else _project_root() / "data" / "exports" / "qlib_research"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_exists(path: Path) -> tuple[bool, str | None]:
    try:
        return path.exists(), None
    except Exception as e:
        return False, str(e)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return str(value)
    return value


def _append_history(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_json_safe(payload), ensure_ascii=False, default=str) + "\n")


def _package_version() -> str | None:
    for dist_name in ("pyqlib", "qlib"):
        try:
            return importlib.metadata.version(dist_name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def qlib_status(
    provider_uri: str | None = None,
    universe: str = DEFAULT_UNIVERSE,
    freq: str = DEFAULT_FREQ,
) -> dict[str, Any]:
    provider = provider_uri or os.getenv("FACTOR_PLATFORM_PROVIDER_URI") or DEFAULT_PROVIDER_URI
    provider_path = Path(provider)
    notes: list[str] = []

    package_available = importlib.util.find_spec("qlib") is not None
    package_version = _package_version() if package_available else None
    if not package_available:
        notes.append("Native qlib package is not installed. Install pyqlib and configure provider_uri before running mining.")

    provider_exists, provider_error = _safe_exists(provider_path)
    if provider_error:
        notes.append(f"Provider path check failed: {provider_error}")
    if not provider_exists:
        notes.append(f"Provider path not found: {provider}")

    calendar_candidates = [provider_path / "calendars" / f"{freq}.txt", provider_path / "calendars" / "day.txt"]
    calendar_ok = any(_safe_exists(p)[0] for p in calendar_candidates)
    if provider_exists and not calendar_ok:
        notes.append("Qlib calendar file is missing, expected calendars/day.txt or matching frequency calendar.")

    instruments_candidates = [
        provider_path / "instruments" / f"{universe}.txt",
        provider_path / "instruments" / "all.txt",
    ]
    instruments_ok = any(_safe_exists(p)[0] for p in instruments_candidates)
    if provider_exists and not instruments_ok:
        notes.append(f"Qlib instruments file is missing for universe '{universe}' and no all.txt fallback was found.")

    features_path = provider_path / "features"
    features_ok, features_error = _safe_exists(features_path)
    if features_error:
        notes.append(f"Feature directory check failed: {features_error}")
    if provider_exists and not features_ok:
        notes.append("Qlib features directory is missing.")

    data_available = bool(provider_exists and calendar_ok and instruments_ok and features_ok)
    if not package_available:
        status = "QLIB_NOT_READY"
    elif not data_available:
        status = "DATA_NOT_READY"
    else:
        status = "READY"

    if status == "READY":
        notes.append("Native qlib package and provider layout are ready.")

    return {
        "status": status,
        "provider_uri": provider,
        "universe": universe,
        "freq": freq,
        "package": "qlib",
        "package_available": package_available,
        "package_version": package_version,
        "data_available": data_available,
        "checks": {
            "provider_path": provider_exists,
            "calendar": calendar_ok,
            "instruments": instruments_ok,
            "features": features_ok,
        },
        "notes": notes,
    }


def _require_ready(provider_uri: str | None, universe: str, freq: str) -> dict[str, Any]:
    readiness = qlib_status(provider_uri=provider_uri, universe=universe, freq=freq)
    if readiness["status"] != "READY":
        raise QlibResearchError(
            status=str(readiness["status"]),
            message=f"Native qlib is not ready: {readiness['status']}",
            readiness=readiness,
        )
    return readiness


def _default_factor_pool(factor_pool: Optional[Iterable[str]] = None, factor_limit: Optional[int] = None) -> list[dict[str, Any]]:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    requested = set(factor_pool or [])
    out: list[dict[str, Any]] = []
    for info in list_factors():
        if requested and info.factor_name not in requested:
            continue
        expression = (info.parameter_schema or {}).get("expression", {}).get("value")
        if not expression:
            continue
        if not _is_native_expression_compatible(str(expression)):
            continue
        if not info.factor_name.startswith("QLIB_ALPHA_") and not requested:
            continue
        direction = (info.parameter_schema or {}).get("direction_hint", {}).get("value", "unknown")
        out.append(
            {
                "factor_name": info.factor_name,
                "display_name": info.display_name,
                "category": info.category,
                "expression": expression,
                "direction_hint": direction,
            }
        )
    if factor_limit is not None:
        out = out[: max(int(factor_limit), 0)]
    return out


def _is_native_expression_compatible(expression: str) -> bool:
    forbidden_tokens = (
        "PositiveDelta",
        "NegativeDelta",
        "AbsDelta",
        "Slope",
        "Rsquare",
        "Residual",
        "Return",
    )
    if any(token in expression for token in forbidden_tokens):
        return False
    return "$" in expression


def _load_native_factor_panel(
    provider_uri: str,
    universe: str,
    start_date: date | None,
    end_date: date | None,
    freq: str,
    factors: list[dict[str, Any]],
    horizon: int,
) -> pd.DataFrame:
    import qlib
    from qlib.data import D

    try:
        from qlib.constant import REG_CN
    except Exception:
        REG_CN = "cn"

    qlib.init(provider_uri=provider_uri, region=REG_CN)
    fields = ["$close"] + [str(f["expression"]) for f in factors]
    aliases = ["close"] + [str(f["factor_name"]) for f in factors]
    raw = D.features(
        instruments=universe,
        fields=fields,
        start_time=str(start_date) if start_date else None,
        end_time=str(end_date) if end_date else None,
        freq=freq,
    )
    if raw.empty:
        raise ValueError("native qlib returned no feature rows")

    wide = raw.copy()
    wide.columns = aliases[: len(wide.columns)]
    wide = wide.reset_index()
    rename: dict[str, str] = {}
    for c in wide.columns:
        lc = str(c).lower()
        if lc in {"datetime", "date", "trade_date"}:
            rename[c] = "trade_date"
        if lc in {"instrument", "asset", "asset_code"}:
            rename[c] = "asset_code"
    wide = wide.rename(columns=rename)
    if "trade_date" not in wide.columns or "asset_code" not in wide.columns:
        raise ValueError("native qlib feature frame missing instrument/date index columns")
    return _factor_panel_from_wide(wide, factors=factors, horizon=horizon)


def _factor_panel_from_wide(wide: pd.DataFrame, factors: list[dict[str, Any]], horizon: int) -> pd.DataFrame:
    df = wide.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["asset_code"] = df["asset_code"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.sort_values(["asset_code", "trade_date"], kind="mergesort")

    h = max(int(horizon), 1)
    entry = df.groupby("asset_code", sort=False)["close"].shift(-1)
    exit_ = df.groupby("asset_code", sort=False)["close"].shift(-(h + 1))
    df["forward_return"] = exit_ / entry - 1.0
    df["entry_trade_date"] = df.groupby("asset_code", sort=False)["trade_date"].shift(-1)
    df["exit_trade_date"] = df.groupby("asset_code", sort=False)["trade_date"].shift(-(h + 1))

    frames: list[pd.DataFrame] = []
    for f in factors:
        name = str(f["factor_name"])
        if name not in df.columns:
            continue
        part = df[["trade_date", "asset_code", "forward_return", "entry_trade_date", "exit_trade_date", name]].copy()
        part = part.rename(columns={name: "factor_value"})
        part["factor_name"] = name
        part["factor_value"] = pd.to_numeric(part["factor_value"], errors="coerce")
        frames.append(part)
    if not frames:
        raise ValueError("no factor columns were returned by native qlib")

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.replace([np.inf, -np.inf], np.nan)
    panel = panel.dropna(subset=["trade_date", "asset_code", "factor_name", "factor_value", "forward_return"])
    return panel


def _spearman(x: pd.Series, y: pd.Series) -> float:
    return float(x.rank().corr(y.rank()))


def _quantile_returns(group: pd.DataFrame, quantiles: int) -> pd.DataFrame:
    g = group.dropna(subset=["factor_value", "forward_return"]).copy()
    if g["factor_value"].nunique(dropna=True) < 2 or len(g) < max(quantiles, 2):
        return pd.DataFrame()
    try:
        g["quantile"] = pd.qcut(g["factor_value"], q=quantiles, labels=False, duplicates="drop") + 1
    except ValueError:
        return pd.DataFrame()
    return g.groupby("quantile", as_index=False)["forward_return"].mean()


def _summarize_factor_panel(panel: pd.DataFrame, quantiles: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ic_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    rank_rows: list[dict[str, Any]] = []
    q = max(int(quantiles), 2)

    for factor_name, fdf in panel.groupby("factor_name", sort=True):
        total_rows = int(fdf.shape[0])
        dates = sorted(fdf["trade_date"].unique().tolist())
        for trade_date, ddf in fdf.groupby("trade_date", sort=True):
            clean = ddf.dropna(subset=["factor_value", "forward_return"])
            row: dict[str, Any] = {
                "factor_name": factor_name,
                "trade_date": str(trade_date),
                "sample_count": int(clean.shape[0]),
                "ic": np.nan,
                "rank_ic": np.nan,
            }
            if clean.shape[0] >= 5 and clean["factor_value"].nunique(dropna=True) >= 2:
                row["ic"] = float(clean["factor_value"].corr(clean["forward_return"]))
                row["rank_ic"] = _spearman(clean["factor_value"], clean["forward_return"])
            ic_rows.append(row)

            qret = _quantile_returns(clean, q)
            if not qret.empty:
                qret["factor_name"] = factor_name
                qret["trade_date"] = str(trade_date)
                group_rows.extend(qret.to_dict(orient="records"))

        ic_df_factor = pd.DataFrame([r for r in ic_rows if r["factor_name"] == factor_name])
        grp_df_factor = pd.DataFrame([r for r in group_rows if r["factor_name"] == factor_name])
        ic_mean = float(pd.to_numeric(ic_df_factor.get("ic"), errors="coerce").mean()) if not ic_df_factor.empty else np.nan
        rank_ic_mean = (
            float(pd.to_numeric(ic_df_factor.get("rank_ic"), errors="coerce").mean()) if not ic_df_factor.empty else np.nan
        )
        ic_std = float(pd.to_numeric(ic_df_factor.get("ic"), errors="coerce").std(ddof=0)) if not ic_df_factor.empty else np.nan
        rank_ic_std = (
            float(pd.to_numeric(ic_df_factor.get("rank_ic"), errors="coerce").std(ddof=0)) if not ic_df_factor.empty else np.nan
        )
        icir = float(ic_mean / ic_std * np.sqrt(252.0)) if ic_std and not np.isnan(ic_std) else np.nan
        rank_icir = float(rank_ic_mean / rank_ic_std * np.sqrt(252.0)) if rank_ic_std and not np.isnan(rank_ic_std) else np.nan
        positive_ic_ratio = (
            float((pd.to_numeric(ic_df_factor.get("ic"), errors="coerce") > 0).mean()) if not ic_df_factor.empty else np.nan
        )

        long_short = np.nan
        monotonicity = np.nan
        if not grp_df_factor.empty:
            avg_by_q = grp_df_factor.groupby("quantile")["forward_return"].mean().sort_index()
            if len(avg_by_q) >= 2:
                long_short = float(avg_by_q.iloc[-1] - avg_by_q.iloc[0])
                monotonicity = float(pd.Series(avg_by_q.index.astype(float)).corr(avg_by_q.reset_index(drop=True), method="spearman"))

        factor_values = pd.to_numeric(fdf["factor_value"], errors="coerce")
        missing_rate = float(1.0 - factor_values.notna().mean()) if total_rows else 1.0
        coverage = float(factor_values.notna().mean()) if total_rows else 0.0
        score = np.nan_to_num(rank_ic_mean, nan=0.0) * 0.45
        score += np.nan_to_num(ic_mean, nan=0.0) * 0.25
        score += np.nan_to_num(long_short, nan=0.0) * 0.20
        score += np.nan_to_num(monotonicity, nan=0.0) * 0.10
        rank_rows.append(
            {
                "factor_name": factor_name,
                "coverage": coverage,
                "missing_rate": missing_rate,
                "ic_mean": ic_mean,
                "rank_ic_mean": rank_ic_mean,
                "icir": icir,
                "rank_icir": rank_icir,
                "positive_ic_ratio": positive_ic_ratio,
                "long_short_mean": long_short,
                "monotonicity": monotonicity,
                "stability": positive_ic_ratio,
                "score": float(score),
                "date_count": int(len(dates)),
                "sample_count": total_rows,
            }
        )

    ic_df = pd.DataFrame(ic_rows)
    group_df = pd.DataFrame(group_rows)
    ranking = pd.DataFrame(rank_rows).sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    return ranking, ic_df, group_df


def run_factor_mining(
    factor_pool: Optional[list[str]] = None,
    provider_uri: str | None = None,
    universe: str = DEFAULT_UNIVERSE,
    start_date: date | None = None,
    end_date: date | None = None,
    horizon: int = 1,
    quantiles: int = 5,
    top_k: int = 20,
    freq: str = DEFAULT_FREQ,
    factor_limit: int | None = None,
) -> dict[str, Any]:
    readiness = _require_ready(provider_uri=provider_uri, universe=universe, freq=freq)
    provider = provider_uri or readiness["provider_uri"]
    factors = _default_factor_pool(factor_pool=factor_pool, factor_limit=factor_limit)
    if not factors:
        raise ValueError("no qlib-compatible factors found in the requested factor pool")

    panel = _load_native_factor_panel(
        provider_uri=provider,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        freq=freq,
        factors=factors,
        horizon=max(int(horizon), 1),
    )
    if panel.empty:
        raise ValueError("factor mining produced no usable observations")

    ranking, ic_df, group_df = _summarize_factor_panel(panel, quantiles=quantiles)

    run_id = _new_id("qlib_mine")
    run_dir = _research_root() / "factor_mining" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    panel_path = run_dir / "factor_panel.parquet"
    ranking_path = run_dir / "factor_ranking.parquet"
    ic_path = run_dir / "ic_series.parquet"
    group_path = run_dir / "group_returns.parquet"
    panel.to_parquet(panel_path, index=False)
    ranking.to_parquet(ranking_path, index=False)
    ic_df.to_parquet(ic_path, index=False)
    group_df.to_parquet(group_path, index=False)

    top = _json_safe(ranking.head(max(int(top_k), 0)).to_dict(orient="records"))
    summary = {
        "run_id": run_id,
        "status": "SUCCESS",
        "generated_at": _now_utc(),
        "provider_uri": provider,
        "universe": universe,
        "freq": freq,
        "date_range": {
            "start_date": str(start_date) if start_date else str(panel["trade_date"].min()),
            "end_date": str(end_date) if end_date else str(panel["trade_date"].max()),
        },
        "horizon": int(horizon),
        "quantiles": int(quantiles),
        "factor_count": int(len(factors)),
        "observation_count": int(panel.shape[0]),
        "artifact_path": str(run_dir),
        "artifacts": {
            "factor_panel": str(panel_path),
            "factor_ranking": str(ranking_path),
            "ic_series": str(ic_path),
            "group_returns": str(group_path),
        },
        "top_factors": top,
        "timing_note": "Factor values are observed at t close; labels use close[t+1+horizon] / close[t+1] - 1.",
        "readiness": readiness,
    }
    summary = _json_safe(summary)
    _write_json(run_dir / "summary.json", summary)
    try:
        from app.services.research_quality_service import evaluate_research_quality

        quality = evaluate_research_quality(source_type="qlib_factor_mining", source_run_id=run_id)
        summary["quality_gate"] = {
            "source_run_id": quality.get("source_run_id"),
            "quality_status": quality.get("quality_status"),
            "quality_score": quality.get("quality_score"),
            "promotion_status": quality.get("promotion_status"),
            "reason_codes": quality.get("reason_codes") or [],
            "research_ops_object_id": quality.get("research_ops_object_id"),
            "artifact_path": quality.get("artifact_path"),
        }
        summary["promotion_status"] = quality.get("promotion_status")
        summary["not_executable"] = bool(quality.get("not_executable"))
        summary["quality_reason_codes"] = quality.get("reason_codes") or []
        _write_json(run_dir / "summary.json", summary)
    except Exception as e:
        summary["quality_gate"] = {
            "quality_status": "WARN",
            "promotion_status": "SHADOW_REVIEW",
            "reason_codes": ["QUALITY_EVALUATION_FAILED"],
            "message": str(e),
        }
        summary["promotion_status"] = "SHADOW_REVIEW"
        summary["not_executable"] = False
        summary["quality_reason_codes"] = ["QUALITY_EVALUATION_FAILED"]
        _write_json(run_dir / "summary.json", summary)
    _append_history(_research_root() / "factor_mining" / "history.jsonl", summary)
    try:
        from app.services.research_ops_registry import register_factor_run_artifact, register_validation_result_from_mining

        register_factor_run_artifact({**summary, "source_system": "native_qlib_factor_mining"})
        register_validation_result_from_mining(summary)
    except Exception:
        pass
    return {
        "run_id": run_id,
        "status": "SUCCESS",
        "factor_count": int(len(factors)),
        "date_range": summary["date_range"],
        "artifact_path": str(run_dir),
        "top_factors": top,
        "quality_gate": summary.get("quality_gate"),
        "promotion_status": summary.get("promotion_status"),
        "not_executable": summary.get("not_executable"),
        "quality_reason_codes": summary.get("quality_reason_codes") or [],
    }


def _history_items(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(items))[: max(int(limit), 0)]


def _attach_quality_gate(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("quality_gate") or not summary.get("run_id"):
        return summary
    try:
        from app.services.research_quality_service import try_read_quality_report

        quality = try_read_quality_report(str(summary["run_id"]))
        if quality:
            summary = dict(summary)
            summary["quality_gate"] = {
                "source_run_id": quality.get("source_run_id"),
                "quality_status": quality.get("quality_status"),
                "quality_score": quality.get("quality_score"),
                "promotion_status": quality.get("promotion_status"),
                "reason_codes": quality.get("reason_codes") or [],
                "research_ops_object_id": quality.get("research_ops_object_id"),
                "artifact_path": quality.get("artifact_path"),
            }
            summary["promotion_status"] = quality.get("promotion_status")
            summary["not_executable"] = bool(quality.get("not_executable"))
            summary["quality_reason_codes"] = quality.get("reason_codes") or []
    except Exception:
        pass
    return summary


def list_factor_mining_runs(limit: int = 50) -> list[dict[str, Any]]:
    return [_attach_quality_gate(item) for item in _history_items(_research_root() / "factor_mining" / "history.jsonl", limit=limit)]


def get_factor_mining_run(run_id: str) -> dict[str, Any]:
    run_dir = _research_root() / "factor_mining" / run_id
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"factor mining run not found: {run_id}")
    summary = _attach_quality_gate(_read_json(summary_path))
    ranking = _json_safe(pd.read_parquet(run_dir / "factor_ranking.parquet").head(200).to_dict(orient="records"))
    ic_tail = _json_safe(pd.read_parquet(run_dir / "ic_series.parquet").tail(500).to_dict(orient="records"))
    group_tail = _json_safe(pd.read_parquet(run_dir / "group_returns.parquet").tail(500).to_dict(orient="records"))
    return {"summary": summary, "factor_ranking": ranking, "ic_series": ic_tail, "group_returns": group_tail}


def _normalize_factor_weights(ranking: pd.DataFrame, selected_factors: list[str], weighting_method: str) -> dict[str, float]:
    rows = ranking[ranking["factor_name"].isin(selected_factors)].copy()
    found = set(rows["factor_name"].astype(str).tolist())
    missing = [f for f in selected_factors if f not in found]
    if missing:
        raise ValueError(f"selected factors are not in mining run: {missing}")
    if rows.empty:
        raise ValueError("selected factor set is empty")

    method = weighting_method.lower()
    if method == "equal":
        raw = pd.Series(1.0, index=rows["factor_name"].astype(str))
    elif method in {"ic_weighted", "ic"}:
        raw = pd.Series(pd.to_numeric(rows["ic_mean"], errors="coerce").clip(lower=0.0).fillna(0.0).values, index=rows["factor_name"].astype(str))
    elif method in {"rank_ic_weighted", "rankic", "rank_ic"}:
        raw = pd.Series(
            pd.to_numeric(rows["rank_ic_mean"], errors="coerce").clip(lower=0.0).fillna(0.0).values,
            index=rows["factor_name"].astype(str),
        )
    else:
        raise ValueError("weighting_method must be one of equal, ic_weighted, rank_ic_weighted")

    if float(raw.sum()) <= 0.0:
        raw = pd.Series(1.0, index=rows["factor_name"].astype(str))
    weights = raw / raw.sum()
    return {str(k): float(v) for k, v in weights.items()}


def build_portfolio(
    mining_run_id: str,
    selected_factors: Optional[list[str]] = None,
    weighting_method: str = "equal",
    top_n: int = 5,
    long_top_n: int = 30,
) -> dict[str, Any]:
    run_dir = _research_root() / "factor_mining" / mining_run_id
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"factor mining run not found: {mining_run_id}")
    mining_summary = _read_json(summary_path)
    ranking = pd.read_parquet(run_dir / "factor_ranking.parquet")
    panel = pd.read_parquet(run_dir / "factor_panel.parquet")

    if selected_factors is None or not selected_factors:
        selected_factors = ranking.head(max(int(top_n), 1))["factor_name"].astype(str).tolist()
    weights = _normalize_factor_weights(ranking, selected_factors=selected_factors, weighting_method=weighting_method)
    try:
        from app.services.research_quality_service import summarize_quality_for_portfolio

        quality_gate = summarize_quality_for_portfolio(mining_run_id, selected_factors)
    except Exception as e:
        quality_gate = {
            "quality_gate": None,
            "promotion_status": "SHADOW_ONLY",
            "not_executable": True,
            "quality_reason_codes": ["QUALITY_GATE_UNAVAILABLE"],
            "quality_error": str(e),
        }

    df = panel[panel["factor_name"].isin(weights)].copy()
    if df.empty:
        raise ValueError("no panel rows available for selected factors")
    df["factor_value"] = pd.to_numeric(df["factor_value"], errors="coerce")

    def zscore(s: pd.Series) -> pd.Series:
        std = s.std(ddof=0)
        if not std or np.isnan(std):
            return pd.Series(0.0, index=s.index)
        return (s - s.mean()) / std

    df["factor_z"] = df.groupby(["trade_date", "factor_name"], sort=False)["factor_value"].transform(zscore)
    df["factor_weight"] = df["factor_name"].map(weights).astype(float)
    df["weighted_score"] = df["factor_z"] * df["factor_weight"]
    scores = df.groupby(["trade_date", "asset_code"], as_index=False)["weighted_score"].sum().rename(columns={"weighted_score": "score"})

    unique_dates = sorted(scores["trade_date"].unique().tolist())
    next_date = {d: unique_dates[i + 1] for i, d in enumerate(unique_dates[:-1])}
    scores["effective_trade_date"] = scores["trade_date"].map(next_date)
    scores = scores.dropna(subset=["effective_trade_date"])
    scores = scores.sort_values(["trade_date", "score"], ascending=[True, False], kind="mergesort")
    top = scores.groupby("trade_date", as_index=False, sort=False).head(max(int(long_top_n), 1)).copy()
    top["asset_count"] = top.groupby("trade_date")["asset_code"].transform("count")
    top["weight"] = 1.0 / top["asset_count"].replace(0, np.nan)
    signals = top.rename(columns={"trade_date": "signal_date", "effective_trade_date": "trade_date"})[
        ["trade_date", "signal_date", "asset_code", "weight", "score"]
    ].copy()
    signals["trade_date"] = pd.to_datetime(signals["trade_date"]).dt.date
    signals["signal_date"] = pd.to_datetime(signals["signal_date"]).dt.date
    signals["execution_note"] = "effective_trade_date is the next trading day after factor signal_date."

    portfolio_id = _new_id("qlib_port")
    port_dir = _research_root() / "portfolios" / portfolio_id
    port_dir.mkdir(parents=True, exist_ok=True)
    signal_path = port_dir / "signals.parquet"
    signals.to_parquet(signal_path, index=False)

    summary = {
        "portfolio_id": portfolio_id,
        "created_at": _now_utc(),
        "mining_run_id": mining_run_id,
        "provider_uri": mining_summary.get("provider_uri"),
        "universe": mining_summary.get("universe"),
        "selected_factors": selected_factors,
        "weighting_method": weighting_method,
        "weights": weights,
        "signal_artifact_path": str(signal_path),
        "signal_count": int(signals.shape[0]),
        "date_count": int(signals["trade_date"].nunique()) if not signals.empty else 0,
        "timing_note": "Portfolio signals are written on the next trading date, so the existing backtest shift executes no earlier than t+1.",
        "quality_gate": quality_gate.get("quality_gate"),
        "promotion_status": quality_gate.get("promotion_status"),
        "not_executable": bool(quality_gate.get("not_executable")),
        "quality_reason_codes": quality_gate.get("quality_reason_codes") or [],
    }
    if quality_gate.get("quality_error"):
        summary["quality_error"] = quality_gate.get("quality_error")
    _write_json(port_dir / "summary.json", summary)
    _append_history(_research_root() / "portfolios" / "history.jsonl", summary)
    try:
        from app.services.research_ops_registry import register_portfolio_proposal

        register_portfolio_proposal(summary)
    except Exception:
        pass
    return summary


def list_portfolios(limit: int = 50) -> list[dict[str, Any]]:
    return _history_items(_research_root() / "portfolios" / "history.jsonl", limit=limit)


def get_portfolio(portfolio_id: str) -> dict[str, Any]:
    path = _research_root() / "portfolios" / portfolio_id / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"portfolio not found: {portfolio_id}")
    return _read_json(path)


def read_portfolio_signals(portfolio_id: str) -> pd.DataFrame:
    summary = get_portfolio(portfolio_id)
    signal_path = Path(str(summary["signal_artifact_path"]))
    if not signal_path.exists():
        raise FileNotFoundError(f"portfolio signal artifact not found: {signal_path}")
    df = pd.read_parquet(signal_path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["asset_code"] = df["asset_code"].astype(str)
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    return df
