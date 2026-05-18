import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.services import native_qlib_research_service as svc


def _mock_panel(factors: list[dict]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=8, freq="B").date
    assets = [f"A{i:02d}" for i in range(8)]
    rows = []
    for d in dates:
        for i, asset in enumerate(assets):
            forward = i / 100.0
            for factor in factors:
                name = factor["factor_name"]
                value = float(i if name.endswith("ROC20_V1") else 10 - i)
                rows.append(
                    {
                        "trade_date": d,
                        "asset_code": asset,
                        "factor_name": name,
                        "factor_value": value,
                        "forward_return": forward,
                        "entry_trade_date": d,
                        "exit_trade_date": d,
                    }
                )
    return pd.DataFrame(rows)


class TestNativeQlibResearchService(unittest.TestCase):
    def test_status_reports_qlib_not_ready_when_package_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch("importlib.util.find_spec", return_value=None):
            p = Path(td)
            (p / "calendars").mkdir()
            (p / "calendars" / "day.txt").write_text("2020-01-01\n", encoding="utf-8")
            (p / "instruments").mkdir()
            (p / "instruments" / "csi300.txt").write_text("A\t2020-01-01\t2020-12-31\n", encoding="utf-8")
            (p / "features").mkdir()
            out = svc.qlib_status(provider_uri=str(p), universe="csi300")
            self.assertEqual(out["status"], "QLIB_NOT_READY")
            self.assertFalse(out["package_available"])
            self.assertTrue(out["data_available"])

    def test_factor_mining_blocks_when_native_qlib_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"FACTOR_PLATFORM_QLIB_RESEARCH_DIR": td}):
            readiness = {"status": "QLIB_NOT_READY"}
            with patch.object(
                svc,
                "_require_ready",
                side_effect=svc.QlibResearchError("QLIB_NOT_READY", "not ready", readiness),
            ):
                with self.assertRaises(svc.QlibResearchError):
                    svc.run_factor_mining(factor_limit=2)
            self.assertFalse((Path(td) / "factor_mining").exists())

    def test_factor_mining_outputs_ranking_ic_and_group_returns(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"FACTOR_PLATFORM_QLIB_RESEARCH_DIR": td}):
            ready = {"status": "READY", "provider_uri": "mock", "notes": []}

            def loader(**kwargs):
                return _mock_panel(kwargs["factors"])

            with patch.object(svc, "_require_ready", return_value=ready), patch.object(
                svc, "_load_native_factor_panel", side_effect=loader
            ):
                out = svc.run_factor_mining(
                    provider_uri="mock",
                    universe="csi300",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 1, 31),
                    horizon=1,
                    quantiles=4,
                    top_k=2,
                    factor_pool=["QLIB_ALPHA_ROC20_V1", "QLIB_ALPHA_STD20_V1"],
                )

            self.assertEqual(out["status"], "SUCCESS")
            self.assertEqual(out["factor_count"], 2)
            detail = svc.get_factor_mining_run(out["run_id"])
            self.assertTrue(detail["factor_ranking"])
            self.assertTrue(detail["ic_series"])
            self.assertTrue(detail["group_returns"])
            self.assertIn("rank_ic_mean", detail["factor_ranking"][0])

    def test_portfolio_build_validates_factors_and_normalizes_weights(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ", {"FACTOR_PLATFORM_QLIB_RESEARCH_DIR": td}):
            ready = {"status": "READY", "provider_uri": "mock", "notes": []}

            def loader(**kwargs):
                return _mock_panel(kwargs["factors"])

            with patch.object(svc, "_require_ready", return_value=ready), patch.object(
                svc, "_load_native_factor_panel", side_effect=loader
            ):
                mining = svc.run_factor_mining(
                    provider_uri="mock",
                    factor_pool=["QLIB_ALPHA_ROC20_V1", "QLIB_ALPHA_STD20_V1"],
                    top_k=2,
                )

            with self.assertRaises(ValueError):
                svc.build_portfolio(mining["run_id"], selected_factors=["MISSING_FACTOR"])

            portfolio = svc.build_portfolio(
                mining["run_id"],
                selected_factors=["QLIB_ALPHA_ROC20_V1", "QLIB_ALPHA_STD20_V1"],
                weighting_method="equal",
                long_top_n=3,
            )
            self.assertAlmostEqual(sum(portfolio["weights"].values()), 1.0, places=8)
            signals = svc.read_portfolio_signals(portfolio["portfolio_id"])
            per_day = signals.groupby("trade_date")["weight"].sum()
            self.assertTrue((per_day.round(8) == 1.0).all())
            self.assertTrue((pd.to_datetime(signals["trade_date"]) > pd.to_datetime(signals["signal_date"])).all())


if __name__ == "__main__":
    unittest.main()
