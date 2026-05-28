# Docker-only Roadshow

This guide is for a presentation machine that has Docker installed but does not have Python, Node.js, Postgres, Redis, qlib, Wind/Kaggle data, or local API keys.

## Build the Portable Data Directory

On the source workstation, build the portable data directory once:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_portable_data.ps1
```

This writes:

```text
data/portable/mcqlib
data/portable/kaggle
data/portable/manifest.json
```

When moving to another computer, copy the project folder together with `data/portable`. The compose files mount this directory by default.

## Build the Roadshow Database Dump

On the source workstation, import the portable market data into Postgres once and write a reusable demo dump:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_roadshow_db.ps1
```

This writes:

```text
data/db_dumps/roadshow_demo.dump
data/db_dumps/roadshow_import_manifest.json
```

For a fast smoke test, add limits:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_roadshow_db.ps1 -InstrumentLimit 20 -StructuredRowLimit 2000
```

Do not commit `data/portable`, `data/db_dumps`, or `data/artifacts`. Copy them with the roadshow folder when changing computers.

## Start

```powershell
docker compose -f docker-compose.roadshow.yml up -d --build
```

Open:

```text
http://localhost:3000/dashboard
```

If port `3000` is occupied:

```powershell
$env:FRONTEND_PORT=3010
docker compose -f docker-compose.roadshow.yml up -d --build
```

## What This Mode Includes

- A production Next.js container.
- A FastAPI backend container.
- A Postgres container for app metadata, factor runs, tasks, audit logs, reports, and imported roadshow market data.
- A one-shot `db-restore` container that restores `data/db_dumps/roadshow_demo.dump` when the database is empty or the dump checksum changes.
- A Redis container and Celery worker.
- Portable qlib/Wind/processed data mounted from `data/portable` for rebuilding the database dump.
- Local artifact storage under `data/artifacts`, with metadata registered in Postgres.
- Read-only demo fixtures embedded in `web/src/lib/demo/roadshow-fixtures.json` as fallback if an optional data or AI provider is unavailable.

## Why It Does Not Commit Real Data

Large qlib, OHLCV, database dumps, and generated artifacts should not be committed to Git. Keep `data/portable`, `data/db_dumps`, and `data/artifacts` outside version control and transfer them with the roadshow folder or as separate archives.

If you want to override the portable data directory with local real data, set the mounts explicitly:

```powershell
$env:FACTOR_PLATFORM_HOST_MCQLIB_DATA="D:/mcQlib/data"
$env:FACTOR_PLATFORM_HOST_KAGGLE_DATA="D:/Kaggle/data"
docker compose -f docker-compose.roadshow.yml up -d --build
```

Roadshow mode sets `FACTOR_PLATFORM_STALE_DATA_BLOCKS=0` by default. Stale historical data is shown as a warning instead of blocking the demo. This does not make the data live or current.

## Check

```powershell
docker compose -f docker-compose.roadshow.yml ps
docker compose -f docker-compose.roadshow.yml exec -T postgres psql -U postgres -d factor_platform -c "\dt"
docker compose -f docker-compose.roadshow.yml exec -T postgres psql -U postgres -d factor_platform -c "select source_id,row_count,asset_count,start_date,end_date from market_data_sources order by source_id"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_stack_health.ps1 -FrontendHost localhost -ApiKey ROADSHOW_ADMIN_KEY
```

## Stop

```powershell
docker compose -f docker-compose.roadshow.yml down
```

## Risk Note

Roadshow data and fixtures are suitable for project presentation, module walkthroughs, and workflow explanation, but they are not live market data and do not constitute investment advice.
