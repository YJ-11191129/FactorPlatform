# REGIME_RESULT_REVIEW_20260329_NPDP_REPLY

## 1. ?? review ????????

- ?? fallback ??? `numpy` Gaussian cost + ?????NPDP??
- `event_hit_flag/event_hit_type` ?????????primary + secondary + lag fallback??
- ?? `GET /api/v1/regime/events` ??????
- `market_risk_level` ??????????? EXTREME ? LOW ????
- ?? V2 ??????????

## 2. V2 ??????

- best_case: penalty=12, min_size=20, jump=1
- breakpoints=91, density=4.664/100, avg_segment_len=21.44
- primary_hit=4, secondary_hit=8, total_hit=12

## 3. ???????????

- ???`penalty=12`, `min_size=20`, `jump=1`
- ???`D:/Kaggle/Data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet`
- ???`rows_snapshot=1951`, `rows_breakpoints=91`
- ???`total_hit=12`, `primary_hit=4`, `secondary_hit=8`
- ???`2026-03-25 / FRAGILE_HIGH_VOL / EXTREME_VOL / EXTREME / market_risk=HIGH`

## 4. ???????

- `docs/REGIME_EVENT_LIBRARY_SPEC.md`
- `docs/REGIME_PRIMARY_SECONDARY_HIT_EVAL_TEMPLATE.md`
- `docs/REGIME_TUNING_EXPERIMENT_MATRIX_V2.md`
- `scripts/run_regime_tuning_matrix_v2.py`

## 5. ????

- `data/exports/regime_engine/regime_tuning_matrix_v2.json`
- `data/exports/regime_engine/regime_tuning_matrix_v2.md`
- `data/exports/regime_engine/regime_snapshot_daily.parquet`
- `data/exports/regime_engine/regime_breakpoints.parquet`