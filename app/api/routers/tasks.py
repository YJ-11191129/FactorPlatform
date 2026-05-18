from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import Actor, require_role
from app.api.schemas.tasks import (
    SubmitComputeStoreIn,
    SubmitSingleFactorAnalysisIn,
    SubmitSingleFactorReportIn,
    TaskJobOut,
)
from app.db.session import db_session
from app.services.task_service import (
    cancel_job,
    enqueue_analyze_single_factor,
    enqueue_compute_store,
    enqueue_generate_report,
    get_job,
    list_jobs,
)


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _job_out(j) -> TaskJobOut:
    return TaskJobOut(
        job_id=j.job_id,
        job_type=j.job_type,
        status=j.status,
        actor=j.actor,
        role=j.role,
        celery_task_id=j.celery_task_id,
        payload=dict(j.payload or {}),
        result=dict(j.result or {}),
        error=j.error,
        progress=int(j.progress or 0),
        created_at=j.created_at.isoformat(),
        updated_at=j.updated_at.isoformat(),
        started_at=(j.started_at.isoformat() if j.started_at else None),
        finished_at=(j.finished_at.isoformat() if j.finished_at else None),
    )


@router.post("/compute-store", response_model=TaskJobOut)
def submit_compute_store(
    payload: SubmitComputeStoreIn,
    actor: Actor = Depends(require_role("operator", "admin")),
) -> TaskJobOut:
    try:
        with db_session() as db:
            job = enqueue_compute_store(db, actor=actor.key_id, role=actor.role, payload=payload.model_dump(mode="json"))
        return _job_out(job)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/analyze-single-factor", response_model=TaskJobOut)
def submit_single_factor_analysis(
    payload: SubmitSingleFactorAnalysisIn,
    actor: Actor = Depends(require_role("operator", "admin")),
) -> TaskJobOut:
    try:
        with db_session() as db:
            job = enqueue_analyze_single_factor(
                db,
                actor=actor.key_id,
                role=actor.role,
                payload=payload.model_dump(mode="json"),
            )
        return _job_out(job)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/generate-report-single-factor", response_model=TaskJobOut)
def submit_single_factor_report(
    payload: SubmitSingleFactorReportIn,
    actor: Actor = Depends(require_role("operator", "admin")),
) -> TaskJobOut:
    try:
        with db_session() as db:
            job = enqueue_generate_report(
                db,
                actor=actor.key_id,
                role=actor.role,
                payload=payload.model_dump(mode="json"),
            )
        return _job_out(job)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("", response_model=list[TaskJobOut])
def list_task_jobs(
    limit: int = 50,
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> list[TaskJobOut]:
    try:
        with db_session() as db:
            jobs = list_jobs(db, limit=limit)
        return [_job_out(j) for j in jobs]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{job_id}", response_model=TaskJobOut)
def get_task_job(
    job_id: str,
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> TaskJobOut:
    try:
        with db_session() as db:
            job = get_job(db, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_out(job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/{job_id}/cancel", response_model=TaskJobOut)
def cancel_task_job(
    job_id: str,
    actor: Actor = Depends(require_role("operator", "admin")),
) -> TaskJobOut:
    try:
        with db_session() as db:
            job = cancel_job(db, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_out(job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

