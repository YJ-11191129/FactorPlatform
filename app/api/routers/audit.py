from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import Actor, require_role
from app.db.session import db_session
from app.models.audit_log import AuditLog


router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit_logs(
    limit: int = 200,
    actor: Actor = Depends(require_role("admin")),
) -> dict:
    try:
        from sqlalchemy import select

        with db_session() as db:
            rows = list(
                db.scalars(
                    select(AuditLog)
                    .order_by(AuditLog.created_at.desc())
                    .limit(max(1, int(limit)))
                ).all()
            )
        return {
            "items": [
                {
                    "id": r.id,
                    "request_id": r.request_id,
                    "actor": r.actor,
                    "role": r.role,
                    "method": r.method,
                    "path": r.path,
                    "action": r.action,
                    "resource": r.resource,
                    "status_code": r.status_code,
                    "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat(),
                    "extra": r.extra,
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

