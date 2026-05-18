from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from app.strategies.base import BaseStrategy, StrategyContext, StrategyInfo
from app.strategies.registry import register_strategy


@register_strategy
class MomMaV1Strategy(BaseStrategy):
    @classmethod
    def info(cls) -> StrategyInfo:
        return StrategyInfo(
            strategy_id="stg_mom_ma_v1",
            strategy_name="Momentum + MA Bias (Demo)",
            description="Demo strategy: equal-weight top momentum by last return.",
            version="v1",
            owner="research",
            parameter_schema={
                "topk": {"type": "int", "default": 10, "min": 1},
            },
        )

    def run(self, ctx: StrategyContext, params: Mapping[str, Any]) -> pd.DataFrame:
        topk = int(params.get("topk", 10))
        px = ctx.prices().copy()
        px = px.sort_values(["asset_code", "trade_date"], kind="mergesort")
        px["ret_1d"] = px.groupby("asset_code", sort=False)["close"].pct_change()
        last_dates = ctx.dates()

        rows: list[dict[str, Any]] = []
        for d in last_dates:
            day = px[px["trade_date"] == d]
            day = day.dropna(subset=["ret_1d"])
            if day.empty:
                continue
            top = day.sort_values("ret_1d", ascending=False).head(topk)
            w = 1.0 / float(len(top))
            for a in top["asset_code"].astype(str).tolist():
                rows.append({"trade_date": d, "asset_code": a, "weight": w})
        return pd.DataFrame(rows)
