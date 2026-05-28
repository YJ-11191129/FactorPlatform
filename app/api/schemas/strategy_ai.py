from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StrategyIndicatorSpec(BaseModel):
    type: str
    name: Optional[str] = None
    field: str = "close"
    window: Optional[int] = None
    fast_window: Optional[int] = None
    slow_window: Optional[int] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class StrategyRiskSpec(BaseModel):
    max_position_pct: float = 0.2
    max_positions: int = 10
    stop_loss: bool = False
    stop_loss_atr_multiple: Optional[float] = None
    take_profit: bool = False
    notes: List[str] = Field(default_factory=list)


class StrategyExecutionSpec(BaseModel):
    signal_time: str = "close_t"
    trade_time: str = "next_bar"
    fee_bps: float = 5.0
    slippage_bps: float = 0.0
    rebalance_frequency: str = "1d"


class StrategySpec(BaseModel):
    name: str
    description: str = ""
    asset_class: str = "equity"
    universe: List[str] = Field(default_factory=list)
    timeframe: str = "1d"
    direction: str = "long_only"
    indicators: List[StrategyIndicatorSpec] = Field(default_factory=list)
    entry_rules: List[str] = Field(default_factory=list)
    exit_rules: List[str] = Field(default_factory=list)
    ranking: Optional[str] = None
    risk: StrategyRiskSpec = Field(default_factory=StrategyRiskSpec)
    execution: StrategyExecutionSpec = Field(default_factory=StrategyExecutionSpec)
    assumptions: List[str] = Field(default_factory=list)
    rationale: List[str] = Field(default_factory=list)
    disclaimer: str = "Research use only. This is not financial advice."


class StrategyValidationIssue(BaseModel):
    severity: str
    code: str
    message: str
    field: Optional[str] = None


class StrategyValidationResult(BaseModel):
    is_valid: bool
    issues: List[StrategyValidationIssue] = Field(default_factory=list)
    normalized_spec: StrategySpec
    timing_assumptions: List[str] = Field(default_factory=list)
    supported_features: List[str] = Field(default_factory=list)
    disclaimer: str = "Backtest output is for research and risk identification only; not investment advice."


class GenerateStrategyIn(BaseModel):
    prompt: str
    provider: Optional[str] = None
    market: Optional[str] = None
    universe: Optional[List[str]] = None
    timeframe: str = "1d"
    risk_profile: str = "balanced"
    language: str = "zh"


class GenerateStrategyOut(BaseModel):
    spec: StrategySpec
    validation: StrategyValidationResult
    provider: str
    llm_ready: bool
    used_fallback: bool = False
    raw_model_output: Optional[Dict[str, Any]] = None


class ValidateStrategyIn(BaseModel):
    spec: StrategySpec


class RunAiBacktestIn(BaseModel):
    spec: StrategySpec
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    universe: Optional[List[str]] = None
    data_source: Optional[str] = None
    qlib_region: Optional[str] = None
    provider_uri: Optional[str] = None
    qlib_universe: Optional[str] = None
    initial_cash: float = 1_000_000.0
    fee_bps: Optional[float] = None
    use_adj: bool = True
    run_validation: bool = True


class RunAiBacktestOut(BaseModel):
    backtest_id: str
    created_at: str
    summary: Dict[str, Any]
    validation: StrategyValidationResult
    data_health: Optional[Dict[str, Any]] = None


class ExplainBacktestIn(BaseModel):
    spec: StrategySpec
    summary: Dict[str, Any]
    provider: Optional[str] = None
    language: str = "zh"


class ExplainBacktestOut(BaseModel):
    explanation: Dict[str, Any]
    provider: str
    llm_ready: bool
    used_fallback: bool = False


class LLMProviderStatusOut(BaseModel):
    default_provider: str
    providers: List[Dict[str, Any]]
