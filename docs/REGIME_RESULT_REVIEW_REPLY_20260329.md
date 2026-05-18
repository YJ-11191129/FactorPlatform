# REGIME_RESULT_REVIEW_REPLY_20260329

## 1. ??????

- ???`regime_v1_gaussian_cpd_npdp`?? `numpy` Gaussian cost + ?????
- ???`D:/Kaggle/Data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet`
- ???`min_size=20`, `penalty=10`, `jump=1`, `eps=1.0`, `min_samples=10`
- shock dates?`2020-02-03, 2022-04-25, 2024-10-09, 2025-04-07`

## 2. ????

- `rows_snapshot`: 1951
- `rows_breakpoints`: 91
- `date_range`: 2018-03-09 ~ 2026-03-25
- `latest`: 2026-03-25 / FRAGILE_HIGH_VOL / EXTREME_VOL / EXTREME / market_risk_level=HIGH

## 3. P0 ????

### 3.1 event_hit_flag ??? false
- total_hit=6, primary_hit=4, secondary_hit=2

### 3.2 market_risk_level ???
- ???? `EXTREME_VOL + EXTREME tail risk` -> `market_risk_level=HIGH`?????????

### 3.3 ???? shock ?????
- shock `2020-02-03` -> breakpoint `2020-02-03` (distance_days=0), hit=True (PRIMARY_SHOCK_HIT), severity=15.5098
- shock `2022-04-25` -> breakpoint `2022-04-25` (distance_days=0), hit=True (PRIMARY_SHOCK_HIT), severity=10.2935
- shock `2024-10-09` -> breakpoint `2024-10-09` (distance_days=0), hit=True (PRIMARY_SHOCK_HIT), severity=15.1111
- shock `2025-04-07` -> breakpoint `2025-04-07` (distance_days=0), hit=True (PRIMARY_SHOCK_HIT), severity=17.8536

## 4. ????

- regime_counts: `{'POST_SHOCK_REBOUND': 693, 'FRAGILE_HIGH_VOL': 609, 'TREND_RISK_ON': 337, 'LIQUIDITY_SHOCK': 290, 'CALM_LOW_VOL': 22}`
- volatility_counts: `{'NORMAL_VOL': 830, 'LOW_VOL': 442, 'HIGH_VOL': 371, 'EXTREME_VOL': 308}`
- market_risk_counts: `{'HIGH': 1324, 'LOW': 378, 'MEDIUM': 249}`

## 5. ????

- `data/exports/regime_engine/regime_snapshot_daily.parquet`
- `data/exports/regime_engine/regime_breakpoints.parquet`
- `data/exports/regime_engine/regime_run_real_summary_npdp.json`

## 6. ?????

1. ???? `penalty=12, min_size=25`???????? shock hit?
2. ? `event_hit_type` ?? API ????Regime Monitor / breakpoints table??
3. ? label mapping ?? `MID_VOL_TRANSITION`?????? CALM ???????