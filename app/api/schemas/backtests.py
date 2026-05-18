from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StrategyInfoOut(BaseModel):
    strategy_id: str
    strategy_name: str
    description: str
    version: str
    owner: str
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    python_entry: str


class RunBacktestIn(BaseModel):
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    universe: Optional[List[str]] = None
    initial_cash: float = 1_000_000.0
    fee_bps: float = 5.0
    use_adj: bool = True


class RunBacktestOut(BaseModel):
    backtest_id: str
    created_at: str
    summary: Dict[str, Any]
    data_health: Optional[Dict[str, Any]] = None


class BacktestSummaryOut(BaseModel):
    backtest_id: str
    created_at: str
    strategy_id: str
    strategy_name: str
    portfolio_id: Optional[str] = None
    params: Dict[str, Any]
    initial_cash: float
    fee_bps: float
    universe_size: int
    metrics: Dict[str, Any]


class BacktestDataStatusOut(BaseModel):
    source: str
    columns: List[str]
    start_date: str
    end_date: str
    asset_count: int
    row_count: int
    data_health: Optional[Dict[str, Any]] = None
