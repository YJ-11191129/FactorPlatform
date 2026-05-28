import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from app.api.routers import factors as factors_router
from app.api.schemas.factors import RunStockRadarIn, StockRadarFactorSpec
from app.services import data_maintenance_service as dms


def _write_daily(path: Path, latest: date) -> None:
    pd.DataFrame(
        [
            {"date": latest.isoformat(), "wind_code": "A", "close": 1.0},
            {"date": latest.isoformat(), "wind_code": "B", "close": 2.0},
        ]
    ).to_parquet(path, index=False)


class TestDataFreshnessGate(unittest.TestCase):
    def test_audit_reports_ok_blocked_and_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fresh = root / "fresh.parquet"
            stale = root / "stale.parquet"
            missing = root / "missing.parquet"
            _write_daily(fresh, date.today())
            _write_daily(stale, date.today() - timedelta(days=10))

            specs = [
                dms.DataSourceSpec("wind_stock_ohlcv", "Fresh critical", fresh, "parquet", freshness_days=5),
                dms.DataSourceSpec("qlib_cn_daily", "Stale critical", stale, "parquet", freshness_days=5),
                dms.DataSourceSpec("qlib_us_daily", "Missing critical", missing, "parquet", freshness_days=5),
            ]
            with patch.object(dms, "configured_sources", lambda: specs):
                audit = dms.audit_data_paths()

            self.assertEqual(audit["blocking_status"], "BLOCKED")
            self.assertEqual(audit["status_counts"]["OK"], 1)
            self.assertEqual(audit["status_counts"]["STALE"], 1)
            self.assertEqual(audit["status_counts"]["MISSING"], 1)
            self.assertEqual({b["source_id"] for b in audit["blockers"]}, {"qlib_cn_daily", "qlib_us_daily"})
            self.assertIn("qlib_cn_chenditc", {r["updater_id"] for r in audit["recommendations"]})

    def test_stale_source_allows_historical_requested_date_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stale.parquet"
            latest = date.today() - timedelta(days=10)
            _write_daily(path, latest)
            specs = [dms.DataSourceSpec("wind_stock_ohlcv", "Backtest OHLCV", path, "parquet", freshness_days=5)]
            with patch.object(dms, "configured_sources", lambda: specs):
                live_gate = dms.evaluate_backtest_data_gate()
                historical_gate = dms.evaluate_backtest_data_gate(requested_end_date=latest)

            self.assertEqual(live_gate["blocking_status"], "BLOCKED")
            self.assertEqual(historical_gate["blocking_status"], "WARN")

    def test_backtest_gate_can_use_latest_available_date_for_historical_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stale.parquet"
            latest = date.today() - timedelta(days=10)
            _write_daily(path, latest)
            specs = [dms.DataSourceSpec("wind_stock_ohlcv", "Backtest OHLCV", path, "parquet", freshness_days=5)]
            with patch.object(dms, "configured_sources", lambda: specs):
                live_gate = dms.evaluate_backtest_data_gate()
                backtest_gate = dms.evaluate_backtest_data_gate(allow_latest_available=True)

            self.assertEqual(live_gate["blocking_status"], "BLOCKED")
            self.assertEqual(backtest_gate["blocking_status"], "WARN")
            self.assertTrue(backtest_gate["using_latest_available"])
            self.assertEqual(backtest_gate["effective_end_date"], latest.isoformat())
            self.assertIn("latest available historical date", backtest_gate["message"])

    def test_qlib_backtest_gate_can_use_latest_available_date(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td) / "qlib"
            provider.mkdir()
            latest = date.today() - timedelta(days=10)
            specs = [dms.DataSourceSpec("qlib_cn_daily", "Qlib CN daily provider", provider, "qlib_provider", freshness_days=5)]
            source = {
                "source_id": "qlib_cn_daily",
                "status": "STALE",
                "end_date": latest.isoformat(),
                "freshness_reason": "latest data is stale",
            }
            with patch.object(dms, "configured_sources", lambda: specs), patch.object(dms, "_source_from_audit", lambda _source_id: source):
                live_gate = dms.evaluate_stock_radar_data_gate(str(provider))
                backtest_gate = dms.evaluate_stock_radar_data_gate(str(provider), allow_latest_available=True)

            self.assertEqual(live_gate["blocking_status"], "BLOCKED")
            self.assertEqual(backtest_gate["blocking_status"], "WARN")
            self.assertTrue(backtest_gate["using_latest_available"])
            self.assertEqual(backtest_gate["effective_end_date"], latest.isoformat())
            self.assertIn("latest available historical date", backtest_gate["message"])

    def test_unknown_updater_id_is_explainable(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown updater_id"):
            dms.run_daily_data_maintenance(dry_run=True, updater_id="not_a_real_updater")

    def test_dry_run_does_not_write_latest_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "fresh.parquet"
            _write_daily(path, date.today())
            specs = [dms.DataSourceSpec("wind_stock_ohlcv", "Fresh critical", path, "parquet", freshness_days=5)]
            with patch.object(dms, "configured_sources", lambda: specs), patch.dict(
                os.environ, {"FACTOR_PLATFORM_DATA_MAINTENANCE_DIR": str(root / "reports")}
            ):
                out = dms.run_daily_data_maintenance(
                    dry_run=True,
                    refresh_factor_registry=False,
                    refresh_stock_screen=False,
                    run_radar_smoke=False,
                )

            self.assertTrue(out["dry_run"])
            self.assertFalse((root / "reports" / "latest.json").exists())

    def test_stock_radar_api_rejects_blocked_live_run(self) -> None:
        payload = RunStockRadarIn(
            provider_uri=r"D:\missing\qlib",
            universe="csi300",
            factors=[StockRadarFactorSpec(factor_name="MOM_RET_N_D_V1", params={"n": 20})],
        )
        blocked = {"blocking_status": "BLOCKED", "message": "qlib source is stale"}
        with patch.object(factors_router, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: blocked), patch.object(
            factors_router, "run_stock_radar"
        ) as run_mock:
            with self.assertRaises(HTTPException) as ctx:
                factors_router.run_stock_radar_api(payload)

        self.assertEqual(ctx.exception.status_code, 409)
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
