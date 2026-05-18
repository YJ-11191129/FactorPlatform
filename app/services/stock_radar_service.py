from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

from app.datahub.loaders.qlib_bin import load_daily_bar, read_calendar
from app.factors.registry import ensure_registered, get_factor
from app.services.factor_service import DEFAULT_FACTOR_MODULES


DEFAULT_QLIB_PROVIDER_URI = os.getenv("FACTOR_PLATFORM_PROVIDER_URI", r"D:\mcQlib\data\qlib_bin\cn_data")


def _normalize_factor_key(factor_name: str, params: Mapping[str, Any]) -> str:
    if not params:
        return factor_name
    suffix = "_".join(f"{k}{params[k]}" for k in sorted(params))
    return f"{factor_name}__{suffix}"


def _schema_value(schema: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = schema.get(key)
    if isinstance(value, Mapping):
        return value.get("value", default)
    return default if value is None else value


def _winsorized_zscore(s: pd.Series, winsorize_q: float) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = x.dropna()
    if valid.empty:
        return pd.Series(np.nan, index=s.index)

    q = max(0.0, min(float(winsorize_q), 0.25))
    if q > 0 and valid.size >= 5:
        lo, hi = valid.quantile([q, 1.0 - q])
        x = x.clip(lower=float(lo), upper=float(hi))

    med = float(x.median(skipna=True))
    iqr = float(x.quantile(0.75) - x.quantile(0.25))
    if np.isfinite(iqr) and iqr > 1e-12:
        scale = iqr / 1.349
    else:
        scale = float(x.std(skipna=True))

    if not np.isfinite(scale) or scale <= 1e-12:
        return pd.Series(0.0, index=s.index).where(x.notna(), np.nan)

    return ((x - med) / scale).clip(-5.0, 5.0)


def _resolve_asof_date(daily_bar: pd.DataFrame, asof_date: Optional[date]) -> date:
    dates = pd.to_datetime(daily_bar["trade_date"]).dt.date
    if asof_date is not None:
        available = dates[dates <= asof_date]
        if available.empty:
            raise ValueError(f"no qlib daily bar on or before asof_date={asof_date}")
        return max(available)
    return max(dates)


def _resolve_next_trade_date(provider_uri: str, signal_date: date) -> Optional[str]:
    try:
        calendar = read_calendar(provider_uri)
    except Exception:
        return None

    future = calendar[calendar.date > signal_date]
    if future.empty:
        return None
    return future[0].date().isoformat()


def run_stock_radar(
    *,
    provider_uri: str = DEFAULT_QLIB_PROVIDER_URI,
    universe: str = "csi300",
    factors: list[Mapping[str, Any]],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    asof_date: Optional[date] = None,
    instrument_limit: Optional[int] = 300,
    topn: int = 50,
    min_score: Optional[float] = None,
    min_factor_count: int = 1,
    winsorize_q: float = 0.01,
) -> dict[str, Any]:
    """Compute a cross-sectional stock radar from qlib daily bars.

    Timing discipline:
    - factor values are observed with data available through signal_date/asof_date;
    - ranking is formed on signal_date;
    - any trade using the ranking should execute no earlier than the next trading day.
    """

    if not factors:
        raise ValueError("at least one factor is required")

    provider_uri = str(provider_uri or "").strip()
    universe = str(universe or "").strip().lower()
    if not provider_uri:
        raise ValueError("provider_uri is required")
    if not universe:
        raise ValueError("universe is required")
    if instrument_limit is not None and int(instrument_limit) < 1:
        raise ValueError("instrument_limit must be >= 1")
    if int(topn) < 1:
        raise ValueError("topn must be >= 1")
    min_factor_count = int(min_factor_count)
    if min_factor_count < 1:
        raise ValueError("min_factor_count must be >= 1")

    provider_path = Path(provider_uri)
    if not provider_path.exists():
        raise ValueError(f"qlib provider_uri does not exist: {provider_uri}")
    if not (provider_path / "calendars" / "day.txt").exists():
        raise ValueError(f"qlib provider_uri missing calendars/day.txt: {provider_uri}")
    universe_file = "all.txt" if universe == "all" else f"{universe}.txt"
    if not (provider_path / "instruments" / universe_file).exists():
        raise ValueError(f"qlib universe file not found: {provider_path / 'instruments' / universe_file}")

    ensure_registered(DEFAULT_FACTOR_MODULES)

    daily_bar = load_daily_bar(
        provider_uri=provider_uri,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        instrument_limit=instrument_limit,
    )
    if daily_bar.empty:
        raise ValueError(f"no qlib daily bar loaded from {provider_uri} universe={universe}")

    signal_date = _resolve_asof_date(daily_bar, asof_date or end_date)
    base = (
        daily_bar.loc[pd.to_datetime(daily_bar["trade_date"]).dt.date == signal_date, ["trade_date", "asset_code", "close", "volume"]]
        .drop_duplicates("asset_code")
        .copy()
    )
    if base.empty:
        raise ValueError(f"no instruments available on signal_date={signal_date}")

    row_count_on_signal_date = int(base.shape[0])

    factor_meta: list[dict[str, Any]] = []

    for idx, spec in enumerate(factors):
        factor_name = str(spec.get("factor_name") or "").strip()
        if not factor_name:
            raise ValueError(f"factor[{idx}] missing factor_name")
        params = dict(spec.get("params") or {})
        weight = float(spec.get("weight", 1.0))
        direction = str(spec.get("direction", "positive")).lower()
        sign = -1.0 if direction in {"negative", "lower_better", "short"} else 1.0

        rf = get_factor(factor_name)
        info = rf.info
        schema = dict(info.parameter_schema or {})
        values = rf.factor_cls.compute(daily_bar=daily_bar, params=params)
        values["trade_date"] = pd.to_datetime(values["trade_date"]).dt.date
        current = values.loc[values["trade_date"] == signal_date, ["asset_code", "factor_value"]].copy()
        key = _normalize_factor_key(factor_name, params)
        raw_col = f"{key}__raw"
        score_col = f"{key}__score"
        rank_col = f"{key}__rank_pct"

        base = base.merge(current.rename(columns={"factor_value": raw_col}), on="asset_code", how="left")
        base[score_col] = _winsorized_zscore(base[raw_col], winsorize_q=winsorize_q) * sign
        base[rank_col] = base[score_col].rank(pct=True, ascending=True)

        factor_meta.append(
            {
                "key": key,
                "factor_name": factor_name,
                "display_name": info.display_name,
                "category": info.category,
                "family": _schema_value(schema, "family"),
                "expression": _schema_value(schema, "expression"),
                "direction_hint": _schema_value(schema, "direction_hint"),
                "source": _schema_value(schema, "source"),
                "params": params,
                "weight": weight,
                "direction": "negative" if sign < 0 else "positive",
                "raw_col": raw_col,
                "score_col": score_col,
                "rank_col": rank_col,
                "non_null_count": int(base[raw_col].notna().sum()),
                "coverage_ratio": float(base[raw_col].notna().sum() / max(row_count_on_signal_date, 1)),
            }
        )

    score_parts = []
    weight_sum = 0.0
    for meta in factor_meta:
        w = abs(float(meta["weight"]))
        if w <= 0:
            meta["normalized_weight"] = 0.0
            continue
        score_parts.append(base[meta["score_col"]].fillna(0.0) * float(meta["weight"]))
        weight_sum += w

    if not score_parts or weight_sum <= 0:
        raise ValueError("at least one factor weight must be non-zero")

    for meta in factor_meta:
        meta["normalized_weight"] = float(meta["weight"]) / weight_sum

    score_cols = [m["score_col"] for m in factor_meta]
    base["valid_factor_count"] = base[score_cols].notna().sum(axis=1)
    base["missing_factor_count"] = len(score_cols) - base["valid_factor_count"]
    base["factor_coverage"] = base["valid_factor_count"] / max(len(score_cols), 1)
    base = base.loc[base["valid_factor_count"] >= min_factor_count].copy()
    if base.empty:
        raise ValueError(
            f"no stocks passed min_factor_count={min_factor_count}; "
            f"loaded={row_count_on_signal_date}, factors={len(score_cols)}"
        )

    base["score"] = sum(score_parts) / weight_sum
    base["score_percentile"] = base["score"].rank(pct=True, ascending=True)
    base = base.sort_values(["score", "asset_code"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    base["rank"] = np.arange(1, len(base) + 1)

    before_filter = int(base.shape[0])
    if min_score is not None:
        base = base.loc[base["score"] >= float(min_score)].copy()
    base = base.head(max(1, int(topn))).copy()

    items: list[dict[str, Any]] = []
    for _, row in base.iterrows():
        factor_values = {m["key"]: (None if pd.isna(row[m["raw_col"]]) else float(row[m["raw_col"]])) for m in factor_meta}
        factor_scores = {m["key"]: (None if pd.isna(row[m["score_col"]]) else float(row[m["score_col"]])) for m in factor_meta}
        factor_ranks = {m["key"]: (None if pd.isna(row[m["rank_col"]]) else float(row[m["rank_col"]])) for m in factor_meta}
        factor_contributions = {
            m["key"]: (
                None
                if pd.isna(row[m["score_col"]])
                else float(row[m["score_col"]]) * float(m["normalized_weight"])
            )
            for m in factor_meta
        }
        top_factor_contributors = sorted(
            [
                {
                    "key": key,
                    "contribution": value,
                }
                for key, value in factor_contributions.items()
                if value is not None and np.isfinite(value)
            ],
            key=lambda x: abs(float(x["contribution"])),
            reverse=True,
        )[:5]
        items.append(
            {
                "rank": int(row["rank"]),
                "trade_date": str(row["trade_date"]),
                "asset_code": str(row["asset_code"]),
                "close": None if pd.isna(row.get("close")) else float(row["close"]),
                "volume": None if pd.isna(row.get("volume")) else float(row["volume"]),
                "score": float(row["score"]),
                "score_percentile": float(row["score_percentile"]),
                "valid_factor_count": int(row["valid_factor_count"]),
                "missing_factor_count": int(row["missing_factor_count"]),
                "factor_coverage": float(row["factor_coverage"]),
                "factor_values": factor_values,
                "factor_scores": factor_scores,
                "factor_ranks": factor_ranks,
                "factor_contributions": factor_contributions,
                "top_factor_contributors": top_factor_contributors,
            }
        )

    next_trade_date = _resolve_next_trade_date(provider_uri, signal_date)

    return {
        "universe": universe,
        "provider_uri": provider_uri,
        "signal_date": signal_date.isoformat(),
        "effective_trade_date": next_trade_date or "next_trading_day",
        "row_count_on_signal_date": row_count_on_signal_date,
        "row_count_before_score_filter": before_filter,
        "row_count": len(items),
        "topn": int(topn),
        "min_score": min_score,
        "min_factor_count": min_factor_count,
        "factors": factor_meta,
        "items": items,
        "timing_note": "Factors use data through signal_date; rankings should be traded no earlier than the next trading day.",
    }
