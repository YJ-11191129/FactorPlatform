from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.datahub.loaders.qlib_bin import read_calendar, read_instruments
from app.services.factor_library_master_service import (
    _build_factor_registry_df,
    _factor_registry_path,
    _strategy_registry_path,
    _build_strategy_registry_df,
    run_stock_screen,
)
from app.services.stock_radar_service import DEFAULT_QLIB_PROVIDER_URI, run_stock_radar


DEFAULT_WIND_ROOT = r"D:\Kaggle\data\wind_data"
DEFAULT_PROCESSED_ROOT = r"D:\Kaggle\data\processed"
DEFAULT_US_QLIB_PROVIDER_URI = r"D:\mcQlib\data\qlib_bin\us_data"
CRITICAL_SOURCE_IDS = {"qlib_cn_daily", "qlib_us_daily", "wind_stock_ohlcv"}
TRUTHY = {"1", "true", "True", "YES", "yes", "on", "ON"}
SOURCE_UPDATERS = {
    "qlib_cn_daily": "qlib_cn_chenditc",
    "qlib_us_daily": "qlib_us_yahoo_full",
    "wind_stock_ohlcv": "wind_ohlcv",
}


@dataclass(frozen=True)
class DataSourceSpec:
    source_id: str
    label: str
    path: Path
    kind: str
    freshness_days: int | None = 5
    date_columns: tuple[str, ...] = ("date", "trade_date", "report_date")
    asset_columns: tuple[str, ...] = ("wind_code", "asset_code", "code", "symbol")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _maintenance_root() -> Path:
    root = Path(os.getenv("FACTOR_PLATFORM_DATA_MAINTENANCE_DIR", str(_project_root() / "data" / "exports" / "data_maintenance")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        return None


def _size_bytes(path: Path) -> int | None:
    try:
        if path.is_file():
            return int(path.stat().st_size)
        return None
    except Exception:
        return None


def _days_since(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        d = pd.to_datetime(date_text).date()
    except Exception:
        return None
    return int((date.today() - d).days)


def _status_from_freshness(exists: bool, latest_date: str | None, freshness_days: int | None) -> str:
    if not exists:
        return "MISSING"
    if freshness_days is None or latest_date is None:
        return "OK"
    days = _days_since(latest_date)
    if days is None:
        return "WARN"
    return "STALE" if days > freshness_days else "OK"


def _stale_data_blocks() -> bool:
    return os.getenv("FACTOR_PLATFORM_STALE_DATA_BLOCKS", "1") in TRUTHY


def _norm_path(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _source_note(item: dict[str, Any]) -> str | None:
    if not item.get("exists"):
        return "source path does not exist"
    if item.get("status") == "STALE":
        latest = item.get("end_date") or "unknown"
        days = item.get("days_since_latest")
        threshold = item.get("freshness_days")
        return f"latest data date {latest} is {days} days old; freshness threshold is {threshold} days"
    if item.get("status") == "WARN":
        return "freshness could not be determined"
    return None


def _annotate_source(item: dict[str, Any]) -> dict[str, Any]:
    source_id = str(item.get("source_id") or "")
    note = _source_note(item)
    item["is_blocking"] = source_id in CRITICAL_SOURCE_IDS
    item["freshness_reason"] = note
    if note and note not in item.get("notes", []):
        item.setdefault("notes", []).append(note)
    return item


def _recommendations_for_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in sources:
        source_id = str(item.get("source_id") or "")
        updater_id = SOURCE_UPDATERS.get(source_id)
        if not updater_id:
            continue
        if item.get("status") not in {"MISSING", "STALE", "WARN"}:
            continue
        out.append(
            {
                "source_id": source_id,
                "status": item.get("status"),
                "updater_id": updater_id,
                "label": updater_id.replace("_", " "),
                "reason": item.get("freshness_reason") or "; ".join(item.get("notes") or []),
            }
        )
    return out


def _health_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = [
        {
            "source_id": item.get("source_id"),
            "label": item.get("label"),
            "status": item.get("status"),
            "path": item.get("path"),
            "reason": item.get("freshness_reason") or "; ".join(item.get("notes") or []),
            "updater_id": SOURCE_UPDATERS.get(str(item.get("source_id") or "")),
        }
        for item in sources
        if item.get("is_blocking") and (item.get("status") == "MISSING" or (item.get("status") == "STALE" and _stale_data_blocks()))
    ]
    if blockers:
        blocking_status = "BLOCKED"
    elif any(item.get("status") == "WARN" for item in sources if item.get("is_blocking")):
        blocking_status = "WARN"
    elif any(item.get("status") in {"STALE", "WARN"} for item in sources):
        blocking_status = "WARN"
    else:
        blocking_status = "OK"
    return {
        "blocking_status": blocking_status,
        "blockers": blockers,
        "recommendations": _recommendations_for_sources(sources),
    }


def configured_sources() -> list[DataSourceSpec]:
    wind_root = Path(os.getenv("FACTOR_PLATFORM_WIND_DATA_ROOT", DEFAULT_WIND_ROOT))
    processed_root = Path(os.getenv("FACTOR_PLATFORM_PROCESSED_DATA_ROOT", DEFAULT_PROCESSED_ROOT))
    qlib_provider = Path(os.getenv("FACTOR_PLATFORM_PROVIDER_URI", DEFAULT_QLIB_PROVIDER_URI))
    us_qlib_provider = Path(os.getenv("FACTOR_PLATFORM_US_PROVIDER_URI", DEFAULT_US_QLIB_PROVIDER_URI))
    real_ohlcv = Path(os.getenv("FACTOR_PLATFORM_REAL_OHLCV_PATH", str(wind_root / "02_daily_stock" / "stock_daily_ohlcv.parquet")))
    financial_statement = Path(os.getenv("FACTOR_PLATFORM_FINANCIAL_STATEMENT_PATH", str(processed_root / "financial_statement.parquet")))
    return [
        DataSourceSpec("qlib_cn_daily", "Qlib CN daily provider", qlib_provider, "qlib_provider", freshness_days=5),
        DataSourceSpec("qlib_us_daily", "Qlib US daily provider", us_qlib_provider, "qlib_provider", freshness_days=5),
        DataSourceSpec("wind_root", "Wind data root", wind_root, "directory", freshness_days=None),
        DataSourceSpec("wind_master", "Wind master data", wind_root / "01_master", "directory", freshness_days=None),
        DataSourceSpec("wind_stock_ohlcv", "Wind stock daily OHLCV", real_ohlcv, "parquet", freshness_days=5),
        DataSourceSpec("wind_daily_basic", "Wind stock daily basic", wind_root / "02_daily_stock" / "stock_daily_basic.parquet", "parquet", freshness_days=5),
        DataSourceSpec("macro_cross_asset", "Macro cross-asset daily", wind_root / "03_market_state" / "macro_cross_asset_daily.parquet", "parquet", freshness_days=5),
        DataSourceSpec("financial_statement", "Financial statement PIT data", financial_statement, "parquet", freshness_days=120, date_columns=("report_date", "ann_dt", "date")),
        DataSourceSpec("processed_root", "Processed data root", processed_root, "directory", freshness_days=None),
        DataSourceSpec("openbb_sdk", "OpenBB Python SDK", Path(os.getenv("FACTOR_PLATFORM_OPENBB_CONFIG_DIR", str(Path.home() / ".openbb_platform"))), "openbb_sdk", freshness_days=None),
    ]


def _read_parquet_status(spec: DataSourceSpec) -> dict[str, Any]:
    path = spec.path
    out: dict[str, Any] = {
        "source_id": spec.source_id,
        "label": spec.label,
        "path": str(path),
        "kind": spec.kind,
        "exists": path.exists(),
        "file_size_bytes": _size_bytes(path),
        "mtime": _mtime_iso(path),
        "row_count": None,
        "asset_count": None,
        "start_date": None,
        "end_date": None,
        "freshness_days": spec.freshness_days,
        "days_since_latest": None,
        "status": "MISSING",
        "notes": [],
    }
    if not path.exists():
        out["notes"].append("path does not exist")
        return out

    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(str(path))
        out["row_count"] = int(pf.metadata.num_rows)
        names = set(pf.schema.names)
        date_col = next((c for c in spec.date_columns if c in names), None)
        asset_col = next((c for c in spec.asset_columns if c in names), None)
        read_cols = [c for c in [date_col, asset_col] if c]
        if read_cols:
            df = pf.read(columns=read_cols).to_pandas()
            if date_col and not df.empty:
                d = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if not d.empty:
                    out["start_date"] = str(d.min().date())
                    out["end_date"] = str(d.max().date())
            if asset_col and not df.empty:
                out["asset_count"] = int(df[asset_col].dropna().astype(str).nunique())
    except Exception as e:
        out["notes"].append(f"parquet inspect failed: {e}")

    out["days_since_latest"] = _days_since(out["end_date"])
    out["status"] = _status_from_freshness(bool(out["exists"]), out["end_date"], spec.freshness_days)
    return out


def _read_directory_status(spec: DataSourceSpec) -> dict[str, Any]:
    path = spec.path
    out: dict[str, Any] = {
        "source_id": spec.source_id,
        "label": spec.label,
        "path": str(path),
        "kind": spec.kind,
        "exists": path.exists(),
        "file_size_bytes": None,
        "mtime": _mtime_iso(path) if path.exists() else None,
        "row_count": None,
        "asset_count": None,
        "start_date": None,
        "end_date": None,
        "freshness_days": spec.freshness_days,
        "days_since_latest": None,
        "status": "OK" if path.exists() else "MISSING",
        "notes": [],
    }
    if not path.exists():
        out["notes"].append("path does not exist")
        return out
    try:
        children = list(path.iterdir())
        out["child_count"] = len(children)
        out["sample_children"] = [c.name for c in children[:12]]
    except Exception as e:
        out["notes"].append(f"directory inspect failed: {e}")
    return out


def _read_qlib_status(spec: DataSourceSpec) -> dict[str, Any]:
    path = spec.path
    out = _read_directory_status(spec)
    out["calendar_count"] = None
    out["instrument_counts"] = {}
    out["feature_dir_count"] = None
    if not path.exists():
        return out

    try:
        cal = read_calendar(str(path))
        if len(cal):
            out["calendar_count"] = int(len(cal))
            out["start_date"] = str(cal.min().date())
            out["end_date"] = str(cal.max().date())
            out["days_since_latest"] = _days_since(out["end_date"])
    except Exception as e:
        out["notes"].append(f"qlib calendar inspect failed: {e}")

    try:
        ins_dir = path / "instruments"
        counts: dict[str, int] = {}
        if ins_dir.exists():
            for file in sorted(ins_dir.glob("*.txt")):
                try:
                    counts[file.stem] = len(read_instruments(str(path), file.stem))
                except Exception:
                    counts[file.stem] = len([line for line in file.read_text(encoding="utf-8").splitlines() if line.strip()])
        out["instrument_counts"] = counts
    except Exception as e:
        out["notes"].append(f"qlib instrument inspect failed: {e}")

    try:
        features = path / "features"
        if features.exists():
            out["feature_dir_count"] = len([p for p in features.iterdir() if p.is_dir()])
    except Exception as e:
        out["notes"].append(f"qlib features inspect failed: {e}")

    if not out["end_date"]:
        out["status"] = "WARN"
        if "qlib provider exists but calendar/latest date is unreadable" not in out["notes"]:
            out["notes"].append("qlib provider exists but calendar/latest date is unreadable")
    else:
        out["status"] = _status_from_freshness(bool(out["exists"]), out["end_date"], spec.freshness_days)
    return out


def _read_openbb_status(spec: DataSourceSpec) -> dict[str, Any]:
    try:
        from app.services.openbb_information_service import latest_openbb_index, openbb_status

        status = openbb_status()
        latest = latest_openbb_index() or {}
    except Exception as e:
        status = {
            "status": "WARN",
            "package_version": None,
            "available": {},
            "notes": [f"OpenBB readiness check failed: {e}"],
            "install_hint": "Install OpenBB in the backend Python environment: pip install openbb",
        }
        latest = {}

    notes = list(status.get("notes") or [])
    if status.get("install_hint"):
        notes.append(str(status.get("install_hint")))
    latest_history = latest.get("history") if isinstance(latest, dict) else []
    latest_entry = latest_history[0] if latest_history else None
    return {
        "source_id": spec.source_id,
        "label": spec.label,
        "path": "python:openbb",
        "kind": spec.kind,
        "exists": status.get("status") == "READY",
        "file_size_bytes": None,
        "mtime": None,
        "row_count": None,
        "asset_count": None,
        "start_date": None,
        "end_date": str(latest_entry.get("fetched_at"))[:10] if isinstance(latest_entry, dict) and latest_entry.get("fetched_at") else None,
        "freshness_days": spec.freshness_days,
        "days_since_latest": _days_since(str(latest_entry.get("fetched_at"))[:10]) if isinstance(latest_entry, dict) and latest_entry.get("fetched_at") else None,
        "status": status.get("status") or "WARN",
        "notes": notes,
        "package_version": status.get("package_version"),
        "available": status.get("available") or {},
        "latest_query": latest_entry,
    }


def audit_data_paths() -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    try:
        from app.services.market_data_repository import MarketDataRepository, postgres_market_data_enabled

        if postgres_market_data_enabled():
            db_sources = [dict(item) for item in MarketDataRepository().source_status_items()]
            if db_sources:
                sources.extend(_annotate_source(item) for item in db_sources)
    except Exception:
        sources = []

    if not sources:
        for spec in configured_sources():
            if spec.kind == "qlib_provider":
                item = _read_qlib_status(spec)
            elif spec.kind == "openbb_sdk":
                item = _read_openbb_status(spec)
            elif spec.kind == "parquet":
                item = _read_parquet_status(spec)
            else:
                item = _read_directory_status(spec)
            sources.append(_annotate_source(item))

    counts: dict[str, int] = {}
    for item in sources:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    overall = "OK"
    if counts.get("MISSING"):
        overall = "MISSING"
    elif counts.get("STALE"):
        overall = "STALE"
    elif counts.get("WARN"):
        overall = "WARN"

    health = _health_summary(sources)
    audit = {
        "generated_at": _now_iso(),
        "overall_status": overall,
        "blocking_status": health["blocking_status"],
        "blockers": health["blockers"],
        "recommendations": health["recommendations"],
        "status_counts": counts,
        "sources": sources,
    }
    try:
        from app.services.research_ops_registry import register_data_snapshot_from_audit

        register_data_snapshot_from_audit(audit)
    except Exception:
        pass
    return audit


def _parse_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _gate_from_source(item: dict[str, Any], requested_end_date: date | str | None = None) -> dict[str, Any]:
    requested = _parse_date(requested_end_date)
    latest = _parse_date(item.get("end_date"))
    source_id = str(item.get("source_id") or "")
    status = str(item.get("status") or "WARN")
    reason = item.get("freshness_reason") or "; ".join(item.get("notes") or [])
    base = {
        "source_id": source_id,
        "status": status,
        "source": item,
        "requested_end_date": requested.isoformat() if requested else None,
        "latest_date": latest.isoformat() if latest else None,
        "reason": reason,
        "recommendation": SOURCE_UPDATERS.get(source_id),
    }
    if status == "MISSING":
        return {**base, "blocking_status": "BLOCKED", "message": f"{source_id} is missing: {reason}"}
    if requested and latest and requested > latest:
        return {
            **base,
            "blocking_status": "BLOCKED",
            "message": f"{source_id} only has data through {latest.isoformat()}, requested {requested.isoformat()}",
        }
    if status == "STALE":
        if requested and latest and requested <= latest:
            return {
                **base,
                "blocking_status": "WARN",
                "message": f"{source_id} is stale for live use but valid for requested historical date {requested.isoformat()}",
            }
        if not _stale_data_blocks():
            return {
                **base,
                "blocking_status": "WARN",
                "message": f"{source_id} is stale for live use but allowed for roadshow/historical demo mode: {reason}",
            }
        return {**base, "blocking_status": "BLOCKED", "message": f"{source_id} is stale for live use: {reason}"}
    if status == "WARN":
        return {**base, "blocking_status": "WARN", "message": reason or f"{source_id} freshness is uncertain"}
    return {**base, "blocking_status": "OK", "message": f"{source_id} freshness is OK"}


def _source_from_audit(source_id: str) -> dict[str, Any] | None:
    audit = audit_data_paths()
    for item in audit["sources"]:
        if item.get("source_id") == source_id:
            return item
    return None


def evaluate_backtest_data_gate(
    requested_end_date: date | str | None = None,
    *,
    allow_latest_available: bool = False,
) -> dict[str, Any]:
    try:
        from app.services.market_data_repository import MarketDataRepository, postgres_market_data_enabled

        if postgres_market_data_enabled():
            item = MarketDataRepository().status_item("wind_stock_ohlcv")
            if item is not None:
                latest = _parse_date(item.get("end_date"))
                effective_end_date = requested_end_date
                using_latest_available = bool(allow_latest_available and requested_end_date is None and latest is not None)
                if using_latest_available:
                    effective_end_date = latest
                gate = _gate_from_source(_annotate_source(item), requested_end_date=effective_end_date)
                if using_latest_available:
                    gate["original_requested_end_date"] = None
                    gate["effective_end_date"] = latest.isoformat() if latest else None
                    gate["using_latest_available"] = True
                return gate
    except Exception:
        pass

    override = os.getenv("FACTOR_PLATFORM_BACKTEST_OHLCV_PATH")
    if override:
        item = _annotate_source(
            _read_parquet_status(
                DataSourceSpec(
                    "wind_stock_ohlcv",
                    "Backtest OHLCV",
                    Path(override),
                    "parquet",
                    freshness_days=5,
                )
            )
        )
    else:
        item = _source_from_audit("wind_stock_ohlcv")
    if item is None:
        return {"blocking_status": "BLOCKED", "message": "wind_stock_ohlcv source is not configured", "source_id": "wind_stock_ohlcv"}

    latest = _parse_date(item.get("end_date"))
    effective_end_date = requested_end_date
    using_latest_available = bool(allow_latest_available and requested_end_date is None and latest is not None)
    if using_latest_available:
        effective_end_date = latest

    gate = _gate_from_source(item, requested_end_date=effective_end_date)
    if using_latest_available:
        gate["original_requested_end_date"] = None
        gate["effective_end_date"] = latest.isoformat() if latest else None
        gate["using_latest_available"] = True
        if gate.get("blocking_status") == "WARN" and str(item.get("status") or "") == "STALE":
            reason = gate.get("reason") or item.get("freshness_reason") or "; ".join(item.get("notes") or [])
            gate["message"] = (
                f"wind_stock_ohlcv is stale for live use but backtest will run through "
                f"latest available historical date {latest.isoformat()}: {reason}"
            )
    return gate


def evaluate_stock_radar_data_gate(
    provider_uri: str,
    requested_end_date: date | str | None = None,
    *,
    allow_latest_available: bool = False,
) -> dict[str, Any]:
    def gate_for_item(item: dict[str, Any]) -> dict[str, Any]:
        latest = _parse_date(item.get("end_date"))
        effective_end_date = requested_end_date
        using_latest_available = bool(allow_latest_available and requested_end_date is None and latest is not None)
        if using_latest_available:
            effective_end_date = latest

        gate = _gate_from_source(item, requested_end_date=effective_end_date)
        if using_latest_available:
            gate["original_requested_end_date"] = None
            gate["effective_end_date"] = latest.isoformat() if latest else None
            gate["using_latest_available"] = True
            if gate.get("blocking_status") == "WARN" and str(item.get("status") or "") == "STALE":
                reason = gate.get("reason") or item.get("freshness_reason") or "; ".join(item.get("notes") or [])
                source_id = str(item.get("source_id") or "qlib_daily")
                gate["message"] = (
                    f"{source_id} is stale for live use but backtest will run through "
                    f"latest available historical date {latest.isoformat()}: {reason}"
                )
        return gate

    try:
        from app.services.market_data_repository import MarketDataRepository, postgres_market_data_enabled, resolve_market_source_id

        if postgres_market_data_enabled():
            source_id = resolve_market_source_id(provider_uri=provider_uri)
            item = MarketDataRepository().status_item(source_id)
            if item is not None:
                item["is_blocking"] = True
                return gate_for_item(_annotate_source(item))
    except Exception:
        pass

    provider_norm = _norm_path(provider_uri)
    for spec in configured_sources():
        if spec.kind == "qlib_provider" and _norm_path(spec.path) == provider_norm:
            item = _source_from_audit(spec.source_id)
            if item is None:
                break
            return gate_for_item(item)

    item = _annotate_source(
        _read_qlib_status(
            DataSourceSpec(
                "qlib_custom_daily",
                "Custom qlib daily provider",
                Path(provider_uri),
                "qlib_provider",
                freshness_days=5,
            )
        )
    )
    item["is_blocking"] = True
    return gate_for_item(item)


def _write_report(payload: dict[str, Any], run_id: str) -> dict[str, str]:
    root = _maintenance_root()
    day_dir = root / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    json_path = day_dir / f"{run_id}.json"
    latest_path = root / "latest.json"
    md_path = day_dir / f"{run_id}.md"
    artifacts = {"json_path": str(json_path), "latest_path": str(latest_path), "markdown_path": str(md_path)}
    payload["artifacts"] = artifacts
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    latest_path.write_text(json_text, encoding="utf-8")
    lines = [
        f"# Data Maintenance Report {run_id}",
        "",
        f"- generated_at: {payload.get('generated_at')}",
        f"- overall_status: {payload.get('overall_status')}",
        f"- blocking_status: {payload.get('audit', {}).get('blocking_status')}",
        "",
        "## Blockers",
    ]
    for item in payload.get("audit", {}).get("blockers", []):
        lines.append(f"- {item.get('source_id')}: {item.get('status')} | {item.get('reason')}")
    lines.extend([
        "",
        "## Sources",
    ])
    for item in payload.get("audit", {}).get("sources", []):
        lines.append(
            f"- {item.get('source_id')}: {item.get('status')} | {item.get('path')} | latest={item.get('end_date')} | rows={item.get('row_count')}"
        )
    lines.extend(["", "## Steps"])
    for step in payload.get("steps", []):
        lines.append(f"- {step.get('name')}: {step.get('status')} {step.get('message', '')}")
    artifacts_status = payload.get("signal_center_artifacts") or {}
    lines.extend(
        [
            "",
            "## Signal Center Artifacts",
            f"- snapshot_status: {artifacts_status.get('snapshot_status')}",
            f"- snapshot_generated_at: {artifacts_status.get('snapshot_generated_at')}",
            f"- outcome_status: {artifacts_status.get('outcome_status')}",
            f"- outcome_computed_at: {artifacts_status.get('outcome_computed_at')}",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    try:
        from app.services.artifact_service import register_artifact

        artifacts["json_artifact_id"] = register_artifact(json_path, artifact_type="data_maintenance_report", run_id=run_id, file_type="json").get("artifact_id")
        artifacts["markdown_artifact_id"] = register_artifact(md_path, artifact_type="data_maintenance_report", run_id=run_id, file_type="md").get("artifact_id")
    except Exception:
        pass
    return artifacts


def _refresh_factor_registry() -> dict[str, Any]:
    df = _build_factor_registry_df()
    sp = _strategy_registry_path()
    _factor_registry_path().parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_factor_registry_path(), index=False)
    if not sp.exists():
        _build_strategy_registry_df().to_parquet(sp, index=False)
    return {"factor_count": int(df.shape[0]), "path": str(_factor_registry_path())}


def _run_external_updater() -> dict[str, Any]:
    command = os.getenv("FACTOR_PLATFORM_DATA_UPDATE_COMMAND", "").strip()
    if not command:
        return {"skipped": True, "message": "FACTOR_PLATFORM_DATA_UPDATE_COMMAND is not configured"}
    proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60 * 60)
    if proc.returncode != 0:
        raise RuntimeError(f"external updater failed rc={proc.returncode}: {proc.stderr[-2000:] or proc.stdout[-2000:]}")
    return {
        "skipped": False,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _run_command(args: list[str], timeout_seconds: int = 60 * 60) -> dict[str, Any]:
    proc = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=timeout_seconds)
    result = {
        "command": args,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    if proc.returncode != 0:
        raise RuntimeError(f"updater failed rc={proc.returncode}: {proc.stderr[-2000:] or proc.stdout[-2000:]}")
    return result


def _registered_updater_command(updater_id: str) -> list[str]:
    root = _project_root()
    wind_root = Path(os.getenv("FACTOR_PLATFORM_WIND_DATA_ROOT", DEFAULT_WIND_ROOT))
    qlib_provider = Path(os.getenv("FACTOR_PLATFORM_PROVIDER_URI", DEFAULT_QLIB_PROVIDER_URI))
    us_qlib_provider = Path(os.getenv("FACTOR_PLATFORM_US_PROVIDER_URI", DEFAULT_US_QLIB_PROVIDER_URI))
    commands = {
        "wind_ohlcv": [
            sys.executable,
            str(root / "scripts" / "update_stock_daily_ohlcv.py"),
            "--data-root",
            str(wind_root),
        ],
        "qlib_cn_chenditc": [
            sys.executable,
            str(root / "scripts" / "download_chenditc_qlib_data.py"),
            "--target-dir",
            str(qlib_provider),
            "--keep-archive",
            "--retries",
            "20",
        ],
        "qlib_us_yahoo_smoke": [
            sys.executable,
            str(root / "scripts" / "update_us_qlib_yahoo.py"),
            "--provider-uri",
            str(us_qlib_provider),
            "--symbols",
            "AAPL",
            "MSFT",
            "NVDA",
            "--dry-run",
            "--retries",
            "3",
        ],
        "qlib_us_yahoo_full": [
            sys.executable,
            str(root / "scripts" / "update_us_qlib_yahoo.py"),
            "--provider-uri",
            str(us_qlib_provider),
            "--universes",
            "sp500",
            "nasdaq100",
            "--backup",
            "--include-all-file",
            "--sleep",
            "0.2",
            "--retries",
            "5",
            "--workers",
            "8",
        ],
    }
    try:
        return commands[updater_id]
    except KeyError:
        known = ", ".join(sorted(commands))
        raise ValueError(f"unknown updater_id={updater_id}; available updaters: {known}") from None


def _run_registered_updater(updater_id: str) -> dict[str, Any]:
    command = _registered_updater_command(updater_id)
    return _run_command(command)


def _run_cn_radar_smoke() -> dict[str, Any]:
    return {
        k: v
        for k, v in run_stock_radar(
            universe="csi300",
            instrument_limit=80,
            topn=10,
            factors=[
                {"factor_name": "QLIB_ALPHA_ROC20_V1", "params": {}, "weight": 0.4, "direction": "positive"},
                {"factor_name": "QLIB_ALPHA_RANK20_V1", "params": {}, "weight": 0.25, "direction": "positive"},
                {"factor_name": "QLIB_ALPHA_SUMP20_V1", "params": {}, "weight": 0.35, "direction": "positive"},
            ],
        ).items()
        if k in {"universe", "signal_date", "effective_trade_date", "row_count", "row_count_before_score_filter"}
    }


def _run_us_radar_smoke() -> dict[str, Any]:
    provider_uri = os.getenv("FACTOR_PLATFORM_US_PROVIDER_URI", DEFAULT_US_QLIB_PROVIDER_URI)
    return {
        k: v
        for k, v in run_stock_radar(
            provider_uri=provider_uri,
            universe="all",
            instrument_limit=20,
            topn=10,
            factors=[
                {"factor_name": "QLIB_ALPHA_ROC20_V1", "params": {}, "weight": 0.5, "direction": "positive"},
                {"factor_name": "QLIB_ALPHA_MA20_V1", "params": {}, "weight": 0.5, "direction": "positive"},
            ],
        ).items()
        if k in {"universe", "signal_date", "effective_trade_date", "row_count", "row_count_before_score_filter"}
    }


def _run_signal_center_snapshot(*, dry_run: bool = False) -> dict[str, Any]:
    from app.services.signal_generation_service import generate_signal_snapshot

    return generate_signal_snapshot(dry_run=dry_run)


def _signal_center_artifact_status() -> dict[str, Any]:
    try:
        from app.services.signal_generation_service import read_latest_signal_snapshot
        from app.services.signal_outcome_service import read_latest_outcomes

        snapshot = read_latest_signal_snapshot() or {}
        outcomes = read_latest_outcomes()
        return {
            "snapshot_status": snapshot.get("status") or "NO_SNAPSHOT",
            "snapshot_generated_at": snapshot.get("generated_at"),
            "signal_date": snapshot.get("signal_date"),
            "source_run_id": snapshot.get("source_run_id") or outcomes.get("source_run_id"),
            "outcome_status": outcomes.get("status") or "NO_OUTCOMES",
            "outcome_computed_at": outcomes.get("computed_at"),
            "outcome_count": outcomes.get("generated_count", 0),
            "outcome_pending_count": outcomes.get("pending_count", 0),
        }
    except Exception as e:
        return {"snapshot_status": "UNKNOWN", "outcome_status": "UNKNOWN", "message": str(e)}


def run_daily_data_maintenance(
    *,
    dry_run: bool = False,
    refresh_factor_registry: bool = True,
    refresh_stock_screen: bool = True,
    refresh_signal_center_snapshot: bool = True,
    run_radar_smoke: bool = True,
    run_external_updater: bool = False,
    updater_id: str | None = None,
) -> dict[str, Any]:
    run_id = f"data_maint_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    steps: list[dict[str, Any]] = []
    audit_before = audit_data_paths()

    def step(name: str, fn) -> None:
        if dry_run:
            steps.append({"name": name, "status": "SKIPPED", "message": "dry_run=true"})
            return
        try:
            result = fn()
            steps.append({"name": name, "status": "SUCCESS", "result": result})
        except Exception as e:
            steps.append({"name": name, "status": "FAILED", "message": str(e)})

    if updater_id:
        _registered_updater_command(updater_id)
        step(f"data_updater_{updater_id}", lambda: _run_registered_updater(updater_id))
    if run_external_updater:
        step("external_data_updater", _run_external_updater)
    if refresh_factor_registry:
        step("refresh_factor_registry", _refresh_factor_registry)
    if refresh_stock_screen:
        step("refresh_stock_screen", lambda: run_stock_screen(topn=3000))
    if refresh_signal_center_snapshot:
        try:
            signal_result = _run_signal_center_snapshot(dry_run=dry_run)
            if dry_run:
                steps.append({"name": "signal_center_snapshot", "status": "SKIPPED", "message": "dry_run=true", "result": signal_result})
            elif signal_result.get("status") == "BLOCKED":
                steps.append(
                    {
                        "name": "signal_center_snapshot",
                        "status": "SKIPPED",
                        "message": signal_result.get("message") or "data freshness gate blocked Signal Center snapshot generation",
                        "result": signal_result,
                    }
                )
            else:
                steps.append({"name": "signal_center_snapshot", "status": "SUCCESS", "result": signal_result})
        except Exception as e:
            steps.append({"name": "signal_center_snapshot", "status": "FAILED", "message": str(e)})
    if run_radar_smoke:
        step("stock_radar_smoke_cn", _run_cn_radar_smoke)
        step("stock_radar_smoke_us", _run_us_radar_smoke)

    audit_after = audit_data_paths() if not dry_run else audit_before
    failed = [s for s in steps if s.get("status") == "FAILED"]
    payload = {
        "run_id": run_id,
        "generated_at": _now_iso(),
        "dry_run": dry_run,
        "overall_status": "FAILED" if failed else audit_after["overall_status"],
        "audit": audit_after,
        "audit_before": audit_before,
        "signal_center_artifacts": _signal_center_artifact_status(),
        "steps": steps,
    }
    if not dry_run:
        payload["artifacts"] = _write_report(payload, run_id)
        try:
            from app.services.research_ops_registry import register_data_snapshot_from_audit

            register_data_snapshot_from_audit(audit_after, run_id=run_id, artifacts=payload.get("artifacts"))
        except Exception:
            pass
    return payload


def read_latest_maintenance_report() -> dict[str, Any] | None:
    path = _maintenance_root() / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
