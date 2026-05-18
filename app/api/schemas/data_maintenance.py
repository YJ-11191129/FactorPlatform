from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DataSourceStatusOut(BaseModel):
    source_id: str
    label: str
    path: str
    kind: str
    exists: bool
    status: str
    file_size_bytes: Optional[int] = None
    mtime: Optional[str] = None
    row_count: Optional[int] = None
    asset_count: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    freshness_days: Optional[int] = None
    days_since_latest: Optional[int] = None
    is_blocking: bool = False
    freshness_reason: Optional[str] = None
    notes: List[str] = []
    child_count: Optional[int] = None
    sample_children: Optional[List[str]] = None
    calendar_count: Optional[int] = None
    instrument_counts: Optional[Dict[str, int]] = None
    feature_dir_count: Optional[int] = None


class DataPathAuditOut(BaseModel):
    generated_at: str
    overall_status: str
    blocking_status: str = "OK"
    blockers: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    status_counts: Dict[str, int]
    sources: List[DataSourceStatusOut]


class RunDailyDataMaintenanceIn(BaseModel):
    dry_run: bool = False
    refresh_factor_registry: bool = True
    refresh_stock_screen: bool = True
    run_radar_smoke: bool = True
    run_external_updater: bool = False
    updater_id: Optional[str] = None


class DataMaintenanceRunOut(BaseModel):
    run_id: str
    generated_at: str
    dry_run: bool
    overall_status: str
    audit: Dict[str, Any]
    audit_before: Dict[str, Any]
    steps: List[Dict[str, Any]]
    artifacts: Optional[Dict[str, str]] = None
