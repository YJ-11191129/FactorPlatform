from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SubmitComputeStoreIn(BaseModel):
    factor_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    universe_name: str = "A_SHARE_ALL"
    factor_version: str = "V1"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    instrument_limit: Optional[int] = 200


class SubmitSingleFactorAnalysisIn(BaseModel):
    calc_batch_id: str
    horizon: int = 1
    quantiles: int = 5
    value_col: str = "neutralized_value"


class SubmitSingleFactorReportIn(BaseModel):
    analysis_id: str
    enable_pdf: bool = False


class TaskJobOut(BaseModel):
    job_id: str
    job_type: str
    status: str
    actor: str
    role: str
    celery_task_id: Optional[str] = None
    payload: Dict[str, Any]
    result: Dict[str, Any]
    error: Optional[str] = None
    progress: int
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

