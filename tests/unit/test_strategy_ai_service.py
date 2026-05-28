import os
import struct
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.api.schemas.strategy_ai import StrategyIndicatorSpec, StrategySpec
from app.services import backtest_service
from app.services.strategy_validator import validate_strategy_spec


def _write_feature(path: Path, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(values, dtype="<f4")
    path.write_bytes(struct.pack("<I", 0) + arr.tobytes(order="C"))


def _write_qlib_provider(root: Path, symbol: str) -> None:
    (root / "calendars").mkdir(parents=True, exist_ok=True)
    (root / "instruments").mkdir(parents=True, exist_ok=True)
    (root / "calendars" / "day.txt").write_text("2020-01-01\n2020-01-02\n2020-01-03\n", encoding="utf-8")
    row = f"{symbol}\t2020-01-01\t2020-01-03\n"
    (root / "instruments" / "csi300.txt").write_text(row, encoding="utf-8")
    (root / "instruments" / "all.txt").write_text(row, encoding="utf-8")

    feature_dir = root / "features" / symbol.lower()
    _write_feature(feature_dir / "open.day.bin", [100.0, 110.0, 121.0])
    _write_feature(feature_dir / "high.day.bin", [100.0, 110.0, 121.0])
    _write_feature(feature_dir / "low.day.bin", [100.0, 110.0, 121.0])
    _write_feature(feature_dir / "close.day.bin", [100.0, 110.0, 121.0])
    _write_feature(feature_dir / "volume.day.bin", [1000.0, 1000.0, 1000.0])
    _write_feature(feature_dir / "factor.day.bin", [1.0, 1.0, 1.0])


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

    def test_validator_downgrades_unknown_optional_ranking(self) -> None:
        spec = self._valid_spec()
        spec.ranking = "missing_rank"
        result = validate_strategy_spec(spec)
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.normalized_spec.ranking)
        self.assertTrue(any(issue.code == "unknown_ranking" and issue.severity == "warning" for issue in result.issues))

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
            with patch.object(backtest_service, "_load_daily_bar_from_source", lambda *_, **__: prices), patch.object(
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

    def test_strategy_spec_backtest_defaults_to_qlib_cn_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            provider = root / "qlib_cn"
            _write_qlib_provider(provider, "SZ000001")

            with patch.dict(
                os.environ,
                {
                    "FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE": "qlib",
                    "FACTOR_PLATFORM_PROVIDER_URI": str(provider),
                    "FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION": "cn",
                },
                clear=False,
            ), patch.object(backtest_service, "_select_backtest_root", lambda: root / "backtests"), patch.object(
                backtest_service, "new_backtest_id", lambda prefix="bt": "ai_bt_qlib_test"
            ), patch.object(
                backtest_service, "_now_utc", lambda: "2026-01-01T00:00:00Z"
            ):
                spec = self._valid_spec()
                spec.universe = ["000001.SZ"]
                artifact, summary = backtest_service.run_strategy_spec_backtest(
                    spec=spec.model_dump(),
                    initial_cash=100.0,
                    fee_bps=0.0,
                    use_adj=False,
                )

            eq = pd.read_parquet(artifact.equity_curve_path)
            self.assertEqual(summary["price_data_source"]["kind"], "qlib")
            self.assertEqual(summary["price_data_source"]["source_id"], "qlib_cn_daily")
            self.assertEqual(summary["price_data_source"]["instruments"], ["SZ000001"])
            self.assertAlmostEqual(float(eq.iloc[1]["equity"]), 100.0, places=8)
            self.assertAlmostEqual(float(eq.iloc[2]["equity"]), 110.0, places=5)

    def test_ai_backtest_source_normalizes_cn_qlib_symbols(self) -> None:
        source = backtest_service.resolve_ai_backtest_data_source(
            {"asset_class": "equity", "universe": ["000001.SZ", "600000.SH"]},
            universe=None,
        )

        self.assertEqual(source.kind, "qlib")
        self.assertEqual(source.region, "cn")
        self.assertEqual(source.source_id, "qlib_cn_daily")
        self.assertEqual(source.instruments, ("SZ000001", "SH600000"))

    def test_ai_backtest_source_infers_us_qlib_for_tickers(self) -> None:
        source = backtest_service.resolve_ai_backtest_data_source(
            {"asset_class": "equity", "universe": ["AAPL", "MSFT"]},
            universe=None,
        )

        self.assertEqual(source.kind, "qlib")
        self.assertEqual(source.region, "us")
        self.assertEqual(source.source_id, "qlib_us_daily")
        self.assertEqual(source.instruments, ("AAPL", "MSFT"))


if __name__ == "__main__":
    unittest.main()
