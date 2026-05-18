from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.datahub.services.daily_bar_service import sync_daily_bar_to_parquet


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-uri", default=r"D:\mcQlib\data\qlib_bin")
    parser.add_argument("--universe", default="csi300", choices=["all", "csi100", "csi300", "csi500"])
    parser.add_argument("--start-date", type=_parse_date, default=None)
    parser.add_argument("--end-date", type=_parse_date, default=None)
    parser.add_argument("--instrument-limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    project_root = str(PROJECT_ROOT)
    out = sync_daily_bar_to_parquet(
        project_root=project_root,
        provider_uri=args.provider_uri,
        universe=args.universe,
        start_date=args.start_date,
        end_date=args.end_date,
        instrument_limit=args.instrument_limit,
        overwrite=args.overwrite,
    )
    print(str(out))


if __name__ == "__main__":
    main()
