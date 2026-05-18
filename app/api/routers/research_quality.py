from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies.auth import require_role
from app.services.research_quality_service import evaluate_research_quality, list_quality_runs, read_quality_report


router = APIRouter(prefix="/api/research-quality", tags=["research-quality"])


class ResearchQualityEvaluateIn(BaseModel):
    source_type: str = "qlib_factor_mining"
    source_run_id: str
    thresholds: dict[str, Any] | None = None


@router.post("/evaluate", dependencies=[Depends(require_role("operator", "admin"))])
def evaluate_research_quality_api(payload: ResearchQualityEvaluateIn) -> dict[str, Any]:
    try:
        return evaluate_research_quality(
            source_type=payload.source_type,
            source_run_id=payload.source_run_id,
            thresholds=payload.thresholds,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"status": "SOURCE_ARTIFACT_NOT_FOUND", "message": str(e)})
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"status": "INVALID_REQUEST", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"status": "QUALITY_EVALUATION_FAILED", "message": str(e)})


@router.get("/runs", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def list_research_quality_runs(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    return {"items": list_quality_runs(limit=limit)}


@router.get("/runs/{source_run_id}", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_research_quality_run(source_run_id: str) -> dict[str, Any]:
    try:
        return read_quality_report(source_run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"status": "QUALITY_REPORT_NOT_FOUND", "message": str(e)})
