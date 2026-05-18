from __future__ import annotations

from celery import Celery

from app.core.settings import get_settings


def create_celery() -> Celery:
    settings = get_settings()
    c = Celery(
        "factor_platform",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=[
            "app.tasks.jobs",
        ],
    )
    c.conf.update(
        task_track_started=True,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone=settings.timezone,
        enable_utc=True,
    )
    return c


celery_app = create_celery()

