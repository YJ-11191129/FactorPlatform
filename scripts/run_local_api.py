from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _set_default_env() -> None:
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/factor_platform")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("FACTOR_PLATFORM_REQUIRE_DB", "1")
    os.environ.setdefault("FACTOR_PLATFORM_REQUIRE_AUTH", "1")
    os.environ.setdefault("FACTOR_PLATFORM_API_KEYS", "LOCAL_ADMIN_KEY:admin,LOCAL_VIEW_KEY:viewer")
    os.environ.setdefault("FACTOR_PLATFORM_FORCE_REAL_DAILY", "0")
    os.environ.setdefault(
        "FACTOR_PLATFORM_REAL_OHLCV_PATH",
        "D:/Kaggle/data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet",
    )


def main() -> None:
    _set_default_env()
    require_db = os.getenv("FACTOR_PLATFORM_REQUIRE_DB", "0") in {"1", "true", "True", "YES", "yes"}
    if require_db:
        runpy.run_path("scripts/init_db.py", run_name="__main__")
    port = int(os.getenv("FACTOR_PLATFORM_API_PORT", "8002"))
    uvicorn.run("app.api.app:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
