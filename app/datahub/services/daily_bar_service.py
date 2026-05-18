from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from app.datahub.loaders.qlib_bin import load_daily_bar


def processed_daily_bar_path(project_root: str, universe: str) -> Path:
    return Path(project_root) / "data" / "processed" / f"daily_bar_{universe}.parquet"


def sync_daily_bar_to_parquet(
    project_root: str,
    provider_uri: str,
    universe: str = "csi300",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    instrument_limit: Optional[int] = None,
    overwrite: bool = False,
) -> Path:
    out_path = processed_daily_bar_path(project_root, universe)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not overwrite:
        return out_path

    df = load_daily_bar(
        provider_uri=provider_uri,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        instrument_limit=instrument_limit,
    )
    df.to_parquet(out_path, index=False)
    return out_path


def load_daily_bar_from_parquet(
    project_root: str,
    universe: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    path = processed_daily_bar_path(project_root, universe)
    df = pd.read_parquet(path)

    if start_date is not None:
        df = df[df["trade_date"] >= start_date]
    if end_date is not None:
        df = df[df["trade_date"] <= end_date]

    return df

