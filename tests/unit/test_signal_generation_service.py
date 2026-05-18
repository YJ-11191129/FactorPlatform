import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.routers import signal_center as signal_router
from app.services import signal_generation_service as sgs


def _regime(label: str = "TREND_RISK_ON") -> dict:
    return {
        "snapshot_time": "2026-05-10T08:00:00Z",
        "regime_label": label,
        "cpd_score": 0.12,
        "cluster_id": 2,
        "severity_score": 0.24,
        "volatility_state": "NORMAL_VOL",
        "liquidity_state": "NORMAL",
        "tail_risk_state": "NORMAL",
        "market_risk_level": "LOW",
        "data_source": "unit_test",
    }


def _radar() -> dict:
    return {
        "universe": "csi300",
        "provider_uri": r"D:\qlib\cn_data",
        "signal_date": "2026-05-08",
        "effective_trade_date": "2026-05-11",
        "items": [
            {
                "rank": 1,
                "asset_code": "SH600000",
                "close": 10.0,
                "score": 1.25,
                "score_percentile": 0.95,
                "factor_values": {"QLIB_ALPHA_ROC20_V1": 0.10},
                "factor_scores": {"QLIB_ALPHA_ROC20_V1": 1.50},
                "top_factor_contributors": [{"key": "QLIB_ALPHA_ROC20_V1", "contribution": 0.67}],
            },
            {
                "rank": 2,
                "asset_code": "SH600001",
                "close": 8.0,
                "score": 0.84,
                "score_percentile": 0.75,
                "factor_values": {"QLIB_ALPHA_ROC20_V1": 0.04},
                "factor_scores": {"QLIB_ALPHA_ROC20_V1": 0.90},
                "top_factor_contributors": [{"key": "QLIB_ALPHA_ROC20_V1", "contribution": 0.42}],
            },
        ],
    }


class TestSignalGenerationService(unittest.TestCase):
    def test_generate_live_signals_from_radar_and_regime(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            with patch.object(sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: {"blocking_status": "OK"}), patch.object(
                sgs, "get_latest_regime_snapshot", lambda: _regime("TREND_RISK_ON")
            ), patch.object(sgs, "run_stock_radar", lambda **_kwargs: _radar()):
                out = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)

            self.assertEqual(out["status"], "OK")
            self.assertEqual(out["generated_count"], 2)
            self.assertEqual(out["items"][0]["side"], "LONG")
            self.assertEqual(out["items"][0]["signal_template"], "TREND_CONTINUATION_LONG_V2")
            self.assertTrue((Path(td) / "latest_signals.json").exists())
            self.assertTrue((Path(td) / "latest_run.json").exists())
            self.assertTrue((Path(td) / "history.jsonl").exists())

    def test_blocked_data_gate_does_not_call_stock_radar(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            blocked = {"blocking_status": "BLOCKED", "message": "qlib source is stale"}
            with patch.object(sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: blocked), patch.object(
                sgs, "run_stock_radar"
            ) as radar_mock:
                out = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)

            self.assertEqual(out["status"], "BLOCKED")
            self.assertEqual(out["items"], [])
            radar_mock.assert_not_called()
            self.assertEqual(sgs.read_latest_signal_snapshot()["status"], "BLOCKED")

    def test_warn_data_gate_adds_freshness_note(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            warn = {"blocking_status": "WARN", "message": "stale but allowed for requested historical date"}
            with patch.object(sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: warn), patch.object(
                sgs, "get_latest_regime_snapshot", lambda: _regime("POST_SHOCK_REBOUND")
            ), patch.object(sgs, "run_stock_radar", lambda **_kwargs: _radar()):
                out = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)

            self.assertEqual(out["status"], "WARN")
            self.assertIn("stale but allowed", out["items"][0]["freshness_note"])
            self.assertIn("data_freshness_warn", out["items"][0]["reason_tags"])

    def test_router_blocked_live_keeps_shadow_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            with patch.object(sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: {"blocking_status": "OK"}), patch.object(
                sgs, "get_latest_regime_snapshot", lambda: _regime("LIQUIDITY_SHOCK")
            ), patch.object(sgs, "run_stock_radar", lambda **_kwargs: _radar()):
                out = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)

            self.assertEqual(out["generated_count"], 2)
            self.assertEqual(out["blocked_count"], 2)
            self.assertEqual(out["counts"]["shadow_count"], 2)
            self.assertEqual(out["items"][0]["entry_type"], "NO_TRADE")
            self.assertEqual(out["shadow_items"][0]["execution_mode"], "shadow")
            self.assertTrue(out["shadow_items"][0]["not_executable"])
            self.assertEqual(out["shadow_items"][0]["side"], "LONG")
            self.assertGreater(out["shadow_items"][0]["entry_price"], 0)

    def test_stale_regime_blocks_live_but_generates_shadow(self) -> None:
        stale = {**_regime("TREND_RISK_ON"), "date": "2026-05-01", "snapshot_time": "2026-05-01T15:00:00+08:00"}
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            with patch.object(sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: {"blocking_status": "OK"}), patch.object(
                sgs, "get_latest_regime_snapshot", lambda: stale
            ), patch.object(sgs, "run_stock_radar", lambda **_kwargs: _radar()):
                out = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)

            self.assertEqual(out["router_decision"]["block_reason"], "REGIME_STALE_BLOCKED")
            self.assertEqual(out["regime_freshness"]["status"], "STALE_BLOCKED")
            self.assertEqual(out["items"][0]["status"], "BLOCKED")
            self.assertEqual(out["shadow_items"][0]["execution_mode"], "shadow")

    def test_dry_run_reports_config_without_writing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": td}):
            with patch.object(sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: {"blocking_status": "OK"}):
                out = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2, dry_run=True)

            self.assertEqual(out["status"], "DRY_RUN")
            self.assertEqual(out["config"]["universe"], "csi300")
            self.assertFalse((Path(td) / "latest_signals.json").exists())

    def test_live_route_reads_snapshot_without_generating(self) -> None:
        snapshot = {
            "status": "OK",
            "generated_at": "2026-05-10T08:00:00Z",
            "signal_date": "2026-05-08",
            "data_health": {"blocking_status": "OK"},
            "items": [{"signal_id": "sig_1", "instrument": "SH600000", "confidence": 0.8, "status": "ACTIVE"}],
        }
        with patch.object(signal_router, "read_latest_signal_snapshot", lambda: snapshot), patch.object(
            signal_router, "read_latest_signal_run", lambda: None
        ), patch.object(signal_router, "generate_signal_snapshot") as generate_mock:
            out = signal_router.get_signals_live(page=1, page_size=20)

        self.assertEqual(out["total"], 1)
        self.assertEqual(out["generated_at"], "2026-05-10T08:00:00Z")
        generate_mock.assert_not_called()

    def test_snapshot_history_retention_keeps_latest_entries(self) -> None:
        env = {"FACTOR_PLATFORM_SIGNAL_CENTER_DIR": "", "FACTOR_PLATFORM_SIGNAL_SNAPSHOT_KEEP": "2"}
        with tempfile.TemporaryDirectory() as td:
            env["FACTOR_PLATFORM_SIGNAL_CENTER_DIR"] = td
            with patch.dict(os.environ, env), patch.object(
                sgs, "evaluate_stock_radar_data_gate", lambda *_args, **_kwargs: {"blocking_status": "OK"}
            ), patch.object(sgs, "get_latest_regime_snapshot", lambda: _regime("TREND_RISK_ON")), patch.object(
                sgs, "run_stock_radar", lambda **_kwargs: _radar()
            ):
                sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)
                sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)
                latest = sgs.generate_signal_snapshot(provider_uri=r"D:\qlib\cn_data", universe="csi300", topn=2)

            history_lines = (Path(td) / "history.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(history_lines), 2)
            latest_file = json.loads((Path(td) / "latest_signals.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_file["source_run_id"], latest["source_run_id"])

    def test_signal_detail_uses_real_factor_contributions(self) -> None:
        signal = {
            "signal_id": "sig_1",
            "instrument": "SH600000",
            "signal_time": "2026-05-10T08:00:00Z",
            "status": "ACTIVE",
            "risk_level": "LOW",
            "regime_label": "TREND_RISK_ON",
            "volatility_state": "NORMAL_VOL",
            "tail_risk_state": "NORMAL",
            "reason_tags": ["stock_radar_candidate"],
            "_factor_contributions": [{"factor": "QLIB_ALPHA_ROC20_V1", "contribution": 0.67}],
        }
        snapshot = {"regime_snapshot": _regime("TREND_RISK_ON"), "items": [signal]}
        with patch.object(signal_router, "find_signal", lambda _sid, execution_mode=None: (signal, snapshot)), patch.object(
            signal_router, "read_signal_history", lambda limit=250: []
        ), patch.object(signal_router, "read_latest_signal_run", lambda: None):
            out = signal_router.get_signal_detail("sig_1")

        self.assertEqual(out["factor_contributions"][0]["factor"], "QLIB_ALPHA_ROC20_V1")
        self.assertNotEqual(out["factor_contributions"][0]["factor"], "ILLIQ_20D")

    def test_router_mapping_by_regime(self) -> None:
        self.assertEqual(sgs.build_strategy_router(_regime("TREND_RISK_ON"))["risk_scale"], 1.0)
        self.assertEqual(sgs.build_strategy_router(_regime("FRAGILE_HIGH_VOL"))["risk_scale"], 0.4)
        self.assertEqual(sgs.build_strategy_router(_regime("POST_SHOCK_REBOUND"))["risk_scale"], 0.7)
        self.assertEqual(sgs.build_strategy_router(_regime("LIQUIDITY_SHOCK"))["risk_scale"], 0.0)
        self.assertEqual(sgs.build_strategy_router(_regime("UNKNOWN"))["risk_scale"], 0.25)


if __name__ == "__main__":
    unittest.main()
