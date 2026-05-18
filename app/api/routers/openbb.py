from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import Actor, require_role
from app.services.openbb_information_service import (
    OpenBBError,
    openbb_status,
    query_company_news,
    query_economy_calendar,
    query_world_news,
)


router = APIRouter(prefix="/api/openbb", tags=["openbb"])


def _handle_openbb_error(e: OpenBBError) -> HTTPException:
    code = 400 if e.status == "INVALID_REQUEST" else 503
    return HTTPException(status_code=code, detail={"status": e.status, "message": e.message, "readiness": e.readiness})


@router.get("/status")
def get_openbb_status(actor: Actor = Depends(require_role("viewer", "operator", "admin"))) -> dict[str, Any]:
    return openbb_status()


@router.get("/news/world")
def get_openbb_world_news(
    term: str | None = Query(None),
    topics: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    provider: str | None = Query(None),
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> dict[str, Any]:
    try:
        return query_world_news(term=term, topics=topics, start_date=start_date, end_date=end_date, limit=limit, provider=provider)
    except OpenBBError as e:
        raise _handle_openbb_error(e)
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "OPENBB_QUERY_FAILED", "message": str(e)})


@router.get("/news/company")
def get_openbb_company_news(
    symbol: str = Query(..., min_length=1),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    provider: str | None = Query(None),
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> dict[str, Any]:
    try:
        return query_company_news(symbol=symbol, start_date=start_date, end_date=end_date, limit=limit, provider=provider)
    except OpenBBError as e:
        raise _handle_openbb_error(e)
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "OPENBB_QUERY_FAILED", "message": str(e)})


@router.get("/economy/calendar")
def get_openbb_economy_calendar(
    country: str | None = Query(None),
    importance: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    provider: str | None = Query(None),
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> dict[str, Any]:
    try:
        return query_economy_calendar(country=country, importance=importance, start_date=start_date, end_date=end_date, limit=limit, provider=provider)
    except OpenBBError as e:
        raise _handle_openbb_error(e)
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "OPENBB_QUERY_FAILED", "message": str(e)})
