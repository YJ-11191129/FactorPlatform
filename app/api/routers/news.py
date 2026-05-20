from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import Actor, require_role
from app.services.news_aggregation_service import NewsQuery, search_news, summarize_news
from app.services.openbb_information_service import OpenBBError


router = APIRouter(prefix="/api/v1/news", tags=["news"])
logger = logging.getLogger("factor_platform.news")


@router.get("/search")
def search(
    topic: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    lang: str = Query("zh-CN"),
    region: str = Query("CN"),
    source: str = Query("google_news_rss"),
    provider: str | None = Query(None),
    symbol: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    topics: str | None = Query(None),
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> dict:
    try:
        return search_news(
            NewsQuery(
                topic=topic,
                limit=limit,
                lang=lang,
                region=region,
                source=source,
                provider=provider,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                topics=topics,
            )
        )
    except OpenBBError as e:
        raise HTTPException(status_code=503, detail={"status": e.status, "message": e.message, "readiness": e.readiness})
    except Exception as e:
        logger.exception("news search failed")
        raise HTTPException(status_code=503, detail={"message": "news service unavailable"})


@router.get("/summary")
def summary(
    topic: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    lang: str = Query("zh-CN"),
    region: str = Query("CN"),
    source: str = Query("google_news_rss"),
    provider: str | None = Query(None),
    symbol: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    topics: str | None = Query(None),
    actor: Actor = Depends(require_role("viewer", "operator", "admin")),
) -> dict:
    try:
        data = search_news(
            NewsQuery(
                topic=topic,
                limit=limit,
                lang=lang,
                region=region,
                source=source,
                provider=provider,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                topics=topics,
            )
        )
        return {
            "topic": topic,
            "fetched_at": data.get("fetched_at"),
            "count": data.get("count"),
            "summary": summarize_news(list(data.get("items") or [])),
            "items": data.get("items"),
            "source": data.get("source"),
            "endpoint": data.get("endpoint"),
            "provider": data.get("provider"),
            "warnings": data.get("warnings") or [],
            "artifact_path": data.get("artifact_path"),
            "research_ops_object_id": data.get("research_ops_object_id"),
        }
    except OpenBBError as e:
        raise HTTPException(status_code=503, detail={"status": e.status, "message": e.message, "readiness": e.readiness})
    except Exception as e:
        logger.exception("news summary failed")
        raise HTTPException(status_code=503, detail={"message": "news service unavailable"})
