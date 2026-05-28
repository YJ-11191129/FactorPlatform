from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FactorPlatform/0.1",
    "Accept": "application/rss+xml, application/xml, application/json, text/xml;q=0.9, */*;q=0.8",
}


@dataclass(frozen=True)
class NewsQuery:
    topic: str
    lang: str = "zh-CN"
    region: str = "CN"
    limit: int = 20
    source: str = "google_news_rss"
    provider: str | None = None
    symbol: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    topics: str | None = None


def _clean_text(s: str) -> str:
    x = (s or "").strip()
    x = re.sub(r"\s+", " ", x)
    return x


def _google_news_rss_url(query: str, lang: str, region: str) -> str:
    hl = lang
    gl = region
    ceid = f"{region}:{'zh-Hans' if lang.startswith('zh') else 'en'}"
    q = requests.utils.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def _gdelt_doc_url(query: str) -> str:
    q = requests.utils.quote(query)
    return f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=artlist&format=json&sort=hybridrel"


def _parse_rss(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item"):
        title = _clean_text((item.findtext("title") or ""))
        link = _clean_text((item.findtext("link") or ""))
        pub = _clean_text((item.findtext("pubDate") or ""))
        source_el = item.find("source")
        source = _clean_text(source_el.text if source_el is not None else "")
        items.append(
            {
                "title": title,
                "link": link,
                "published_at": pub,
                "source": source,
            }
        )
    return items


def _parse_gdelt_articles(data: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    items = []
    for row in list(data.get("articles") or [])[:limit]:
        title = _clean_text(str(row.get("title") or ""))
        link = _clean_text(str(row.get("url") or ""))
        source = _clean_text(str(row.get("domain") or row.get("sourcecountry") or "GDELT"))
        published = _clean_text(str(row.get("seendate") or ""))
        if not title:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "published_at": published,
                "source": source,
            }
        )
    return items


def _search_google_news(query: NewsQuery, limit: int) -> dict[str, Any]:
    url = _google_news_rss_url(query.topic, query.lang, query.region)
    t0 = time.time()
    r = requests.get(url, timeout=12, headers=REQUEST_HEADERS)
    r.raise_for_status()
    r.encoding = "utf-8"
    items = _parse_rss(r.text)[:limit]
    return {
        "topic": query.topic,
        "source": "google_news_rss",
        "request_url": url,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "items": items,
        "count": len(items),
        "latency_ms": int((time.time() - t0) * 1000),
        "warnings": [],
    }


def _search_gdelt(query: NewsQuery, limit: int, warning: str | None = None) -> dict[str, Any]:
    t0 = time.time()
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query.topic,
        "mode": "artlist",
        "format": "json",
        "sort": "hybridrel",
        "maxrecords": limit,
    }
    r = requests.get(url, params=params, timeout=15, headers=REQUEST_HEADERS)
    r.raise_for_status()
    data = r.json()
    items = _parse_gdelt_articles(data, limit)
    return {
        "topic": query.topic,
        "source": "gdelt_doc",
        "request_url": _gdelt_doc_url(query.topic),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "items": items,
        "count": len(items),
        "latency_ms": int((time.time() - t0) * 1000),
        "warnings": [warning] if warning else [],
    }


def search_news(query: NewsQuery) -> dict[str, Any]:
    if not query.topic.strip():
        raise ValueError("topic is required")
    limit = max(1, min(int(query.limit), 100))
    source = (query.source or "google_news_rss").strip().lower()
    if source == "openbb":
        from app.services.openbb_information_service import query_company_news, query_world_news

        if query.symbol:
            data = query_company_news(
                symbol=query.symbol,
                start_date=query.start_date,
                end_date=query.end_date,
                limit=limit,
                provider=query.provider,
            )
        else:
            data = query_world_news(
                term=query.topic,
                topics=query.topics,
                start_date=query.start_date,
                end_date=query.end_date,
                limit=limit,
                provider=query.provider,
            )
        return {
            "topic": query.topic,
            "source": "openbb",
            "request_url": "",
            "fetched_at": data.get("fetched_at"),
            "items": data.get("items") or [],
            "count": data.get("count") or 0,
            "latency_ms": data.get("latency_ms") or 0,
            "endpoint": data.get("endpoint"),
            "provider": data.get("provider"),
            "warnings": data.get("warnings") or [],
            "artifact_path": data.get("artifact_path"),
            "research_ops_object_id": data.get("research_ops_object_id"),
        }
    if source != "google_news_rss":
        raise ValueError(f"unknown news source={query.source}; supported sources: google_news_rss, openbb")
    try:
        return _search_google_news(query, limit)
    except Exception as e:
        return _search_gdelt(query, limit, warning=f"Google News RSS unavailable; used GDELT fallback. ({type(e).__name__})")


def summarize_news(items: list[dict[str, Any]]) -> dict[str, Any]:
    out = {
        "highlights": [],
        "sources": {},
    }
    for it in items[:20]:
        title = it.get("title")
        if title:
            out["highlights"].append(title)
        src = it.get("source") or "unknown"
        out["sources"][src] = int(out["sources"].get(src, 0)) + 1
    return out


def llm_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())
