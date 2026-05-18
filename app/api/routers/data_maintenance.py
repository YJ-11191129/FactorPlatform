from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import require_role
from app.api.schemas.data_maintenance import (
    DataMaintenanceRunOut,
    DataPathAuditOut,
    RunDailyDataMaintenanceIn,
)
from app.services.data_maintenance_service import (
    audit_data_paths,
    read_latest_maintenance_report,
    run_daily_data_maintenance,
)


router = APIRouter(prefix="/api/data-maintenance", tags=["data-maintenance"])


@router.get("/paths", response_model=DataPathAuditOut, dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_data_paths() -> DataPathAuditOut:
    try:
        return DataPathAuditOut(**audit_data_paths())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily-update", response_model=DataMaintenanceRunOut, dependencies=[Depends(require_role("operator", "admin"))])
def post_daily_update(payload: RunDailyDataMaintenanceIn) -> DataMaintenanceRunOut:
    try:
        out = run_daily_data_maintenance(
            dry_run=payload.dry_run,
            refresh_factor_registry=payload.refresh_factor_registry,
            refresh_stock_screen=payload.refresh_stock_screen,
            run_radar_smoke=payload.run_radar_smoke,
            run_external_updater=payload.run_external_updater,
            updater_id=payload.updater_id,
        )
        return DataMaintenanceRunOut(**out)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/latest", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_latest_report() -> dict:
    report = read_latest_maintenance_report()
    if report is None:
        raise HTTPException(status_code=404, detail="no data maintenance report found")
    return report
