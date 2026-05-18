import tempfile
import unittest
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

import pandas as pd

from app.services import backtest_service
from app.strategies.base import BaseStrategy, StrategyInfo


@dataclass(frozen=True)
class _RS:
    info: StrategyInfo
    strategy_cls: type[BaseStrategy]
    python_entry: str = "tests:Dummy"


class _RebalanceStrategy(BaseStrategy):
    @classmethod
    def info(cls) -> StrategyInfo:
        return StrategyInfo(strategy_id="stg_test", strategy_name="test", description="test")

    def run(self, ctx: Any, params: Mapping[str, Any]) -> pd.DataFrame:
        d0 = ctx.dates()[0]
        d2 = ctx.dates()[-1]
        return pd.DataFrame(
            [
                {"trade_date": d0, "asset_code": "A", "weight": 1.0},
                {"trade_date": d2, "asset_code": "B", "weight": 1.0},
            ]
        )


class _DuplicatePositionsStrategy(BaseStrategy):
    @classmethod
    def info(cls) -> StrategyInfo:
        return StrategyInfo(strategy_id="stg_test_dup", strategy_name="test", description="test")

    def run(self, ctx: Any, params: Mapping[str, Any]) -> pd.DataFrame:
        d0 = ctx.dates()[0]
        return pd.DataFrame(
            [
                {"trade_date": d0, "asset_code": "A", "weight": 0.5},
                {"trade_date": d0, "asset_code": "A", "weight": 0.5},
            ]
        )


class TestBacktestService(unittest.TestCase):
    def test_load_and_normalize_ohlcv_mapping_and_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ohlcv.parquet"
            raw = pd.DataFrame(
                [
                    {"date": "2020-01-01", "wind_code": "A", "close": 100.0, "volume": 10.0},
                    {"date": "2020-01-02", "wind_code": "A", "close": 110.0, "volume": 11.0},
                    {"date": "2020-01-01", "wind_code": "B", "close": 100.0, "volume": 12.0},
                    {"date": "2020-01-02", "wind_code": "B", "close": 100.0, "volume": 13.0},
                ]
            )
            raw.to_parquet(p, index=False)

            out = backtest_service._load_and_normalize_ohlcv(
                p, start_date=date(2020, 1, 2), end_date=date(2020, 1, 2), universe=["A"]
            )
            self.assertEqual(out["trade_date"].min(), date(2020, 1, 2))
            self.assertEqual(out["trade_date"].max(), date(2020, 1, 2))
            self.assertEqual(out["asset_code"].nunique(), 1)
            self.assertEqual(out["asset_code"].iloc[0], "A")
            self.assertIn("open", out.columns)
            self.assertIn("high", out.columns)
            self.assertIn("low", out.columns)
            self.assertIn("adj_factor", out.columns)

    def test_run_backtest_rebalance_missing_assets_reset_to_zero(self) -> None:
        prices = pd.DataFrame(
            [
                {"trade_date": date(2020, 1, 1), "asset_code": "A", "close": 100.0},
                {"trade_date": date(2020, 1, 2), "asset_code": "A", "close": 110.0},
                {"trade_date": date(2020, 1, 3), "asset_code": "A", "close": 121.0},
                {"trade_date": date(2020, 1, 1), "asset_code": "B", "close": 100.0},
                {"trade_date": date(2020, 1, 2), "asset_code": "B", "close": 100.0},
                {"trade_date": date(2020, 1, 3), "asset_code": "B", "close": 100.0},
            ]
        )

        rs = _RS(info=_RebalanceStrategy.info(), strategy_cls=_RebalanceStrategy)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(backtest_service, "ensure_strategies_loaded", lambda: None), patch.object(
                backtest_service, "get_strategy", lambda _: rs
            ), patch.object(backtest_service, "_load_daily_bar", lambda **_: prices), patch.object(
                backtest_service, "_select_backtest_root", lambda: root
            ), patch.object(backtest_service, "new_backtest_id", lambda: "bt_test"), patch.object(
                backtest_service, "_now_utc", lambda: "2026-01-01T00:00:00Z"
            ):
                artifact, _ = backtest_service.run_backtest(
                    strategy_id="stg_test",
                    params={},
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 1, 3),
                    initial_cash=1_000_000.0,
                    fee_bps=5.0,
                    use_adj=False,
                )
                eq = pd.read_parquet(artifact.equity_curve_path)
                self.assertEqual(int(eq.shape[0]), 3)
                last = float(eq.iloc[-1]["equity"])
                self.assertAlmostEqual(last, 1209147.6375, places=4)

    def test_run_backtest_dedup_positions(self) -> None:
        prices = pd.DataFrame(
            [
                {"trade_date": date(2020, 1, 1), "asset_code": "A", "close": 100.0},
                {"trade_date": date(2020, 1, 2), "asset_code": "A", "close": 110.0},
            ]
        )

        rs = _RS(info=_DuplicatePositionsStrategy.info(), strategy_cls=_DuplicatePositionsStrategy)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(backtest_service, "ensure_strategies_loaded", lambda: None), patch.object(
                backtest_service, "get_strategy", lambda _: rs
            ), patch.object(backtest_service, "_load_daily_bar", lambda **_: prices), patch.object(
                backtest_service, "_select_backtest_root", lambda: root
            ), patch.object(backtest_service, "new_backtest_id", lambda: "bt_test"), patch.object(
                backtest_service, "_now_utc", lambda: "2026-01-01T00:00:00Z"
            ):
                artifact, _ = backtest_service.run_backtest(
                    strategy_id="stg_test_dup",
                    params={},
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 1, 2),
                    initial_cash=1_000_000.0,
                    fee_bps=0.0,
                    use_adj=False,
                )
                pos = pd.read_parquet(artifact.positions_path)
                self.assertEqual(int(pos.shape[0]), 1)
                self.assertAlmostEqual(float(pos.iloc[0]["weight"]), 1.0, places=8)

    def test_run_portfolio_backtest_uses_delayed_position_returns(self) -> None:
        prices = pd.DataFrame(
            [
                {"trade_date": date(2020, 1, 1), "asset_code": "A", "close": 100.0},
                {"trade_date": date(2020, 1, 2), "asset_code": "A", "close": 200.0},
                {"trade_date": date(2020, 1, 3), "asset_code": "A", "close": 300.0},
                {"trade_date": date(2020, 1, 4), "asset_code": "A", "close": 600.0},
            ]
        )
        signals = pd.DataFrame(
            [
                {
                    "trade_date": date(2020, 1, 2),
                    "signal_date": date(2020, 1, 1),
                    "asset_code": "A",
                    "weight": 1.0,
                }
            ]
        )
        portfolio = {
            "portfolio_id": "qlib_port_test",
            "mining_run_id": "qlib_mine_test",
            "selected_factors": ["F1"],
            "weighting_method": "equal",
            "signal_artifact_path": "mock/signals.parquet",
            "timing_note": "test",
        }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(backtest_service, "_load_daily_bar", lambda **_: prices), patch.object(
                backtest_service, "_select_backtest_root", lambda: root
            ), patch.object(backtest_service, "new_backtest_id", lambda prefix="bt": "bt_port_test"), patch.object(
                backtest_service, "_now_utc", lambda: "2026-01-01T00:00:00Z"
            ), patch(
                "app.services.native_qlib_research_service.get_portfolio", lambda _: portfolio
            ), patch(
                "app.services.native_qlib_research_service.read_portfolio_signals", lambda _: signals
            ):
                artifact, summary = backtest_service.run_portfolio_backtest(
                    portfolio_id="qlib_port_test",
                    initial_cash=100.0,
                    fee_bps=0.0,
                    use_adj=False,
                )

            eq = pd.read_parquet(artifact.equity_curve_path)
            self.assertEqual(summary["portfolio_id"], "qlib_port_test")
            self.assertAlmostEqual(float(eq.iloc[1]["equity"]), 100.0, places=8)
            self.assertAlmostEqual(float(eq.iloc[2]["equity"]), 150.0, places=8)


if __name__ == "__main__":
    unittest.main()
