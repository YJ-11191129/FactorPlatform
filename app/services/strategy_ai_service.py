from __future__ import annotations

import json
from typing import Any

from app.api.schemas.strategy_ai import (
    ExplainBacktestIn,
    ExplainBacktestOut,
    GenerateStrategyIn,
    GenerateStrategyOut,
    StrategyExecutionSpec,
    StrategyIndicatorSpec,
    StrategyRiskSpec,
    StrategySpec,
)
from app.services.llm import build_llm_provider
from app.services.llm.provider_base import LLMProviderError
from app.services.strategy_validator import validate_strategy_spec


SYSTEM_PROMPT = """You are a quantitative research assistant for a risk-aware backtesting platform.
Return JSON only. Do not promise profits. Do not provide financial advice.
Generate a structured strategy specification that can be safely validated and backtested.

The executor supports only:
- daily long_only strategies
- indicators: sma, ema, momentum, volatility, atr, rsi
- rule syntax: field > value, field < other_field, field >= value, field <= value, field == value, field != value
- base fields: open, high, low, close, volume

Use simple snake_case indicator names, then reference those names in rules.
Assume signals are formed after close_t and applied on the next bar.
"""


def generate_strategy_spec(payload: GenerateStrategyIn) -> GenerateStrategyOut:
    provider = build_llm_provider(payload.provider)
    status = provider.status()
    raw: dict[str, Any] | None = None
    used_fallback = False

    if status.ready:
        user = {
            "task": "generate_strategy_spec",
            "prompt": payload.prompt,
            "market": payload.market,
            "requested_universe": payload.universe,
            "timeframe": payload.timeframe,
            "risk_profile": payload.risk_profile,
            "language": payload.language,
            "output_schema": _strategy_schema_hint(),
        }
        try:
            raw = provider.complete_json(SYSTEM_PROMPT, json.dumps(user, ensure_ascii=False), timeout_s=90)
            spec = StrategySpec.model_validate(raw.get("strategy") if isinstance(raw.get("strategy"), dict) else raw)
        except Exception:
            spec = _fallback_spec(payload)
            used_fallback = True
    else:
        spec = _fallback_spec(payload)
        used_fallback = True

    validation = validate_strategy_spec(spec)
    return GenerateStrategyOut(
        spec=validation.normalized_spec,
        validation=validation,
        provider=status.name,
        llm_ready=status.ready,
        used_fallback=used_fallback,
        raw_model_output=raw,
    )


def explain_backtest(payload: ExplainBacktestIn) -> ExplainBacktestOut:
    provider = build_llm_provider(payload.provider)
    status = provider.status()
    if status.ready:
        system = (
            "You are a risk-aware quantitative research reviewer. Return JSON only. "
            "Explain backtest results with uncertainty, limits, and next validation steps. "
            "Do not make trading recommendations or profit promises."
        )
        user = {
            "task": "explain_backtest",
            "strategy_spec": payload.spec.model_dump(),
            "summary": payload.summary,
            "language": payload.language,
            "output_schema": {
                "executive_summary": "string",
                "risk_notes": ["string"],
                "metric_interpretation": [{"metric": "string", "interpretation": "string"}],
                "failure_modes": ["string"],
                "next_experiments": ["string"],
                "disclaimer": "string",
            },
        }
        try:
            out = provider.complete_json(system, json.dumps(user, ensure_ascii=False), timeout_s=90)
            return ExplainBacktestOut(explanation=out, provider=status.name, llm_ready=True, used_fallback=False)
        except LLMProviderError:
            pass

    return ExplainBacktestOut(
        explanation=_fallback_explanation(payload.summary),
        provider=status.name,
        llm_ready=status.ready,
        used_fallback=True,
    )


def _fallback_spec(payload: GenerateStrategyIn) -> StrategySpec:
    prompt = payload.prompt.lower()
    universe = payload.universe or _infer_universe(prompt)

    indicators = [
        StrategyIndicatorSpec(type="ema", name="ema_20", window=20),
        StrategyIndicatorSpec(type="ema", name="ema_60", window=60),
        StrategyIndicatorSpec(type="momentum", name="momentum_20", window=20),
        StrategyIndicatorSpec(type="volatility", name="volatility_20", window=20),
    ]
    entry_rules = ["ema_20 > ema_60", "momentum_20 > 0"]
    exit_rules = ["ema_20 < ema_60"]

    if any(k in prompt for k in ["rsi", "超买", "超卖"]):
        indicators.append(StrategyIndicatorSpec(type="rsi", name="rsi_14", window=14))
        entry_rules.append("rsi_14 < 70")
    if any(k in prompt for k in ["atr", "止损", "stop"]):
        indicators.append(StrategyIndicatorSpec(type="atr", name="atr_14", window=14))

    return StrategySpec(
        name="AI Volatility Aware Trend Screen",
        description="Template strategy generated from a fallback rule set when the selected LLM is unavailable.",
        asset_class=payload.market or "equity",
        universe=universe,
        timeframe=payload.timeframe or "1d",
        direction="long_only",
        indicators=indicators,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        ranking="momentum_20",
        risk=StrategyRiskSpec(max_position_pct=0.2, max_positions=5, stop_loss=("止损" in prompt or "stop" in prompt)),
        execution=StrategyExecutionSpec(signal_time="close_t", trade_time="next_bar", fee_bps=5.0),
        assumptions=[
            "Fallback template used because the selected LLM provider was unavailable or returned invalid JSON.",
            "Signals are screened after close and applied by the backtest engine on the next bar.",
        ],
        rationale=[
            "Trend filter uses EMA alignment.",
            "Momentum ranking chooses stronger candidates among eligible assets.",
            "Volatility filter is included for risk review even when not used as a hard entry condition.",
        ],
    )


def _infer_universe(prompt: str) -> list[str]:
    if any(k in prompt for k in ["gold", "xau", "黄金"]):
        return ["XAUUSD"]
    if any(k in prompt for k in ["btc", "bitcoin", "比特币"]):
        return ["BTCUSD"]
    if any(k in prompt for k in ["sp500", "s&p", "标普"]):
        return ["SPX"]
    return []


def _strategy_schema_hint() -> dict[str, Any]:
    return {
        "strategy": {
            "name": "string",
            "description": "string",
            "asset_class": "equity|futures|fx|crypto|multi_asset",
            "universe": ["string"],
            "timeframe": "1d",
            "direction": "long_only",
            "indicators": [{"type": "ema", "name": "ema_20", "field": "close", "window": 20}],
            "entry_rules": ["ema_20 > ema_60"],
            "exit_rules": ["ema_20 < ema_60"],
            "ranking": "momentum_20",
            "risk": {"max_position_pct": 0.2, "max_positions": 5, "stop_loss": False},
            "execution": {"signal_time": "close_t", "trade_time": "next_bar", "fee_bps": 5.0},
            "assumptions": ["string"],
            "rationale": ["string"],
            "disclaimer": "Research use only. This is not financial advice.",
        }
    }


def _fallback_explanation(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    return {
        "executive_summary": "LLM explanation is unavailable. The platform produced a deterministic research summary from backtest metrics.",
        "risk_notes": [
            "Review timing assumptions before trusting results.",
            "Transaction costs and slippage assumptions can materially change outcomes.",
            "Run out-of-sample and parameter sensitivity checks.",
        ],
        "metric_interpretation": [
            {"metric": k, "interpretation": f"Observed value: {v}"}
            for k, v in list(metrics.items())[:8]
        ],
        "failure_modes": [
            "Regime shift may invalidate the signal logic.",
            "Sparse trades or concentrated assets may reduce robustness.",
            "High turnover may be understated if slippage is too low.",
        ],
        "next_experiments": [
            "Run a walk-forward split.",
            "Stress test fee_bps and slippage assumptions.",
            "Compare against a simple benchmark over the same dates.",
        ],
        "disclaimer": "Research use only; not investment advice.",
    }
