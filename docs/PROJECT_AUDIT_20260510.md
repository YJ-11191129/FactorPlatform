# FactorPlatform Project Audit 2026-05-10

> Scope: data freshness, qlib CN/US providers, Stock Radar, Signal Center, backend API smoke, frontend build.

## Executive Summary

- Project is operational for qlib-based CN/US factor ranking and Signal Center snapshot display.
- CN qlib is fresh through `2026-05-08` using the daily-updated local `cn_data` provider.
- US qlib is fresh through `2026-05-08` after Yahoo-based incremental update.
- Stock Radar smoke tests passed for both CN and US providers.
- Signal Center snapshot generation passed and latest snapshot contains 30 signals for `2026-05-08`.
- Frontend production build passed with Next.js.
- Main remaining blocker is Wind A-share OHLCV freshness: latest is `2026-04-14`.

## Maintenance Run

- run_id: `data_maint_20260510_064047`
- generated_at: `2026-05-10T06:41:45Z`
- maintenance_status: `STALE`
- audit_overall_status: `STALE`
- blocking_status: `BLOCKED`
- status_counts: `{'OK': 5, 'STALE': 4}`

Artifacts:
- json_path: `D:\FactorPlatform\data\exports\data_maintenance\2026-05-10\data_maint_20260510_064047.json`
- latest_path: `D:\FactorPlatform\data\exports\data_maintenance\latest.json`
- markdown_path: `D:\FactorPlatform\data\exports\data_maintenance\2026-05-10\data_maint_20260510_064047.md`

## Data Source Status

| Source | Status | Start | End | Lag Days | Assets / Instruments | Features | Path |
|---|---:|---:|---:|---:|---|---:|---|
| `qlib_cn_daily` | `OK` | 2000-01-04 | 2026-05-08 | 2 | all=6091, csi1000=2739, csi300=939, csi500=1774, csi800=1993, csiall=5718 | 6091 | `D:\mcQlib\data\qlib_bin\cn_data` |
| `qlib_us_daily` | `OK` | 1999-12-31 | 2026-05-08 | 2 | all=8994, nasdaq100=283, sp500=745 | 9012 | `D:\mcQlib\data\qlib_bin\us_data` |
| `wind_stock_ohlcv` | `STALE` | 2018-01-02 | 2026-04-14 | 26 | 5493 | - | `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_ohlcv.parquet` |
| `wind_daily_basic` | `STALE` | 2018-01-02 | 2026-03-25 | 46 | 5493 | - | `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_basic.parquet` |
| `macro_cross_asset` | `STALE` | 2018-01-02 | 2026-03-25 | 46 | 7 | - | `D:\Kaggle\data\wind_data\03_market_state\macro_cross_asset_daily.parquet` |
| `financial_statement` | `STALE` | 2018-03-31 | 2025-12-31 | 130 | 5493 | - | `D:\Kaggle\data\processed\financial_statement.parquet` |
| `wind_root` | `OK` | - | - | - | - | - | `D:\Kaggle\data\wind_data` |
| `wind_master` | `OK` | - | - | - | - | - | `D:\Kaggle\data\wind_data\01_master` |
| `processed_root` | `OK` | - | - | - | - | - | `D:\Kaggle\data\processed` |

## Blocking Issues

- `wind_stock_ohlcv`: `STALE` | latest data date 2026-04-14 is 26 days old; freshness threshold is 5 days | `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_ohlcv.parquet`

## Maintenance Steps

| Step | Status | Key Result |
|---|---:|---|
| `refresh_factor_registry` | `SUCCESS` | `factor_count=190, path=D:\FactorPlatform\data\exports\factor_library\factor_registry.parquet` |
| `refresh_stock_screen` | `SUCCESS` | `asof_date=2026-03-25, row_count=3000, latest_path=D:\FactorPlatform\data\exports\factor_library\screened_universe_latest.parquet` |
| `signal_center_snapshot` | `SUCCESS` | `signal_date=2026-05-08, status=OK, snapshot_path=D:\FactorPlatform\data\exports\signal_center\latest_signals.json` |
| `stock_radar_smoke_cn` | `SUCCESS` | `universe=csi300, signal_date=2026-05-08, row_count=10, before=72` |
| `stock_radar_smoke_us` | `SUCCESS` | `universe=all, signal_date=2026-05-08, row_count=3, before=3` |

## Backend API Smoke

Passed:

- `GET /api/data-maintenance/paths` -> `200`
- `GET /api/data-maintenance/latest` -> `200`
- `GET /api/factors` -> `200`
- `GET /api/factor-library/screen/latest` -> `200`
- `GET /api/v1/signals/live` -> `200`, `items=20`, `signal_date=2026-05-08`
- `GET /api/v1/signals/history` -> `200`, `items=20`
- `GET /api/v1/signals/snapshots` -> `200`, `items=2`
- `GET /api/v1/signals/outcomes` -> `200`, `items=30`, `status=OK`, `signal_date=2026-05-08`
- `GET /api/v1/regime/current` -> `200`
- `GET /api/v1/regime/history` -> `200`, `items=1963`

Note: `/api/signal-center/signals` is not a valid route; the live Signal Center route is `/api/v1/signals/live`.

## Stock Radar Smoke

- CN `csi300`: `200`, `signal_date=2026-05-08`, `row_count=5`, top sample `SZ000823`, `SZ000636`, `SZ000036`.
- US `sp500`: `200`, `signal_date=2026-05-08`, `row_count=5`, top sample `APH`, `CDNS`, `BIO`.

## Frontend Build

Passed:

```powershell
cd D:\FactorPlatform\web
node node_modules/next/dist/bin/next build
```

Build output confirmed routes including `/data-maintenance`, `/signal-center`, `/stock-radar`, `/regime-monitor`, `/factors`, and `/backend/[...path]`.

## Known Gaps

- Wind OHLCV is stale at `2026-04-14`; this remains the primary blocker for Wind-backed A-share workflows.
- Wind daily basic and macro files are stale at `2026-03-25`.
- Financial statement PIT file is stale at `2025-12-31` relative to the 120-day threshold.
- US qlib `all` feature dirs are larger than active instrument counts because historical/failed/delisted symbols remain on disk; current `sp500` and `nasdaq100` instrument files are usable.

## Next Commands

Refresh Wind OHLCV once Wind API is usable:

```powershell
cd D:\FactorPlatform
python scripts\update_stock_daily_ohlcv.py --data-root D:\Kaggle\data\wind_data --start 2026-04-15 --end 2026-05-10
python scripts\run_daily_data_maintenance.py
```

Refresh qlib CN daily source:

```powershell
python scripts\download_chenditc_qlib_data.py --target-dir D:\mcQlib\data\qlib_bin\cn_data --keep-archive --retries 20
```

Refresh qlib US selected universes:

```powershell
python scripts\update_us_qlib_yahoo.py --provider-uri D:\mcQlib\data\qlib_bin\us_data --universes sp500 nasdaq100 --include-all-file --sleep 1 --retries 5 --max-failures 30
```
