from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from app.factors.base import BaseFactor, FactorInfo
from app.factors.registry import register_factor


@register_factor
class MABias(BaseFactor):
    @classmethod
    def info(cls) -> FactorInfo:
        return FactorInfo(
            factor_name="TREND_MA_BIAS_N_D_V1",
            display_name="均线乖离率",
            category="TREND",
            description="(close/MA(N)-1)，用于衡量价格相对均线偏离程度。",
            version="V1",
            dependencies=["daily_bar.trade_date", "daily_bar.asset_code", "daily_bar.close"],
            parameter_schema={"n": {"type": "int", "default": 20, "min": 2, "max": 252}},
        )

    @classmethod
    def validate_params(cls, params: Mapping[str, Any]) -> dict[str, Any]:
        p = dict(params)
        n = int(p.get("n", 20))
        if n < 2 or n > 252:
            raise ValueError("n must be in [2, 252]")
        return {"n": n}

    @classmethod
    def compute(cls, daily_bar: pd.DataFrame, params: Mapping[str, Any]) -> pd.DataFrame:
        p = cls.validate_params(params)
        n = p["n"]

        df = daily_bar[["trade_date", "asset_code", "close"]].copy()
        df = df.sort_values(["asset_code", "trade_date"], kind="mergesort")
        ma = df.groupby("asset_code")["close"].transform(lambda s: s.rolling(n, min_periods=n).mean())
        df["factor_value"] = df["close"] / ma - 1.0
        out = df[["trade_date", "asset_code", "factor_value"]].dropna()
        return cls.post_check(out)
