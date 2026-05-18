from __future__ import annotations

import json
import math
import os
import secrets
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from app.datahub.loaders.qlib_bin import read_calendar
from app.services.data_maintenance_service import evaluate_stock_radar_data_gate
from app.services.regime_engine import get_latest_regime_snapshot
from app.services.stock_radar_service import DEFAULT_QLIB_PROVIDER_URI, run_stock_radar


DEFAULT_SIGNAL_FACTORS: list[dict[str, Any]] = [
    {"factor_name": "QLIB_ALPHA_ROC20_V1", "params": {}, "weight": 0.45, "direction": "positive"},
    {"factor_name": "QLIB_ALPHA_RSV20_V1", "params": {}, "weight": 0.30, "direction": "positive"},
    {"factor_name": "QLIB_ALPHA_STD20_V1", "params": {}, "weight": 0.25, "direction": "negative"},
]

ROUTER_VERSION = "router_v1_real_regime"
CONSERVATIVE_TEMPLATE = "MEAN_REVERSION_LIGHT_V1"
CRISIS_TEMPLATE = "OBSERVE_ONLY_CRISIS_V1"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def signal_center_root() -> Path:
    root = Path(os.getenv("FACTOR_PLATFORM_SIGNAL_CENTER_DIR", str(_project_root() / "data" / "exports" / "signal_center")))
    return root


def _latest_signals_path() -> Path:
    return signal_center_root() / "latest_signals.json"


def _latest_run_path() -> Path:
    return signal_center_root() / "latest_run.json"


def _history_path() -> Path:
    return signal_center_root() / "history.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _signal_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"signal_{ts}_{secrets.token_hex(3)}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _append_history(payload: Mapping[str, Any]) -> None:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_jsonable(dict(payload)), ensure_ascii=False) + "\n")
    _compact_history(path)


def _snapshot_retention_count() -> int:
    raw = os.getenv("FACTOR_PLATFORM_SIGNAL_SNAPSHOT_KEEP", "50")
    try:
        return max(1, int(raw))
    except Exception:
        return 50


def _compact_history(path: Path) -> None:
    keep = _snapshot_retention_count()
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return
    if len(lines) <= keep:
        return
    path.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")


def _configured_provider_uri() -> str:
    return os.getenv("FACTOR_PLATFORM_PROVIDER_URI", DEFAULT_QLIB_PROVIDER_URI)


def _configured_universe() -> str:
    return os.getenv("FACTOR_PLATFORM_SIGNAL_UNIVERSE", "csi300")


def _configured_topn() -> int:
    raw = os.getenv("FACTOR_PLATFORM_SIGNAL_TOPN", "30")
    try:
        return max(1, int(raw))
    except Exception:
        return 30


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _market_from_context(provider_uri: str, universe: str) -> str:
    text = f"{provider_uri} {universe}".lower()
    if "us_data" in text or universe.lower() in {"sp500", "nasdaq100"}:
        return "US"
    return "CN"


@contextmanager
def _regime_env(provider_uri: str | None, universe: str | None):
    old_provider = os.environ.get("FACTOR_PLATFORM_PROVIDER_URI")
    old_universe = os.environ.get("FACTOR_PLATFORM_REGIME_UNIVERSE")
    if provider_uri:
        os.environ["FACTOR_PLATFORM_PROVIDER_URI"] = str(provider_uri)
    if universe:
        os.environ["FACTOR_PLATFORM_REGIME_UNIVERSE"] = str(universe)
    try:
        try:
            from app.services import regime_engine

            regime_engine.get_regime_artifacts.cache_clear()
        except Exception:
            pass
        yield
    finally:
        if old_provider is None:
            os.environ.pop("FACTOR_PLATFORM_PROVIDER_URI", None)
        else:
            os.environ["FACTOR_PLATFORM_PROVIDER_URI"] = old_provider
        if old_universe is None:
            os.environ.pop("FACTOR_PLATFORM_REGIME_UNIVERSE", None)
        else:
            os.environ["FACTOR_PLATFORM_REGIME_UNIVERSE"] = old_universe
        try:
            from app.services import regime_engine

            regime_engine.get_regime_artifacts.cache_clear()
        except Exception:
            pass


def _base_regime_snapshot(provider_uri: str | None = None, universe: str | None = None) -> dict[str, Any]:
    try:
        if provider_uri or universe:
            with _regime_env(provider_uri, universe):
                snapshot = get_latest_regime_snapshot()
        else:
            snapshot = get_latest_regime_snapshot()
        if snapshot:
            return dict(snapshot)
    except Exception:
        pass
    now = _now_iso()
    return {
        "snapshot_time": now,
        "regime_label": "UNKNOWN",
        "cpd_score": 0.0,
        "cluster_id": -1,
        "severity_score": 0.0,
        "volatility_state": "UNKNOWN",
        "liquidity_state": "UNKNOWN",
        "tail_risk_state": "UNKNOWN",
        "market_risk_level": "UNKNOWN",
        "data_source": "unavailable",
        "provider_uri": provider_uri,
        "universe": universe,
    }


def _trading_lag_days(provider_uri: str, regime_date: date | None, signal_date: date | None) -> int | None:
    if regime_date is None or signal_date is None:
        return None
    if regime_date >= signal_date:
        return 0
    try:
        calendar = read_calendar(provider_uri)
        dates = sorted(calendar.date)
        return sum(1 for d in dates if regime_date < d <= signal_date)
    except Exception:
        return max(0, (signal_date - regime_date).days)


def _regime_freshness(
    *,
    regime_snapshot: Mapping[str, Any],
    provider_uri: str,
    universe: str,
    signal_date: Any,
) -> dict[str, Any]:
    regime_date = _parse_date(regime_snapshot.get("date")) or _parse_date(regime_snapshot.get("snapshot_time"))
    parsed_signal_date = _parse_date(signal_date)
    lag = _trading_lag_days(provider_uri, regime_date, parsed_signal_date)
    if regime_date is None:
        status = "STALE_BLOCKED"
        block_reason = "REGIME_DATE_MISSING_BLOCKED"
    elif lag is None:
        status = "UNKNOWN"
        block_reason = None
    elif lag > 1:
        status = "STALE_BLOCKED"
        block_reason = "REGIME_STALE_BLOCKED"
    else:
        status = "OK"
        block_reason = None
    return {
        "regime_date": regime_date.isoformat() if regime_date else None,
        "signal_date": parsed_signal_date.isoformat() if parsed_signal_date else None,
        "provider_uri": provider_uri,
        "universe": universe,
        "freshness_lag_days": lag,
        "status": status,
        "is_stale": status == "STALE_BLOCKED",
        "block_reason": block_reason,
    }


def build_strategy_router(regime_snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snapshot = dict(regime_snapshot or _base_regime_snapshot())
    regime = str(snapshot.get("regime_label") or "UNKNOWN")
    volatility = str(snapshot.get("volatility_state") or "UNKNOWN")
    tail_risk = str(snapshot.get("tail_risk_state") or "UNKNOWN")
    market_risk = str(snapshot.get("market_risk_level") or "UNKNOWN")

    enabled = [CONSERVATIVE_TEMPLATE]
    blocked = ["AGGRESSIVE_TREND_LONG_V1"]
    risk_scale = 0.25
    profile = "unknown_conservative_profile"
    block_reason = None

    extreme_markers = {regime, volatility, tail_risk, market_risk}
    if "LIQUIDITY_SHOCK" in extreme_markers or "EXTREME" in extreme_markers or market_risk == "BLOCKED":
        enabled = [CRISIS_TEMPLATE]
        blocked = ["AGGRESSIVE_TREND_LONG_V1", "TREND_CONTINUATION_LONG_V2", "POST_SHOCK_REBOUND_LONG_V1"]
        risk_scale = 0.0
        profile = "liquidity_shock_observe_only_profile"
        block_reason = "LIQUIDITY_SHOCK_BLOCKED" if "LIQUIDITY_SHOCK" in extreme_markers else "EXTREME_RISK_BLOCKED"
    elif regime == "FRAGILE_HIGH_VOL":
        enabled = ["DEFENSIVE_BREAKOUT_V1", CONSERVATIVE_TEMPLATE]
        blocked = ["AGGRESSIVE_TREND_LONG_V1"]
        risk_scale = 0.4
        profile = "fragile_high_vol_defensive_profile"
    elif regime == "POST_SHOCK_REBOUND":
        enabled = ["POST_SHOCK_REBOUND_LONG_V1", CONSERVATIVE_TEMPLATE]
        blocked = ["AGGRESSIVE_TREND_LONG_V1"]
        risk_scale = 0.7
        profile = "post_shock_rebound_profile"
    elif regime in {"TREND_RISK_ON", "NORMAL_VOL_STABLE"} or str(snapshot.get("market_state") or "").startswith("BULL"):
        enabled = ["TREND_CONTINUATION_LONG_V2", "AGGRESSIVE_TREND_LONG_V1"]
        blocked = []
        risk_scale = 1.0
        profile = "trend_risk_on_profile"

    return {
        "router_version": ROUTER_VERSION,
        "source": "regime_snapshot",
        "current_regime": regime,
        "regime_snapshot_time": snapshot.get("snapshot_time"),
        "enabled_templates": enabled,
        "blocked_templates": blocked,
        "risk_scale": risk_scale,
        "turnover_limit": 0.25 if risk_scale > 0 else 0.0,
        "threshold_profile": profile,
        "block_reason": block_reason,
        "is_live_blocked": risk_scale <= 0,
    }


def _apply_regime_freshness_to_router(router: Mapping[str, Any], freshness: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(router)
    if not freshness.get("is_stale"):
        return out
    blocked_templates = list(out.get("blocked_templates") or [])
    for template in ["AGGRESSIVE_TREND_LONG_V1", "TREND_CONTINUATION_LONG_V2", "POST_SHOCK_REBOUND_LONG_V1"]:
        if template not in blocked_templates:
            blocked_templates.append(template)
    out.update(
        {
            "enabled_templates": [CRISIS_TEMPLATE],
            "blocked_templates": blocked_templates,
            "risk_scale": 0.0,
            "turnover_limit": 0.0,
            "threshold_profile": "regime_stale_observe_only_profile",
            "block_reason": freshness.get("block_reason") or "REGIME_STALE_BLOCKED",
            "is_live_blocked": True,
            "regime_freshness": dict(freshness),
        }
    )
    return out


def _risk_level(confidence: float, risk_scale: float) -> str:
    if risk_scale <= 0:
        return "BLOCKED"
    if risk_scale < 0.5 or confidence < 0.62:
        return "HIGH"
    if confidence >= 0.8 and risk_scale >= 0.7:
        return "LOW"
    return "MEDIUM"


def _factor_contributions(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_values = dict(item.get("factor_values") or {})
    scores = dict(item.get("factor_scores") or {})
    out: list[dict[str, Any]] = []
    for contrib in item.get("top_factor_contributors") or []:
        key = str(contrib.get("key") or "")
        if not key:
            continue
        out.append(
            {
                "factor": key,
                "raw_value": raw_values.get(key),
                "zscore": scores.get(key),
                "contribution": contrib.get("contribution"),
                "direction": "positive" if _safe_float(contrib.get("contribution")) >= 0 else "negative",
            }
        )
    return out


def _shadow_template(router: Mapping[str, Any]) -> str:
    blocked = [str(x) for x in (router.get("blocked_templates") or [])]
    for preferred in ["TREND_CONTINUATION_LONG_V2", "POST_SHOCK_REBOUND_LONG_V1", "AGGRESSIVE_TREND_LONG_V1"]:
        if preferred in blocked:
            return preferred
    return blocked[0] if blocked else str((router.get("enabled_templates") or [CONSERVATIVE_TEMPLATE])[0])


def _signal_from_radar_item(
    *,
    item: Mapping[str, Any],
    radar: Mapping[str, Any],
    regime_snapshot: Mapping[str, Any],
    router: Mapping[str, Any],
    provider_uri: str,
    universe: str,
    generated_at: str,
    data_health: Mapping[str, Any],
    execution_mode: str = "live",
) -> dict[str, Any]:
    rank = int(item.get("rank") or 0)
    score_percentile = _safe_float(item.get("score_percentile"), default=0.5)
    confidence = _clamp(0.45 + 0.5 * score_percentile, 0.45, 0.95)
    risk_scale = _safe_float(router.get("risk_scale"), default=0.25)
    blocked = risk_scale <= 0
    is_shadow = execution_mode == "shadow"
    close = _safe_float(item.get("close"), default=0.0)
    signal_date = str(radar.get("signal_date") or item.get("trade_date") or "")
    signal_id = f"sig_{signal_date.replace('-', '')}_{rank:04d}"
    template = _shadow_template(router) if is_shadow else str((router.get("enabled_templates") or [CONSERVATIVE_TEMPLATE])[0])
    proposed_position_scale = round(_clamp(0.45 + score_percentile * 0.55, 0.05, 1.0), 4)
    position_scale = proposed_position_scale if is_shadow else (0.0 if blocked else round(_clamp(risk_scale * proposed_position_scale, 0.05, 1.0), 4))
    risk_level = _risk_level(confidence, risk_scale)
    status = "BLOCKED" if blocked else "ACTIVE"
    freshness_note = None
    if data_health.get("blocking_status") == "WARN":
        freshness_note = str(data_health.get("message") or data_health.get("reason") or "data freshness warning")
    if router.get("block_reason") == "REGIME_STALE_BLOCKED":
        lag = ((router.get("regime_freshness") or {}).get("freshness_lag_days"))
        freshness_note = f"Regime snapshot is stale by {lag} trading day(s); live execution is blocked."

    reason_tags = [
        "stock_radar_candidate",
        f"regime_{str(regime_snapshot.get('regime_label') or 'UNKNOWN').lower()}",
        f"router_{str(router.get('threshold_profile') or 'unknown')}",
    ]
    if freshness_note:
        reason_tags.append("data_freshness_warn")
    if blocked:
        reason_tags.append("router_blocked_template")
    if is_shadow:
        reason_tags.extend(["shadow_candidate", "not_executable"])
    if router.get("block_reason"):
        reason_tags.append(str(router.get("block_reason")).lower())

    factor_contribs = _factor_contributions(item)
    return {
        "signal_id": signal_id,
        "execution_mode": execution_mode,
        "not_executable": bool(is_shadow),
        "instrument": str(item.get("asset_code") or ""),
        "market": _market_from_context(provider_uri, universe),
        "asset_type": "STOCK",
        "timeframe": "1D",
        "side": "LONG" if is_shadow else ("NEUTRAL" if blocked else "LONG"),
        "signal_time": generated_at,
        "entry_type": "NEXT_TRADING_DAY_OPEN" if is_shadow else ("NO_TRADE" if blocked else "NEXT_TRADING_DAY_OPEN"),
        "entry_price": close if is_shadow else (0.0 if blocked else close),
        "stop_loss": round(close * 0.95, 6) if is_shadow else (0.0 if blocked else round(close * 0.95, 6)),
        "take_profit": round(close * 1.10, 6) if is_shadow else (0.0 if blocked else round(close * 1.10, 6)),
        "confidence": round(confidence, 4),
        "risk_level": risk_level,
        "regime_label": str(regime_snapshot.get("regime_label") or "UNKNOWN"),
        "volatility_state": str(regime_snapshot.get("volatility_state") or "UNKNOWN"),
        "tail_risk_state": str(regime_snapshot.get("tail_risk_state") or "UNKNOWN"),
        "position_scale": position_scale,
        "proposed_position_scale": proposed_position_scale,
        "router_risk_scale": risk_scale,
        "router_block_reason": router.get("block_reason"),
        "router_threshold_profile": router.get("threshold_profile"),
        "reason_tags": reason_tags,
        "status": status,
        "signal_template": template,
        "expected_holding_bars": 10 if is_shadow else (0 if blocked else 10),
        "created_at": generated_at,
        "updated_at": generated_at,
        "score": item.get("score"),
        "score_percentile": item.get("score_percentile"),
        "effective_trade_date": radar.get("effective_trade_date"),
        "freshness_note": freshness_note,
        "_factor_contributions": factor_contribs,
        "_filter_results": {
            "allow_signal": False if is_shadow else status in {"ACTIVE", "MONITORED", "NOTIFIED"},
            "risk_level": risk_level,
            "filter_reasons": reason_tags,
            "suppressed_alternatives": list(router.get("blocked_templates") or []),
        },
    }


def _write_snapshot(snapshot: Mapping[str, Any]) -> None:
    summary = {
        "run_id": snapshot.get("source_run_id"),
        "status": snapshot.get("status"),
        "generated_at": snapshot.get("generated_at"),
        "signal_date": snapshot.get("signal_date"),
        "generated_count": snapshot.get("generated_count"),
        "blocked_count": snapshot.get("blocked_count"),
        "counts": snapshot.get("counts"),
        "data_health": snapshot.get("data_health"),
        "regime_freshness": snapshot.get("regime_freshness"),
        "router_decision": snapshot.get("router_decision") or snapshot.get("router"),
        "snapshot_path": str(_latest_signals_path()),
    }
    _write_json(_latest_signals_path(), snapshot)
    _write_json(_latest_run_path(), summary)
    _append_history(snapshot)
    try:
        from app.services.research_ops_registry import register_signal_snapshot

        register_signal_snapshot(snapshot)
    except Exception:
        pass


def generate_signal_snapshot(
    *,
    provider_uri: str | None = None,
    universe: str | None = None,
    topn: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    provider = provider_uri or _configured_provider_uri()
    signal_universe = universe or _configured_universe()
    signal_topn = topn or _configured_topn()
    generated_at = _now_iso()
    run_id = _signal_run_id()
    data_health = evaluate_stock_radar_data_gate(provider)
    config = {
        "provider_uri": provider,
        "universe": signal_universe,
        "topn": signal_topn,
        "factors": DEFAULT_SIGNAL_FACTORS,
    }

    if dry_run:
        return {
            "status": "DRY_RUN",
            "generated_at": generated_at,
            "generated_count": 0,
            "blocked_count": 0,
            "counts": {"live_active_count": 0, "router_blocked_count": 0, "shadow_count": 0},
            "data_health": data_health,
            "config": config,
            "snapshot_path": str(_latest_signals_path()),
        }

    if data_health.get("blocking_status") == "BLOCKED":
        snapshot = {
            "status": "BLOCKED",
            "message": data_health.get("message") or "data freshness gate blocked Signal Center snapshot generation",
            "generated_at": generated_at,
            "signal_date": None,
            "data_source": {"provider_uri": provider, "universe": signal_universe},
            "data_health": data_health,
            "source_run_id": run_id,
            "generated_count": 0,
            "blocked_count": 0,
            "counts": {"live_active_count": 0, "router_blocked_count": 0, "shadow_count": 0},
            "items": [],
            "signals": [],
            "shadow_items": [],
            "config": config,
            "snapshot_path": str(_latest_signals_path()),
        }
        _write_snapshot(snapshot)
        return snapshot

    radar = run_stock_radar(
        provider_uri=provider,
        universe=signal_universe,
        factors=DEFAULT_SIGNAL_FACTORS,
        instrument_limit=None,
        topn=signal_topn,
        min_factor_count=1,
    )
    regime_snapshot = _base_regime_snapshot(provider, signal_universe)
    regime_snapshot["provider_uri"] = provider
    regime_snapshot["universe"] = signal_universe
    freshness = _regime_freshness(
        regime_snapshot=regime_snapshot,
        provider_uri=provider,
        universe=signal_universe,
        signal_date=radar.get("signal_date"),
    )
    regime_snapshot["regime_freshness"] = freshness
    router = _apply_regime_freshness_to_router(build_strategy_router(regime_snapshot), freshness)
    signals = [
        _signal_from_radar_item(
            item=item,
            radar=radar,
            regime_snapshot=regime_snapshot,
            router=router,
            provider_uri=provider,
            universe=signal_universe,
            generated_at=generated_at,
            data_health=data_health,
            execution_mode="live",
        )
        for item in radar.get("items", [])
    ]
    shadow_signals = [
        _signal_from_radar_item(
            item=item,
            radar=radar,
            regime_snapshot=regime_snapshot,
            router=router,
            provider_uri=provider,
            universe=signal_universe,
            generated_at=generated_at,
            data_health=data_health,
            execution_mode="shadow",
        )
        for item, live in zip(radar.get("items", []), signals)
        if live.get("status") == "BLOCKED"
    ]
    blocked_count = sum(1 for item in signals if item.get("status") == "BLOCKED")
    live_active_count = sum(1 for item in signals if item.get("status") == "ACTIVE")
    status = "WARN" if data_health.get("blocking_status") == "WARN" else "OK"
    snapshot = {
        "status": status,
        "generated_at": generated_at,
        "signal_date": radar.get("signal_date"),
        "effective_trade_date": radar.get("effective_trade_date"),
        "data_source": {"provider_uri": provider, "universe": signal_universe},
        "data_health": data_health,
        "source_run_id": run_id,
        "regime_snapshot": regime_snapshot,
        "router": router,
        "router_decision": router,
        "regime_freshness": freshness,
        "generated_count": len(signals),
        "blocked_count": blocked_count,
        "counts": {
            "live_active_count": live_active_count,
            "router_blocked_count": blocked_count,
            "shadow_count": len(shadow_signals),
        },
        "items": signals,
        "signals": signals,
        "shadow_items": shadow_signals,
        "config": config,
        "snapshot_path": str(_latest_signals_path()),
    }
    _write_snapshot(snapshot)
    return snapshot


def read_latest_signal_snapshot() -> dict[str, Any] | None:
    return _read_json(_latest_signals_path())


def read_latest_signal_run() -> dict[str, Any] | None:
    return _read_json(_latest_run_path())


def read_signal_history(limit: int = 100) -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in reversed(lines[-max(limit, 1) :]):
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def public_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in signal.items() if not str(k).startswith("_")}


def latest_router() -> dict[str, Any]:
    snapshot = read_latest_signal_snapshot()
    if snapshot and isinstance(snapshot.get("router_decision"), dict):
        return dict(snapshot["router_decision"])
    if snapshot and isinstance(snapshot.get("router"), dict):
        router = dict(snapshot["router"])
        if isinstance(snapshot.get("regime_freshness"), dict):
            router.setdefault("regime_freshness", snapshot.get("regime_freshness"))
        return router
    return build_strategy_router(_base_regime_snapshot())


def find_signal(signal_id: str, execution_mode: str | None = None) -> tuple[dict[str, Any], dict[str, Any]] | None:
    modes = [execution_mode] if execution_mode in {"live", "shadow"} else ["live", "shadow"]

    def _iter_signals(snapshot: Mapping[str, Any], mode: str):
        key = "shadow_items" if mode == "shadow" else "items"
        for row in snapshot.get(key) or ([] if key == "shadow_items" else snapshot.get("signals") or []):
            yield row

    snapshot = read_latest_signal_snapshot()
    if snapshot:
        for mode in modes:
            for signal in _iter_signals(snapshot, mode):
                if signal.get("signal_id") == signal_id:
                    out = dict(signal)
                    out.setdefault("execution_mode", mode)
                    return out, snapshot
    for hist in read_signal_history(limit=500):
        for mode in modes:
            for signal in _iter_signals(hist, mode):
                if signal.get("signal_id") == signal_id:
                    out = dict(signal)
                    out.setdefault("execution_mode", mode)
                    return out, hist
    return None
