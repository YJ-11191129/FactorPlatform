from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, Field


class FactorInfoOut(BaseModel):
    factor_name: str
    display_name: str
    category: str
    description: str
    version: str
    dependencies: List[str]
    parameter_schema: Dict[str, Any]


class RunDemoFactorIn(BaseModel):
    factor_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    save: bool = False


class RunQlibFactorIn(BaseModel):
    factor_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    provider_uri: str = Field(default=r"D:\mcQlib\data\qlib_bin\cn_data")
    universe: str = Field(default="csi300")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    instrument_limit: int = 50
    save: bool = False


class RunFactorOut(BaseModel):
    factor_name: str
    row_count: int
    preview: List[Mapping[str, Any]]
    columns: List[str]
    message: Optional[str] = None
    calc_batch_id: Optional[str] = None
    download_url: Optional[str] = None


class ComputeStoreFactorIn(BaseModel):
    factor_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    universe_name: str = "A_SHARE_ALL"
    factor_version: str = "V1"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    instrument_limit: Optional[int] = 200


class ComputeStoreFactorOut(BaseModel):
    factor_name: str
    calc_batch_id: str
    row_count: int
    factor_values_path: str
    computed_at: str


class FactorValuesQueryOut(BaseModel):
    items: List[Mapping[str, Any]]


class RunStockScreenIn(BaseModel):
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    min_listed_days: Optional[int] = 250
    exclude_st: bool = True
    trade_status: str = "交易"
    min_roe_avg: Optional[float] = None
    min_oper_rev_growth_ttm: Optional[float] = None
    min_net_profit_growth_ttm: Optional[float] = None
    max_debt_to_asset: Optional[float] = None
    topn: int = 2000


class RunStockScreenOut(BaseModel):
    screen_rule_id: str
    asof_date: str
    row_count: int
    latest_path: str
    history_path: str
    financial_statement_path: Optional[str] = None
    financial_rows_used: Optional[int] = None
    financial_coverage_ratio: Optional[float] = None


class StockRadarFactorSpec(BaseModel):
    factor_name: str = "MOM_RET_N_D_V1"
    params: Dict[str, Any] = Field(default_factory=lambda: {"n": 20})
    weight: float = 1.0
    direction: Literal["positive", "negative"] = "positive"


class RunStockRadarIn(BaseModel):
    provider_uri: str = Field(default=r"D:\mcQlib\data\qlib_bin\cn_data")
    universe: str = "csi300"
    factors: List[StockRadarFactorSpec] = Field(
        default_factory=lambda: [
            StockRadarFactorSpec(factor_name="MOM_RET_N_D_V1", params={"n": 20}, weight=0.6, direction="positive"),
            StockRadarFactorSpec(factor_name="TREND_MA_BIAS_N_D_V1", params={"n": 20}, weight=0.4, direction="positive"),
        ]
    )
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    asof_date: Optional[date] = None
    instrument_limit: Optional[int] = 300
    topn: int = 50
    min_score: Optional[float] = None
    min_factor_count: int = 1
    winsorize_q: float = 0.01


class RunStockRadarOut(BaseModel):
    universe: str
    provider_uri: str
    signal_date: str
    effective_trade_date: str
    row_count_on_signal_date: int
    row_count_before_score_filter: int
    row_count: int
    topn: int
    min_score: Optional[float] = None
    min_factor_count: int = 1
    factors: List[Mapping[str, Any]]
    items: List[Mapping[str, Any]]
    timing_note: str
    data_health: Optional[Mapping[str, Any]] = None
