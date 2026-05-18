from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.services import native_qlib_research_service as qlib_svc
from app.services import research_quality_service as quality_svc
from app.services import research_ops_registry as registry


def _write_mining_run(root: Path, run_id: str, *, bad_timing: bool = False, ranking_overrides: dict | None = None) -> Path:
    run_dir = root / "factor_mining" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2024-01-02", periods=45)
    rows = []
    for idx, d in enumerate(dates[:-2]):
        entry = d if bad_timing else dates[idx + 1]
        exit_ = dates[idx + 2]
        for asset_idx in range(12):
            rows.append(
                {
                    "trade_date": d.date(),
                    "entry_trade_date": entry.date(),
                    "exit_trade_date": exit_.date(),
                    "asset_code": f"A{asset_idx:03d}",
                    "factor_name": "FACTOR_A",
                    "factor_value": float(asset_idx),
                    "forward_return": float(asset_idx) / 100.0,
                }
            )
    panel = pd.DataFrame(rows)
    ranking = pd.DataFrame(
        [
            {
                "factor_name": "FACTOR_A",
                "coverage": 0.92,
                "missing_rate": 0.08,
                "ic_mean": 0.04,
                "rank_ic_mean": 0.05,
                "icir": 1.0,
                "rank_icir": 1.0,
                "positive_ic_ratio": 0.62,
                "long_short_mean": 0.012,
                "monotonicity": 0.35,
                "stability": 0.62,
                "score": 0.1,
                "date_count": 43,
                "sample_count": int(panel.shape[0]),
                "rank": 1,
                **(ranking_overrides or {}),
            }
        ]
    )
    ic = pd.DataFrame({"factor_name": "FACTOR_A", "trade_date": [str(d.date()) for d in dates[:43]], "ic": 0.04, "rank_ic": 0.05})
    group = pd.DataFrame({"factor_name": "FACTOR_A", "trade_date": [str(dates[0].date())], "quantile": [1], "forward_return": [0.01]})
    panel.to_parquet(run_dir / "factor_panel.parquet", index=False)
    ranking.to_parquet(run_dir / "factor_ranking.parquet", index=False)
    ic.to_parquet(run_dir / "ic_series.parquet", index=False)
    group.to_parquet(run_dir / "group_returns.parquet", index=False)
    summary = {
        "run_id": run_id,
        "status": "SUCCESS",
        "generated_at": "2026-05-10T01:00:00Z",
        "provider_uri": "mock",
        "universe": "csi300",
        "freq": "day",
        "date_range": {"start_date": str(dates[0].date()), "end_date": str(dates[-1].date())},
        "horizon": 1,
        "quantiles": 5,
        "factor_count": 1,
        "observation_count": int(panel.shape[0]),
        "artifact_path": str(run_dir),
        "artifacts": {
            "factor_panel": str(run_dir / "factor_panel.parquet"),
            "factor_ranking": str(run_dir / "factor_ranking.parquet"),
            "ic_series": str(run_dir / "ic_series.parquet"),
            "group_returns": str(run_dir / "group_returns.parquet"),
        },
        "top_factors": ranking.to_dict(orient="records"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return run_dir


class TestResearchQualityService(unittest.TestCase):
    def test_quality_passes_for_well_aligned_factor_mining_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qlib_root = Path(td) / "qlib"
            with self._env(td, qlib_root):
                _write_mining_run(qlib_root, "run_pass")
                report = quality_svc.evaluate_research_quality(source_run_id="run_pass")
                self.assertEqual(report["quality_status"], "PASS")
                self.assertEqual(report["promotion_status"], "PRODUCTION_CANDIDATE")
                self.assertFalse(report["not_executable"])
                self.assertIsNotNone(report["research_ops_object_id"])
                lineage = registry.get_lineage("run_pass")
                self.assertTrue(any(n["object_id"] == "validation_result_quality_run_pass" for n in lineage["nodes"]))

    def test_timing_leakage_fails_quality(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qlib_root = Path(td) / "qlib"
            with self._env(td, qlib_root):
                _write_mining_run(qlib_root, "run_bad_timing", bad_timing=True)
                report = quality_svc.evaluate_research_quality(source_run_id="run_bad_timing")
                self.assertEqual(report["quality_status"], "FAIL")
                self.assertIn("TIMING_LEAKAGE_RISK", report["reason_codes"])

    def test_coverage_and_date_count_fail_without_fake_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qlib_root = Path(td) / "qlib"
            with self._env(td, qlib_root):
                _write_mining_run(
                    qlib_root,
                    "run_low_coverage",
                    ranking_overrides={"coverage": 0.5, "missing_rate": 0.5, "date_count": 5},
                )
                report = quality_svc.evaluate_research_quality(source_run_id="run_low_coverage")
                self.assertEqual(report["quality_status"], "FAIL")
                self.assertIn("FACTOR_COVERAGE_FAIL", report["reason_codes"])
                self.assertIn("DATE_COUNT_TOO_LOW", report["reason_codes"])

    def test_suspiciously_high_ic_warns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qlib_root = Path(td) / "qlib"
            with self._env(td, qlib_root):
                _write_mining_run(qlib_root, "run_high_ic", ranking_overrides={"ic_mean": 0.31, "rank_ic_mean": 0.32})
                report = quality_svc.evaluate_research_quality(source_run_id="run_high_ic")
                self.assertEqual(report["quality_status"], "WARN")
                self.assertIn("SUSPICIOUSLY_HIGH_IC", report["reason_codes"])

    def test_portfolio_missing_quality_is_shadow_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qlib_root = Path(td) / "qlib"
            with self._env(td, qlib_root):
                _write_mining_run(qlib_root, "run_no_quality")
                portfolio = qlib_svc.build_portfolio("run_no_quality", selected_factors=["FACTOR_A"], long_top_n=3)
                self.assertEqual(portfolio["promotion_status"], "SHADOW_ONLY")
                self.assertTrue(portfolio["not_executable"])
                self.assertIn("QUALITY_REPORT_MISSING", portfolio["quality_reason_codes"])

    def test_quality_api_reads_existing_artifact_and_missing_is_404(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qlib_root = Path(td) / "qlib"
            with self._env(td, qlib_root):
                _write_mining_run(qlib_root, "run_api")
                client = TestClient(create_app())
                ok = client.post("/api/research-quality/evaluate", json={"source_run_id": "run_api"})
                self.assertEqual(ok.status_code, 200)
                self.assertEqual(ok.json()["source_run_id"], "run_api")
                fetched = client.get("/api/research-quality/runs/run_api")
                self.assertEqual(fetched.status_code, 200)
                missing = client.post("/api/research-quality/evaluate", json={"source_run_id": "missing"})
                self.assertEqual(missing.status_code, 404)

    def _env(self, td: str, qlib_root: Path):
        from unittest.mock import patch

        return patch.dict(
            os.environ,
            {
                "FACTOR_PLATFORM_QLIB_RESEARCH_DIR": str(qlib_root),
                "FACTOR_PLATFORM_RESEARCH_QUALITY_DIR": str(Path(td) / "quality"),
                "FACTOR_PLATFORM_RESEARCH_OPS_DIR": str(Path(td) / "research_ops"),
            },
        )


if __name__ == "__main__":
    unittest.main()
