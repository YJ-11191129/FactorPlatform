from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from app.strategies.base import BaseStrategy, StrategyContext, StrategyInfo
from app.strategies.registry import register_strategy


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, window: int = 6) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    roll_up = up.rolling(window=window, min_periods=window).mean()
    roll_down = down.rolling(window=window, min_periods=window).mean()
    rs = roll_up / (roll_down.replace(0.0, np.nan))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _kdj_k(close: pd.Series, window: int = 9) -> pd.Series:
    low = close.rolling(window=window, min_periods=window).min()
    high = close.rolling(window=window, min_periods=window).max()
    denom = (high - low).replace(0.0, np.nan)
    rsv = ((close - low) / denom * 100.0).fillna(50.0)
    k = rsv.ewm(alpha=1.0 / 3.0, adjust=False).mean()
    return k.fillna(50.0)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    fast = _ema(close, 12)
    slow = _ema(close, 26)
    diff = fast - slow
    signal = _ema(diff, 9)
    return diff, signal


@register_strategy
class VolumePriceBreakoutStrategy(BaseStrategy):
    @classmethod
    def info(cls) -> StrategyInfo:
        return StrategyInfo(
            strategy_id="stg_volume_price_breakout_v1",
            strategy_name="量价突破短线策略",
            description="量价突破：RSI/KDJ/MACD + 放量过滤，等权持仓。",
            version="v1",
            owner="user",
            parameter_schema={
                "holding_num": {"type": "int", "default": 10, "min": 1},
                "rebalance_frequency": {"type": "int", "default": 1, "min": 1},
                "rsi_threshold": {"type": "float", "default": 30.0, "min": 0.0, "max": 100.0},
                "kdj_k_threshold": {"type": "float", "default": 20.0, "min": 0.0, "max": 100.0},
                "volume_ratio_threshold": {"type": "float", "default": 1.5, "min": 0.0},
            },
        )

    def run(self, ctx: StrategyContext, params: Mapping[str, Any]) -> pd.DataFrame:
        holding_num = int(params.get("holding_num", 10))
        rebalance_frequency = int(params.get("rebalance_frequency", 1))
        rsi_threshold = float(params.get("rsi_threshold", 30.0))
        kdj_k_threshold = float(params.get("kdj_k_threshold", 20.0))
        volume_ratio_threshold = float(params.get("volume_ratio_threshold", 1.5))

        px = ctx.prices().copy()
        px["trade_date"] = pd.to_datetime(px["trade_date"]).dt.date
        px["asset_code"] = px["asset_code"].astype(str)
        px = px.sort_values(["asset_code", "trade_date"], kind="mergesort")
        px["close"] = pd.to_numeric(px["close"], errors="coerce")
        if "volume" in px.columns:
            px["volume"] = pd.to_numeric(px["volume"], errors="coerce")
        else:
            px["volume"] = np.nan
        px = px.dropna(subset=["trade_date", "asset_code", "close"]).reset_index(drop=True)

        px["rsi_6d"] = px.groupby("asset_code", sort=False)["close"].transform(lambda s: _rsi(s, 6))
        px["kdj_k"] = px.groupby("asset_code", sort=False)["close"].transform(lambda s: _kdj_k(s, 9))

        def _macd_diff(s: pd.Series) -> pd.DataFrame:
            d, sig = _macd(s)
            return pd.DataFrame({"macd_diff": d, "macd_signal": sig}, index=s.index)

        macd_df = px.groupby("asset_code", sort=False)["close"].apply(_macd_diff).reset_index(level=0, drop=True)
        px = pd.concat([px, macd_df], axis=1)

        px["volume_sma_20d"] = px.groupby("asset_code", sort=False)["volume"].transform(lambda s: s.rolling(20, min_periods=20).mean())
        px["volume_ratio"] = (px["volume"] / px["volume_sma_20d"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)

        px["signal"] = (
            (
                (px["rsi_6d"] < rsi_threshold)
                | (px["kdj_k"] < kdj_k_threshold)
                | (px["macd_diff"] > px["macd_signal"])
            )
            & (px["volume_ratio"] > volume_ratio_threshold)
        )

        dates = sorted(px["trade_date"].unique().tolist())
        current_weights: dict[str, float] = {}
        rows: list[dict[str, Any]] = []

        for i, d in enumerate(dates):
            if i == 0 or rebalance_frequency <= 1 or (i % rebalance_frequency == 0):
                day = px[px["trade_date"] == d].copy()
                sig = day[day["signal"]].copy()
                if sig.empty:
                    sig = day[day["volume_ratio"] > volume_ratio_threshold].copy()
                if sig.empty:
                    current_weights = {}
                else:
                    sig = sig.sort_values(["volume_ratio", "rsi_6d"], ascending=[False, True])
                    top = sig.head(holding_num)
                    w = 1.0 / float(len(top))
                    current_weights = {a: w for a in top["asset_code"].astype(str).tolist()}

            for a, w in current_weights.items():
                rows.append({"trade_date": d, "asset_code": a, "weight": float(w)})

        return pd.DataFrame(rows)


def main() -> int:
    return 0


if __name__ == "__main__":
  raise SystemExit(main())
