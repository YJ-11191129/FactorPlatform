# FactorPlatform Project Audit

> Date: 2026-05-10  
> Scope: data freshness gate, data maintenance, qlib CN/US data, Stock Radar, backtest gates, Signal Center live signal chain, frontend build  
> Status: platform can run historical qlib research and audited derived workflows; live Signal Center and live radar are intentionally blocked when critical data is stale.

## 1. Executive Summary

The project has moved from "can run demos" toward "runs only when data is explainably fresh enough".

Completed in the latest audit cycle:

- Data maintenance now returns `blocking_status`, `blockers`, `recommendations`, per-source `is_blocking`, and freshness reasons.
- Registered data updaters are wired behind explicit `updater_id` values:
  - `wind_ohlcv`
  - `qlib_cn_chenditc`
  - `qlib_us_yahoo_smoke`
  - `qlib_us_yahoo_full`
- Stock Radar and backtest APIs now enforce data freshness gates.
- Data Maintenance UI shows blockers, recommendations, latest report, and explicit updater buttons.
- Signal Center v1 now has a real daily live-signal chain:
  - data gate
  - Stock Radar candidates
  - Regime-derived router
  - file-backed signal snapshot
  - live/detail/router APIs reading the snapshot
- Daily maintenance can refresh a Signal Center snapshot and supports `--no-signal-center`.
- Frontend production build is now verified from this environment.

Current live blockers:

- `qlib_cn_daily` is stale: latest date `2020-09-25`.
- `wind_stock_ohlcv` is stale: latest date `2026-04-14`.
- Because CN qlib is stale, Signal Center default live snapshot generation is blocked until CN data is refreshed or a fresher provider is configured.

Important current improvement:

- `qlib_us_daily` is now fresh enough in the local audit: latest date `2026-05-08`.

## 2. Current Data Source Audit

Latest dry-run audit result on 2026-05-10:

- Overall status: `STALE`
- Blocking status: `BLOCKED`

Current source status:

| Source | Status | Start | End | Coverage |
|---|---:|---:|---:|---:|
| `qlib_cn_daily` | `STALE` | `1999-11-10` | `2020-09-25` | `all=3875`, `csi100=246`, `csi300=820`, `csi500=2017`, `features=3875` |
| `qlib_us_daily` | `OK` | `1999-12-31` | `2026-05-08` | `all=8994`, `nasdaq100=341`, `sp500=755`, `features=8994` |
| `wind_stock_ohlcv` | `STALE` | `2018-01-02` | `2026-04-14` | `rows=11024451`, `assets=5493` |
| `wind_daily_basic` | `STALE` | `2018-01-02` | `2026-03-25` | `rows=10953042`, `assets=5493` |
| `macro_cross_asset` | `STALE` | `2018-01-02` | `2026-03-25` | `rows=13958`, `assets=7` |
| `financial_statement` | `STALE` | `2018-03-31` | `2025-12-31` | `rows=175776`, `assets=5493` |

Blocking sources:

- `qlib_cn_daily`: `qlib_cn_chenditc` recommended.
- `wind_stock_ohlcv`: `wind_ohlcv` recommended.

Interpretation:

- US qlib can now support current US Stock Radar scenarios for `sp500` and `nasdaq100`.
- CN qlib still points to the old historical official package and blocks default CN live signal generation.
- Wind OHLCV remains the key blocker for live Wind-backed backtests and broader A-share live workflows.

## 3. Implemented Capabilities

### 3.1 Data Freshness Gate

Main files:

- `app/services/data_maintenance_service.py`
- `app/api/routers/data_maintenance.py`
- `web/src/app/data-maintenance/page.tsx`

Implemented behavior:

- `GET /api/data-maintenance/paths` reports:
  - `blocking_status`: `OK | WARN | BLOCKED`
  - `blockers`
  - `recommendations`
  - per-source `is_blocking`
  - per-source `freshness_reason`
- `POST /api/data-maintenance/daily-update` supports optional `updater_id`.
- Unknown updater IDs return explainable errors.
- Dry-run mode does not write maintenance reports or raw data.
- Data Maintenance UI distinguishes:
  - audit
  - derived artifact refresh
  - raw data updater execution

### 3.2 Stock Radar And Backtest Gates

Main files:

- `app/api/routers/factors.py`
- `app/api/routers/backtests.py`

Implemented behavior:

- Stock Radar rejects live runs when the selected qlib provider is `BLOCKED`.
- Backtests reject runs when the selected OHLCV source cannot cover the requested end date.
- Historical runs can proceed as `WARN` when stale data still covers the requested date.
- Responses include `data_health` metadata so UI/API consumers can show timing and freshness notes.

### 3.3 Signal Center Real Live Chain v1

Main files:

- `app/services/signal_generation_service.py`
- `app/api/routers/signal_center.py`
- `web/src/app/signal-center/page.tsx`
- `web/src/app/strategy-router/page.tsx`

Implemented behavior:

- Signal generation reuses Stock Radar and Regime Engine.
- Default signal factors:
  - `QLIB_ALPHA_ROC20_V1`
  - `QLIB_ALPHA_RSV20_V1`
  - `QLIB_ALPHA_STD20_V1`
- File-backed snapshots are written to:
  - `data/exports/signal_center/latest_signals.json`
  - `data/exports/signal_center/latest_run.json`
  - `data/exports/signal_center/history.jsonl`
- `GET /api/v1/signals/live` reads the latest snapshot only; it does not recompute on page load.
- `POST /api/v1/signals/refresh` explicitly generates a new snapshot.
- `GET /api/v1/signals/by-id/{signal_id}` returns real factor contribution data from the generated Stock Radar candidate.
- `GET /api/v1/strategy-router/current` is now computed from the latest Regime snapshot, not a static constant.

Router mapping:

| Regime | Risk scale | Behavior |
|---|---:|---|
| `LIQUIDITY_SHOCK` or extreme risk | `0.0` | observe-only / block aggressive templates |
| `FRAGILE_HIGH_VOL` | `0.4` | defensive templates |
| `POST_SHOCK_REBOUND` | `0.7` | rebound template |
| `TREND_RISK_ON` / stable | `1.0` | trend templates |
| `UNKNOWN` | `0.25` | conservative template only |

### 3.4 Existing Data Update Scripts

CN qlib daily refresh:

```powershell
cd D:\FactorPlatform
python scripts\download_chenditc_qlib_data.py --target-dir D:\mcQlib\data\qlib_bin\cn_data --keep-archive --retries 20
```

US qlib Yahoo smoke:

```powershell
cd D:\FactorPlatform
python scripts\update_us_qlib_yahoo.py --provider-uri D:\mcQlib\data\qlib_bin\us_data --symbols AAPL MSFT NVDA --start 2026-05-01 --end 2026-05-10 --dry-run --retries 3
```

US qlib Yahoo full first pass:

```powershell
cd D:\FactorPlatform
python scripts\update_us_qlib_yahoo.py --provider-uri D:\mcQlib\data\qlib_bin\us_data --universes sp500 nasdaq100 --backup --include-all-file --sleep 0.2 --retries 5
```

Wind OHLCV refresh:

```powershell
cd D:\FactorPlatform
python scripts\update_stock_daily_ohlcv.py --data-root D:\Kaggle\data\wind_data
```

## 4. Verification Results

Backend compile:

```powershell
python -m py_compile app\services\signal_generation_service.py app\api\routers\signal_center.py app\services\data_maintenance_service.py scripts\run_daily_data_maintenance.py
```

Unit tests:

```powershell
python -m pytest tests\unit -q
```

Result:

- `24 passed`

Frontend build:

```powershell
cd D:\FactorPlatform\web
node node_modules\next\dist\bin\next build
```

Result:

- Next.js production build passed.

Maintenance dry-runs:

```powershell
python scripts\run_daily_data_maintenance.py --dry-run --no-radar-smoke --no-stock-screen --no-factor-registry
python scripts\run_daily_data_maintenance.py --dry-run --no-signal-center --no-radar-smoke --no-stock-screen --no-factor-registry
```

Result:

- Both commands passed.
- Signal Center dry-run reported the expected CN qlib freshness block without writing a snapshot.

## 5. Known Gaps And Risks

### 5.1 CN qlib Still Blocks Default Signal Center

Default Signal Center generation uses `FACTOR_PLATFORM_PROVIDER_URI`, currently the CN provider:

```text
D:\mcQlib\data\qlib_bin\cn_data
```

That provider ends at `2020-09-25`, so live signal generation is correctly blocked.

Recommended fix:

```powershell
python scripts\download_chenditc_qlib_data.py --target-dir D:\mcQlib\data\qlib_bin\cn_data --keep-archive --retries 20
```

### 5.2 Wind Data Still Needs Operational Refresh

Wind OHLCV is stale at `2026-04-14`.

This affects:

- live Wind-backed backtests
- broad A-share production validation
- any Signal Center extension that depends on Wind parquet rather than qlib

Wind updates require the local Wind client to be installed, running, and logged in.

### 5.3 Signal Center Performance Is Still Placeholder

Live signals are now real snapshot outputs, but performance and attribution endpoints are still placeholder/static until actual signal outcomes are persisted.

Affected endpoints:

- `GET /api/v1/signals/performance/summary`
- `GET /api/v1/signals/performance/timeseries`
- `GET /api/v1/signals/performance/attribution`

These endpoints now label themselves as placeholder output.

### 5.4 Raw Data Updaters Are Explicit By Design

Daily maintenance does not silently download full raw data by default.

Use explicit updater IDs:

```powershell
python scripts\run_daily_data_maintenance.py --updater-id qlib_cn_chenditc
python scripts\run_daily_data_maintenance.py --updater-id qlib_us_yahoo_smoke
python scripts\run_daily_data_maintenance.py --updater-id qlib_us_yahoo_full
python scripts\run_daily_data_maintenance.py --updater-id wind_ohlcv
```

## 6. Recommended Next Steps

1. Refresh CN qlib through `qlib_cn_chenditc`, rerun maintenance, then generate the first real CN Signal Center snapshot.
2. Fix Wind login/start and refresh `wind_stock_ohlcv` to remove the live backtest blocker.
3. Persist Signal Center outcomes so performance/attribution can be replaced with real statistics.
4. Add a small frontend detail-page cleanup pass to remove remaining demo-only actions such as replay/subscribe/export messages.
5. Consider a US-specific Signal Center preset using the now-fresh `qlib_us_daily` provider.

## 7. Current Operational Commands

Audit only:

```powershell
cd D:\FactorPlatform
python scripts\run_daily_data_maintenance.py --dry-run
```

Audit without Signal Center snapshot planning:

```powershell
python scripts\run_daily_data_maintenance.py --dry-run --no-signal-center
```

Refresh derived artifacts only:

```powershell
python scripts\run_daily_data_maintenance.py --no-radar-smoke
```

Generate Signal Center snapshot through API:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8002/api/v1/signals/refresh -ContentType "application/json" -Body "{}"
```

Check qlib source dates:

```powershell
@'
from app.services.data_maintenance_service import audit_data_paths
out = audit_data_paths()
for item in out["sources"]:
    if item["source_id"] in {"qlib_cn_daily", "qlib_us_daily"}:
        print(item["source_id"], item["status"], item.get("start_date"), item.get("end_date"), item.get("instrument_counts"), item.get("feature_dir_count"))
'@ | python -
```

Run unit tests:

```powershell
python -m pytest tests\unit -q
```

Build frontend:

```powershell
cd D:\FactorPlatform\web
node node_modules\next\dist\bin\next build
```
