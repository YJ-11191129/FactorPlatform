from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import require_role
from app.services.research_ops_registry import (
    daily_brief,
    get_lineage,
    get_object,
    list_objects,
    rebuild_index_from_artifacts,
)


router = APIRouter(prefix="/api/research-ops", tags=["research-ops"])


@router.get("/objects", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def list_research_ops_objects(
    object_type: str | None = None,
    asof_date: str | None = None,
    source_run_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    return {
        "items": list_objects(
            object_type=object_type,
            asof_date=asof_date,
            source_run_id=source_run_id,
            limit=limit,
        )
    }


@router.get("/objects/{object_id}", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_research_ops_object(object_id: str) -> dict:
    item = get_object(object_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"status": "NOT_FOUND", "message": f"research ops object not found: {object_id}"})
    return item


@router.get("/lineage/{object_id}", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_research_ops_lineage(object_id: str) -> dict:
    out = get_lineage(object_id)
    if out.get("root") is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "NOT_FOUND",
                "message": f"research ops lineage object not found: {object_id}",
                "missing_references": out.get("missing_references", []),
            },
        )
    return out


@router.get("/daily-brief", dependencies=[Depends(require_role("viewer", "operator", "admin"))])
def get_research_ops_daily_brief(asof_date: str | None = None) -> dict:
    return daily_brief(asof_date=asof_date)


@router.post("/rebuild-index", dependencies=[Depends(require_role("operator", "admin"))])
def rebuild_research_ops_index(reset: bool = False) -> dict:
    return rebuild_index_from_artifacts(reset=reset)
