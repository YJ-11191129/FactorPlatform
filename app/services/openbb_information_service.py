from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


OPENBB_INSTALL_HINT = "Install OpenBB in the backend Python environment: pip install openbb; then run openbb-build if the interface needs rebuilding."


class OpenBBError(RuntimeError):
    def __init__(self, status: str, message: str, readiness: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.readiness = dict(readiness or {})


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def openbb_root() -> Path:
    root = Path(os.getenv("FACTOR_PLATFORM_OPENBB_DIR", str(_project_root() / "data" / "exports" / "openbb")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today_text() -> str:
    return date.today().isoformat()


def _short_hash(payload: Any, length: int = 10) -> str:
    raw = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    chars = []
    for ch in text:
        chars.append(ch if ch.isalnum() or ch in {"_", "-", "."} else "_")
    return ("".join(chars).strip("_") or _short_hash(text))[:120]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        import numpy as np

        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            number = float(value)
            return number if math.isfinite(number) else None
        if isinstance(value, (np.bool_,)):
            return bool(value)
    except Exception:
        pass
    return value


@lru_cache(maxsize=1)
def _load_obb() -> Any:
    from openbb import obb

    return obb


def _package_version() -> str | None:
    for name in ("openbb", "openbb-core"):
        try:
            return importlib.metadata.version(name)
        except Exception:
            continue
    return None


def _endpoint_exists(obb: Any, route: str) -> bool:
    current = obb
    for part in route.split("."):
        if not hasattr(current, part):
            return False
        current = getattr(current, part)
    return callable(current)


def openbb_status() -> dict[str, Any]:
    available = {
        "news_world": False,
        "news_company": False,
        "economy_calendar": False,
    }
    notes: list[str] = []
    spec = importlib.util.find_spec("openbb")
    if spec is None:
        return {
            "status": "OPENBB_NOT_READY",
            "package_version": None,
            "available": available,
            "notes": ["OpenBB Python package is not installed."],
            "install_hint": OPENBB_INSTALL_HINT,
            "config_path": str(Path.home() / ".openbb_platform"),
        }

    version = _package_version()
    try:
        obb = _load_obb()
    except Exception as e:
        return {
            "status": "WARN",
            "package_version": version,
            "available": available,
            "notes": [f"OpenBB package is installed but import failed: {e}"],
            "install_hint": "Try running openbb-build, then restart the backend process.",
            "config_path": str(Path.home() / ".openbb_platform"),
        }

    route_map = {
        "news_world": "news.world",
        "news_company": "news.company",
        "economy_calendar": "economy.calendar",
    }
    for key, route in route_map.items():
        available[key] = _endpoint_exists(obb, route)
        if not available[key]:
            notes.append(f"OpenBB endpoint obb.{route} is unavailable in the installed interface.")

    status = "READY" if all(available.values()) else "WARN"
    if status == "READY":
        notes.append("OpenBB Python SDK is importable and required v1 endpoints are present.")
    return {
        "status": status,
        "package_version": version,
        "available": available,
        "notes": notes,
        "install_hint": None if status == "READY" else "Install missing OpenBB extensions/providers and run openbb-build.",
        "config_path": str(Path.home() / ".openbb_platform"),
    }


def _require_endpoint(endpoint_key: str) -> dict[str, Any]:
    readiness = openbb_status()
    available = readiness.get("available") or {}
    if readiness.get("status") == "OPENBB_NOT_READY":
        raise OpenBBError(
            str(readiness.get("status") or "OPENBB_NOT_READY"),
            f"OpenBB is not ready for {endpoint_key}.",
            readiness,
        )
    if not available.get(endpoint_key):
        raise OpenBBError("OPENBB_ENDPOINT_NOT_AVAILABLE", f"OpenBB endpoint {endpoint_key} is not available.", readiness)
    return readiness


def _get_route_callable(route: str):
    current = _load_obb()
    for part in route.split("."):
        current = getattr(current, part)
    if not callable(current):
        raise OpenBBError("OPENBB_ENDPOINT_NOT_AVAILABLE", f"OpenBB route obb.{route} is not callable.", openbb_status())
    return current


def _model_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if hasattr(value, "dict"):
        return dict(value.dict())
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {"value": value}


def _obbject_to_rows(result: Any) -> list[dict[str, Any]]:
    try:
        if hasattr(result, "to_df"):
            df = result.to_df()
            if df is not None and not df.empty:
                return [_json_safe(row) for row in df.reset_index().to_dict(orient="records")]
    except Exception:
        pass

    raw = getattr(result, "results", result)
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        if isinstance(raw.get("results"), list):
            raw = raw["results"]
        else:
            return [_json_safe(raw)]
    if isinstance(raw, list):
        return [_json_safe(_model_to_dict(item)) for item in raw]
    return [_json_safe(_model_to_dict(raw))]


def _warnings_to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return [_json_safe(value)]


def _first(row: Mapping[str, Any], *names: str) -> Any:
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
        if name.lower() in lower and lower[name.lower()] not in (None, ""):
            return lower[name.lower()]
    return None


def _normalize_news_item(row: Mapping[str, Any], *, endpoint: str, provider: str | None) -> dict[str, Any]:
    title = _first(row, "title", "headline", "name") or "Untitled OpenBB news item"
    link = _first(row, "url", "link", "article_url") or ""
    published = _first(row, "date", "published_at", "published", "updated", "created")
    source = _first(row, "source", "publisher", "provider") or provider or "openbb"
    return {
        "title": str(title),
        "link": str(link),
        "published_at": str(published) if published is not None else None,
        "source": str(source),
        "provider": provider,
        "openbb_endpoint": endpoint,
        "extra": _json_safe(dict(row)),
    }


def _normalize_calendar_item(row: Mapping[str, Any], *, provider: str | None) -> dict[str, Any]:
    event = _first(row, "event", "category", "name") or "Economic event"
    published = _first(row, "date", "datetime")
    source = _first(row, "source", "provider") or provider or "openbb"
    return {
        "title": str(event),
        "link": "",
        "published_at": str(published) if published is not None else None,
        "source": str(source),
        "provider": provider,
        "openbb_endpoint": "economy.calendar",
        "country": _first(row, "country"),
        "importance": _first(row, "importance"),
        "category": _first(row, "category"),
        "actual": _first(row, "actual"),
        "consensus": _first(row, "consensus"),
        "previous": _first(row, "previous"),
        "extra": _json_safe(dict(row)),
    }


def _call_openbb(route: str, params: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None, list[Any], dict[str, Any]]:
    fn = _get_route_callable(route)
    call_args = {k: v for k, v in params.items() if v not in (None, "", [])}
    try:
        result = fn(**call_args)
    except Exception as e:
        raise OpenBBError("OPENBB_QUERY_FAILED", f"OpenBB query obb.{route} failed: {e}", openbb_status()) from e
    provider = getattr(result, "provider", None) or call_args.get("provider")
    warnings = _warnings_to_list(getattr(result, "warnings", None))
    extra = _json_safe(getattr(result, "extra", {}) or {})
    return _obbject_to_rows(result), provider, warnings, extra


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_json_safe(dict(row)), ensure_ascii=False) + "\n")


def _persist_response(response: dict[str, Any]) -> dict[str, Any]:
    day_dir = openbb_root() / _today_text()
    query_id = str(response["query_id"])
    run_dir = day_dir / _safe_id(query_id)
    json_path = run_dir / "query_result.json"
    items_path = run_dir / "items.jsonl"
    response["artifact_path"] = str(json_path)
    response["items_artifact_path"] = str(items_path)
    _write_json(json_path, response)
    _append_jsonl(items_path, list(response.get("items") or []))

    latest_path = openbb_root() / "latest_index.json"
    try:
        index = json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        index = {"latest_by_endpoint": {}, "history": []}
    entry = {
        "query_id": query_id,
        "endpoint": response.get("endpoint"),
        "provider": response.get("provider"),
        "fetched_at": response.get("fetched_at"),
        "count": response.get("count"),
        "artifact_path": str(json_path),
    }
    index.setdefault("latest_by_endpoint", {})[str(response.get("endpoint"))] = entry
    history = [entry] + [item for item in index.get("history", []) if item.get("query_id") != query_id]
    index["history"] = history[:200]
    _write_json(latest_path, index)
    return response


def _register_external_evidence(response: dict[str, Any]) -> str | None:
    try:
        from app.services.research_ops_registry import register_external_evidence

        obj = register_external_evidence(response)
        return str(obj.get("object_id"))
    except Exception:
        return None


def _base_response(*, endpoint: str, query: Mapping[str, Any], provider: str | None, rows: list[dict[str, Any]], warnings: list[Any], extra: Mapping[str, Any], latency_ms: int) -> dict[str, Any]:
    fetched_at = _now_iso()
    query_id = f"openbb_{endpoint.replace('.', '_')}_{fetched_at.replace(':', '').replace('-', '')}_{_short_hash({'endpoint': endpoint, 'query': query, 'rows': len(rows)}, 8)}"
    return {
        "query_id": query_id,
        "source": "openbb",
        "endpoint": endpoint,
        "provider": provider,
        "fetched_at": fetched_at,
        "query": dict(query),
        "items": rows,
        "count": len(rows),
        "warnings": warnings,
        "extra": _json_safe(dict(extra or {})),
        "latency_ms": latency_ms,
        "artifact_path": None,
        "research_ops_object_id": None,
    }


def query_world_news(
    *,
    term: str | None = None,
    topics: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
    provider: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    _require_endpoint("news_world")
    limit = max(1, min(int(limit or 20), 100))
    query = {"term": term, "topics": topics, "start_date": start_date, "end_date": end_date, "limit": limit, "provider": provider}
    t0 = time.time()
    rows, actual_provider, warnings, extra = _call_openbb("news.world", query)
    items = [_normalize_news_item(row, endpoint="news.world", provider=actual_provider) for row in rows[:limit]]
    response = _base_response(endpoint="news.world", query=query, provider=actual_provider, rows=items, warnings=warnings, extra=extra, latency_ms=int((time.time() - t0) * 1000))
    if persist:
        response = _persist_response(response)
        response["research_ops_object_id"] = _register_external_evidence(response)
        _write_json(Path(str(response["artifact_path"])), response)
    return response


def query_company_news(
    *,
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
    provider: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    clean_symbol = str(symbol or "").strip()
    if not clean_symbol:
        raise OpenBBError("INVALID_REQUEST", "symbol is required for OpenBB company news.", openbb_status())
    _require_endpoint("news_company")
    limit = max(1, min(int(limit or 20), 100))
    query = {"symbol": clean_symbol, "start_date": start_date, "end_date": end_date, "limit": limit, "provider": provider}
    t0 = time.time()
    rows, actual_provider, warnings, extra = _call_openbb("news.company", query)
    items = [_normalize_news_item(row, endpoint="news.company", provider=actual_provider) for row in rows[:limit]]
    response = _base_response(endpoint="news.company", query=query, provider=actual_provider, rows=items, warnings=warnings, extra=extra, latency_ms=int((time.time() - t0) * 1000))
    if persist:
        response = _persist_response(response)
        response["research_ops_object_id"] = _register_external_evidence(response)
        _write_json(Path(str(response["artifact_path"])), response)
    return response


def query_economy_calendar(
    *,
    country: str | None = None,
    importance: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    provider: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    _require_endpoint("economy_calendar")
    limit = max(1, min(int(limit or 50), 500))
    query = {"country": country, "importance": importance, "start_date": start_date, "end_date": end_date, "limit": limit, "provider": provider}
    call_query = {"start_date": start_date, "end_date": end_date, "provider": provider}
    t0 = time.time()
    rows, actual_provider, warnings, extra = _call_openbb("economy.calendar", call_query)
    if country:
        country_l = str(country).lower()
        rows = [row for row in rows if country_l in str(_first(row, "country") or "").lower()]
    if importance:
        importance_l = str(importance).lower()
        rows = [row for row in rows if importance_l == str(_first(row, "importance") or "").lower()]
    items = [_normalize_calendar_item(row, provider=actual_provider) for row in rows[:limit]]
    response = _base_response(endpoint="economy.calendar", query=query, provider=actual_provider, rows=items, warnings=warnings, extra=extra, latency_ms=int((time.time() - t0) * 1000))
    if persist:
        response = _persist_response(response)
        response["research_ops_object_id"] = _register_external_evidence(response)
        _write_json(Path(str(response["artifact_path"])), response)
    return response


def latest_openbb_index() -> dict[str, Any] | None:
    path = openbb_root() / "latest_index.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
