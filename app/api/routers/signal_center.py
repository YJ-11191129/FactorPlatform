from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.dependencies.auth import require_role
from app.services.regime_engine import (
    get_breakpoints_items,
    get_event_library,
    get_latest_regime_snapshot,
    get_regime_history_items,
    get_regime_snapshot_at,
    get_regime_timeline_items,
    refresh_regime_artifacts,
)
from app.services.signal_generation_service import (
    find_signal,
    generate_signal_snapshot,
    latest_router,
    public_signal,
    read_latest_signal_run,
    read_latest_signal_snapshot,
    read_signal_history,
)
from app.services.signal_outcome_service import (
    get_signal_outcome,
    list_signal_outcomes,
    list_signal_snapshots,
    performance_attribution,
    performance_summary,
    performance_timeseries,
    refresh_signal_outcomes,
)
from app.services.similar_period_engine import SimilarPeriodParams, persist_similar_outputs, run_similar_period_lookup

router = APIRouter(prefix="/api/v1", tags=["signal-center"])


def _dt(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def _regime_export_dir() -> Path:
    override = os.getenv("FACTOR_PLATFORM_REGIME_DIR")
    root = Path(override) if override else (Path(__file__).resolve().parents[3] / "data" / "exports" / "regime_engine")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_similar_period_outputs(recompute: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = _regime_export_dir()
    snapshot_path = root / "regime_snapshot_daily.parquet"
    lookup_path = root / "similar_period_lookup.parquet"
    profile_path = root / "current_state_profile.parquet"

    if recompute or (not snapshot_path.exists()):
        refresh_regime_artifacts()

    if recompute or (not lookup_path.exists()) or (not profile_path.exists()):
        params = SimilarPeriodParams(
            eps=float(os.getenv("FACTOR_PLATFORM_SIMILAR_DBSCAN_EPS", "1.5")),
            min_samples=int(os.getenv("FACTOR_PLATFORM_SIMILAR_DBSCAN_MIN_SAMPLES", "10")),
            topk=int(os.getenv("FACTOR_PLATFORM_SIMILAR_TOPK", "20")),
            lookback_exclude=int(os.getenv("FACTOR_PLATFORM_SIMILAR_LOOKBACK_EXCLUDE", "40")),
            sequence_window=int(os.getenv("FACTOR_PLATFORM_SIMILAR_SEQUENCE_WINDOW", "5")),
            pca_dim=int(os.getenv("FACTOR_PLATFORM_SIMILAR_PCA_DIM", "6")),
            model_version=os.getenv("FACTOR_PLATFORM_SIMILAR_MODEL_VERSION", "similar_period_dbscan_v1"),
        )
        lookup, profile = run_similar_period_lookup(str(snapshot_path), params)
        persist_similar_outputs(lookup, profile, str(root))
        return lookup, profile

    return pd.read_parquet(lookup_path), pd.read_parquet(profile_path)


SIGNALS: list[dict[str, Any]] = [
    {
        "signal_id": "sig_20260329_0001",
        "instrument": "510300.SH",
        "market": "CN",
        "asset_type": "ETF",
        "timeframe": "30m",
        "side": "LONG",
        "signal_time": "2026-03-29T10:00:00+08:00",
        "entry_type": "MARKET_ON_BAR_OPEN",
        "entry_price": 4.182,
        "stop_loss": 4.120,
        "take_profit": 4.315,
        "confidence": 0.81,
        "risk_level": "MEDIUM",
        "regime_label": "POST_SHOCK_REBOUND",
        "volatility_state": "HIGH_VOL",
        "tail_risk_state": "ELEVATED",
        "position_scale": 0.65,
        "reason_tags": ["post_shock_rebound", "liquidity_recovery_confirmed", "vrp_normalizing"],
        "status": "ACTIVE",
        "signal_template": "POST_SHOCK_REBOUND_LONG_V1",
        "expected_holding_bars": 8,
        "created_at": "2026-03-29T10:00:01+08:00",
        "updated_at": "2026-03-29T10:00:01+08:00",
    },
    {
        "signal_id": "sig_20260329_0002",
        "instrument": "510500.SH",
        "market": "CN",
        "asset_type": "ETF",
        "timeframe": "30m",
        "side": "SHORT",
        "signal_time": "2026-03-29T10:30:00+08:00",
        "entry_type": "LIMIT_NEAR_VWAP",
        "entry_price": 5.031,
        "stop_loss": 5.115,
        "take_profit": 4.902,
        "confidence": 0.74,
        "risk_level": "HIGH",
        "regime_label": "FRAGILE_HIGH_VOL",
        "volatility_state": "HIGH_VOL",
        "tail_risk_state": "STRESSED",
        "position_scale": 0.4,
        "reason_tags": ["dispersion_rising", "downside_semivol_spike", "breadth_deterioration"],
        "status": "ACTIVE",
        "signal_template": "FRAGILE_SHORT_DEFENSIVE_V1",
        "expected_holding_bars": 6,
        "created_at": "2026-03-29T10:30:01+08:00",
        "updated_at": "2026-03-29T10:30:01+08:00",
    },
    {
        "signal_id": "sig_20260329_0003",
        "instrument": "159915.SZ",
        "market": "CN",
        "asset_type": "ETF",
        "timeframe": "1D",
        "side": "LONG",
        "signal_time": "2026-03-29T11:00:00+08:00",
        "entry_type": "MARKET_ON_CLOSE",
        "entry_price": 1.876,
        "stop_loss": 1.821,
        "take_profit": 1.972,
        "confidence": 0.67,
        "risk_level": "MEDIUM",
        "regime_label": "TREND_RISK_ON",
        "volatility_state": "NORMAL_VOL",
        "tail_risk_state": "NORMAL",
        "position_scale": 0.72,
        "reason_tags": ["trend_strength_confirmed", "volume_expansion", "vrp_compressing"],
        "status": "MONITORED",
        "signal_template": "TREND_CONTINUATION_LONG_V2",
        "expected_holding_bars": 12,
        "created_at": "2026-03-29T11:00:01+08:00",
        "updated_at": "2026-03-29T11:00:01+08:00",
    },
    {
        "signal_id": "sig_20260329_0004",
        "instrument": "000300.SH",
        "market": "CN",
        "asset_type": "INDEX",
        "timeframe": "5m",
        "side": "NEUTRAL",
        "signal_time": "2026-03-29T11:15:00+08:00",
        "entry_type": "NO_TRADE",
        "entry_price": 0,
        "stop_loss": 0,
        "take_profit": 0,
        "confidence": 0.58,
        "risk_level": "BLOCKED",
        "regime_label": "LIQUIDITY_SHOCK",
        "volatility_state": "EXTREME_VOL",
        "tail_risk_state": "EXTREME",
        "position_scale": 0.0,
        "reason_tags": ["shock_window_active", "liquidity_too_tight", "router_blocked_template"],
        "status": "BLOCKED",
        "signal_template": "OBSERVE_ONLY_CRISIS_V1",
        "expected_holding_bars": 0,
        "created_at": "2026-03-29T11:15:01+08:00",
        "updated_at": "2026-03-29T11:15:01+08:00",
    },
]

HISTORY_SIGNALS: list[dict[str, Any]] = []
for idx in range(1, 61):
    base = SIGNALS[idx % len(SIGNALS)]
    signal_time = datetime(2026, 2, 1, 9, 30) + timedelta(days=idx)
    HISTORY_SIGNALS.append(
        {
            **base,
            "signal_id": f"hist_{idx:04d}",
            "signal_time": signal_time.isoformat() + "+08:00",
            "status": "CLOSED",
            "realized_pnl": round(((idx % 9) - 4) * 0.0045, 4),
            "holding_bars": (idx % 12) + 2,
        }
    )

SHOCK_EVENTS = [
    {
        "event_id": "shock_20250407_tariff",
        "event_date": "2025-04-07",
        "event_type": "POLICY_TARIFF_SHOCK",
        "severity": 0.91,
        "detected_regime": "LIQUIDITY_SHOCK",
        "status": "RECOVERY",
        "pre_window": {"from": -60, "to": -1},
        "impact_window": {"from": 0, "to": 5},
        "stress_window": {"from": 6, "to": 20},
        "recovery_window": {"from": 21, "to": 60},
        "state_summary": {
            "pre": "TREND_RISK_ON",
            "impact": "LIQUIDITY_SHOCK",
            "stress": "FRAGILE_HIGH_VOL",
            "recovery": "POST_SHOCK_REBOUND",
        },
    },
    {
        "event_id": "shock_20260312_liquidity",
        "event_date": "2026-03-12",
        "event_type": "LIQUIDITY_GAP",
        "severity": 0.72,
        "detected_regime": "FRAGILE_HIGH_VOL",
        "status": "STRESS",
        "pre_window": {"from": -40, "to": -1},
        "impact_window": {"from": 0, "to": 3},
        "stress_window": {"from": 4, "to": 18},
        "recovery_window": {"from": 19, "to": 50},
        "state_summary": {
            "pre": "CALM_LOW_VOL",
            "impact": "FRAGILE_HIGH_VOL",
            "stress": "LIQUIDITY_SHOCK",
            "recovery": "POST_SHOCK_REBOUND",
        },
    },
]

ROUTER_CURRENT = {
    "router_version": "router_v1",
    "current_regime": "FRAGILE_HIGH_VOL",
    "enabled_templates": ["DEFENSIVE_BREAKOUT_V1", "MEAN_REVERSION_LIGHT_V1"],
    "blocked_templates": ["AGGRESSIVE_TREND_LONG_V1"],
    "risk_scale": 0.42,
    "turnover_limit": 0.25,
    "threshold_profile": "fragile_high_vol_profile",
}

ROUTER_HISTORY = [
    {
        "changed_at": "2026-03-28T09:10:00+08:00",
        "changed_by": "admin",
        "regime": "FRAGILE_HIGH_VOL",
        "field": "risk_scale",
        "old_value": "0.55",
        "new_value": "0.42",
    },
    {
        "changed_at": "2026-03-27T15:42:00+08:00",
        "changed_by": "researcher_a",
        "regime": "LIQUIDITY_SHOCK",
        "field": "blocked_templates",
        "old_value": "[]",
        "new_value": "[AGGRESSIVE_TREND_LONG_V1]",
    },
]

NOTIFICATIONS = [
    {"time": "2026-03-29T10:31:00+08:00", "channel": "IN_APP", "title": "SHORT signal fired", "signal_id": "sig_20260329_0002"},
    {"time": "2026-03-29T10:01:00+08:00", "channel": "WEBSOCKET", "title": "LONG signal fired", "signal_id": "sig_20260329_0001"},
    {"time": "2026-03-29T09:58:00+08:00", "channel": "TELEGRAM", "title": "Regime changed to FRAGILE_HIGH_VOL", "signal_id": None},
]

REPLAY_STORE: dict[str, dict[str, str]] = {}


def _paginate(items: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    end = start + page_size
    sliced = items[start:end]
    return {
        "items": sliced,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "has_more": end < len(items),
    }


def _snapshot_metadata(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    run = read_latest_signal_run()
    source = snapshot or run or {}
    return {
        "status": source.get("status") or ("NO_SNAPSHOT" if snapshot is None else "UNKNOWN"),
        "message": source.get("message"),
        "generated_at": source.get("generated_at"),
        "signal_date": source.get("signal_date"),
        "data_source": source.get("data_source"),
        "data_health": source.get("data_health"),
        "source_run_id": source.get("source_run_id") or source.get("run_id"),
        "snapshot_path": source.get("snapshot_path"),
        "router_decision": source.get("router_decision") or source.get("router"),
        "counts": source.get("counts"),
        "regime_freshness": source.get("regime_freshness"),
    }


def _signals_from_snapshot(snapshot: dict[str, Any] | None, execution_mode: str = "live") -> list[dict[str, Any]]:
    if not snapshot:
        return []
    if execution_mode == "shadow":
        return [public_signal(item) for item in (snapshot.get("shadow_items") or [])]
    return [public_signal(item) for item in (snapshot.get("items") or snapshot.get("signals") or [])]


def _history_signals() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for snapshot in read_signal_history(limit=250):
        for signal in snapshot.get("items") or snapshot.get("signals") or []:
            row = public_signal(signal)
            row.setdefault("snapshot_generated_at", snapshot.get("generated_at"))
            out.append(row)
    return out


def _apply_signal_filters(items: list[dict[str, Any]], **filters: Any) -> list[dict[str, Any]]:
    out = items
    for key, value in filters.items():
        if hasattr(value, "default"):
            value = value.default
        if value is None:
            continue
        if key == "confidence_min":
            out = [i for i in out if i.get("confidence", 0) >= value]
            continue
        if key == "confidence_max":
            out = [i for i in out if i.get("confidence", 0) <= value]
            continue
        out = [i for i in out if str(i.get(key)) == str(value)]
    return out


@router.get("/signals/live")
def get_signals_live(
    market: str | None = None,
    asset_type: str | None = None,
    timeframe: str | None = None,
    side: str | None = None,
    regime_label: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    instrument: str | None = None,
    signal_template: str | None = None,
    confidence_min: float | None = Query(None, ge=0, le=1),
    confidence_max: float | None = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str = "signal_time",
    sort_order: str = "desc",
) -> dict[str, Any]:
    snapshot = read_latest_signal_snapshot()
    signals = _signals_from_snapshot(snapshot, "live")
    filtered = _apply_signal_filters(
        signals,
        market=market,
        asset_type=asset_type,
        timeframe=timeframe,
        side=side,
        regime_label=regime_label,
        risk_level=risk_level,
        status=status,
        instrument=instrument,
        signal_template=signal_template,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
    )
    reverse = sort_order == "desc"
    if sort_by in {"signal_time", "confidence", "entry_price", "score", "score_percentile"}:
        filtered = sorted(filtered, key=lambda x: x.get(sort_by, 0), reverse=reverse)
    out = _paginate(filtered, page, page_size)
    out.update(_snapshot_metadata(snapshot))
    out["execution_mode"] = "live"
    return out


@router.get("/signals/shadow")
def get_signals_shadow(
    market: str | None = None,
    asset_type: str | None = None,
    timeframe: str | None = None,
    side: str | None = None,
    regime_label: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    instrument: str | None = None,
    signal_template: str | None = None,
    confidence_min: float | None = Query(None, ge=0, le=1),
    confidence_max: float | None = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str = "signal_time",
    sort_order: str = "desc",
) -> dict[str, Any]:
    snapshot = read_latest_signal_snapshot()
    signals = _signals_from_snapshot(snapshot, "shadow")
    filtered = _apply_signal_filters(
        signals,
        market=market,
        asset_type=asset_type,
        timeframe=timeframe,
        side=side,
        regime_label=regime_label,
        risk_level=risk_level,
        status=status,
        instrument=instrument,
        signal_template=signal_template,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
    )
    reverse = sort_order == "desc"
    if sort_by in {"signal_time", "confidence", "entry_price", "score", "score_percentile"}:
        filtered = sorted(filtered, key=lambda x: x.get(sort_by, 0), reverse=reverse)
    out = _paginate(filtered, page, page_size)
    out.update(_snapshot_metadata(snapshot))
    out["execution_mode"] = "shadow"
    return out


@router.post("/signals/refresh", dependencies=[Depends(require_role("operator", "admin"))])
def refresh_signals(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload or {}
    try:
        return generate_signal_snapshot(
            provider_uri=body.get("provider_uri"),
            universe=body.get("universe"),
            topn=body.get("topn"),
            instrument_limit=body.get("instrument_limit"),
            dry_run=bool(body.get("dry_run", False)),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/signals/snapshots")
def get_signal_snapshots(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    return list_signal_snapshots(limit=limit)


@router.get("/signals/outcomes")
def get_signal_outcomes(
    signal_id: str | None = None,
    status: str | None = None,
    execution_mode: str = "live",
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    return list_signal_outcomes(signal_id=signal_id, status=status, execution_mode=execution_mode, limit=limit, offset=offset)


@router.post("/signals/outcomes/refresh", dependencies=[Depends(require_role("operator", "admin"))])
def refresh_signal_outcomes_endpoint(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload or {}
    try:
        return refresh_signal_outcomes(
            provider_uri=body.get("provider_uri"),
            universe=body.get("universe"),
            horizon_days=int(body.get("horizon_days") or 10),
            dry_run=bool(body.get("dry_run", False)),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/signals/outcomes/{signal_id}")
def get_signal_outcome_endpoint(signal_id: str, execution_mode: str = "live") -> dict[str, Any]:
    outcome = get_signal_outcome(signal_id, execution_mode=execution_mode)
    if outcome is None:
        raise HTTPException(status_code=404, detail="SIGNAL_OUTCOME_NOT_FOUND")
    return outcome


@router.get("/signals/by-id/{signal_id}")
def get_signal_detail(signal_id: str, execution_mode: str | None = None) -> dict[str, Any]:
    found = find_signal(signal_id, execution_mode=execution_mode)
    if found is None:
        raise HTTPException(status_code=404, detail="SIGNAL_NOT_FOUND")
    signal, snapshot = found
    public = public_signal(signal)

    regime_snapshot = snapshot.get("regime_snapshot") if isinstance(snapshot.get("regime_snapshot"), dict) else None
    if not regime_snapshot:
        regime_snapshot = get_regime_snapshot_at(_dt(public["signal_time"]))
    if not regime_snapshot:
        regime_snapshot = {
            "snapshot_time": public["signal_time"],
            "regime_label": public["regime_label"],
            "cpd_score": 0.0,
            "cluster_id": -1,
            "severity_score": 0.0,
            "volatility_state": public["volatility_state"],
            "liquidity_state": "UNKNOWN",
            "tail_risk_state": public["tail_risk_state"],
            "shock_proximity": "OUTSIDE_EVENT_WINDOW",
        }

    similar = [s for s in _history_signals() if s.get("signal_id") != signal_id][:6]
    signal_mode = str(public.get("execution_mode") or execution_mode or "live")
    outcome = get_signal_outcome(signal_id, execution_mode=signal_mode)
    if outcome:
        performance_tracking = {
            "status": outcome.get("outcome_status"),
            "unrealized_pnl": outcome.get("unrealized_pnl"),
            "realized_pnl": outcome.get("realized_pnl"),
            "mfe": outcome.get("mfe"),
            "mae": outcome.get("mae"),
            "bars_elapsed": outcome.get("holding_bars"),
            "entry_date": outcome.get("entry_date"),
            "last_date": outcome.get("last_date"),
            "source_run_id": outcome.get("source_run_id"),
            "execution_mode": outcome.get("execution_mode"),
        }
        outcome_status = outcome.get("outcome_status") or "UNKNOWN"
    else:
        performance_tracking = {
            "status": "PENDING_OUTCOME",
            "unrealized_pnl": None,
            "realized_pnl": None,
            "mfe": None,
            "mae": None,
            "bars_elapsed": 0,
            "entry_date": None,
            "last_date": None,
            "source_run_id": snapshot.get("source_run_id") or snapshot.get("run_id"),
            "execution_mode": signal_mode,
        }
        outcome_status = "PENDING_OUTCOME"
    return {
        "signal": public,
        "regime_snapshot": regime_snapshot,
        "factor_contributions": signal.get("_factor_contributions") or [],
        "filter_results": signal.get("_filter_results")
        or {
            "allow_signal": public["status"] in {"ACTIVE", "MONITORED", "NOTIFIED"},
            "risk_level": public["risk_level"],
            "filter_reasons": public.get("reason_tags") or [],
            "suppressed_alternatives": [],
        },
        "notification_logs": get_notification_logs()["items"],
        "outcome_status": outcome_status,
        "outcome": outcome,
        "performance_tracking": performance_tracking,
        "similar_signals": similar,
    }


@router.get("/signals/history")
def get_signal_history(
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    instrument: str | None = None,
    timeframe: str | None = None,
    signal_template: str | None = None,
    regime_label: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    side: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> dict[str, Any]:
    signals = _history_signals()
    filtered = _apply_signal_filters(
        signals,
        instrument=instrument,
        timeframe=timeframe,
        signal_template=signal_template,
        regime_label=regime_label,
        risk_level=risk_level,
        status=status,
        side=side,
    )

    if from_:
        start = _dt(from_)
        filtered = [i for i in filtered if _dt(i["signal_time"]) >= start]
    if to:
        end = _dt(to)
        filtered = [i for i in filtered if _dt(i["signal_time"]) <= end]

    filtered = sorted(filtered, key=lambda x: x["signal_time"], reverse=True)
    return _paginate(filtered, page, page_size)


@router.post("/signals/replay")
def create_signal_replay(payload: dict[str, Any]) -> dict[str, str]:
    raise HTTPException(status_code=501, detail="SIGNAL_REPLAY_NOT_IMPLEMENTED_FOR_REAL_OUTCOMES")


@router.get("/signals/replay/{replay_id}")
def get_signal_replay(replay_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=501, detail="SIGNAL_REPLAY_NOT_IMPLEMENTED_FOR_REAL_OUTCOMES")


@router.get("/signals/performance/summary")
def get_performance_summary(execution_mode: str = "live") -> dict[str, Any]:
    summary = performance_summary(execution_mode=execution_mode)
    return {"summary": summary, **summary}


@router.get("/signals/performance/timeseries")
def get_performance_timeseries(
    metric: str = "cum_pnl",
    granularity: str = "day",
    execution_mode: str = "live",
) -> dict[str, Any]:
    out = performance_timeseries(metric=metric, granularity=granularity, execution_mode=execution_mode)
    return {**out, "items": out.get("points", [])}


@router.get("/signals/performance/attribution")
def get_performance_attribution(execution_mode: str = "live") -> dict[str, Any]:
    out = performance_attribution(execution_mode=execution_mode)
    normalize = lambda rows: [{"label": row.get("name"), **row} for row in rows]
    return {
        **out,
        "by_regime": normalize(out.get("by_regime", [])),
        "by_template": normalize(out.get("by_template", [])),
        "by_risk_level": normalize(out.get("by_risk_level", [])),
        "by_shock_window": normalize(out.get("by_shock_window", [])),
    }


@router.get("/regime/current")
def get_regime_current() -> dict[str, Any]:
    try:
        out = get_latest_regime_snapshot()
    except Exception:
        now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        return {
            "snapshot_time": now,
            "regime_label": "UNKNOWN",
            "cpd_score": 0.0,
            "cluster_id": -1,
            "severity_score": 0.0,
            "volatility_state": "UNKNOWN",
            "liquidity_state": "UNKNOWN",
            "tail_risk_state": "UNKNOWN",
            "data_source": "unavailable",
        }
    if out:
        return out
    raise HTTPException(status_code=404, detail="REGIME_NOT_FOUND")


@router.get("/regime/history")
def get_regime_history(
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
) -> dict[str, Any]:
    start: date | None = None
    end: date | None = None
    if isinstance(from_, str) and from_:
        start = date.fromisoformat(from_)
    if isinstance(to, str) and to:
        end = date.fromisoformat(to)
    return {"items": get_regime_history_items(from_date=start, to_date=end)}


@router.get("/regime/timeline")
def get_regime_timeline(
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
) -> dict[str, Any]:
    start: date | None = None
    end: date | None = None
    if isinstance(from_, str) and from_:
        start = date.fromisoformat(from_)
    if isinstance(to, str) and to:
        end = date.fromisoformat(to)
    return {"items": get_regime_timeline_items(from_date=start, to_date=end)}


@router.get("/regime/breakpoints")
def get_regime_breakpoints() -> dict[str, Any]:
    return {"items": get_breakpoints_items()}


@router.post("/regime/recompute")
def recompute_regime() -> dict[str, Any]:
    snapshot, breakpoints = refresh_regime_artifacts()
    return {
        "status": "OK",
        "snapshot_rows": int(snapshot.shape[0]),
        "breakpoint_rows": int(breakpoints.shape[0]),
    }


@router.get("/regime/events")
def get_regime_events() -> dict[str, Any]:
    return get_event_library()


@router.get("/regime/similar-periods")
def get_regime_similar_periods(topk: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    lookup, _ = _ensure_similar_period_outputs(recompute=False)
    if lookup.empty:
        return {"items": []}
    out = lookup.sort_values("match_rank").head(topk).to_dict(orient="records")
    return {"items": out}


@router.get("/regime/current-state-profile")
def get_regime_current_state_profile() -> dict[str, Any]:
    _, profile = _ensure_similar_period_outputs(recompute=False)
    if profile.empty:
        raise HTTPException(status_code=404, detail="CURRENT_STATE_PROFILE_NOT_FOUND")
    return profile.iloc[0].to_dict()


@router.post("/regime/similar-periods/recompute")
def recompute_regime_similar_periods() -> dict[str, Any]:
    lookup, profile = _ensure_similar_period_outputs(recompute=True)
    return {
        "status": "OK",
        "lookup_rows": int(lookup.shape[0]),
        "profile_rows": int(profile.shape[0]),
        "asof_date": str(profile.iloc[0]["asof_date"]) if not profile.empty else None,
    }


@router.get("/shocks")
def get_shocks(
    event_type: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    severity_min: float | None = None,
) -> dict[str, Any]:
    items = SHOCK_EVENTS
    if event_type:
        items = [i for i in items if i["event_type"] == event_type]
    if severity_min is not None:
        items = [i for i in items if i["severity"] >= severity_min]
    if from_:
        items = [i for i in items if i["event_date"] >= from_]
    if to:
        items = [i for i in items if i["event_date"] <= to]
    return {"items": items}


@router.get("/shocks/{event_id}")
def get_shock_detail(event_id: str) -> dict[str, Any]:
    event = next((e for e in SHOCK_EVENTS if e["event_id"] == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail="SHOCK_NOT_FOUND")
    return event


@router.get("/shocks/{event_id}/replay")
def get_shock_replay(event_id: str) -> dict[str, Any]:
    _ = get_shock_detail(event_id)
    return {
        "event_id": event_id,
        "windows": {
            "pre": [{"date": "2025-03-21", "cum_pnl": 0.002}],
            "impact": [{"date": "2025-04-08", "cum_pnl": -0.018}],
            "stress": [{"date": "2025-04-16", "cum_pnl": -0.032}],
            "recovery": [{"date": "2025-05-15", "cum_pnl": 0.009}],
        },
        "metrics": {
            "vix_jump": 0.18,
            "vrp_change": 0.26,
            "illiq_change": 0.11,
            "breadth_change": -0.23,
        },
    }


@router.get("/strategy-router/current")
def get_strategy_router_current() -> dict[str, Any]:
    return latest_router()


@router.get("/strategy-router/history")
def get_strategy_router_history() -> dict[str, Any]:
    snapshot = read_latest_signal_snapshot()
    router = snapshot.get("router") if snapshot else None
    if not snapshot or not isinstance(router, dict):
        return {"items": []}
    return {
        "items": [
            {
                "changed_at": snapshot.get("generated_at"),
                "changed_by": "system",
                "regime": router.get("current_regime"),
                "field": "router_snapshot",
                "old_value": "n/a",
                "new_value": router.get("threshold_profile"),
            }
        ]
    }


@router.get("/notifications/logs")
def get_notification_logs() -> dict[str, Any]:
    run = read_latest_signal_run()
    if not run:
        return {"items": []}
    return {
        "items": [
            {
                "time": run.get("generated_at"),
                "channel": "SYSTEM",
                "title": f"Signal snapshot {run.get('status', 'UNKNOWN')}",
                "signal_id": None,
            }
        ]
    }


@router.get("/metadata/enums")
def get_metadata_enums() -> dict[str, Any]:
    return {
        "market": ["CN", "US", "Mixed"],
        "asset_type": ["ETF", "INDEX", "STOCK"],
        "timeframe": ["5m", "15m", "30m", "1D"],
        "side": ["LONG", "SHORT", "NEUTRAL"],
        "risk_level": ["LOW", "MEDIUM", "HIGH", "BLOCKED"],
        "regime_label": [
            "CALM_LOW_VOL",
            "NORMAL_VOL_STABLE",
            "TREND_RISK_ON",
            "FRAGILE_HIGH_VOL",
            "LIQUIDITY_SHOCK",
            "POST_SHOCK_REBOUND",
            "TRANSITION",
            "INFLATION_ENERGY_SHOCK",
            "UNKNOWN",
        ],
        "market_state": [
            "BULL_UPTREND",
            "BEAR_DOWNTREND",
            "RANGE_BOUND",
            "RANGE_BOUND_WEAK",
            "RELIEF_REBOUND",
            "RISK_OFF_DERISKING",
            "POST_GEO_SHOCK_REBOUND",
            "POLICY_RISK_ON",
            "BLOWOFF_EUPHORIA",
            "BULL_UPTREND_CORRECTION",
            "BEAR_MARKET_RALLY",
        ],
        "event_context": [
            "NONE",
            "PRIMARY_SHOCK_HIT",
            "PRIMARY_POLICY_REGIME_HIT",
            "SECONDARY_TRANSITION_HIT",
            "PRIMARY_SHOCK_WINDOW",
            "PRIMARY_POLICY_REGIME_WINDOW",
            "POST_SHOCK_WINDOW",
            "POST_POLICY_WINDOW",
            "PRIMARY_GEO_ENERGY_SHOCK_HIT",
            "SECONDARY_GEO_ENERGY_ESCALATION_HIT",
            "PERSISTENT_ENERGY_CRISIS_WINDOW_HIT",
            "GEO_ENERGY_CLUSTER_HIT",
        ],
        "trend_strength": ["WEAK", "MODERATE", "STRONG", "EXTREME"],
        "status": ["DRAFT", "FILTERED", "ACTIVE", "NOTIFIED", "MONITORED", "CLOSED", "BLOCKED", "INVALIDATED"],
        "signal_template": [
            "POST_SHOCK_REBOUND_LONG_V1",
            "FRAGILE_SHORT_DEFENSIVE_V1",
            "TREND_CONTINUATION_LONG_V2",
            "DEFENSIVE_BREAKOUT_V1",
            "MEAN_REVERSION_LIGHT_V1",
            "AGGRESSIVE_TREND_LONG_V1",
            "OBSERVE_ONLY_CRISIS_V1",
        ],
    }


@router.get("/metadata/instruments")
def get_metadata_instruments() -> dict[str, Any]:
    return {
        "items": [
            {"instrument": "510300.SH", "name": "300ETF", "market": "CN", "asset_type": "ETF"},
            {"instrument": "510500.SH", "name": "500ETF", "market": "CN", "asset_type": "ETF"},
            {"instrument": "159915.SZ", "name": "CYB ETF", "market": "CN", "asset_type": "ETF"},
            {"instrument": "000300.SH", "name": "CSI300", "market": "CN", "asset_type": "INDEX"},
        ]
    }


@router.get("/metadata/signal-templates")
def get_metadata_signal_templates() -> dict[str, Any]:
    return {
        "items": [
            {"template": "POST_SHOCK_REBOUND_LONG_V1", "description": "Post-shock rebound long signal"},
            {"template": "FRAGILE_SHORT_DEFENSIVE_V1", "description": "Defensive short in fragile regime"},
            {"template": "TREND_CONTINUATION_LONG_V2", "description": "Trend continuation long signal"},
            {"template": "DEFENSIVE_BREAKOUT_V1", "description": "Defensive breakout signal"},
            {"template": "OBSERVE_ONLY_CRISIS_V1", "description": "Observe-only signal when regime or data risk blocks trading"},
        ]
    }
