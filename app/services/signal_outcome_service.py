"""File-backed outcome and performance tracking for Signal Center."""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.datahub.loaders.qlib_bin import load_daily_bar
from app.services.market_data_repository import MarketDataRepository, postgres_market_data_enabled, resolve_market_source_id
from app.services.signal_generation_service import (
    read_latest_signal_snapshot,
    read_signal_history,
    signal_center_root,
)


DEFAULT_HORIZON_DAYS = 10


def outcomes_path() -> Path:
    return signal_center_root() / "latest_outcomes.json"


def outcomes_history_path() -> Path:
    return signal_center_root() / "outcomes_history.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _jsonable_number(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), 8)


def _status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(item.get("outcome_status") or "UNKNOWN") for item in items))


def _normalize_execution_mode(value: str | None) -> str:
    mode = str(value or "live").strip().lower()
    return mode if mode in {"live", "shadow", "all"} else "live"


def _snapshot_signals(snapshot: dict[str, Any], execution_mode: str = "live") -> list[dict[str, Any]]:
    mode = _normalize_execution_mode(execution_mode)
    live = [dict(item, execution_mode="live") for item in (snapshot.get("items") or snapshot.get("signals") or [])]
    shadow = [dict(item, execution_mode="shadow") for item in (snapshot.get("shadow_items") or [])]
    if mode == "shadow":
        return shadow
    if mode == "all":
        return live + shadow
    return live


def _outcome_items(payload: dict[str, Any], execution_mode: str = "live") -> list[dict[str, Any]]:
    mode = _normalize_execution_mode(execution_mode)
    if mode == "shadow":
        return list(payload.get("shadow_items") or [])
    if mode == "all":
        return list(payload.get("items") or []) + list(payload.get("shadow_items") or [])
    return list(payload.get("items") or [])


def _source_config(snapshot: dict[str, Any], provider_uri: str | None, universe: str | None) -> tuple[str | None, str]:
    source = snapshot.get("data_source")
    source_provider = source.get("provider_uri") if isinstance(source, dict) else source
    source_universe = source.get("universe") if isinstance(source, dict) else None
    provider = provider_uri or source_provider or os.getenv("FACTOR_PLATFORM_PROVIDER_URI")
    universe_name = universe or source_universe or os.getenv("FACTOR_PLATFORM_SIGNAL_UNIVERSE", "csi300")
    return provider, universe_name


def _signal_start_date(signal: dict[str, Any], snapshot: dict[str, Any]) -> date | None:
    return (
        _parse_date(signal.get("effective_trade_date"))
        or _parse_date(signal.get("signal_date"))
        or _parse_date(snapshot.get("signal_date"))
        or _parse_date(snapshot.get("generated_at"))
    )


def _pending_outcome(
    signal: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    reason: str,
    status: str = "PENDING_OUTCOME",
) -> dict[str, Any]:
    execution_mode = _normalize_execution_mode(signal.get("execution_mode"))
    if execution_mode == "shadow" and status == "PENDING_OUTCOME":
        status = "SHADOW_PENDING"
    return {
        "signal_id": signal.get("id") or signal.get("signal_id"),
        "execution_mode": execution_mode,
        "not_executable": bool(signal.get("not_executable")) if execution_mode == "shadow" else False,
        "source_run_id": snapshot.get("run_id") or snapshot.get("source_run_id"),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "signal_date": signal.get("signal_date") or snapshot.get("signal_date"),
        "instrument": signal.get("instrument"),
        "name": signal.get("name"),
        "side": signal.get("side"),
        "regime_label": signal.get("regime_label"),
        "signal_template": signal.get("signal_template"),
        "risk_level": signal.get("risk_level"),
        "confidence": signal.get("confidence"),
        "expected_holding_bars": signal.get("expected_holding_bars"),
        "entry_date": None,
        "entry_price": _safe_float(signal.get("entry_price")),
        "last_date": None,
        "last_price": None,
        "holding_bars": 0,
        "mfe": None,
        "mae": None,
        "realized_pnl": None,
        "unrealized_pnl": None,
        "outcome_status": status,
        "reason": reason,
        "price_path": [],
    }


def _build_outcome(
    signal: dict[str, Any],
    snapshot: dict[str, Any],
    asset_bars: pd.DataFrame,
    *,
    horizon_days: int,
) -> dict[str, Any]:
    signal_id = signal.get("id") or signal.get("signal_id")
    execution_mode = _normalize_execution_mode(signal.get("execution_mode"))
    start_date = _signal_start_date(signal, snapshot)
    if not signal_id:
        return _pending_outcome(signal, snapshot, reason="signal_id_missing")
    if execution_mode == "live" and str(signal.get("status") or "").upper() == "BLOCKED":
        return _pending_outcome(signal, snapshot, reason="signal_blocked_by_router", status="NO_TRADE")
    if str(signal.get("side") or "LONG").upper() != "LONG":
        return _pending_outcome(signal, snapshot, reason="outcome_v1_tracks_long_signals_only")
    if start_date is None:
        return _pending_outcome(signal, snapshot, reason="effective_trade_date_missing")
    if asset_bars.empty:
        return _pending_outcome(signal, snapshot, reason="price_coverage_missing")

    bars = asset_bars.copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.date
    bars = bars[bars["trade_date"] >= start_date].sort_values("trade_date")
    if bars.empty:
        return _pending_outcome(signal, snapshot, reason="price_coverage_missing")

    expected_holding_bars = int(_safe_float(signal.get("expected_holding_bars")) or horizon_days)
    expected_holding_bars = max(1, min(expected_holding_bars, max(1, horizon_days)))
    evaluation = bars.head(expected_holding_bars + 1).copy()
    entry_bar = evaluation.iloc[0]
    entry_price = (
        _safe_float(entry_bar.get("open"))
        or _safe_float(entry_bar.get("close"))
        or _safe_float(signal.get("entry_price"))
    )
    if entry_price is None or entry_price <= 0:
        return _pending_outcome(signal, snapshot, reason="entry_price_missing_or_invalid")

    last_bar = evaluation.iloc[-1]
    last_price = _safe_float(last_bar.get("close")) or entry_price
    high = evaluation["high"].map(_safe_float).dropna()
    low = evaluation["low"].map(_safe_float).dropna()
    if high.empty:
        high = evaluation["close"].map(_safe_float).dropna()
    if low.empty:
        low = evaluation["close"].map(_safe_float).dropna()

    holding_bars = max(0, len(evaluation) - 1)
    unrealized = (last_price / entry_price) - 1.0
    realized = unrealized if holding_bars >= expected_holding_bars else None
    status = "SHADOW_EVALUATED" if execution_mode == "shadow" else ("CLOSED" if realized is not None else "OPEN")
    price_path = []
    for _, row in evaluation.iterrows():
        close = _safe_float(row.get("close"))
        if close is None:
            continue
        price_path.append(
            {
                "date": str(row.get("trade_date")),
                "close": _jsonable_number(close),
                "return": _jsonable_number((close / entry_price) - 1.0),
            }
        )

    return {
        "signal_id": signal_id,
        "execution_mode": execution_mode,
        "not_executable": bool(signal.get("not_executable")) if execution_mode == "shadow" else False,
        "source_run_id": snapshot.get("run_id") or snapshot.get("source_run_id"),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "signal_date": signal.get("signal_date") or snapshot.get("signal_date"),
        "instrument": signal.get("instrument"),
        "name": signal.get("name"),
        "side": signal.get("side") or "LONG",
        "regime_label": signal.get("regime_label"),
        "signal_template": signal.get("signal_template"),
        "risk_level": signal.get("risk_level"),
        "confidence": signal.get("confidence"),
        "expected_holding_bars": expected_holding_bars,
        "entry_date": str(entry_bar.get("trade_date")),
        "entry_price": _jsonable_number(entry_price),
        "last_date": str(last_bar.get("trade_date")),
        "last_price": _jsonable_number(last_price),
        "holding_bars": holding_bars,
        "mfe": _jsonable_number(((float(high.max()) / entry_price) - 1.0) if not high.empty else None),
        "mae": _jsonable_number(((float(low.min()) / entry_price) - 1.0) if not low.empty else None),
        "realized_pnl": _jsonable_number(realized),
        "unrealized_pnl": _jsonable_number(unrealized),
        "outcome_status": status,
        "reason": "shadow_candidate_evaluated" if execution_mode == "shadow" else None,
        "price_path": price_path,
    }


def _load_price_frame(
    snapshot: dict[str, Any],
    instruments: list[str],
    *,
    provider_uri: str | None,
    universe: str | None,
) -> pd.DataFrame:
    provider, universe_name = _source_config(snapshot, provider_uri, universe)
    if not provider or not instruments:
        return pd.DataFrame()
    start_dates = [
        parsed
        for signal in _snapshot_signals(snapshot, "all")
        if (parsed := _signal_start_date(signal, snapshot)) is not None
    ]
    start_date = min(start_dates).isoformat() if start_dates else None
    if postgres_market_data_enabled():
        source_id = resolve_market_source_id(provider_uri=provider, universe=universe_name)
        repo = MarketDataRepository(source_id)
        try:
            if repo.source_exists(source_id):
                return repo.load_daily_bar(
                    source_id=source_id,
                    provider_uri=provider,
                    universe=universe_name,
                    start_date=_parse_date(start_date),
                    instruments=instruments,
                    instrument_limit=len(instruments),
                )
        except Exception:
            pass
    return load_daily_bar(
        provider,
        universe_name,
        start_date=start_date,
        instruments=instruments,
        instrument_limit=len(instruments),
    )


def refresh_signal_outcomes(
    *,
    provider_uri: str | None = None,
    universe: str | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    dry_run: bool = False,
) -> dict[str, Any]:
    snapshot = read_latest_signal_snapshot()
    computed_at = _now_iso()
    if not snapshot:
        return {
            "status": "NO_SNAPSHOT",
            "data_source": "signal_outcomes",
            "execution_mode": "live",
            "computed_at": computed_at,
            "source_run_id": None,
            "generated_count": 0,
            "shadow_generated_count": 0,
            "pending_count": 0,
            "shadow_pending_count": 0,
            "items": [],
            "shadow_items": [],
            "outcome_path": str(outcomes_path()),
            "dry_run": dry_run,
        }

    signals = _snapshot_signals(snapshot, "live")
    shadow_signals = _snapshot_signals(snapshot, "shadow")
    all_signals = signals + shadow_signals
    instruments = sorted({str(item.get("instrument")) for item in all_signals if item.get("instrument")})
    price_error = None
    try:
        price_frame = _load_price_frame(snapshot, instruments, provider_uri=provider_uri, universe=universe)
    except Exception as e:
        price_error = str(e)
        price_frame = pd.DataFrame()
    by_asset: dict[str, pd.DataFrame] = {}
    if not price_frame.empty and "asset_code" in price_frame.columns:
        for asset, rows in price_frame.groupby("asset_code"):
            by_asset[str(asset)] = rows

    outcomes = [
        _build_outcome(
            signal,
            snapshot,
            by_asset.get(str(signal.get("instrument")), pd.DataFrame()),
            horizon_days=horizon_days,
        )
        for signal in signals
    ]
    shadow_outcomes = [
        _build_outcome(
            signal,
            snapshot,
            by_asset.get(str(signal.get("instrument")), pd.DataFrame()),
            horizon_days=horizon_days,
        )
        for signal in shadow_signals
    ]
    status_counts = _status_counts(outcomes)
    shadow_status_counts = _status_counts(shadow_outcomes)
    payload = {
        "status": "OK" if all_signals else "EMPTY_SNAPSHOT",
        "data_source": "signal_outcomes",
        "execution_mode": "live",
        "computed_at": computed_at,
        "source_run_id": snapshot.get("run_id") or snapshot.get("source_run_id"),
        "source_snapshot_path": str(signal_center_root() / "latest_signals.json"),
        "signal_date": snapshot.get("signal_date"),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "generated_count": len(outcomes),
        "shadow_generated_count": len(shadow_outcomes),
        "pending_count": int(status_counts.get("PENDING_OUTCOME", 0)),
        "shadow_pending_count": int(shadow_status_counts.get("SHADOW_PENDING", 0)),
        "status_counts": status_counts,
        "shadow_status_counts": shadow_status_counts,
        "counts": {
            "live": {
                "generated_count": len(outcomes),
                "pending_count": int(status_counts.get("PENDING_OUTCOME", 0)),
                "status_counts": status_counts,
            },
            "shadow": {
                "generated_count": len(shadow_outcomes),
                "pending_count": int(shadow_status_counts.get("SHADOW_PENDING", 0)),
                "status_counts": shadow_status_counts,
            },
        },
        "price_error": price_error,
        "items": outcomes,
        "shadow_items": shadow_outcomes,
        "outcome_path": str(outcomes_path()),
        "dry_run": dry_run,
    }
    if dry_run:
        return payload

    root = signal_center_root()
    root.mkdir(parents=True, exist_ok=True)
    outcomes_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with outcomes_history_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    try:
        from app.services.research_ops_registry import register_outcome_payload

        register_outcome_payload(payload)
    except Exception:
        pass
    return payload


def read_latest_outcomes() -> dict[str, Any]:
    path = outcomes_path()
    if not path.exists():
        return {
            "status": "NO_OUTCOMES",
            "data_source": "signal_outcomes",
            "execution_mode": "live",
            "computed_at": None,
            "source_run_id": None,
            "generated_count": 0,
            "shadow_generated_count": 0,
            "pending_count": 0,
            "shadow_pending_count": 0,
            "status_counts": {},
            "shadow_status_counts": {},
            "items": [],
            "shadow_items": [],
            "outcome_path": str(path),
        }
    return json.loads(path.read_text(encoding="utf-8"))


def get_signal_outcome(signal_id: str, execution_mode: str | None = "live") -> dict[str, Any] | None:
    payload = read_latest_outcomes()
    for item in _outcome_items(payload, execution_mode or "live"):
        if str(item.get("signal_id")) == str(signal_id):
            return item
    return None


def list_signal_outcomes(
    *,
    signal_id: str | None = None,
    status: str | None = None,
    execution_mode: str | None = "live",
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    payload = read_latest_outcomes()
    mode = _normalize_execution_mode(execution_mode)
    items = _outcome_items(payload, mode)
    if signal_id:
        items = [item for item in items if str(item.get("signal_id")) == str(signal_id)]
    if status:
        wanted = status.upper()
        items = [item for item in items if str(item.get("outcome_status") or "").upper() == wanted]
    total = len(items)
    return {
        **payload,
        "execution_mode": mode,
        "total": total,
        "items": items[offset : offset + limit],
        "limit": limit,
        "offset": offset,
    }


def _pnl_value(item: dict[str, Any]) -> float | None:
    return _safe_float(item.get("realized_pnl")) if item.get("realized_pnl") is not None else _safe_float(item.get("unrealized_pnl"))


def _evaluated_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if _pnl_value(item) is not None]


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _max_drawdown(pnls: list[float]) -> float:
    peak = 0.0
    equity = 0.0
    drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)
    return drawdown


def _profit_factor(pnls: list[float]) -> float:
    gains = sum(pnl for pnl in pnls if pnl > 0)
    losses = abs(sum(pnl for pnl in pnls if pnl < 0))
    if losses == 0:
        return 0.0 if gains == 0 else round(gains, 8)
    return gains / losses


def _breakdown(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for item in items:
        pnl = _pnl_value(item)
        if pnl is None:
            continue
        groups[str(item.get(key) or "UNKNOWN")].append(pnl)
    return [
        {
            "label": label,
            "count": len(values),
            "avg_pnl": _jsonable_number(_avg(values)) or 0.0,
            "win_rate": _jsonable_number(sum(1 for value in values if value > 0) / len(values)) or 0.0,
        }
        for label, values in sorted(groups.items())
    ]


def _confidence_breakdown(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for item in items:
        pnl = _pnl_value(item)
        confidence = _safe_float(item.get("confidence"))
        if pnl is None or confidence is None:
            continue
        if confidence >= 0.75:
            label = "high"
        elif confidence >= 0.55:
            label = "medium"
        else:
            label = "low"
        groups[label].append(pnl)
    return [
        {
            "label": label,
            "count": len(values),
            "avg_pnl": _jsonable_number(_avg(values)) or 0.0,
            "win_rate": _jsonable_number(sum(1 for value in values if value > 0) / len(values)) or 0.0,
        }
        for label, values in sorted(groups.items())
    ]


def performance_summary(execution_mode: str | None = "live") -> dict[str, Any]:
    payload = read_latest_outcomes()
    mode = _normalize_execution_mode(execution_mode)
    items = _outcome_items(payload, mode)
    evaluated = _evaluated_items(items)
    pending_statuses = {"PENDING_OUTCOME", "SHADOW_PENDING"} if mode == "all" else ({"SHADOW_PENDING"} if mode == "shadow" else {"PENDING_OUTCOME"})
    pending_count = sum(1 for item in items if str(item.get("outcome_status") or "").upper() in pending_statuses)
    no_trade_count = sum(1 for item in items if str(item.get("outcome_status") or "").upper() == "NO_TRADE")
    pnls = [_pnl_value(item) or 0.0 for item in evaluated]
    wins = [pnl for pnl in pnls if pnl > 0]
    holding = [int(_safe_float(item.get("holding_bars")) or 0) for item in evaluated]
    avg_pnl = _jsonable_number(_avg(pnls)) or 0.0
    return {
        "data_source": "signal_outcomes",
        "execution_mode": mode,
        "source_run_id": payload.get("source_run_id"),
        "source_snapshot_id": payload.get("source_run_id"),
        "computed_at": payload.get("computed_at"),
        "status": payload.get("status") or "NO_OUTCOMES",
        "total_signals": len(items),
        "evaluated_signals": len(evaluated),
        "pending_signals": pending_count,
        "no_trade_signals": no_trade_count,
        "avg_forward_return": avg_pnl,
        "avg_pnl": avg_pnl,
        "win_rate": _jsonable_number((len(wins) / len(pnls)) if pnls else 0.0) or 0.0,
        "profit_factor": _jsonable_number(_profit_factor(pnls)) or 0.0,
        "max_drawdown": _jsonable_number(_max_drawdown(pnls)) or 0.0,
        "avg_holding_bars": _jsonable_number(_avg([float(value) for value in holding])) or 0.0,
        "breakdowns": {
            "by_regime": _breakdown(evaluated, "regime_label"),
            "by_confidence_bucket": _confidence_breakdown(evaluated),
            "by_template": _breakdown(evaluated, "signal_template"),
            "by_risk_level": _breakdown(evaluated, "risk_level"),
        },
    }


def performance_timeseries(metric: str = "cum_pnl", granularity: str = "daily", execution_mode: str | None = "live") -> dict[str, Any]:
    payload = read_latest_outcomes()
    mode = _normalize_execution_mode(execution_mode)
    evaluated = sorted(
        _evaluated_items(_outcome_items(payload, mode)),
        key=lambda item: str(item.get("last_date") or item.get("entry_date") or item.get("signal_date") or ""),
    )
    points = []
    cumulative = 0.0
    peak = 0.0
    pnls: list[float] = []
    for item in evaluated:
        pnl = _pnl_value(item) or 0.0
        pnls.append(pnl)
        cumulative += pnl
        peak = max(peak, cumulative)
        if metric == "win_rate":
            value = sum(1 for value in pnls if value > 0) / len(pnls)
        elif metric == "drawdown":
            value = cumulative - peak
        elif metric == "profit_factor":
            value = _profit_factor(pnls)
        else:
            value = cumulative
        points.append(
            {
                "date": item.get("last_date") or item.get("entry_date") or item.get("signal_date"),
                "value": _jsonable_number(value) or 0.0,
                "count": len(pnls),
            }
        )
    return {
        "data_source": "signal_outcomes",
        "execution_mode": mode,
        "source_run_id": payload.get("source_run_id"),
        "computed_at": payload.get("computed_at"),
        "metric": metric,
        "granularity": granularity,
        "points": points,
    }


def performance_attribution(execution_mode: str | None = "live") -> dict[str, Any]:
    payload = read_latest_outcomes()
    mode = _normalize_execution_mode(execution_mode)
    evaluated = _evaluated_items(_outcome_items(payload, mode))

    def group(key: str) -> list[dict[str, Any]]:
        groups: dict[str, list[float]] = defaultdict(list)
        for item in evaluated:
            pnl = _pnl_value(item)
            if pnl is not None:
                groups[str(item.get(key) or "UNKNOWN")].append(pnl)
        return [
            {
                "name": name,
                "contribution": _jsonable_number(sum(values)) or 0.0,
                "count": len(values),
            }
            for name, values in sorted(groups.items())
        ]

    return {
        "data_source": "signal_outcomes",
        "execution_mode": mode,
        "source_run_id": payload.get("source_run_id"),
        "computed_at": payload.get("computed_at"),
        "by_template": group("signal_template"),
        "by_regime": group("regime_label"),
        "by_risk_level": group("risk_level"),
        "by_shock_window": [{"name": "not_classified", "contribution": 0.0, "count": len(evaluated)}],
    }


def list_signal_snapshots(limit: int = 50) -> dict[str, Any]:
    rows = []
    for item in read_signal_history(limit=limit):
        rows.append(
            {
                "run_id": item.get("source_run_id") or item.get("run_id"),
                "status": item.get("status"),
                "generated_at": item.get("generated_at"),
                "signal_date": item.get("signal_date"),
                "data_health": item.get("data_health"),
                "generated_count": item.get("generated_count"),
                "blocked_count": item.get("blocked_count"),
                "counts": item.get("counts"),
                "router_decision": item.get("router_decision") or item.get("router"),
                "regime_freshness": item.get("regime_freshness"),
                "snapshot_path": item.get("snapshot_path") or str(signal_center_root() / "latest_signals.json"),
                "data_source": item.get("data_source"),
            }
        )
    return {
        "items": rows,
        "total": len(rows),
        "latest": rows[0] if rows else None,
        "retention_count": int(os.getenv("FACTOR_PLATFORM_SIGNAL_SNAPSHOT_KEEP", "50")),
    }
