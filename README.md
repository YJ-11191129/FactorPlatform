# FactorPlatform

FactorPlatform is an AI-assisted financial research and trading support platform. It is designed as a risk-aware research terminal for market intelligence, stock screening, strategy generation, backtesting, attribution, and data maintenance.

The project is not a trading signal website and does not provide investment advice. Its purpose is to help researchers organize evidence, understand uncertainty, screen candidates, and validate strategy ideas before making independent decisions.

## Highlights

- Professional fintech landing page and research dashboard.
- AI stock radar with factor-based candidate screening and contribution explanations.
- Macro intelligence module for news summaries, event chains, and cross-asset scenario analysis.
- AI strategy builder that turns research hypotheses into structured strategy drafts.
- Backtest workspace with timing assumptions, transaction costs, positions, and result pages.
- Signal center for regime-aware signal screening, router decisions, notifications, and outcome tracking.
- Performance attribution for strategy review and research reporting.
- Regime monitor for volatility, liquidity, tail-risk, and historical state context.
- Factor registry and data maintenance pages for qlib, OHLCV, freshness checks, and operational health.
- Explicit fallback states for demo and offline scenarios so mock data is not mistaken for live research output.

## Product Modules

| Module | Route | Purpose |
| --- | --- | --- |
| Landing page | `/` | Institutional-style product introduction for AI market intelligence. |
| Dashboard | `/dashboard` | Main research workspace with market board, AI stock entry, macro intelligence entry, and module navigation. |
| Stock Radar | `/stock-radar` | Multi-factor candidate pool using momentum, trend, volatility, and volume-price features. |
| Macro Intel | `/macro-intel` | News summary, event impact chain, and scenario-style macro analysis. |
| AI Strategy Builder | `/ai-strategy-builder` | Generate and validate strategy specifications from research intent. |
| Strategies / Backtests | `/strategies`, `/backtests/[id]` | Backtest configuration, execution, metrics, equity curves, and result review. |
| Signal Center | `/signal-center`, `/signal-center/[id]` | Signal screening, risk context, router status, and detailed signal evidence. |
| Performance | `/performance` | KPI overview, time-series curves, and attribution breakdowns. |
| Regime Monitor | `/regime-monitor` | Market regime timeline, similar historical periods, and shock context. |
| Factors | `/factors`, `/factors/[factorName]` | Factor registry, qlib readiness, factor metadata, and quality gates. |
| Data Maintenance | `/data-maintenance` | Data freshness, source paths, row counts, lag checks, and refresh tasks. |
| Settings | `/settings` | Language, advanced research mode, and local configuration controls. |

## Architecture

```text
Frontend (Next.js / React / Ant Design)
  -> API proxy and client adapters
  -> Backend (FastAPI)
  -> Services: factors, news, signals, strategies, backtests, data maintenance
  -> Workers: Celery + Redis
  -> Storage: Postgres + local data folders
  -> Research data: qlib CN/US, OHLCV, news sources, strategy library
```

## Tech Stack

### Frontend

- Next.js 14
- React 18
- TypeScript
- Ant Design
- TradingView widgets with local fallback charts

### Backend

- FastAPI
- Pydantic
- SQLAlchemy / Alembic
- Postgres
- Redis
- Celery
- pandas / numpy / scipy / scikit-learn / statsmodels

### Research and Reporting

- qlib-compatible local data paths
- AI provider routing through configurable LLM settings
- Report generation scripts using ReportLab and PyMuPDF

## Repository Layout

```text
app/                     Backend application
  api/                   FastAPI routers and schemas
  services/              Research, strategy, signal, news, and data services
  tasks/                 Celery tasks
  factors/               Factor-related utilities
  strategies/            Strategy logic

web/                     Next.js frontend
  src/app/               App Router pages
  src/components/        Shared layout, charts, visuals, and UI components
  src/lib/demo/          Checked-in roadshow fixtures for Docker-only demos
  src/lib/               API clients, adapters, i18n, and feature flags
  src/types/             Frontend types

scripts/                 Local run, health check, data refresh, and report scripts
tests/                   Unit tests
docs/                    Demo and operations documentation
demo/                    Docker placeholder mounts and demo support files
config/                  Config files
strategy_library/        Strategy examples and templates
```

## Quick Start

### 1. Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8003
```

The local backend is usually expected at:

```text
http://127.0.0.1:8003
```

### 2. Frontend

```powershell
cd web
npm install
npm run dev -- --hostname 0.0.0.0 --port 3001
```

The local frontend is usually expected at:

```text
http://localhost:3001/dashboard
```

### 3. Docker Compose

```powershell
docker compose up -d --build
```

The compose stack includes Postgres, Redis, backend, worker, and frontend services. The backend container waits for Postgres and Redis health checks, runs Alembic migrations through `scripts/init_db.py`, and syncs code factor metadata before serving traffic.

Open:

```text
http://localhost:3000/dashboard
http://localhost:8002/docs
```

Useful checks:

```powershell
docker compose ps
docker compose exec -T postgres psql -U postgres -d factor_platform -c "\dt"
powershell -ExecutionPolicy Bypass -File scripts/check_stack_health.ps1 -ApiKey LOCAL_ADMIN_KEY
```

Real market data mounts are optional and controlled by `FACTOR_PLATFORM_HOST_MCQLIB_DATA` and `FACTOR_PLATFORM_HOST_KAGGLE_DATA`; when they are not set, Docker uses the checked-in empty placeholder mount so the stack does not depend on this workstation's `D:` drive.

### 4. Docker-only Roadshow

Use this mode on a presentation computer that has Docker but no Python, Node.js, local database, qlib, or local market data:

```powershell
docker compose -f docker-compose.roadshow.yml up -d --build
```

Then open:

```text
http://localhost:3000/dashboard
```

Roadshow mode runs the full local stack: Postgres container, Redis container, FastAPI backend, Celery worker, and Next.js frontend. It also enables the checked-in fixture fallback from `web/src/lib/demo/roadshow-fixtures.json`, so read-heavy presentation pages remain available if optional market data or external AI providers are unavailable. The fixture data is synthetic and clearly labeled as demo data.

If port `3000` is occupied, choose another host port:

```powershell
$env:FRONTEND_PORT=3010
docker compose -f docker-compose.roadshow.yml up -d --build
```

For a Docker-only machine with mounted real data, set the optional host mounts before starting:

```powershell
$env:FACTOR_PLATFORM_HOST_MCQLIB_DATA="D:/mcQlib/data"
$env:FACTOR_PLATFORM_HOST_KAGGLE_DATA="D:/Kaggle/data"
docker compose -f docker-compose.roadshow.yml up -d --build
```

Useful roadshow commands:

```powershell
docker compose -f docker-compose.roadshow.yml ps
docker compose -f docker-compose.roadshow.yml exec -T postgres psql -U postgres -d factor_platform -c "\dt"
powershell -ExecutionPolicy Bypass -File scripts/check_stack_health.ps1 -ApiKey ROADSHOW_ADMIN_KEY
docker compose -f docker-compose.roadshow.yml logs -f backend frontend
docker compose -f docker-compose.roadshow.yml down
```

## Environment Variables

Copy the examples and adjust local paths and keys:

```powershell
Copy-Item .env.local.example .env.local
Copy-Item web\.env.local.example web\.env.local
```

Important variables:

| Variable | Purpose |
| --- | --- |
| `FACTOR_PLATFORM_API_KEYS` | Comma-separated API key and role pairs, for example `LOCAL_ADMIN_KEY:admin,LOCAL_VIEW_KEY:viewer`. |
| `FACTOR_PLATFORM_REQUIRE_AUTH` | Enables API key checks when set to `1`. |
| `FACTOR_PLATFORM_REQUIRE_DB` | Requires database-backed services when set to `1`. |
| `DATABASE_URL` | Postgres connection string. |
| `REDIS_URL` | Redis connection string. |
| `FACTOR_PLATFORM_PROVIDER_URI` | Local qlib CN data path. |
| `FACTOR_PLATFORM_US_PROVIDER_URI` | Local qlib US data path. |
| `FACTOR_PLATFORM_REAL_OHLCV_PATH` | Local OHLCV parquet path. |
| `FACTOR_PLATFORM_HOST_MCQLIB_DATA` | Optional host directory mounted into Docker at `/data/mcqlib` for real qlib data. |
| `FACTOR_PLATFORM_HOST_KAGGLE_DATA` | Optional host directory mounted into Docker at `/data/kaggle` for real OHLCV/parquet data. |
| `LLM_PROVIDER` | AI provider selection, for example `deepseek` or `openai_compatible`. |
| `LLM_BASE_URL` | OpenAI-compatible provider base URL. |
| `LLM_API_KEY` | AI provider API key. Do not commit real keys. |
| `NEXT_PUBLIC_API_KEY` | Frontend demo API key for local development. |
| `BACKEND_ORIGIN` | Backend origin used by the Next.js API proxy. |

## Useful Commands

### Frontend checks

```powershell
cd web
npm run lint
npm run build
```

### Backend tests

```powershell
python -m pytest tests/unit
```

### Health check

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_stack_health.ps1
```

### Start local demo helpers

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_all.ps1
```

or, for LAN demo scenarios:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_demo_lan.ps1
```

## Report PDF

The project includes a script for generating a project presentation PDF with module descriptions, competitor analysis, product highlights, commercial outlook, and risk disclaimers.

Install optional report dependencies if needed:

```powershell
python -m pip install reportlab pymupdf pillow pypdf pdfplumber
```

Generate the report:

```powershell
python scripts/build_project_report_pdf.py
```

Generated artifacts are written under `output/pdf/` and are intentionally ignored by Git.

## Data and Demo Modes

FactorPlatform supports real-data and fallback/demo states. Fallback output is meant to keep the demo usable when a backend, data source, or third-party widget is unavailable. The UI should clearly mark fallback or mock states as read-only or non-production data.

Recommended demo principles:

- Never present fallback data as live market truth.
- Keep signal output framed as research support, not direct trading instruction.
- Preserve signal dates, effective trade dates, data source labels, and freshness warnings.
- Use backtests and attribution to validate hypotheses before any real-world decision.

## Risk Disclaimer

FactorPlatform is a research tool and decision-support system. It does not provide investment advice, does not guarantee returns, and should not be interpreted as a deterministic market prediction system. Users remain responsible for validating data, assumptions, model behavior, and regulatory obligations before making any investment or trading decision.
