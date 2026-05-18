# Stock Radar Implementation

## Goal

Stock Radar ranks stocks from a selected qlib universe, then applies a second-stage score filter on the computed factor scores.

## Data Source

- Primary source: qlib binary daily data.
- Default provider: `D:\mcQlib\data\qlib_bin\cn_data`.
- Universe files: `instruments/csi300.txt`, `csi500.txt`, `csi100.txt`, `all.txt`.
- Daily bars loaded by: `app/datahub/loaders/qlib_bin.py`.

## Timing Assumption

- Factor values are observed using data through `signal_date`.
- Rankings are formed on `signal_date`.
- Any portfolio trade based on the ranking should execute no earlier than the next trading day.

This avoids using future information in the radar output.

## Backend

- Service: `app/services/stock_radar_service.py`
- API schema: `app/api/schemas/factors.py`
- API route: `POST /api/factor-library/radar/run`

Default factors:

- `MOM_RET_N_D_V1`, parameter `n=20`
- `TREND_MA_BIAS_N_D_V1`, parameter `n=20`

Qlib Alpha factor extension:

- Module: `app/factors/qlib_alpha.py`
- Category: `QLIB_ALPHA`
- Factor name format: `QLIB_ALPHA_<NAME>_V1`
- Data dependency: qlib_bin daily `open/high/low/close/volume`; no native `qlib` Python package is required.
- Fixed-expression qlib factors use `params={}` in radar payloads.

Registered qlib Alpha factors:

- Verified Alpha15 subset: `CNTP30`, `IMAX30`, `KMID`, `KMID2`, `KSFT2`, `LOW0`, `MA60`, `MAX20`, `MIN5`, `QTLD10`, `RANK20`, `SUMD60`, `SUMP5`, `VSTD30`, `VSUMP20`
- Extra OHLCV factors: `KLEN`, `KUP`, `KUP2`, `KLOW`, `KLOW2`, `KSFT`, `OPEN0`, `HIGH0`, `CLOSE0`, `MA5`, `MA10`, `MA20`, `STD5`, `STD10`, `STD20`, `ROC5`, `ROC10`, `ROC20`, `ROC60`, `VMA5`, `VMA20`, `VMA60`, `VSTD5`, `VSTD20`, `VSTD60`

Score pipeline:

1. Load universe daily bars from qlib.
2. Compute each registered factor.
3. Select latest available `signal_date`, or requested `asof_date`.
4. Winsorize each factor cross-section.
5. Convert each factor to robust z-score.
6. Apply factor direction: positive means higher is better, negative means lower is better.
7. Drop stocks with fewer valid factors than `min_factor_count`.
8. Compute weighted composite score.
9. Sort descending and apply `min_score` / `topn`.

Additional result fields:

- `row_count_on_signal_date`: stock rows loaded on the signal date.
- `valid_factor_count`: number of non-null factor scores for each stock.
- `factor_coverage`: valid factor ratio for each stock.
- `effective_trade_date`: next qlib trading day when available, otherwise `next_trading_day`.

## Frontend

- Page: `web/src/app/stock-radar/page.tsx`
- Sidebar entry: `Stock Radar`
- API client: `web/src/lib/api/factors.ts`

Supported controls:

- qlib provider path
- universe
- instrument limit
- `topn`
- minimum composite score
- minimum valid factor count
- optional date window / as-of date
- factor name
- factor lookback `n`
- factor weight
- factor direction
- CSV export of the current result table
- dynamic factor selector loaded from `GET /api/factors`
- grouped factor options by category, including `QLIB_ALPHA`
- fixed-expression qlib factors hide the `N` parameter and submit empty params

## Current Limitation

This version implements a stable pandas recreation of selected qlib Alpha-style expressions over local qlib_bin data. Native qlib Alpha158/Alpha360 full-pool execution is intentionally not required yet because the active Python environment does not currently provide the `qlib` package and the local CN qlib data does not include `vwap.day.bin`.

## Verification Snapshot

Latest implementation smoke results:

- `GET /api/factors`: 42 total factors, 40 `QLIB_ALPHA` factors.
- Backend radar payload with `QLIB_ALPHA_SUMP5_V1 + QLIB_ALPHA_MA60_V1`: `200`, `signal_date=2020-09-25`, `row_count=5` with `instrument_limit=30`.
- Frontend production proxy `/backend/api/factor-library/radar/run`: `200` with the same qlib Alpha payload.
- `npm run build`: passes when `D:\Qxlib\data\_tools\node-v20.19.0-win-x64` is prepended to `PATH`.
