# Data Audit 2026-05-10

> Generated from the latest FactorPlatform data maintenance report.

## Summary

- run_id: `data_maint_20260510_060334`
- generated_at: `2026-05-10T06:05:55Z`
- maintenance_status: `FAILED`
- audit_overall_status: `STALE`
- blocking_status: `BLOCKED`
- status_counts: `{'OK': 5, 'STALE': 4}`

## Key Findings

- `qlib_cn_daily` is now readable and fresh through `2026-05-08`.
- `qlib_us_daily` is fresh through `2026-05-08`.
- Stock Radar smoke tests passed for both CN and US qlib providers.
- `wind_stock_ohlcv` remains stale at `2026-04-14` and is the active blocking data freshness issue.
- `signal_center_snapshot` failed with `duplicated trade_date+asset_code detected`; this is a derived snapshot integrity issue, not a qlib download failure.

## Blockers

- `wind_stock_ohlcv`: `STALE` | latest data date 2026-04-14 is 26 days old; freshness threshold is 5 days | path: `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_ohlcv.parquet`

## Recommendations

- `wind_stock_ohlcv` -> `wind_ohlcv`: latest data date 2026-04-14 is 26 days old; freshness threshold is 5 days

## Sources

| Source | Status | Start | End | Lag Days | Rows | Assets / Instruments | Features | Path |
|---|---:|---:|---:|---:|---:|---|---:|---|
| `qlib_cn_daily` | `OK` | 2000-01-04 | 2026-05-08 | 2 | - | all=6091, csi1000=31005, csi300=15898, csi500=22000, csi800=58404, csiall=114117 | 6091 | `D:\mcQlib\data\qlib_bin\cn_data` |
| `qlib_us_daily` | `OK` | 1999-12-31 | 2026-05-08 | 2 | - | all=8994, nasdaq100=341, sp500=755 | 9012 | `D:\mcQlib\data\qlib_bin\us_data` |
| `wind_root` | `OK` | - | - | - | - | - | - | `D:\Kaggle\data\wind_data` |
| `wind_master` | `OK` | - | - | - | - | - | - | `D:\Kaggle\data\wind_data\01_master` |
| `wind_stock_ohlcv` | `STALE` | 2018-01-02 | 2026-04-14 | 26 | 11024451 | 5493 | - | `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_ohlcv.parquet` |
| `wind_daily_basic` | `STALE` | 2018-01-02 | 2026-03-25 | 46 | 10953042 | 5493 | - | `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_basic.parquet` |
| `macro_cross_asset` | `STALE` | 2018-01-02 | 2026-03-25 | 46 | 13958 | 7 | - | `D:\Kaggle\data\wind_data\03_market_state\macro_cross_asset_daily.parquet` |
| `financial_statement` | `STALE` | 2018-03-31 | 2025-12-31 | 130 | 175776 | 5493 | - | `D:\Kaggle\data\processed\financial_statement.parquet` |
| `processed_root` | `OK` | - | - | - | - | - | - | `D:\Kaggle\data\processed` |

## Notes

- `wind_stock_ohlcv`: latest data date 2026-04-14 is 26 days old; freshness threshold is 5 days
- `wind_daily_basic`: latest data date 2026-03-25 is 46 days old; freshness threshold is 5 days
- `macro_cross_asset`: latest data date 2026-03-25 is 46 days old; freshness threshold is 5 days
- `financial_statement`: latest data date 2025-12-31 is 130 days old; freshness threshold is 120 days

## Maintenance Steps

| Step | Status | Message / Result |
|---|---:|---|
| `refresh_factor_registry` | `SUCCESS` | `{'factor_count': 190, 'path': 'D:\\FactorPlatform\\data\\exports\\factor_library\\factor_registry.parquet'}` |
| `refresh_stock_screen` | `SUCCESS` | `{'screen_rule_id': 'screen_20260510_060337_888345', 'asof_date': '2026-03-25', 'row_count': 3000, 'latest_path': 'D:\\FactorPlatform\\data\\exports\\factor_library\\screened_universe_latest.parquet', 'history_path': 'D:\\FactorPlatform\\data\\exports\\factor_library\\screened_universe_history.parquet', 'financial_statement_path': 'D:\\Kaggle\\data\\processed\\financial_statement.parquet', 'financial_rows_used': 5493, 'financial_coverage_ratio': 1.0}` |
| `signal_center_snapshot` | `FAILED` | `duplicated trade_date+asset_code detected` |
| `stock_radar_smoke_cn` | `SUCCESS` | `{'universe': 'csi300', 'signal_date': '2026-05-08', 'effective_trade_date': 'next_trading_day', 'row_count_before_score_filter': 72, 'row_count': 10}` |
| `stock_radar_smoke_us` | `SUCCESS` | `{'universe': 'all', 'signal_date': '2026-05-08', 'effective_trade_date': 'next_trading_day', 'row_count_before_score_filter': 3, 'row_count': 3}` |

## Artifacts

- json_path: `D:\FactorPlatform\data\exports\data_maintenance\2026-05-10\data_maint_20260510_060334.json`
- latest_path: `D:\FactorPlatform\data\exports\data_maintenance\latest.json`
- markdown_path: `D:\FactorPlatform\data\exports\data_maintenance\2026-05-10\data_maint_20260510_060334.md`

## Immediate Next Fixes

1. Fix `signal_center_snapshot` duplicate `trade_date+asset_code` handling in the derived snapshot builder.
2. Refresh Wind OHLCV after Wind API is available:

```powershell
cd D:\FactorPlatform
python scripts\update_stock_daily_ohlcv.py --data-root D:\Kaggle\data\wind_data --start 2026-04-15 --end 2026-05-10
python scripts\run_daily_data_maintenance.py
```
