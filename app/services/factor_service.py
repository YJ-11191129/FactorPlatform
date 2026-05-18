from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

from app.datahub.loaders.qlib_bin import load_daily_bar
from app.factors.base import FactorInfo
from app.factors.registry import ensure_registered, get_factor, list_factors


DEFAULT_FACTOR_MODULES = [
    "app.factors.technical.mom_ret",
    "app.factors.technical.ma_bias",
    "app.factors.qlib_alpha",
]


def _demo_daily_bar(days: int = 80) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq="B")
    assets = ["SH600000", "SZ000001"]
    rows: list[dict[str, Any]] = []

    for asset in assets:
        base = 100.0 + (0.3 if asset.startswith("SH") else 0.0)
        px = base + np.cumsum(np.linspace(-0.2, 0.4, len(dates)))
        for d, c in zip(dates, px):
            rows.append({"trade_date": d.date(), "asset_code": asset, "close": float(c)})

    return pd.DataFrame(rows)


def list_factor_infos() -> list[FactorInfo]:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    return list_factors()


def get_factor_info(factor_name: str) -> FactorInfo:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    return get_factor(factor_name).info


def run_demo_factor(factor_name: str, params: Mapping[str, Any]) -> pd.DataFrame:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    rf = get_factor(factor_name)
    daily_bar = _demo_daily_bar(days=120)
    daily_bar = daily_bar.rename(columns={"close": "close"})
    return rf.factor_cls.compute(daily_bar=daily_bar, params=params)


def run_qlib_factor(
    factor_name: str,
    params: Mapping[str, Any],
    provider_uri: str,
    universe: str = "csi300",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    instrument_limit: Optional[int] = 50,
) -> pd.DataFrame:
    ensure_registered(DEFAULT_FACTOR_MODULES)
    rf = get_factor(factor_name)

    daily_bar = load_daily_bar(
        provider_uri=provider_uri,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        instrument_limit=instrument_limit,
    )

    if "close" not in daily_bar.columns:
        raise ValueError("daily_bar missing close")

    return rf.factor_cls.compute(daily_bar=daily_bar, params=params)


def factor_info_dict(fi: FactorInfo) -> dict[str, Any]:
    return asdict(fi)
