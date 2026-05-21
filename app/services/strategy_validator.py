from __future__ import annotations

import re
from typing import Any

from app.api.schemas.strategy_ai import StrategySpec, StrategyValidationIssue, StrategyValidationResult


SUPPORTED_INDICATORS = {
    "sma",
    "ema",
    "momentum",
    "volatility",
    "atr",
    "rsi",
}
SUPPORTED_TIMEFRAMES = {"1d", "daily"}
SUPPORTED_DIRECTIONS = {"long_only"}
SUPPORTED_RULE_OPERATORS = {">", ">=", "<", "<=", "==", "!="}
BASE_COLUMNS = {"open", "high", "low", "close", "volume"}
LOOKAHEAD_PATTERNS = (
    "future",
    "forward_ret",
    "next_close",
    "tomorrow",
    "lead(",
    "shift(-",
    "t+1",
)
RULE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|==|!=)\s*([A-Za-z_][A-Za-z0-9_]*|-?\d+(?:\.\d+)?)\s*$")


def indicator_alias(indicator: Any) -> str:
    typ = str(getattr(indicator, "type", "") or "").strip().lower()
    explicit = str(getattr(indicator, "name", "") or "").strip()
    if explicit:
        return _safe_identifier(explicit)
    window = getattr(indicator, "window", None)
    if window:
        return _safe_identifier(f"{typ}_{int(window)}")
    fast = getattr(indicator, "fast_window", None)
    slow = getattr(indicator, "slow_window", None)
    if fast and slow:
        return _safe_identifier(f"{typ}_{int(fast)}_{int(slow)}")
    return _safe_identifier(typ or "indicator")


def _safe_identifier(raw: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip())
    ident = re.sub(r"_+", "_", ident).strip("_").lower()
    if not ident:
        return "indicator"
    if ident[0].isdigit():
        ident = f"i_{ident}"
    return ident


def _issue(severity: str, code: str, message: str, field: str | None = None) -> StrategyValidationIssue:
    return StrategyValidationIssue(severity=severity, code=code, message=message, field=field)


def validate_strategy_spec(spec: StrategySpec) -> StrategyValidationResult:
    normalized = _normalize_spec(spec)
    issues: list[StrategyValidationIssue] = []

    if not normalized.name.strip():
        issues.append(_issue("error", "missing_name", "Strategy name is required.", "name"))
    if not normalized.universe:
        issues.append(_issue("warning", "missing_universe", "Universe is empty; backtest will use all available assets.", "universe"))
    if normalized.timeframe.lower() not in SUPPORTED_TIMEFRAMES:
        issues.append(_issue("error", "unsupported_timeframe", "Only daily timeframe is supported in the MVP.", "timeframe"))
    if normalized.direction.lower() not in SUPPORTED_DIRECTIONS:
        issues.append(_issue("error", "unsupported_direction", "MVP strategy executor supports long_only strategies only.", "direction"))
    if not normalized.indicators:
        issues.append(_issue("error", "missing_indicators", "At least one supported indicator is required.", "indicators"))
    if not normalized.entry_rules:
        issues.append(_issue("error", "missing_entry_rules", "At least one entry rule is required.", "entry_rules"))

    known_fields = set(BASE_COLUMNS)
    aliases: set[str] = set()
    for i, indicator in enumerate(normalized.indicators):
        typ = indicator.type.strip().lower()
        alias = indicator_alias(indicator)
        aliases.add(alias)
        known_fields.add(alias)
        if typ not in SUPPORTED_INDICATORS:
            issues.append(_issue("error", "unsupported_indicator", f"Unsupported indicator type: {indicator.type}", f"indicators.{i}.type"))
        if typ in {"sma", "ema", "momentum", "volatility", "atr", "rsi"} and not indicator.window:
            issues.append(_issue("error", "missing_indicator_window", f"{typ} requires a positive window.", f"indicators.{i}.window"))
        if indicator.window is not None and int(indicator.window) <= 0:
            issues.append(_issue("error", "invalid_indicator_window", "Indicator window must be positive.", f"indicators.{i}.window"))

    if len(aliases) != len(normalized.indicators):
        issues.append(_issue("error", "duplicate_indicator_alias", "Indicator names must be unique.", "indicators"))

    for field, rules in [("entry_rules", normalized.entry_rules), ("exit_rules", normalized.exit_rules)]:
        for idx, rule in enumerate(rules):
            lower = rule.lower()
            if any(p in lower for p in LOOKAHEAD_PATTERNS):
                issues.append(_issue("error", "lookahead_rule", "Rule appears to reference future information.", f"{field}.{idx}"))
                continue
            match = RULE_RE.match(rule)
            if not match:
                issues.append(_issue("error", "unsupported_rule", f"Unsupported rule syntax: {rule}", f"{field}.{idx}"))
                continue
            lhs, op, rhs = match.group(1), match.group(2), match.group(3)
            if op not in SUPPORTED_RULE_OPERATORS:
                issues.append(_issue("error", "unsupported_operator", f"Unsupported operator: {op}", f"{field}.{idx}"))
            if lhs not in known_fields:
                issues.append(_issue("error", "unknown_rule_field", f"Unknown left-side field: {lhs}", f"{field}.{idx}"))
            if not _is_number(rhs) and rhs not in known_fields:
                issues.append(_issue("error", "unknown_rule_field", f"Unknown right-side field: {rhs}", f"{field}.{idx}"))

    if normalized.ranking and normalized.ranking not in known_fields:
        issues.append(
            _issue(
                "warning",
                "unknown_ranking",
                f"Unknown ranking field: {normalized.ranking}; executor will fall back to equal-weight screening.",
                "ranking",
            )
        )
        normalized.ranking = None

    if normalized.risk.stop_loss:
        issues.append(
            _issue(
                "warning",
                "stop_loss_not_simulated",
                "Stop-loss discipline is recorded in metadata but not yet simulated intraday in the MVP executor.",
                "risk.stop_loss",
            )
        )
    if normalized.execution.signal_time != "close_t":
        issues.append(_issue("warning", "nonstandard_signal_time", "MVP assumes signals are formed after close_t.", "execution.signal_time"))
    if normalized.execution.trade_time not in {"next_bar", "next_open"}:
        issues.append(_issue("warning", "nonstandard_trade_time", "MVP applies positions with a one-bar delay.", "execution.trade_time"))

    is_valid = not any(x.severity == "error" for x in issues)
    return StrategyValidationResult(
        is_valid=is_valid,
        issues=issues,
        normalized_spec=normalized,
        timing_assumptions=[
            "Indicators are observed at close_t.",
            "Signals are formed after close_t.",
            "Positions affect returns from the next available bar through the backtest engine shift.",
            "No model output is executed as arbitrary code.",
        ],
        supported_features=[
            "daily long-only equal-weight screening",
            "sma/ema/momentum/volatility/atr/rsi indicators",
            "simple comparison rules: field > value, field < other_field",
            "optional ranking with max_positions",
        ],
    )


def _normalize_spec(spec: StrategySpec) -> StrategySpec:
    data = spec.model_dump()
    data["timeframe"] = str(data.get("timeframe") or "1d").lower()
    data["direction"] = str(data.get("direction") or "long_only").lower()
    data["universe"] = [str(x).strip() for x in data.get("universe") or [] if str(x).strip()]
    for indicator in data.get("indicators") or []:
        indicator["type"] = str(indicator.get("type") or "").strip().lower()
        indicator["field"] = str(indicator.get("field") or "close").strip().lower()
        indicator["name"] = indicator.get("name") or indicator_alias(type("_Indicator", (), indicator)())
    if data.get("ranking"):
        data["ranking"] = _safe_identifier(str(data["ranking"]))
    data["entry_rules"] = [str(x).strip() for x in data.get("entry_rules") or [] if str(x).strip()]
    data["exit_rules"] = [str(x).strip() for x in data.get("exit_rules") or [] if str(x).strip()]
    return StrategySpec.model_validate(data)


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False
