from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class QlibStatusOut(BaseModel):
    status: str
    provider_uri: str
    universe: str
    freq: str
    package: str
    package_available: bool
    package_version: Optional[str] = None
    data_available: bool
    checks: dict[str, bool]
    notes: list[str]


class RunFactorMiningIn(BaseModel):
    provider_uri: Optional[str] = None
    universe: str = "csi300"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    horizon: int = Field(default=1, ge=1, le=60)
    quantiles: int = Field(default=5, ge=2, le=20)
    top_k: int = Field(default=20, ge=1, le=200)
    freq: str = "day"
    factor_pool: Optional[list[str]] = None
    factor_limit: Optional[int] = Field(default=None, ge=1, le=500)


class FactorMiningRunOut(BaseModel):
    run_id: str
    status: str
    factor_count: int
    date_range: dict[str, Any]
    artifact_path: str
    top_factors: list[dict[str, Any]]
    quality_gate: Optional[dict[str, Any]] = None
    promotion_status: Optional[str] = None
    not_executable: Optional[bool] = None
    quality_reason_codes: list[str] = []


class BuildPortfolioIn(BaseModel):
    mining_run_id: str
    selected_factors: Optional[list[str]] = None
    weighting_method: str = "equal"
    top_n: int = Field(default=5, ge=1, le=50)
    long_top_n: int = Field(default=30, ge=1, le=500)


class PortfolioOut(BaseModel):
    portfolio_id: str
    created_at: str
    mining_run_id: str
    provider_uri: Optional[str] = None
    universe: Optional[str] = None
    selected_factors: list[str]
    weighting_method: str
    weights: dict[str, float]
    signal_artifact_path: str
    signal_count: int
    date_count: int
    timing_note: str
    quality_gate: Optional[dict[str, Any]] = None
    promotion_status: Optional[str] = None
    not_executable: bool = False
    quality_reason_codes: list[str] = []
