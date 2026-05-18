from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.app import app


def _probe_http(url: str, timeout: int = 5) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:  # nosec - internal localhost checks
            raw = resp.read(256_000)
            body: dict[str, Any] | None = None
            if "json" in (resp.headers.get("content-type") or ""):
                body = json.loads(raw.decode("utf-8"))
            return True, str(resp.status), body
    except URLError as e:
        return False, str(e), None
    except Exception as e:  # pragma: no cover
        return False, str(e), None


def _bool(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _env_enabled(name: str) -> bool:
    raw = os.getenv(name)
    return bool(raw) and raw.lower() not in {"0", "false", "no", "off"}


def run() -> dict[str, Any]:
    client = TestClient(app)
    backend_url = os.getenv("FACTOR_PLATFORM_E2E_BACKEND_URL", "http://127.0.0.1:8002").rstrip("/")
    frontend_url = os.getenv("FACTOR_PLATFORM_E2E_FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")
    out: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runtime": {"backend_url": backend_url, "frontend_url": frontend_url},
        "checks": [],
        "summary": {},
    }

    health = client.get("/health")
    out["checks"].append(
        {
            "name": "api_health",
            "status": _bool(health.status_code == 200 and (health.json() or {}).get("status") == "ok"),
            "http_status": health.status_code,
            "sample": health.json() if health.status_code == 200 else {},
        }
    )

    live = client.get("/api/v1/signals/live?page=1&page_size=1")
    live_body = live.json() if live.status_code == 200 else {}
    out["checks"].append(
        {
            "name": "signal_snapshot_read",
            "status": _bool(live.status_code == 200 and "items" in live_body and "status" in live_body),
            "http_status": live.status_code,
            "sample": {
                "status": live_body.get("status"),
                "generated_at": live_body.get("generated_at"),
                "signal_date": live_body.get("signal_date"),
                "source_run_id": live_body.get("source_run_id"),
                "total": live_body.get("total"),
                "counts": live_body.get("counts"),
                "router_decision": live_body.get("router_decision"),
                "regime_freshness": live_body.get("regime_freshness"),
            },
        }
    )

    data_source = live_body.get("data_source") if isinstance(live_body.get("data_source"), dict) else {}
    out["checks"].append(
        {
            "name": "cn_qlib_snapshot_metadata",
            "status": _bool(
                live.status_code == 200
                and bool(live_body.get("signal_date"))
                and str(data_source.get("universe") or "").lower() == "csi300"
                and isinstance(live_body.get("regime_freshness"), dict)
                and isinstance(live_body.get("router_decision"), dict)
            ),
            "http_status": live.status_code,
            "sample": {
                "provider_uri": data_source.get("provider_uri"),
                "universe": data_source.get("universe"),
                "signal_date": live_body.get("signal_date"),
                "regime_freshness": live_body.get("regime_freshness"),
            },
        }
    )

    shadow = client.get("/api/v1/signals/shadow?page=1&page_size=1")
    shadow_body = shadow.json() if shadow.status_code == 200 else {}
    counts = live_body.get("counts") if isinstance(live_body.get("counts"), dict) else {}
    router = live_body.get("router_decision") if isinstance(live_body.get("router_decision"), dict) else {}
    live_blocked = int(counts.get("router_blocked_count") or 0) > 0 or float(router.get("risk_scale") or 1.0) <= 0.0
    out["checks"].append(
        {
            "name": "shadow_candidates_available_when_live_blocked",
            "status": _bool(
                shadow.status_code == 200
                and shadow_body.get("execution_mode") == "shadow"
                and "items" in shadow_body
                and ((not live_blocked) or int(shadow_body.get("total") or 0) > 0)
            ),
            "http_status": shadow.status_code,
            "sample": {
                "live_blocked": live_blocked,
                "shadow_total": shadow_body.get("total"),
                "shadow_count": counts.get("shadow_count"),
            },
        }
    )

    refresh = client.post("/api/v1/signals/refresh", json={"dry_run": True})
    refresh_body = refresh.json() if refresh.status_code < 500 else {}
    out["checks"].append(
        {
            "name": "signal_snapshot_refresh_dry_run",
            "status": _bool(refresh.status_code == 200 and refresh_body.get("status") == "DRY_RUN"),
            "http_status": refresh.status_code,
            "sample": {
                "status": refresh_body.get("status"),
                "snapshot_path": refresh_body.get("snapshot_path"),
                "data_health": refresh_body.get("data_health"),
            },
        }
    )

    snapshots = client.get("/api/v1/signals/snapshots?limit=5")
    snapshots_body = snapshots.json() if snapshots.status_code == 200 else {}
    out["checks"].append(
        {
            "name": "signal_snapshot_history_index",
            "status": _bool(snapshots.status_code == 200 and "items" in snapshots_body and "retention_count" in snapshots_body),
            "http_status": snapshots.status_code,
            "sample": {"total": snapshots_body.get("total"), "latest": snapshots_body.get("latest")},
        }
    )

    perf = client.get("/api/v1/signals/performance/summary?execution_mode=live")
    perf_body = perf.json() if perf.status_code == 200 else {}
    out["checks"].append(
        {
            "name": "performance_uses_signal_outcomes",
            "status": _bool(
                perf.status_code == 200
                and perf_body.get("data_source") == "signal_outcomes"
                and perf_body.get("execution_mode") == "live"
            ),
            "http_status": perf.status_code,
            "sample": {
                "data_source": perf_body.get("data_source"),
                "execution_mode": perf_body.get("execution_mode"),
                "source_run_id": perf_body.get("source_run_id"),
                "computed_at": perf_body.get("computed_at"),
                "evaluated_signals": perf_body.get("evaluated_signals"),
                "no_trade_signals": perf_body.get("no_trade_signals"),
            },
        }
    )

    shadow_perf = client.get("/api/v1/signals/performance/summary?execution_mode=shadow")
    shadow_perf_body = shadow_perf.json() if shadow_perf.status_code == 200 else {}
    out["checks"].append(
        {
            "name": "shadow_performance_separate_from_live",
            "status": _bool(
                shadow_perf.status_code == 200
                and shadow_perf_body.get("data_source") == "signal_outcomes"
                and shadow_perf_body.get("execution_mode") == "shadow"
            ),
            "http_status": shadow_perf.status_code,
            "sample": {
                "data_source": shadow_perf_body.get("data_source"),
                "execution_mode": shadow_perf_body.get("execution_mode"),
                "total_signals": shadow_perf_body.get("total_signals"),
                "evaluated_signals": shadow_perf_body.get("evaluated_signals"),
            },
        }
    )

    outcomes_refresh = client.post("/api/v1/signals/outcomes/refresh", json={"dry_run": True})
    outcomes_body = outcomes_refresh.json() if outcomes_refresh.status_code < 500 else {}
    out["checks"].append(
        {
            "name": "signal_outcomes_refresh_dry_run",
            "status": _bool(outcomes_refresh.status_code == 200 and outcomes_body.get("data_source") == "signal_outcomes"),
            "http_status": outcomes_refresh.status_code,
            "sample": {
                "status": outcomes_body.get("status"),
                "generated_count": outcomes_body.get("generated_count"),
                "shadow_generated_count": outcomes_body.get("shadow_generated_count"),
                "pending_count": outcomes_body.get("pending_count"),
                "shadow_pending_count": outcomes_body.get("shadow_pending_count"),
                "dry_run": outcomes_body.get("dry_run"),
            },
        }
    )

    demo_disabled = not _env_enabled("NEXT_PUBLIC_ALLOW_MOCK_FALLBACK") and not _env_enabled("FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK")
    out["checks"].append(
        {
            "name": "production_mock_fallback_disabled",
            "status": _bool(demo_disabled),
            "sample": {
                "NEXT_PUBLIC_ALLOW_MOCK_FALLBACK": os.getenv("NEXT_PUBLIC_ALLOW_MOCK_FALLBACK"),
                "FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK": os.getenv("FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK"),
            },
        }
    )

    backend_ok, backend_note, backend_body = _probe_http(f"{backend_url}/health")
    frontend_ok, frontend_note, _frontend_body = _probe_http(frontend_url)
    proxy_ok, proxy_note, proxy_body = _probe_http(f"{frontend_url}/backend/api/v1/signals/live?page=1&page_size=1")
    out["checks"].extend(
        [
            {"name": "runtime_backend", "status": _bool(backend_ok), "note": backend_note, "sample": backend_body},
            {"name": "runtime_frontend", "status": _bool(frontend_ok), "note": frontend_note},
            {
                "name": "frontend_proxy_signal_live",
                "status": _bool(proxy_ok and isinstance(proxy_body, dict) and "items" in proxy_body),
                "note": proxy_note,
                "sample": {"status": proxy_body.get("status") if proxy_body else None},
            },
        ]
    )

    passed = sum(1 for check in out["checks"] if check["status"] == "PASS")
    total = len(out["checks"])
    out["summary"] = {"passed": passed, "total": total, "all_passed": passed == total}
    return out


def write_report(result: dict[str, Any], report_path: Path) -> None:
    lines: list[str] = [
        "# E2E Validation Report",
        "",
        f"- Generated At: {result['generated_at']}",
        f"- Backend URL: {result.get('runtime', {}).get('backend_url')}",
        f"- Frontend URL: {result.get('runtime', {}).get('frontend_url')}",
        f"- Passed: {result['summary']['passed']}/{result['summary']['total']}",
        f"- All Passed: {result['summary']['all_passed']}",
        "",
        "## Checks",
        "",
    ]
    for check in result["checks"]:
        lines.append(f"- {check['name']}: **{check['status']}**")
        if check.get("http_status") is not None:
            lines.append(f"  - http_status: {check['http_status']}")
        if check.get("note"):
            lines.append(f"  - note: {check['note']}")
        if check.get("sample") is not None:
            lines.append(f"  - sample: `{json.dumps(check['sample'], ensure_ascii=False, default=str)}`")
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    result = run()
    report = Path("docs") / "E2E_VALIDATION_REPORT.md"
    write_report(result, report)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"report={report}")
