# FactorPlatform Current Runbook

Updated: 2026-05-10

## Planning And Gap Register

The current project plan and gap register is maintained in:

- `docs/PROJECT_PLAN_AND_GAPS_20260510.md`

That document separates data freshness, which is owned by the Data Maintenance artifact, from platform/product gaps such as OpenBB runtime readiness, ResearchOps evidence lineage, qlib native readiness, PM cockpit work, and governance workflow.

## Current Runtime

The validated local runtime is:

- Backend: `http://127.0.0.1:8003`
- Frontend: `http://127.0.0.1:3001`

Ports `8002` and `3000` are currently occupied by `svchost` and reset HTTP requests on this machine. Use `8003/3001` unless those port proxy entries are cleaned up.

## Start Commands

Backend:

```powershell
cd D:\FactorPlatform
python -m uvicorn app.api.app:app --host 127.0.0.1 --port 8003
```

Frontend:

```powershell
cd D:\FactorPlatform\web
$env:BACKEND_ORIGIN = "http://127.0.0.1:8003"
npm run dev -- --hostname 127.0.0.1 --port 3001
```

## Signal Center Operations

Read latest live snapshot:

```powershell
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/live?page=1&page_size=20"
```

Read latest shadow candidates:

```powershell
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/shadow?page=1&page_size=20"
```

Generate a live snapshot:

```powershell
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/refresh" -Method Post -ContentType "application/json" -Body '{"topn":30}'
```

Refresh outcomes:

```powershell
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/outcomes/refresh" -Method Post -ContentType "application/json" -Body '{"horizon_days":10}'
```

Read performance:

```powershell
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/performance/summary?execution_mode=live"
Invoke-RestMethod "http://127.0.0.1:8003/api/v1/signals/performance/summary?execution_mode=shadow"
```

## Latest Signal Snapshot

- Provider: `D:\mcQlib\data\qlib_bin\cn_data`
- Universe: `csi300`
- Signal date: `2026-05-08`
- Source run id: `signal_20260510_064555_e83dbb`
- Generated count: `30`
- Blocked count: `30`
- Outcome status counts: `NO_TRADE=30`

The pipeline is producing real candidates, but the current router sets `risk_scale=0.0`, so no live trades are allowed.

After the double-track blocked work, a refreshed snapshot also contains:

- `shadow_items`: router-blocked Stock Radar candidates preserved for research validation.
- `router_decision`: current Regime/Router risk scale, blocked templates, and `block_reason`.
- `regime_freshness`: `regime_date`, `signal_date`, `freshness_lag_days`, and stale-block reason when applicable.
- `counts`: `live_active_count`, `router_blocked_count`, and `shadow_count`.

If `risk_scale=0`, live remains `NO_TRADE`; shadow rows are marked `execution_mode=shadow` and `not_executable=true`.

## Artifact Paths

Signal Center:

- `data/exports/signal_center/latest_signals.json`
- `data/exports/signal_center/latest_run.json`
- `data/exports/signal_center/history.jsonl`
- `data/exports/signal_center/latest_outcomes.json`
- `data/exports/signal_center/outcomes_history.jsonl`

Data Maintenance:

- `data/exports/data_maintenance/latest.json`
- `data/exports/data_maintenance/<date>/<run_id>.json`
- `data/exports/data_maintenance/<date>/<run_id>.md`

OpenBB evidence:

- `data/exports/openbb/latest_index.json`
- `data/exports/openbb/<date>/<query_id>/query_result.json`
- `data/exports/openbb/<date>/<query_id>/items.jsonl`

ResearchOps registry:

- `data/exports/research_ops/latest_index.json`
- `data/exports/research_ops/lineage_edges.jsonl`
- `data/exports/research_ops/objects/<object_type>/<object_id>.json`

## Environment Variables

- `FACTOR_PLATFORM_PROVIDER_URI`: default qlib provider for Signal Center
- `FACTOR_PLATFORM_SIGNAL_UNIVERSE`: default `csi300`
- `FACTOR_PLATFORM_SIGNAL_TOPN`: default `30`
- `FACTOR_PLATFORM_SIGNAL_CENTER_DIR`: Signal Center artifact directory
- `FACTOR_PLATFORM_SIGNAL_SNAPSHOT_KEEP`: snapshot history retention, default `50`
- `FACTOR_PLATFORM_OPENBB_DIR`: OpenBB evidence artifact directory
- `FACTOR_PLATFORM_OPENBB_CONFIG_DIR`: optional OpenBB config path shown in Data Maintenance
- `NEXT_PUBLIC_ALLOW_MOCK_FALLBACK=1`: explicitly enable frontend demo/mock fallback

Production mode should leave `NEXT_PUBLIC_ALLOW_MOCK_FALLBACK` unset.

OpenBB is optional. If the backend environment does not have `openbb` installed, `/api/openbb/status` returns `OPENBB_NOT_READY`; this is non-blocking for qlib/Wind trading data gates.

## Validation Commands

Unit tests:

```powershell
python -m pytest tests\unit -q
```

Frontend build:

```powershell
cd D:\FactorPlatform\web
node node_modules\next\dist\bin\next build
```

E2E with current runtime ports:

```powershell
cd D:\FactorPlatform
$env:FACTOR_PLATFORM_E2E_BACKEND_URL = "http://127.0.0.1:8003"
$env:FACTOR_PLATFORM_E2E_FRONTEND_URL = "http://127.0.0.1:3001"
python scripts\run_e2e_validation.py
```

Stack health:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_stack_health.ps1 -BackendPort 8003 -FrontendPort 3001 -UseWslProbe
```

Latest validation:

- Unit tests: `57 passed`
- Frontend build: passed
- E2E: `10/10 passed`
- Stack health: `PASS`

## Troubleshooting

- `NO_SNAPSHOT`: generate a snapshot with `/api/v1/signals/refresh`.
- `PENDING_OUTCOME`: signal exists, but post-entry daily price coverage is missing or outcomes have not been refreshed.
- `NO_TRADE`: Router/Regime blocked the candidate; performance excludes it from evaluated PnL.
- `SHADOW_PENDING`: a paper/shadow candidate exists, but post-entry daily bars do not yet cover the evaluation window.
- `SHADOW_EVALUATED`: a paper/shadow candidate has daily-bar outcome metrics. It is research-only and does not enter live PnL.
- `REGIME_STALE_BLOCKED`: Regime date lags signal date by more than one trading day. Live is blocked while shadow candidates can still be inspected.
- `OPENBB_NOT_READY`: OpenBB is not installed/configured in the backend runtime. Macro/News OpenBB evidence is unavailable, but trading data gates are not blocked.
- `QLIB_NOT_READY`: native qlib package/provider readiness is missing; qlib mining is blocked without generating fake results.
- `performance evaluated=0`: real outcome source is active, but no tradable signal has a realized/unrealized path yet.
- `DEMO` mode: check `NEXT_PUBLIC_ALLOW_MOCK_FALLBACK` and `FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK`.
- `8002/3000` reset connections: use `8003/3001` or remove the stale Windows port proxy/listener.

## Remaining Limits

- Outcome v1 uses daily OHLCV only.
- No intraday execution simulation, slippage, fees, or matching engine yet.
- Shock replay is still a future event-window replay engine.
- File-backed artifacts are not yet a multi-user production storage model.
