from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request, Response

from app.core.settings import get_settings
from app.db.session import db_session
from app.models.audit_log import AuditLog


def _request_id() -> str:
    return secrets.token_hex(12)


def _actor_from_key(api_key: str | None) -> tuple[str, str]:
    settings = get_settings()
    raw = settings.api_keys
    if not raw and not settings.require_auth:
        return ("anonymous", "admin")
    if not api_key:
        return ("anonymous", "anonymous")
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":", 1)
        if len(parts) != 2:
            continue
        key, role = parts[0].strip(), parts[1].strip()
        if key == api_key:
            return (key[:6], role or "unknown")
    return ("unknown", "unknown")


def _action_for(path: str, method: str) -> str:
    if path.startswith("/health"):
        return "health"
    if path.startswith("/api/factor-library/compute-store"):
        return "factor_library_compute_store"
    if path.startswith("/api/factor-library/registry/sync"):
        return "factor_library_registry_sync"
    if path.startswith("/api/tasks/"):
        return "task_api"
    if path.startswith("/api/analysis/"):
        return "analysis_api"
    if path.startswith("/api/reports/"):
        return "report_api"
    if path.startswith("/api/"):
        return "api"
    return "http_request"


async def audit_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    rid = request.headers.get("X-Request-Id") or _request_id()
    start = time.perf_counter()
    status = 500
    try:
        response: Response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-Id"] = rid
        return response
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        api_key = request.headers.get("X-API-Key")
        actor, role = _actor_from_key(api_key)
        settings = get_settings()
        if settings.require_db:
            try:
                with db_session() as db:
                    db.add(
                        AuditLog(
                            request_id=rid,
                            actor=actor,
                            role=role,
                            method=request.method,
                            path=str(request.url.path),
                            action=_action_for(str(request.url.path), request.method),
                            resource=None,
                            status_code=int(status),
                            duration_ms=duration_ms,
                            extra={
                                "query": dict(request.query_params),
                                "ts": datetime.now(tz=timezone.utc).isoformat(),
                            },
                        )
                    )
            except Exception:
                pass
