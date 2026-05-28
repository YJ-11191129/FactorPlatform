from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_local_env() -> None:
    root = Path(__file__).resolve().parents[1]
    _load_env_file(root / ".env.local")
    _load_env_file(root / ".env")


def _set_default_env() -> None:
    _load_local_env()
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:factorplatform_dev_password@localhost:5432/factor_platform")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("FACTOR_PLATFORM_REQUIRE_DB", "1")
    os.environ.setdefault("FACTOR_PLATFORM_REQUIRE_AUTH", "1")
    os.environ.setdefault("FACTOR_PLATFORM_API_KEYS", "LOCAL_ADMIN_KEY:admin,LOCAL_VIEW_KEY:viewer")
    os.environ.setdefault("FACTOR_PLATFORM_FORCE_REAL_DAILY", "0")
    os.environ.setdefault("FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE", "qlib")
    os.environ.setdefault("FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION", "cn")
    os.environ.setdefault("FACTOR_PLATFORM_PROVIDER_URI", r"D:\mcQlib\data\qlib_bin\cn_data")
    os.environ.setdefault("FACTOR_PLATFORM_US_PROVIDER_URI", r"D:\mcQlib\data\qlib_bin\us_data")
    os.environ.setdefault(
        "FACTOR_PLATFORM_REAL_OHLCV_PATH",
        "D:/Kaggle/data/wind_data/02_daily_stock/stock_daily_ohlcv.parquet",
    )


def main() -> None:
    _set_default_env()
    require_db = os.getenv("FACTOR_PLATFORM_REQUIRE_DB", "0") in {"1", "true", "True", "YES", "yes"}
    if require_db:
        runpy.run_path("scripts/init_db.py", run_name="__main__")
    port = int(os.getenv("FACTOR_PLATFORM_API_PORT", "8003"))
    host = os.getenv("FACTOR_PLATFORM_API_HOST", "0.0.0.0")
    uvicorn.run("app.api.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
