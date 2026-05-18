from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.data_maintenance_service import run_daily_data_maintenance  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FactorPlatform daily data maintenance.")
    parser.add_argument("--dry-run", action="store_true", help="Audit only; do not refresh derived artifacts.")
    parser.add_argument("--no-factor-registry", action="store_true", help="Skip factor registry refresh.")
    parser.add_argument("--no-stock-screen", action="store_true", help="Skip stock screen refresh.")
    parser.add_argument("--no-signal-center", action="store_true", help="Skip Signal Center snapshot refresh.")
    parser.add_argument("--no-radar-smoke", action="store_true", help="Skip Stock Radar smoke test.")
    parser.add_argument("--run-external-updater", action="store_true", help="Run env-configured FACTOR_PLATFORM_DATA_UPDATE_COMMAND first.")
    parser.add_argument("--updater-id", default=None, help="Run a registered raw data updater, e.g. wind_ohlcv or qlib_us_yahoo_smoke.")
    args = parser.parse_args()

    out = run_daily_data_maintenance(
        dry_run=args.dry_run,
        refresh_factor_registry=not args.no_factor_registry,
        refresh_stock_screen=not args.no_stock_screen,
        refresh_signal_center_snapshot=not args.no_signal_center,
        run_radar_smoke=not args.no_radar_smoke,
        run_external_updater=args.run_external_updater,
        updater_id=args.updater_id,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 1 if out.get("overall_status") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
