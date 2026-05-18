# Data Maintenance

This project now has a daily data maintenance layer for local data path audit and derived artifact refresh.

## Default Data Paths

- Qlib CN daily provider: `D:\mcQlib\data\qlib_bin\cn_data`
- Qlib US daily provider: `D:\mcQlib\data\qlib_bin\us_data`
- Wind root: `D:\Kaggle\data\wind_data`
- Stock OHLCV: `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_ohlcv.parquet`
- Daily basic: `D:\Kaggle\data\wind_data\02_daily_stock\stock_daily_basic.parquet`
- Macro cross asset: `D:\Kaggle\data\wind_data\03_market_state\macro_cross_asset_daily.parquet`
- Financial statement: `D:\Kaggle\data\processed\financial_statement.parquet`

All paths can be overridden with the environment variables shown in `.env.local.example`.

## API

- `GET /api/data-maintenance/paths`
- `POST /api/data-maintenance/daily-update`
- `GET /api/data-maintenance/latest`

The daily update endpoint can refresh:

- factor registry parquet
- stock screen latest/history artifacts
- Stock Radar smoke tests using CN and US qlib daily bars
- optional external updater configured by `FACTOR_PLATFORM_DATA_UPDATE_COMMAND`

The default flow does not download remote data and does not mutate raw Wind/qlib source files.

Current US qlib note: the local `us_data` path now points to the official
historical qlib US daily package. It includes `all`, `sp500`, and `nasdaq100`
instrument files, but the official package is historical and may not be current
to today's date.

## Bring Raw Data To Today

Raw data updates are intentionally separate from the default maintenance run.
Before running these commands, make sure the Wind client is installed, running,
and logged in.

Update A-share OHLCV parquet:

```powershell
cd D:\FactorPlatform
python scripts\update_stock_daily_ohlcv.py --data-root D:\Kaggle\data\wind_data --start 2026-04-15 --end 2026-05-06
```

Refresh CN qlib data from the daily-updated `chenditc/investment_data` release:

```powershell
cd D:\FactorPlatform
python scripts\download_chenditc_qlib_data.py --target-dir D:\mcQlib\data\qlib_bin\cn_data --keep-archive --retries 20
```

Refresh the current local US qlib dataset from Wind when Wind API is available:

```powershell
cd D:\FactorPlatform
python D:\mcQlib\tools\wind_to_qlib.py --start 2005-01-01 --end 2026-05-06 --output-dir D:\mcQlib\data\qlib_bin\us_data
```

Refresh US qlib data from Yahoo Chart API without Wind or native qlib:

```powershell
cd D:\FactorPlatform
python scripts\update_us_qlib_yahoo.py --provider-uri D:\mcQlib\data\qlib_bin\us_data --universes sp500 nasdaq100 --backup --include-all-file --sleep 0.2 --retries 5
```

For a small smoke test before the full update:

```powershell
cd D:\FactorPlatform
python scripts\update_us_qlib_yahoo.py --provider-uri D:\mcQlib\data\qlib_bin\us_data --symbols AAPL MSFT NVDA --start 2026-05-01 --end 2026-05-10 --dry-run --retries 3
```

The Yahoo updater defaults to `start = current us_data calendar latest + 1 day`
and `end = today`. It updates selected feature directories, extends
`calendars/day.txt`, and adjusts `sp500` / `nasdaq100` instrument end dates.
Updating `all=8994` is supported but not recommended as a first pass because it
can take hours and may trigger rate limits.

Native qlib official package download path:

```powershell
python D:\mcQlib\tools\get_data.py qlib_data --target_dir D:\mcQlib\data\qlib_bin\us_data --region us
```

This native qlib command requires the `qlib` Python package to be installed in
the active Python environment. The native official package is useful for
historical baselines, while the `chenditc/investment_data` release is the
preferred CN daily-refresh source.

## CLI

```powershell
cd D:\FactorPlatform
python scripts\run_daily_data_maintenance.py
```

Dry run:

```powershell
python scripts\run_daily_data_maintenance.py --dry-run
```

If you later wire a trusted downloader:

```powershell
$env:FACTOR_PLATFORM_DATA_UPDATE_COMMAND = "powershell -File D:\path\to\your_update_script.ps1"
python scripts\run_daily_data_maintenance.py --run-external-updater
```

## Suggested Windows Task Scheduler Command

Program:

```text
python
```

Arguments:

```text
D:\FactorPlatform\scripts\run_daily_data_maintenance.py
```

Start in:

```text
D:\FactorPlatform
```

Recommended trigger: every trading day after your raw data ingestion job completes.
