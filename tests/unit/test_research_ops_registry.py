from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.services import research_ops_registry as registry


class TestResearchOpsRegistry(unittest.TestCase):
    def test_upsert_is_idempotent_and_edges_do_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_RESEARCH_OPS_DIR": td}):
            registry.reset_registry()
            registry.upsert_object(
                object_id="data_snapshot_1",
                object_type="data_snapshot",
                status="OK",
                source_system="test",
                summary={"blocking_status": "OK"},
            )
            for _ in range(2):
                registry.upsert_object(
                    object_id="factor_run_1",
                    object_type="factor_run",
                    status="SUCCESS",
                    source_system="test",
                    source_run_id="run_1",
                    parents=["data_snapshot_1"],
                    summary={"run_id": "run_1"},
                    external_ids=["run_1"],
                )

            edge_lines = [line for line in (Path(td) / "lineage_edges.jsonl").read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(len(edge_lines), 1)
            objects = registry.list_objects(limit=10)
            self.assertEqual(len(objects), 2)
            self.assertEqual(registry.get_object("factor_run_1")["source_run_id"], "run_1")

    def test_lineage_resolves_signal_id_to_snapshot_router_and_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_RESEARCH_OPS_DIR": td}):
            registry.reset_registry()
            registry.register_data_snapshot_from_audit(
                {
                    "generated_at": "2026-05-10T01:00:00Z",
                    "overall_status": "OK",
                    "blocking_status": "OK",
                    "status_counts": {"OK": 1},
                    "sources": [],
                },
                run_id="data_run_1",
            )
            snapshot = {
                "status": "OK",
                "generated_at": "2026-05-10T02:00:00Z",
                "signal_date": "2026-05-10",
                "source_run_id": "signal_run_1",
                "counts": {"live_active_count": 1, "router_blocked_count": 0, "shadow_count": 0},
                "router_decision": {"risk_scale": 1.0, "block_reason": None},
                "snapshot_path": str(Path(td) / "missing_latest_signals.json"),
                "items": [
                    {
                        "signal_id": "sig_20260510_0001",
                        "status": "ACTIVE",
                        "side": "LONG",
                        "entry_type": "NEXT_TRADING_DAY_OPEN",
                        "instrument": "000001.SZ",
                        "reason_tags": ["pass"],
                    }
                ],
                "shadow_items": [],
            }
            registry.register_signal_snapshot(snapshot)
            registry.register_outcome_payload(
                {
                    "status": "OK",
                    "computed_at": "2026-05-10T03:00:00Z",
                    "source_run_id": "signal_run_1",
                    "signal_date": "2026-05-10",
                    "outcome_path": str(Path(td) / "latest_outcomes.json"),
                    "items": [
                        {
                            "signal_id": "sig_20260510_0001",
                            "outcome_status": "OPEN",
                            "instrument": "000001.SZ",
                            "unrealized_pnl": 0.0123,
                        }
                    ],
                    "shadow_items": [],
                }
            )

            lineage = registry.get_lineage("sig_20260510_0001")
            object_ids = {node["object_id"] for node in lineage["nodes"]}
            self.assertIn("signal_snapshot_signal_run_1", object_ids)
            self.assertIn("router_decision_sig_20260510_0001_live", object_ids)
            self.assertIn("outcome_sig_20260510_0001_live", object_ids)
            self.assertTrue(any(item["reason"] == "artifact_path_missing" for item in lineage["missing_references"]))

    def test_daily_brief_reports_open_gaps_and_shadow_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_RESEARCH_OPS_DIR": td}):
            registry.reset_registry()
            empty = registry.daily_brief(asof_date="2026-05-10")
            self.assertIn("NO_DATA_SNAPSHOT", {gap["code"] for gap in empty["open_gaps"]})

            registry.register_data_snapshot_from_audit(
                {
                    "generated_at": "2026-05-10T01:00:00Z",
                    "overall_status": "OK",
                    "blocking_status": "OK",
                    "status_counts": {"OK": 1},
                    "sources": [],
                }
            )
            registry.register_signal_snapshot(
                {
                    "status": "OK",
                    "generated_at": "2026-05-10T02:00:00Z",
                    "signal_date": "2026-05-10",
                    "source_run_id": "signal_run_shadow",
                    "counts": {"live_active_count": 0, "router_blocked_count": 1, "shadow_count": 1},
                    "items": [],
                    "shadow_items": [
                        {
                            "signal_id": "sig_shadow_1",
                            "status": "BLOCKED",
                            "side": "LONG",
                            "entry_type": "NEXT_TRADING_DAY_OPEN",
                            "router_block_reason": "REGIME_STALE_BLOCKED",
                        }
                    ],
                }
            )
            brief = registry.daily_brief(asof_date="2026-05-10")
            self.assertEqual(brief["shadow_summary"]["shadow_count"], 1)
            self.assertEqual(brief["router_summary"]["blocked_count"], 1)

    def test_rebuild_index_from_signal_and_outcome_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            research_ops = str(Path(td) / "research_ops")
            signal_root = Path(td) / "signal_center"
            signal_root.mkdir()
            snapshot = {
                "status": "OK",
                "generated_at": "2026-05-10T02:00:00Z",
                "signal_date": "2026-05-10",
                "source_run_id": "signal_run_rebuild",
                "counts": {"live_active_count": 1, "router_blocked_count": 0, "shadow_count": 0},
                "items": [{"signal_id": "sig_rebuild_1", "status": "ACTIVE", "side": "LONG"}],
                "shadow_items": [],
                "snapshot_path": str(signal_root / "latest_signals.json"),
            }
            (signal_root / "latest_signals.json").write_text(json.dumps(snapshot), encoding="utf-8")
            (signal_root / "latest_outcomes.json").write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "computed_at": "2026-05-10T03:00:00Z",
                        "source_run_id": "signal_run_rebuild",
                        "signal_date": "2026-05-10",
                        "outcome_path": str(signal_root / "latest_outcomes.json"),
                        "items": [{"signal_id": "sig_rebuild_1", "outcome_status": "OPEN"}],
                        "shadow_items": [],
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "FACTOR_PLATFORM_RESEARCH_OPS_DIR": research_ops,
                    "FACTOR_PLATFORM_SIGNAL_CENTER_DIR": str(signal_root),
                    "FACTOR_PLATFORM_DATA_MAINTENANCE_DIR": str(Path(td) / "data_maintenance"),
                    "FACTOR_PLATFORM_QLIB_RESEARCH_DIR": str(Path(td) / "qlib_research"),
                    "FACTOR_PLATFORM_RUNS_DIR": str(Path(td) / "factor_runs"),
                    "FACTOR_PLATFORM_BACKTEST_DIR": str(Path(td) / "backtests"),
                },
            ):
                stats = registry.rebuild_index_from_artifacts(reset=True)
                self.assertEqual(stats["status"], "OK")
                self.assertIsNotNone(registry.get_object("signal_snapshot_signal_run_rebuild"))
                self.assertIsNotNone(registry.get_object("outcome_sig_rebuild_1_live"))

    def test_research_ops_api_filters_lineage_and_unknown_404(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"FACTOR_PLATFORM_RESEARCH_OPS_DIR": td}):
            registry.reset_registry()
            registry.upsert_object(
                object_id="data_snapshot_api",
                object_type="data_snapshot",
                status="OK",
                asof_date="2026-05-10",
                source_system="test",
                source_run_id="data_api",
                summary={"blocking_status": "OK"},
            )
            app = create_app()
            client = TestClient(app)

            listed = client.get("/api/research-ops/objects", params={"object_type": "data_snapshot", "asof_date": "2026-05-10"})
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["items"][0]["object_id"], "data_snapshot_api")

            lineage = client.get("/api/research-ops/lineage/data_snapshot_api")
            self.assertEqual(lineage.status_code, 200)
            self.assertEqual(lineage.json()["root"]["object_id"], "data_snapshot_api")

            missing = client.get("/api/research-ops/lineage/does_not_exist")
            self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
