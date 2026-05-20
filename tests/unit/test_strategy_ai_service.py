import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.api.schemas.strategy_ai import StrategyIndicatorSpec, StrategySpec
from app.services import backtest_service
from app.services.strategy_validator import validate_strategy_spec


class TestStrategyAIService(unittest.TestCase):
    def _valid_spec(self) -> StrategySpec:
        return StrategySpec(
            name="Test AI momentum",
            universe=["A"],
            indicators=[StrategyIndicatorSpec(type="momentum", name="momentum_1", window=1)],
            entry_rules=["momentum_1 > 0"],
            exit_rules=[],
            ranking="momentum_1",
        )

    def test_validator_rejects_lookahead_rule(self) -> None:
        spec = self._valid_spec()
        spec.entry_rules = ["forward_ret_1d > 0"]
        result = validate_strategy_spec(spec)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(issue.code == "lookahead_rule" for issue in result.issues))

    def test_strategy_spec_backtest_uses_delayed_positions(self) -> None:
        prices = pd.DataFrame(
            [
                {"trade_date": date(2020, 1, 1), "asset_code": "A", "close": 100.0},
                {"trade_date": date(2020, 1, 2), "asset_code": "A", "close": 110.0},
                {"trade_date": date(2020, 1, 3), "asset_code": "A", "close": 121.0},
            ]
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(backtest_service, "_load_daily_bar", lambda **_: prices), patch.object(
                backtest_service, "_select_backtest_root", lambda: root
            ), patch.object(backtest_service, "new_backtest_id", lambda prefix="bt": "ai_bt_test"), patch.object(
                backtest_service, "_now_utc", lambda: "2026-01-01T00:00:00Z"
            ):
                artifact, summary = backtest_service.run_strategy_spec_backtest(
                    spec=self._valid_spec().model_dump(),
                    initial_cash=100.0,
                    fee_bps=0.0,
                    use_adj=False,
                )

            eq = pd.read_parquet(artifact.equity_curve_path)
            self.assertEqual(summary["strategy_id"], "ai_strategy_spec")
            self.assertAlmostEqual(float(eq.iloc[1]["equity"]), 100.0, places=8)
            self.assertAlmostEqual(float(eq.iloc[2]["equity"]), 110.0, places=8)


if __name__ == "__main__":
    unittest.main()
