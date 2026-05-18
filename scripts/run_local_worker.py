from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks.celery_app import celery_app


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
    celery_app.worker_main(["worker", "-l", "info", "-P", "solo"])


if __name__ == "__main__":
    main()
