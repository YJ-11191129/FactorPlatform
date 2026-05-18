from __future__ import annotations

from datetime import datetime, timezone
from datetime import date as _date
from typing import Any

from app.db.session import db_session
from app.models.task_job import TaskJob
from app.services.analysis_service import run_single_factor_analysis
from app.services.factor_library_master_service import compute_and_store_factor_values
from app.services.report_service import generate_single_factor_report
from app.tasks.celery_app import celery_app


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)

def _parse_date(v: Any) -> _date | None:
    if v is None:
        return None
    if isinstance(v, _date):
        return v
    s = str(v)
    if not s:
        return None
    return _date.fromisoformat(s)


def _set_started(job_id: str, celery_task_id: str) -> None:
    with db_session() as db:
        job = db.get(TaskJob, job_id)
        if job is None:
            return
        job.status = "STARTED"
        job.celery_task_id = celery_task_id
        job.started_at = _utcnow()
        job.updated_at = _utcnow()


def _set_success(job_id: str, result: dict[str, Any]) -> None:
    with db_session() as db:
        job = db.get(TaskJob, job_id)
        if job is None:
            return
        job.status = "SUCCESS"
        job.result = dict(result)
        job.progress = 100
        job.finished_at = _utcnow()
        job.updated_at = _utcnow()


def _set_failure(job_id: str, err: str) -> None:
    with db_session() as db:
        job = db.get(TaskJob, job_id)
        if job is None:
            return
        job.status = "FAILURE"
        job.error = err[:4000]
        job.finished_at = _utcnow()
        job.updated_at = _utcnow()


@celery_app.task(bind=True, name="factor_platform.compute_store")
def compute_store_job(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _set_started(job_id, self.request.id)
    try:
        out = compute_and_store_factor_values(
            factor_name=str(payload["factor_name"]),
            params=dict(payload.get("params") or {}),
            universe_name=str(payload.get("universe_name") or "A_SHARE_ALL"),
            factor_version=str(payload.get("factor_version") or "V1"),
            start_date=_parse_date(payload.get("start_date")),
            end_date=_parse_date(payload.get("end_date")),
            instrument_limit=payload.get("instrument_limit"),
        )
        _set_success(job_id, out)
        return out
    except Exception as e:
        _set_failure(job_id, str(e))
        raise


@celery_app.task(bind=True, name="factor_platform.analyze_single_factor")
def analyze_single_factor_job(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _set_started(job_id, self.request.id)
    try:
        out = run_single_factor_analysis(
            calc_batch_id=str(payload["calc_batch_id"]),
            horizon=int(payload.get("horizon") or 1),
            quantiles=int(payload.get("quantiles") or 5),
            value_col=str(payload.get("value_col") or "neutralized_value"),
        )
        _set_success(job_id, out)
        return out
    except Exception as e:
        _set_failure(job_id, str(e))
        raise


@celery_app.task(bind=True, name="factor_platform.generate_report_single_factor")
def generate_report_job(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _set_started(job_id, self.request.id)
    try:
        out = generate_single_factor_report(
            analysis_id=str(payload["analysis_id"]),
            enable_pdf=bool(payload.get("enable_pdf") or False),
        )
        _set_success(job_id, out)
        return out
    except Exception as e:
        _set_failure(job_id, str(e))
        raise
