from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from app.factors.base import BaseFactor, FactorInfo
from app.factors.registry import register_factor


@register_factor
class MOMRet(BaseFactor):
    @classmethod
    def info(cls) -> FactorInfo:
        return FactorInfo(
            factor_name="MOM_RET_N_D_V1",
            display_name="N日动量收益",
            category="MOM",
            description="基于复权收盘价的过去N日收益率：close/close.shift(N)-1。",
            version="V1",
            dependencies=["daily_bar.trade_date", "daily_bar.asset_code", "daily_bar.close"],
            parameter_schema={"n": {"type": "int", "default": 20, "min": 1, "max": 252}},
        )

    @classmethod
    def validate_params(cls, params: Mapping[str, Any]) -> dict[str, Any]:
        p = dict(params)
        n = int(p.get("n", 20))
        if n < 1 or n > 252:
            raise ValueError("n must be in [1, 252]")
        return {"n": n}

    @classmethod
    def compute(cls, daily_bar: pd.DataFrame, params: Mapping[str, Any]) -> pd.DataFrame:
        p = cls.validate_params(params)
        n = p["n"]

        df = daily_bar[["trade_date", "asset_code", "close"]].copy()
        df = df.sort_values(["asset_code", "trade_date"], kind="mergesort")
        df["factor_value"] = df.groupby("asset_code")["close"].transform(lambda s: s / s.shift(n) - 1.0)
        out = df[["trade_date", "asset_code", "factor_value"]].dropna()
        return cls.post_check(out)
