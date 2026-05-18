from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


RESEARCH_OPS_OBJECT_TYPES = {
    "data_snapshot",
    "factor_run",
    "validation_result",
    "signal_snapshot",
    "router_decision",
    "portfolio_proposal",
    "outcome",
    "report_artifact",
    "external_evidence",
}

TERMINAL_STATUSES = {
    "OK",
    "WARN",
    "BLOCKED",
    "SUCCESS",
    "FAILED",
    "PENDING",
    "NO_TRADE",
    "SHADOW_EVALUATED",
    "DRY_RUN",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def registry_root() -> Path:
    root = Path(os.getenv("FACTOR_PLATFORM_RESEARCH_OPS_DIR", str(_project_root() / "data" / "exports" / "research_ops")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _objects_root() -> Path:
    root = registry_root() / "objects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _edges_path() -> Path:
    return registry_root() / "lineage_edges.jsonl"


def _latest_index_path() -> Path:
    return registry_root() / "latest_index.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today_text() -> str:
    return date.today().isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
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
    except Exception:
        pass
    return value


def _short_hash(payload: Any, length: int = 10) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    allowed = []
    for ch in text:
        if ch.isalnum() or ch in {"_", "-", "."}:
            allowed.append(ch)
        else:
            allowed.append("_")
    out = "".join(allowed).strip("_")
    return out or _short_hash(text)


def _normalize_status(status: Any) -> str:
    raw = str(status or "PENDING").upper()
    if raw in {"ACTIVE", "MONITORED", "NOTIFIED", "APPROVED", "SCALED"}:
        return "OK"
    if raw in {"OPEN", "PENDING_OUTCOME", "SHADOW_PENDING"}:
        return "PENDING"
    if raw == "CLOSED":
        return "SUCCESS"
    if raw in TERMINAL_STATUSES:
        return raw
    if raw in {"MISSING", "STALE", "DATA_NOT_READY", "QLIB_NOT_READY", "REGIME_STALE_BLOCKED"}:
        return "BLOCKED"
    if raw in {"EMPTY", "NO_SNAPSHOT", "NO_OUTCOMES"}:
        return "PENDING"
    if raw in {"ERROR", "EXCEPTION"}:
        return "FAILED"
    if raw in {"READY"}:
        return "OK"
    if raw in {"OPENBB_NOT_READY"}:
        return "WARN"
    return raw


def _object_file(object_type: str, object_id: str) -> Path:
    return _objects_root() / _safe_id(object_type) / f"{_safe_id(object_id)}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _coerce_list(values: Iterable[Any] | Any | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        values = [values]
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


def upsert_object(
    *,
    object_id: str,
    object_type: str,
    status: str = "PENDING",
    asof_date: str | date | None = None,
    created_at: str | None = None,
    source_system: str = "unknown",
    source_run_id: str | None = None,
    artifact_paths: Iterable[Any] | None = None,
    summary: Mapping[str, Any] | None = None,
    parents: Iterable[Any] | None = None,
    tags: Iterable[Any] | None = None,
    external_ids: Iterable[Any] | None = None,
) -> dict[str, Any]:
    if object_type not in RESEARCH_OPS_OBJECT_TYPES:
        raise ValueError(f"unsupported research ops object_type: {object_type}")

    envelope = {
        "object_id": str(object_id),
        "object_type": str(object_type),
        "asof_date": str(asof_date or _today_text())[:10],
        "created_at": created_at or _now_iso(),
        "status": _normalize_status(status),
        "source_system": source_system,
        "source_run_id": source_run_id,
        "artifact_paths": _coerce_list(artifact_paths),
        "summary": _json_safe(dict(summary or {})),
        "parents": _coerce_list(parents),
        "tags": _coerce_list(tags),
        "external_ids": _coerce_list(external_ids),
    }
    _write_json(_object_file(object_type, object_id), envelope)
    rebuild_registry_indexes()
    return envelope


def _load_objects() -> list[dict[str, Any]]:
    root = _objects_root()
    objects: list[dict[str, Any]] = []
    for path in root.glob("*/*.json"):
        payload = _read_json(path)
        if payload and payload.get("object_id") and payload.get("object_type"):
            objects.append(payload)
    return objects


def _sort_key(obj: Mapping[str, Any]) -> str:
    return str(obj.get("created_at") or obj.get("asof_date") or "")


def _object_by_id(objects: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(obj.get("object_id")): dict(obj) for obj in objects if obj.get("object_id")}


def _edge_rows(objects: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for obj in objects:
        target = str(obj.get("object_id") or "")
        if not target:
            continue
        for parent in _coerce_list(obj.get("parents")):
            key = (parent, target, "parent")
            if key in seen:
                continue
            seen.add(key)
            rows.append({"source": parent, "target": target, "relation": "parent"})
    return rows


def rebuild_registry_indexes() -> dict[str, Any]:
    objects = sorted(_load_objects(), key=_sort_key, reverse=True)
    edges = _edge_rows(objects)

    edge_path = _edges_path()
    edge_path.parent.mkdir(parents=True, exist_ok=True)
    edge_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in edges),
        encoding="utf-8",
    )

    by_type: dict[str, list[str]] = {}
    latest_by_type: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for obj in objects:
        object_id = str(obj.get("object_id"))
        object_type = str(obj.get("object_type"))
        by_type.setdefault(object_type, []).append(object_id)
        latest_by_type.setdefault(object_type, object_id)
        alias_values = [
            obj.get("source_run_id"),
            object_id,
            *(obj.get("external_ids") or []),
        ]
        summary = obj.get("summary") if isinstance(obj.get("summary"), dict) else {}
        for key in ("signal_id", "signal_ids", "run_id", "portfolio_id", "report_id", "backtest_id", "source_run_id"):
            value = summary.get(key)
            if isinstance(value, list):
                alias_values.extend(value)
            else:
                alias_values.append(value)
        for alias in _coerce_list(alias_values):
            bucket = aliases.setdefault(alias, [])
            if object_id not in bucket:
                bucket.append(object_id)

    index = {
        "generated_at": _now_iso(),
        "object_count": len(objects),
        "edge_count": len(edges),
        "by_type": by_type,
        "latest_by_type": latest_by_type,
        "aliases": aliases,
    }
    _write_json(_latest_index_path(), index)
    return index


def reset_registry() -> None:
    root = registry_root()
    objects = root / "objects"
    if objects.exists():
        shutil.rmtree(objects)
    for path in (_edges_path(), _latest_index_path()):
        path.unlink(missing_ok=True)
    _objects_root()
    rebuild_registry_indexes()


def list_objects(
    *,
    object_type: str | None = None,
    asof_date: str | None = None,
    source_run_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    objects = sorted(_load_objects(), key=_sort_key, reverse=True)
    if object_type:
        objects = [obj for obj in objects if str(obj.get("object_type")) == str(object_type)]
    if asof_date:
        objects = [obj for obj in objects if str(obj.get("asof_date"))[:10] == str(asof_date)[:10]]
    if source_run_id:
        objects = [obj for obj in objects if str(obj.get("source_run_id") or "") == str(source_run_id)]
    return objects[: max(0, int(limit))]


def get_object(object_id: str) -> dict[str, Any] | None:
    for obj in _load_objects():
        if str(obj.get("object_id")) == str(object_id):
            return obj
    return None


def _load_index() -> dict[str, Any]:
    index = _read_json(_latest_index_path())
    if index is None:
        index = rebuild_registry_indexes()
    return index


def _summary_matches(summary: Mapping[str, Any], identifier: str) -> bool:
    for key in ("signal_id", "run_id", "portfolio_id", "report_id", "backtest_id", "source_run_id"):
        value = summary.get(key)
        if str(value) == identifier:
            return True
    for key in ("signal_ids", "portfolio_ids", "report_ids", "backtest_ids"):
        value = summary.get(key)
        if isinstance(value, list) and identifier in {str(x) for x in value}:
            return True
    return False


def find_related_objects(identifier: str) -> list[dict[str, Any]]:
    wanted = str(identifier)
    objects = _object_by_id(_load_objects())
    ids: list[str] = []
    aliases = _load_index().get("aliases") or {}
    for object_id in aliases.get(wanted, []):
        if object_id not in ids:
            ids.append(object_id)
    for obj in objects.values():
        summary = obj.get("summary") if isinstance(obj.get("summary"), dict) else {}
        if (
            str(obj.get("object_id")) == wanted
            or str(obj.get("source_run_id") or "") == wanted
            or wanted in {str(x) for x in obj.get("external_ids") or []}
            or _summary_matches(summary, wanted)
        ):
            object_id = str(obj.get("object_id"))
            if object_id not in ids:
                ids.append(object_id)
    return [objects[object_id] for object_id in ids if object_id in objects]


def _load_edges() -> list[dict[str, str]]:
    path = _edges_path()
    if not path.exists():
        rebuild_registry_indexes()
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            rows.append({"source": str(row.get("source")), "target": str(row.get("target")), "relation": str(row.get("relation") or "parent")})
        except Exception:
            continue
    return rows


def _artifact_missing(obj: Mapping[str, Any]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for raw in _coerce_list(obj.get("artifact_paths")):
        if raw.startswith(("http://", "https://")):
            continue
        try:
            if not Path(raw).exists():
                missing.append({"object_id": str(obj.get("object_id")), "artifact_path": raw, "reason": "artifact_path_missing"})
        except Exception as e:
            missing.append({"object_id": str(obj.get("object_id")), "artifact_path": raw, "reason": str(e)})
    return missing


def get_lineage(identifier: str, *, max_depth: int = 4) -> dict[str, Any]:
    objects_by_id = _object_by_id(_load_objects())
    edges = _load_edges()
    exact = objects_by_id.get(str(identifier))
    related = find_related_objects(identifier) if exact is None else [exact]
    if not related:
        return {
            "root": None,
            "nodes": [],
            "edges": [],
            "missing_references": [{"object_id": str(identifier), "reason": "object_not_registered"}],
        }

    if exact is None:
        root = {
            "object_id": str(identifier),
            "object_type": "external_reference",
            "asof_date": _today_text(),
            "created_at": _now_iso(),
            "status": "OK",
            "source_system": "research_ops_registry",
            "source_run_id": None,
            "artifact_paths": [],
            "summary": {"matched_objects": [obj["object_id"] for obj in related]},
            "parents": [],
            "tags": ["virtual"],
        }
        start_ids = [str(obj["object_id"]) for obj in related]
        virtual_edges = [{"source": str(identifier), "target": sid, "relation": "resolves_to"} for sid in start_ids]
    else:
        root = exact
        start_ids = [str(exact["object_id"])]
        virtual_edges = []

    adjacency: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    for row in edges:
        source = row["source"]
        target = row["target"]
        adjacency.setdefault(source, set()).add(target)
        reverse.setdefault(target, set()).add(source)

    visited: set[str] = set()
    frontier: list[tuple[str, int]] = [(sid, 0) for sid in start_ids]
    while frontier:
        current, depth = frontier.pop(0)
        if current in visited or depth > max_depth:
            continue
        visited.add(current)
        for nxt in sorted(adjacency.get(current, set()) | reverse.get(current, set())):
            if nxt not in visited and depth + 1 <= max_depth:
                frontier.append((nxt, depth + 1))

    nodes = [objects_by_id[obj_id] for obj_id in sorted(visited, key=lambda oid: _sort_key(objects_by_id.get(oid, {})), reverse=True) if obj_id in objects_by_id]
    if exact is None:
        nodes = [root] + nodes

    node_ids = {str(node.get("object_id")) for node in nodes}
    graph_edges = [
        row
        for row in edges
        if row["source"] in node_ids and row["target"] in node_ids
    ]
    graph_edges = virtual_edges + graph_edges

    missing: list[dict[str, str]] = []
    for row in edges:
        if row["source"] in node_ids and row["target"] not in objects_by_id:
            missing.append({"object_id": row["target"], "reason": "target_not_registered"})
        if row["target"] in node_ids and row["source"] not in objects_by_id:
            missing.append({"object_id": row["source"], "reason": "parent_not_registered"})
    for node in nodes:
        if str(node.get("object_type")) != "external_reference":
            missing.extend(_artifact_missing(node))

    return {"root": root, "nodes": nodes, "edges": graph_edges, "missing_references": missing}


def _latest_for_type(object_type: str, *, asof_date: str | None = None) -> dict[str, Any] | None:
    items = list_objects(object_type=object_type, asof_date=asof_date, limit=1)
    if items:
        return items[0]
    if asof_date:
        items = list_objects(object_type=object_type, limit=1)
        if items:
            return items[0]
    return None


def _count_by_status(items: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def daily_brief(asof_date: str | None = None) -> dict[str, Any]:
    day = str(asof_date or _today_text())[:10]
    day_objects = list_objects(asof_date=day, limit=500)
    latest_data = _latest_for_type("data_snapshot", asof_date=day)
    latest_signal = _latest_for_type("signal_snapshot", asof_date=day)
    latest_outcome = _latest_for_type("outcome", asof_date=day)
    reports = list_objects(object_type="report_artifact", asof_date=day, limit=5)
    router_objects = list_objects(object_type="router_decision", asof_date=day, limit=500)

    signal_summary = latest_signal.get("summary", {}) if latest_signal else {}
    data_summary = latest_data.get("summary", {}) if latest_data else {}
    latest_router = router_objects[0] if router_objects else None

    open_gaps: list[dict[str, str]] = []
    if latest_data is None:
        open_gaps.append({"code": "NO_DATA_SNAPSHOT", "message": "No registered data readiness snapshot for this date."})
    if latest_signal is None:
        open_gaps.append({"code": "NO_SIGNAL_SNAPSHOT", "message": "No registered Signal Center snapshot for this date."})
    if latest_outcome is None:
        open_gaps.append({"code": "NO_OUTCOME", "message": "No registered signal outcome artifact for this date."})

    return {
        "asof_date": day,
        "data_health": {
            "status": latest_data.get("status") if latest_data else "PENDING",
            "object_id": latest_data.get("object_id") if latest_data else None,
            "blocking_status": data_summary.get("blocking_status"),
            "blockers": data_summary.get("blockers") or [],
            "recommendations": data_summary.get("recommendations") or [],
        },
        "latest_signal_snapshot": latest_signal,
        "router_summary": {
            "status_counts": _count_by_status(router_objects),
            "latest_decision": latest_router,
            "blocked_count": signal_summary.get("blocked_count") or signal_summary.get("router_blocked_count"),
            "risk_scale": (latest_router.get("summary", {}) or {}).get("risk_scale") if latest_router else None,
            "block_reason": (latest_router.get("summary", {}) or {}).get("block_reason") if latest_router else None,
        },
        "shadow_summary": {
            "shadow_count": signal_summary.get("shadow_count") or (signal_summary.get("counts") or {}).get("shadow_count"),
            "router_blocked_count": signal_summary.get("router_blocked_count") or (signal_summary.get("counts") or {}).get("router_blocked_count"),
        },
        "latest_outcome": latest_outcome,
        "latest_reports": reports,
        "open_gaps": open_gaps,
        "object_status_counts": _count_by_status(day_objects),
    }


def _latest_parent_id(object_type: str) -> str | None:
    latest = _latest_for_type(object_type)
    return str(latest.get("object_id")) if latest else None


def register_data_snapshot_from_audit(
    audit: Mapping[str, Any],
    *,
    run_id: str | None = None,
    artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = str(audit.get("generated_at") or _now_iso())
    source_fingerprint = [
        {
            "source_id": item.get("source_id"),
            "status": item.get("status"),
            "end_date": item.get("end_date"),
            "path": item.get("path"),
        }
        for item in audit.get("sources", []) or []
        if isinstance(item, Mapping)
    ]
    object_id = f"data_snapshot_{_safe_id(run_id) if run_id else generated_at[:10].replace('-', '') + '_' + _short_hash(source_fingerprint, 8)}"
    blocking_status = str(audit.get("blocking_status") or audit.get("overall_status") or "WARN")
    summary = {
        "generated_at": generated_at,
        "overall_status": audit.get("overall_status"),
        "blocking_status": audit.get("blocking_status"),
        "status_counts": audit.get("status_counts") or {},
        "source_count": len(audit.get("sources") or []),
        "blockers": audit.get("blockers") or [],
        "recommendations": audit.get("recommendations") or [],
    }
    artifact_paths = list((artifacts or {}).values())
    return upsert_object(
        object_id=object_id,
        object_type="data_snapshot",
        status=blocking_status,
        asof_date=generated_at[:10],
        created_at=generated_at,
        source_system="data_maintenance",
        source_run_id=run_id,
        artifact_paths=artifact_paths,
        summary=summary,
        tags=["data", "readiness"],
        external_ids=[run_id] if run_id else [],
    )


def register_factor_run_artifact(meta: Mapping[str, Any]) -> dict[str, Any]:
    run_id = str(meta.get("run_id") or meta.get("calc_batch_id") or "")
    if not run_id:
        raise ValueError("factor run registration requires run_id or calc_batch_id")
    artifacts = []
    if meta.get("artifact_path"):
        artifacts.append(meta.get("artifact_path"))
    if meta.get("parquet_path"):
        artifacts.append(meta.get("parquet_path"))
    if meta.get("meta_path"):
        artifacts.append(meta.get("meta_path"))
    if isinstance(meta.get("artifacts"), Mapping):
        artifacts.extend(meta["artifacts"].values())
    summary = {
        "run_id": run_id,
        "factor_name": meta.get("factor_name"),
        "mode": meta.get("mode") or "native_qlib",
        "provider_uri": meta.get("provider_uri"),
        "universe": meta.get("universe"),
        "date_range": meta.get("date_range") or {"start_date": meta.get("start_date"), "end_date": meta.get("end_date")},
        "row_count": meta.get("row_count"),
        "factor_count": meta.get("factor_count"),
        "top_factors": meta.get("top_factors") or [],
    }
    created_at = str(meta.get("generated_at") or meta.get("created_at") or _now_iso())
    return upsert_object(
        object_id=f"factor_run_{_safe_id(run_id)}",
        object_type="factor_run",
        status=str(meta.get("status") or "SUCCESS"),
        asof_date=(meta.get("date_range") or {}).get("end_date") if isinstance(meta.get("date_range"), Mapping) else created_at[:10],
        created_at=created_at,
        source_system=str(meta.get("source_system") or "factor_research"),
        source_run_id=run_id,
        artifact_paths=artifacts,
        summary=summary,
        tags=["factor", str(meta.get("mode") or "native_qlib")],
        external_ids=[run_id],
    )


def register_validation_result_from_mining(summary: Mapping[str, Any]) -> dict[str, Any]:
    run_id = str(summary.get("run_id") or "")
    if not run_id:
        raise ValueError("validation result registration requires run_id")
    artifacts = list((summary.get("artifacts") or {}).values()) if isinstance(summary.get("artifacts"), Mapping) else []
    top = summary.get("top_factors") or []
    first = top[0] if top and isinstance(top[0], Mapping) else {}
    payload = {
        "run_id": run_id,
        "horizon": summary.get("horizon"),
        "quantiles": summary.get("quantiles"),
        "factor_count": summary.get("factor_count"),
        "observation_count": summary.get("observation_count"),
        "top_factor": first.get("factor_name"),
        "top_rank_ic": first.get("rank_ic_mean"),
        "top_ic": first.get("ic_mean"),
        "top_factors": top,
        "timing_note": summary.get("timing_note"),
    }
    created_at = str(summary.get("generated_at") or _now_iso())
    return upsert_object(
        object_id=f"validation_result_{_safe_id(run_id)}",
        object_type="validation_result",
        status=str(summary.get("status") or "SUCCESS"),
        asof_date=(summary.get("date_range") or {}).get("end_date") if isinstance(summary.get("date_range"), Mapping) else created_at[:10],
        created_at=created_at,
        source_system="native_qlib_factor_mining",
        source_run_id=run_id,
        artifact_paths=artifacts,
        summary=payload,
        parents=[f"factor_run_{_safe_id(run_id)}"],
        tags=["validation", "ic", "rank_ic"],
        external_ids=[run_id],
    )


def register_qlib_blocked_event(
    *,
    request: Mapping[str, Any],
    readiness: Mapping[str, Any] | None,
    status: str,
    message: str,
) -> dict[str, Any]:
    created_at = _now_iso()
    event_id = f"qlib_blocked_{created_at[:10].replace('-', '')}_{_short_hash({'request': request, 'readiness': readiness, 'message': message}, 8)}"
    return upsert_object(
        object_id=f"factor_run_{event_id}",
        object_type="factor_run",
        status="BLOCKED",
        asof_date=created_at[:10],
        created_at=created_at,
        source_system="native_qlib_factor_mining",
        source_run_id=event_id,
        artifact_paths=[],
        summary={
            "run_id": event_id,
            "raw_status": status,
            "message": message,
            "request": dict(request),
            "readiness": dict(readiness or {}),
        },
        tags=["factor", "blocked", str(status)],
        external_ids=[event_id],
    )


def register_portfolio_proposal(summary: Mapping[str, Any]) -> dict[str, Any]:
    portfolio_id = str(summary.get("portfolio_id") or "")
    if not portfolio_id:
        raise ValueError("portfolio proposal registration requires portfolio_id")
    mining_run_id = summary.get("mining_run_id")
    parents = []
    if mining_run_id:
        parents.extend([f"factor_run_{_safe_id(mining_run_id)}", f"validation_result_{_safe_id(mining_run_id)}"])
    artifact_paths = [summary.get("signal_artifact_path")]
    created_at = str(summary.get("created_at") or _now_iso())
    return upsert_object(
        object_id=f"portfolio_proposal_{_safe_id(portfolio_id)}",
        object_type="portfolio_proposal",
        status=str(summary.get("status") or "SUCCESS"),
        asof_date=created_at[:10],
        created_at=created_at,
        source_system="native_qlib_portfolio_builder",
        source_run_id=portfolio_id,
        artifact_paths=artifact_paths,
        summary={
            "portfolio_id": portfolio_id,
            "mining_run_id": mining_run_id,
            "selected_factors": summary.get("selected_factors") or [],
            "weighting_method": summary.get("weighting_method"),
            "signal_count": summary.get("signal_count"),
            "date_count": summary.get("date_count"),
            "weights": summary.get("weights") or {},
            "provider_uri": summary.get("provider_uri"),
            "universe": summary.get("universe"),
            "timing_note": summary.get("timing_note"),
        },
        parents=parents,
        tags=["portfolio", "qlib"],
        external_ids=[portfolio_id, mining_run_id],
    )


def register_backtest_artifact(summary: Mapping[str, Any]) -> dict[str, Any]:
    backtest_id = str(summary.get("backtest_id") or "")
    if not backtest_id:
        raise ValueError("backtest registration requires backtest_id")
    portfolio_id = summary.get("portfolio_id")
    parents = [f"portfolio_proposal_{_safe_id(portfolio_id)}"] if portfolio_id else []
    artifacts = []
    summary_path = summary.get("summary_path")
    if summary_path:
        artifacts.append(summary_path)
    source_signal = summary.get("source_signal_artifact_path")
    if source_signal:
        artifacts.append(source_signal)
    created_at = str(summary.get("created_at") or _now_iso())
    return upsert_object(
        object_id=f"portfolio_proposal_{_safe_id(backtest_id)}",
        object_type="portfolio_proposal",
        status="SUCCESS",
        asof_date=created_at[:10],
        created_at=created_at,
        source_system="backtest_service",
        source_run_id=backtest_id,
        artifact_paths=artifacts,
        summary={
            "backtest_id": backtest_id,
            "portfolio_id": portfolio_id,
            "strategy_id": summary.get("strategy_id"),
            "strategy_name": summary.get("strategy_name"),
            "metrics": summary.get("metrics") or {},
            "data_health": summary.get("data_health"),
        },
        parents=parents,
        tags=["backtest", "portfolio"],
        external_ids=[backtest_id, portfolio_id],
    )


def register_signal_snapshot(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    run_id = str(snapshot.get("source_run_id") or snapshot.get("run_id") or "")
    if not run_id:
        raise ValueError("signal snapshot registration requires source_run_id")
    signal_ids = []
    for item in list(snapshot.get("items") or snapshot.get("signals") or []) + list(snapshot.get("shadow_items") or []):
        sid = item.get("signal_id")
        if sid and str(sid) not in signal_ids:
            signal_ids.append(str(sid))

    data_parent = _latest_parent_id("data_snapshot")
    created_at = str(snapshot.get("generated_at") or _now_iso())
    signal_object_id = f"signal_snapshot_{_safe_id(run_id)}"
    counts = snapshot.get("counts") or {}
    objects = [
        upsert_object(
            object_id=signal_object_id,
            object_type="signal_snapshot",
            status=str(snapshot.get("status") or "OK"),
            asof_date=str(snapshot.get("signal_date") or created_at[:10])[:10],
            created_at=created_at,
            source_system="signal_generation_service",
            source_run_id=run_id,
            artifact_paths=[snapshot.get("snapshot_path")],
            summary={
                "run_id": run_id,
                "signal_date": snapshot.get("signal_date"),
                "effective_trade_date": snapshot.get("effective_trade_date"),
                "generated_count": snapshot.get("generated_count"),
                "blocked_count": snapshot.get("blocked_count"),
                "live_active_count": counts.get("live_active_count"),
                "router_blocked_count": counts.get("router_blocked_count"),
                "shadow_count": counts.get("shadow_count"),
                "counts": counts,
                "data_source": snapshot.get("data_source"),
                "data_health": snapshot.get("data_health"),
                "regime_freshness": snapshot.get("regime_freshness"),
                "signal_ids": signal_ids,
            },
            parents=[data_parent] if data_parent else [],
            tags=["signal", "snapshot"],
            external_ids=[run_id, *signal_ids],
        )
    ]

    router = snapshot.get("router_decision") or snapshot.get("router") or {}
    for mode, key in (("live", "items"), ("shadow", "shadow_items")):
        for item in snapshot.get(key) or []:
            sid = str(item.get("signal_id") or "")
            if not sid:
                continue
            objects.append(
                upsert_object(
                    object_id=f"router_decision_{_safe_id(sid)}_{mode}",
                    object_type="router_decision",
                    status=str(item.get("outcome_status") or ("NO_TRADE" if item.get("entry_type") == "NO_TRADE" else item.get("status") or "PENDING")),
                    asof_date=str(snapshot.get("signal_date") or created_at[:10])[:10],
                    created_at=created_at,
                    source_system="signal_router",
                    source_run_id=run_id,
                    artifact_paths=[snapshot.get("snapshot_path")],
                    summary={
                        "signal_id": sid,
                        "execution_mode": mode,
                        "decision": item.get("status"),
                        "side": item.get("side"),
                        "entry_type": item.get("entry_type"),
                        "risk_scale": item.get("router_risk_scale") or router.get("risk_scale"),
                        "block_reason": item.get("router_block_reason") or router.get("block_reason"),
                        "reason_codes": item.get("reason_tags") or [],
                        "instrument": item.get("instrument"),
                        "score": item.get("score"),
                        "score_percentile": item.get("score_percentile"),
                        "router": router,
                    },
                    parents=[signal_object_id],
                    tags=["router", mode],
                    external_ids=[sid, run_id],
                )
            )
    return objects


def register_outcome_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    run_id = str(payload.get("source_run_id") or "")
    created_at = str(payload.get("computed_at") or _now_iso())
    parent = f"signal_snapshot_{_safe_id(run_id)}" if run_id else None
    aggregate_id = f"outcome_{_safe_id(run_id or created_at)}"
    objects = [
        upsert_object(
            object_id=aggregate_id,
            object_type="outcome",
            status=str(payload.get("status") or "OK"),
            asof_date=str(payload.get("signal_date") or created_at[:10])[:10],
            created_at=created_at,
            source_system="signal_outcome_service",
            source_run_id=run_id or None,
            artifact_paths=[payload.get("outcome_path"), payload.get("source_snapshot_path")],
            summary={
                "source_run_id": run_id,
                "computed_at": payload.get("computed_at"),
                "generated_count": payload.get("generated_count"),
                "shadow_generated_count": payload.get("shadow_generated_count"),
                "pending_count": payload.get("pending_count"),
                "shadow_pending_count": payload.get("shadow_pending_count"),
                "status_counts": payload.get("status_counts") or {},
                "shadow_status_counts": payload.get("shadow_status_counts") or {},
            },
            parents=[parent] if parent else [],
            tags=["outcome", "aggregate"],
            external_ids=[run_id],
        )
    ]

    for mode, key in (("live", "items"), ("shadow", "shadow_items")):
        for item in payload.get(key) or []:
            sid = str(item.get("signal_id") or "")
            if not sid:
                continue
            objects.append(
                upsert_object(
                    object_id=f"outcome_{_safe_id(sid)}_{mode}",
                    object_type="outcome",
                    status=str(item.get("outcome_status") or "PENDING"),
                    asof_date=str(item.get("signal_date") or payload.get("signal_date") or created_at[:10])[:10],
                    created_at=created_at,
                    source_system="signal_outcome_service",
                    source_run_id=run_id or None,
                    artifact_paths=[payload.get("outcome_path")],
                    summary={
                        "signal_id": sid,
                        "execution_mode": mode,
                        "instrument": item.get("instrument"),
                        "outcome_status": item.get("outcome_status"),
                        "entry_date": item.get("entry_date"),
                        "last_date": item.get("last_date"),
                        "holding_bars": item.get("holding_bars"),
                        "realized_pnl": item.get("realized_pnl"),
                        "unrealized_pnl": item.get("unrealized_pnl"),
                        "mfe": item.get("mfe"),
                        "mae": item.get("mae"),
                    },
                    parents=[f"router_decision_{_safe_id(sid)}_{mode}", aggregate_id],
                    tags=["outcome", mode],
                    external_ids=[sid, run_id],
                )
            )
    return objects


def register_report_artifact(result: Mapping[str, Any], *, report_type: str) -> dict[str, Any]:
    report_id = str(result.get("report_id") or "")
    if not report_id:
        raise ValueError("report artifact registration requires report_id")
    meta = result.get("meta") if isinstance(result.get("meta"), Mapping) else {}
    run_id = meta.get("run_id") or result.get("analysis_id")
    portfolio_id = meta.get("portfolio_id")
    backtest_id = meta.get("backtest_id")
    parents: list[str] = []
    if run_id and report_type == "qlib_factor_mining":
        parents.extend([f"factor_run_{_safe_id(run_id)}", f"validation_result_{_safe_id(run_id)}"])
    if portfolio_id:
        parents.append(f"portfolio_proposal_{_safe_id(portfolio_id)}")
    if backtest_id:
        parents.append(f"portfolio_proposal_{_safe_id(backtest_id)}")
    created_at = str(result.get("created_at") or _now_iso())
    return upsert_object(
        object_id=f"report_artifact_{_safe_id(report_id)}",
        object_type="report_artifact",
        status=str(result.get("status") or "SUCCESS"),
        asof_date=created_at[:10],
        created_at=created_at,
        source_system="report_service",
        source_run_id=report_id,
        artifact_paths=[result.get("html_path"), result.get("pdf_path")],
        summary={
            "report_id": report_id,
            "report_type": report_type,
            "analysis_id": result.get("analysis_id"),
            "run_id": run_id,
            "portfolio_id": portfolio_id,
            "backtest_id": backtest_id,
            "meta": meta,
        },
        parents=parents,
        tags=["report", report_type],
        external_ids=[report_id, run_id, portfolio_id, backtest_id],
    )


def register_external_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    query_id = str(payload.get("query_id") or payload.get("source_run_id") or "")
    if not query_id:
        raise ValueError("external evidence registration requires query_id")
    query = payload.get("query") if isinstance(payload.get("query"), Mapping) else {}
    fetched_at = str(payload.get("fetched_at") or _now_iso())
    status = "WARN" if payload.get("warnings") else "OK"
    endpoint = str(payload.get("endpoint") or "openbb")
    artifact_paths = [payload.get("artifact_path"), payload.get("items_artifact_path")]
    topic_or_symbol = query.get("term") or query.get("topics") or query.get("symbol") or query.get("country")
    return upsert_object(
        object_id=f"external_evidence_{_safe_id(query_id)}",
        object_type="external_evidence",
        status=status,
        asof_date=fetched_at[:10],
        created_at=fetched_at,
        source_system="openbb_information_service",
        source_run_id=query_id,
        artifact_paths=artifact_paths,
        summary={
            "query_id": query_id,
            "source": payload.get("source"),
            "endpoint": endpoint,
            "provider": payload.get("provider"),
            "query": dict(query),
            "count": payload.get("count"),
            "warnings": payload.get("warnings") or [],
            "topic_or_symbol": topic_or_symbol,
        },
        tags=["openbb", "external_evidence", endpoint.replace(".", "_")],
        external_ids=[query_id, endpoint, payload.get("provider"), topic_or_symbol],
    )


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def rebuild_index_from_artifacts(*, reset: bool = False) -> dict[str, Any]:
    if reset:
        reset_registry()
    stats: dict[str, Any] = {"registered": {}, "errors": []}

    def bump(key: str, count: int = 1) -> None:
        stats["registered"][key] = int(stats["registered"].get(key, 0)) + count

    def capture(key: str, fn) -> None:
        try:
            count = fn()
            bump(key, count if isinstance(count, int) else 1)
        except Exception as e:
            stats["errors"].append({"source": key, "message": str(e)})

    def data_snapshots() -> int:
        from app.services.data_maintenance_service import _maintenance_root

        count = 0
        root = _maintenance_root()
        for path in sorted(root.glob("*/*.json")):
            payload = _read_json(path)
            if not payload:
                continue
            audit = payload.get("audit") if isinstance(payload.get("audit"), Mapping) else payload
            if not isinstance(audit, Mapping):
                continue
            register_data_snapshot_from_audit(audit, run_id=payload.get("run_id"), artifacts=payload.get("artifacts"))
            count += 1
        return count

    def factor_runs() -> int:
        from app.services.run_store import list_runs

        count = 0
        for meta in list_runs(limit=1000):
            register_factor_run_artifact(meta)
            count += 1
        return count

    def qlib_mining() -> int:
        from app.services.native_qlib_research_service import _research_root

        count = 0
        for summary in _iter_jsonl(_research_root() / "factor_mining" / "history.jsonl"):
            register_factor_run_artifact({**summary, "source_system": "native_qlib_factor_mining"})
            register_validation_result_from_mining(summary)
            count += 2
        return count

    def portfolios() -> int:
        from app.services.native_qlib_research_service import _research_root

        count = 0
        for summary in _iter_jsonl(_research_root() / "portfolios" / "history.jsonl"):
            register_portfolio_proposal(summary)
            count += 1
        return count

    def signal_snapshots() -> int:
        from app.services.signal_generation_service import read_latest_signal_snapshot, read_signal_history

        count = 0
        latest = read_latest_signal_snapshot()
        if latest:
            count += len(register_signal_snapshot(latest))
        for snapshot in read_signal_history(limit=500):
            if latest and snapshot.get("source_run_id") == latest.get("source_run_id"):
                continue
            count += len(register_signal_snapshot(snapshot))
        return count

    def outcomes() -> int:
        from app.services.signal_outcome_service import read_latest_outcomes

        payload = read_latest_outcomes()
        if payload.get("status") == "NO_OUTCOMES":
            return 0
        return len(register_outcome_payload(payload))

    def backtests() -> int:
        from app.services.backtest_service import list_backtests

        count = 0
        for summary in list_backtests(limit=1000):
            register_backtest_artifact(summary)
            count += 1
        return count

    def reports() -> int:
        count = 0
        for report in _discover_report_artifacts():
            register_report_artifact(report, report_type=str(report.get("meta", {}).get("report_type") or report.get("report_type") or "unknown"))
            count += 1
        return count

    def quality_reports() -> int:
        try:
            from app.services.research_quality_service import quality_root
        except Exception:
            return 0
        count = 0
        status_map = {"PASS": "OK", "WARN": "WARN", "FAIL": "BLOCKED"}
        for path in sorted(quality_root().glob("*/quality_report.json")):
            report = _read_json(path)
            if not report:
                continue
            source_run_id = str(report.get("source_run_id") or path.parent.name)
            upsert_object(
                object_id=f"validation_result_quality_{_safe_id(source_run_id)}",
                object_type="validation_result",
                status=status_map.get(str(report.get("quality_status")), "WARN"),
                asof_date=str(report.get("asof_date") or report.get("evaluated_at") or "")[:10],
                created_at=str(report.get("evaluated_at") or _now_iso()),
                source_system="research_quality_guard",
                source_run_id=source_run_id,
                artifact_paths=[report.get("artifact_path"), report.get("findings_path")],
                summary={
                    "source_type": report.get("source_type"),
                    "source_run_id": source_run_id,
                    "quality_status": report.get("quality_status"),
                    "quality_score": report.get("quality_score"),
                    "promotion_status": report.get("promotion_status"),
                    "not_executable": report.get("not_executable"),
                    "reason_codes": report.get("reason_codes") or [],
                    "factor_status": report.get("factor_status") or {},
                    "timing_note": report.get("timing_note"),
                },
                parents=[f"factor_run_{_safe_id(source_run_id)}", f"validation_result_{_safe_id(source_run_id)}"],
                tags=["research_quality", str(report.get("quality_status") or "WARN").lower()],
                external_ids=[source_run_id, *(report.get("reason_codes") or [])],
            )
            count += 1
        return count

    def openbb_evidence() -> int:
        try:
            from app.services.openbb_information_service import openbb_root
        except Exception:
            return 0
        count = 0
        for path in sorted(openbb_root().glob("*/*/query_result.json")):
            payload = _read_json(path)
            if not payload:
                continue
            register_external_evidence(payload)
            count += 1
        return count

    for key, fn in (
        ("data_snapshot", data_snapshots),
        ("factor_run", factor_runs),
        ("qlib_factor_mining", qlib_mining),
        ("research_quality", quality_reports),
        ("openbb_evidence", openbb_evidence),
        ("portfolio_proposal", portfolios),
        ("signal_snapshot", signal_snapshots),
        ("outcome", outcomes),
        ("backtest", backtests),
        ("report_artifact", reports),
    ):
        capture(key, fn)

    index = rebuild_registry_indexes()
    stats.update({"status": "OK" if not stats["errors"] else "WARN", "index": index})
    return stats


def _discover_report_artifacts() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    try:
        from app.services.native_qlib_research_service import _research_root

        root = _research_root()
        for path in root.glob("factor_mining/*/report.html"):
            run_id = path.parent.name
            reports.append(
                {
                    "report_id": f"qlib_factor_mining_{run_id}",
                    "analysis_id": run_id,
                    "html_path": str(path),
                    "pdf_path": str(path.with_suffix(".pdf")) if path.with_suffix(".pdf").exists() else None,
                    "meta": {"run_id": run_id, "report_type": "qlib_factor_mining", "data_source": "qlib_factor_mining_artifacts"},
                }
            )
        for path in root.glob("portfolios/*/report.html"):
            portfolio_id = path.parent.name
            reports.append(
                {
                    "report_id": f"qlib_portfolio_backtest_{portfolio_id}",
                    "analysis_id": portfolio_id,
                    "html_path": str(path),
                    "pdf_path": str(path.with_suffix(".pdf")) if path.with_suffix(".pdf").exists() else None,
                    "meta": {
                        "portfolio_id": portfolio_id,
                        "report_type": "qlib_portfolio_backtest",
                        "data_source": "qlib_portfolio_backtest_artifacts",
                    },
                }
            )
    except Exception:
        return reports
    return reports
