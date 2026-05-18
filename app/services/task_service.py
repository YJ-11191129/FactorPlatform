from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task_job import TaskJob
from app.tasks.celery_app import celery_app
from app.tasks.jobs import analyze_single_factor_job, compute_store_job, generate_report_job


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_job(db: Session, job_type: str, actor: str, role: str, payload: dict[str, Any]) -> TaskJob:
    job = TaskJob(
        job_id=uuid4().hex,
        job_type=job_type,
        status="PENDING",
        actor=actor,
        role=role,
        celery_task_id=None,
        payload=dict(payload),
        result={},
        error=None,
        progress=0,
        started_at=None,
        finished_at=None,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(job)
    db.commit()
    return job


def enqueue_compute_store(db: Session, actor: str, role: str, payload: dict[str, Any]) -> TaskJob:
    job = create_job(db, "compute_store", actor, role, payload)
    async_result = compute_store_job.apply_async(args=[job.job_id, payload])
    job.celery_task_id = async_result.id
    job.updated_at = _utcnow()
    db.commit()
    return job


def enqueue_analyze_single_factor(db: Session, actor: str, role: str, payload: dict[str, Any]) -> TaskJob:
    job = create_job(db, "analyze_single_factor", actor, role, payload)
    async_result = analyze_single_factor_job.apply_async(args=[job.job_id, payload])
    job.celery_task_id = async_result.id
    job.updated_at = _utcnow()
    db.commit()
    return job


def enqueue_generate_report(db: Session, actor: str, role: str, payload: dict[str, Any]) -> TaskJob:
    job = create_job(db, "generate_report_single_factor", actor, role, payload)
    async_result = generate_report_job.apply_async(args=[job.job_id, payload])
    job.celery_task_id = async_result.id
    job.updated_at = _utcnow()
    db.commit()
    return job


def get_job(db: Session, job_id: str) -> TaskJob | None:
    return db.get(TaskJob, job_id)


def list_jobs(db: Session, limit: int = 50) -> list[TaskJob]:
    q = select(TaskJob).order_by(TaskJob.created_at.desc()).limit(max(1, int(limit)))
    return list(db.scalars(q).all())


def cancel_job(db: Session, job_id: str) -> TaskJob | None:
    job = db.get(TaskJob, job_id)
    if job is None:
        return None
    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id, terminate=False)
    job.status = "CANCELLED"
    job.updated_at = _utcnow()
    job.finished_at = _utcnow()
    db.commit()
    return job
