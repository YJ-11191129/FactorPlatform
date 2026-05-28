# Docker-only Roadshow

This guide is for a presentation machine that has Docker installed but does not have Python, Node.js, Postgres, Redis, qlib, Wind/Kaggle data, or local API keys.

## Start

```powershell
docker compose -f docker-compose.roadshow.yml up --build
```

Open:

```text
http://localhost:3000/dashboard
```

If port `3000` is occupied:

```powershell
$env:FRONTEND_PORT=3010
docker compose -f docker-compose.roadshow.yml up --build
```

## What This Mode Includes

- A single production Next.js container.
- Read-only demo fixtures embedded in `web/src/lib/demo/roadshow-fixtures.json`.
- Mocked API responses for dashboard support, AI strategy providers, AI strategy generation, validation, demo backtest output, macro intelligence, news summary, signal center, regime monitor, and data-maintenance status.
- Frontend fallback data for stock radar and factor pages when a backend endpoint is intentionally unavailable.

## Why It Does Not Commit Real Data

Large qlib and OHLCV datasets should not be committed to Git. The roadshow stack uses compact synthetic fixtures that are enough to show the workflow without implying live market truth.

For a real-data demo, mount local data explicitly:

```powershell
$env:FACTOR_PLATFORM_HOST_MCQLIB_DATA="D:/mcQlib/data"
$env:FACTOR_PLATFORM_HOST_KAGGLE_DATA="D:/Kaggle/data"
docker compose -f docker-compose.roadshow.yml --profile real-data up --build
```

## Stop

```powershell
docker compose -f docker-compose.roadshow.yml down
```

## Risk Note

Roadshow fixtures are synthetic and read-only. They are suitable for project presentation, module walkthroughs, and workflow explanation, but they are not live market data and do not constitute investment advice.
