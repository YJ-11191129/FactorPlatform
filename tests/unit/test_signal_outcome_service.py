import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.api.routers import signal_center as signal_router
from app.services import signal_outcome_service as sos


def _snapshot() -> dict:
    return {
        "status": "OK",
        "generated_at": "2026-05-10T08:00:00Z",
        "signal_date": "2026-05-08",
        "source_run_id": "signal_run_1",
        "data_source": {"provider_uri": "unit_provider", "universe": "csi300"},
        "items": [
            {
                "signal_id": "sig_1",
                "instrument": "AAA",
                "name": "AAA Corp",
                "side": "LONG",
                "status": "ACTIVE",
                "signal_date": "2026-05-08",
                "effective_trade_date": "2026-05-09",
                "entry_price": 10.0,
                "expected_holding_bars": 2,
                "confidence": 0.82,
                "regime_label": "TREND_RISK_ON",
                "signal_template": "TREND_CONTINUATION_LONG_V2",
                "risk_level": "LOW",
            }
        ],
    }


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"trade_date": "2026-05-09", "asset_code": "AAA", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2},
            {"trade_date": "2026-05-10", "asset_code": "AAA", "open": 10.2, "high": 11.0, "low": 10.1, "close": 10.8},
            {"trade_date": "2026-05-11", "asset_code": "AAA", "open": 10.8, "high": 12.0, "low": 10.7, "close": 11.0},
        ]
    )


def _write_snapshot(root: Path, snapshot: dict | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "latest_signals.json").write_text(json.dumps(snapshot or _snapshot()), encoding="utf-8")


class TestSignalOutcomeService(unittest.TestCase):
    def test_refresh_generates_closed_outcome_from_daily_bars(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            _write_snapshot(Path(td))
            with patch.object(sos, "load_daily_bar", lambda *_args, **_kwargs: _prices()):
                out = sos.refresh_signal_outcomes()

            self.assertEqual(out["data_source"], "signal_outcomes")
            self.assertEqual(out["generated_count"], 1)
            self.assertTrue((Path(td) / "latest_outcomes.json").exists())
            item = out["items"][0]
            self.assertEqual(item["outcome_status"], "CLOSED")
            self.assertEqual(item["holding_bars"], 2)
            self.assertAlmostEqual(item["realized_pnl"], 0.1)
            self.assertAlmostEqual(item["mfe"], 0.2)
            self.assertAlmostEqual(item["mae"], -0.02)

    def test_missing_price_coverage_is_pending_without_fake_pnl(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            _write_snapshot(Path(td))
            with patch.object(sos, "load_daily_bar", lambda *_args, **_kwargs: pd.DataFrame()):
                out = sos.refresh_signal_outcomes()

            item = out["items"][0]
            self.assertEqual(item["outcome_status"], "PENDING_OUTCOME")
            self.assertIsNone(item["realized_pnl"])
            self.assertIsNone(item["unrealized_pnl"])
            self.assertEqual(item["price_path"], [])

    def test_performance_aggregates_latest_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            _write_snapshot(Path(td))
            with patch.object(sos, "load_daily_bar", lambda *_args, **_kwargs: _prices()):
                sos.refresh_signal_outcomes()

            summary = sos.performance_summary()
            timeseries = sos.performance_timeseries()
            attribution = sos.performance_attribution()

            self.assertEqual(summary["data_source"], "signal_outcomes")
            self.assertEqual(summary["evaluated_signals"], 1)
            self.assertEqual(summary["pending_signals"], 0)
            self.assertEqual(summary["no_trade_signals"], 0)
            self.assertAlmostEqual(summary["avg_pnl"], 0.1)
            self.assertEqual(len(timeseries["points"]), 1)
            self.assertEqual(attribution["by_template"][0]["name"], "TREND_CONTINUATION_LONG_V2")

    def test_no_trade_outcomes_are_not_counted_as_pending(self) -> None:
        snap = _snapshot()
        snap["items"][0]["status"] = "BLOCKED"
        snap["items"][0]["side"] = "NEUTRAL"
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            _write_snapshot(Path(td), snap)
            with patch.object(sos, "load_daily_bar", lambda *_args, **_kwargs: _prices()):
                sos.refresh_signal_outcomes()

            summary = sos.performance_summary()

        self.assertEqual(summary["evaluated_signals"], 0)
        self.assertEqual(summary["pending_signals"], 0)
        self.assertEqual(summary["no_trade_signals"], 1)

    def test_shadow_outcomes_do_not_mix_into_live_performance(self) -> None:
        snap = _snapshot()
        snap["items"][0]["status"] = "BLOCKED"
        snap["items"][0]["side"] = "NEUTRAL"
        shadow = {**snap["items"][0], "execution_mode": "shadow", "side": "LONG", "not_executable": True, "status": "BLOCKED"}
        snap["shadow_items"] = [shadow]
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            _write_snapshot(Path(td), snap)
            with patch.object(sos, "load_daily_bar", lambda *_args, **_kwargs: _prices()):
                out = sos.refresh_signal_outcomes()

            live_summary = sos.performance_summary()
            shadow_summary = sos.performance_summary(execution_mode="shadow")

        self.assertEqual(out["items"][0]["outcome_status"], "NO_TRADE")
        self.assertEqual(out["shadow_items"][0]["outcome_status"], "SHADOW_EVALUATED")
        self.assertEqual(live_summary["execution_mode"], "live")
        self.assertEqual(live_summary["evaluated_signals"], 0)
        self.assertEqual(live_summary["no_trade_signals"], 1)
        self.assertEqual(shadow_summary["execution_mode"], "shadow")
        self.assertEqual(shadow_summary["evaluated_signals"], 1)
        self.assertEqual(shadow_summary["no_trade_signals"], 0)

    def test_dry_run_does_not_write_outcome_file(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            _write_snapshot(Path(td))
            with patch.object(sos, "load_daily_bar", lambda *_args, **_kwargs: _prices()):
                out = sos.refresh_signal_outcomes(dry_run=True)

            self.assertTrue(out["dry_run"])
            self.assertFalse((Path(td) / "latest_outcomes.json").exists())

    def test_signal_detail_marks_pending_when_no_outcome_exists(self) -> None:
        signal = {
            "signal_id": "sig_1",
            "instrument": "AAA",
            "signal_time": "2026-05-10T08:00:00Z",
            "status": "ACTIVE",
            "risk_level": "LOW",
            "regime_label": "TREND_RISK_ON",
            "volatility_state": "NORMAL_VOL",
            "tail_risk_state": "NORMAL",
            "reason_tags": ["stock_radar_candidate"],
            "_factor_contributions": [{"factor": "QLIB_ALPHA_ROC20_V1", "contribution": 0.67}],
        }
        snapshot = {"source_run_id": "signal_run_1", "regime_snapshot": {}, "items": [signal]}
        with patch.object(signal_router, "find_signal", lambda _sid, execution_mode=None: (signal, snapshot)), patch.object(
            signal_router, "read_signal_history", lambda limit=250: []
        ), patch.object(signal_router, "read_latest_signal_run", lambda: None), patch.object(
            signal_router, "get_signal_outcome", lambda _sid, execution_mode="live": None
        ):
            out = signal_router.get_signal_detail("sig_1")

        self.assertEqual(out["outcome_status"], "PENDING_OUTCOME")
        self.assertIsNone(out["performance_tracking"]["unrealized_pnl"])


if __name__ == "__main__":
    unittest.main()
