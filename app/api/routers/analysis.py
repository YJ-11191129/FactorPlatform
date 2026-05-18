from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import Actor, require_role
from app.db.session import db_session
from app.models.analysis_result import AnalysisResult


router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("")
def list_analysis(limit: int = 50, actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict:
    try:
        from sqlalchemy import select

        with db_session() as db:
            rows = list(
                db.scalars(
                    select(AnalysisResult)
                    .order_by(AnalysisResult.created_at.desc())
                    .limit(max(1, int(limit)))
                ).all()
            )
        return {
            "items": [
                {
                    "analysis_id": r.analysis_id,
                    "analysis_type": r.analysis_type,
                    "calc_batch_id": r.calc_batch_id,
                    "factor_name": r.factor_name,
                    "factor_version": r.factor_version,
                    "status": r.status,
                    "artifact_path": r.artifact_path,
                    "row_count": r.row_count,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict:
    try:
        with db_session() as db:
            r = db.get(AnalysisResult, analysis_id)
        if r is None:
            raise HTTPException(status_code=404, detail="analysis not found")
        return {
            "analysis_id": r.analysis_id,
            "analysis_type": r.analysis_type,
            "calc_batch_id": r.calc_batch_id,
            "factor_name": r.factor_name,
            "factor_version": r.factor_version,
            "status": r.status,
            "summary": r.summary,
            "artifact_path": r.artifact_path,
            "row_count": r.row_count,
            "created_at": r.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
