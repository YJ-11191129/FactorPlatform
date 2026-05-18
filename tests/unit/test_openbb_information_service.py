from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.services import data_maintenance_service as dms
from app.services import openbb_information_service as svc
from app.services import research_ops_registry as registry


class _FakeNews:
    def world(self, **kwargs):
        return _FakeToDfResult(
            [
                {
                    "title": "Oil supply headline",
                    "url": "https://example.test/oil",
                    "date": "2026-05-10",
                    "source": "Example Wire",
                }
            ]
        )

    def company(self, **kwargs):
        return _FakeResultsResult(
            [
                {
                    "headline": f"{kwargs.get('symbol')} earnings update",
                    "link": "https://example.test/company",
                    "published_at": "2026-05-10",
                    "publisher": "Example Equity",
                }
            ]
        )


class _FakeEconomy:
    def calendar(self, **kwargs):
        return _FakeResultsResult(
            [
                {
                    "event": "CPI",
                    "date": "2026-05-10",
                    "country": "United States",
                    "importance": "high",
                    "actual": "3.1%",
                }
            ]
        )


class _FakeObb:
    news = _FakeNews()
    economy = _FakeEconomy()


class _FakeToDfResult:
    provider = "mock_provider"
    warnings = []
    extra = {"provider_choices": ["mock_provider"]}

    def __init__(self, rows):
        self._rows = rows

    def to_df(self):
        return pd.DataFrame(self._rows)


class _FakeResultsResult:
    provider = "mock_provider"
    warnings = ["sample warning"]
    extra = {}

    def __init__(self, rows):
        self.results = rows


class TestOpenBBInformationService(unittest.TestCase):
    def setUp(self) -> None:
        try:
            svc._load_obb.cache_clear()
        except Exception:
            pass

    def test_status_is_not_ready_when_package_missing(self) -> None:
        with patch("app.services.openbb_information_service.importlib.util.find_spec", return_value=None):
            out = svc.openbb_status()
            self.assertEqual(out["status"], "OPENBB_NOT_READY")
            self.assertIn("pip install openbb", out["install_hint"])

    def test_openbb_query_normalizes_to_df_and_registers_external_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "FACTOR_PLATFORM_OPENBB_DIR": str(Path(td) / "openbb"),
                "FACTOR_PLATFORM_RESEARCH_OPS_DIR": str(Path(td) / "research_ops"),
            },
        ), patch("app.services.openbb_information_service.importlib.util.find_spec", return_value=object()), patch(
            "app.services.openbb_information_service._load_obb", return_value=_FakeObb()
        ):
            out = svc.query_world_news(term="oil", limit=5)
            self.assertEqual(out["source"], "openbb")
            self.assertEqual(out["endpoint"], "news.world")
            self.assertEqual(out["count"], 1)
            self.assertTrue(Path(out["artifact_path"]).exists())
            self.assertIsNotNone(out["research_ops_object_id"])
            obj = registry.get_object(str(out["research_ops_object_id"]))
            self.assertEqual(obj["object_type"], "external_evidence")
            self.assertEqual(obj["summary"]["endpoint"], "news.world")

    def test_results_fallback_and_calendar_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "FACTOR_PLATFORM_OPENBB_DIR": str(Path(td) / "openbb"),
                "FACTOR_PLATFORM_RESEARCH_OPS_DIR": str(Path(td) / "research_ops"),
            },
        ), patch("app.services.openbb_information_service.importlib.util.find_spec", return_value=object()), patch(
            "app.services.openbb_information_service._load_obb", return_value=_FakeObb()
        ):
            company = svc.query_company_news(symbol="AAPL", limit=5)
            self.assertEqual(company["items"][0]["title"], "AAPL earnings update")
            calendar = svc.query_economy_calendar(country="United States", importance="high", limit=5)
            self.assertEqual(calendar["endpoint"], "economy.calendar")
            self.assertEqual(calendar["items"][0]["title"], "CPI")

    def test_openbb_api_and_news_source_explain_not_ready(self) -> None:
        with patch("app.services.openbb_information_service.importlib.util.find_spec", return_value=None):
            client = TestClient(create_app())
            status = client.get("/api/openbb/status")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["status"], "OPENBB_NOT_READY")
            news = client.get("/api/v1/news/search", params={"topic": "oil", "source": "openbb"})
            self.assertEqual(news.status_code, 503)
            self.assertEqual(news.json()["detail"]["status"], "OPENBB_NOT_READY")

    def test_openbb_data_maintenance_source_is_nonblocking(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {"FACTOR_PLATFORM_RESEARCH_OPS_DIR": str(Path(td) / "research_ops")},
        ), patch("app.services.openbb_information_service.importlib.util.find_spec", return_value=None), patch.object(
            dms,
            "configured_sources",
            lambda: [
                dms.DataSourceSpec(
                    "openbb_sdk",
                    "OpenBB Python SDK",
                    Path(td) / ".openbb_platform",
                    "openbb_sdk",
                    freshness_days=None,
                )
            ],
        ):
            audit = dms.audit_data_paths()
            self.assertEqual(audit["blocking_status"], "OK")
            self.assertEqual(audit["sources"][0]["status"], "OPENBB_NOT_READY")
            self.assertFalse(audit["sources"][0]["is_blocking"])


if __name__ == "__main__":
    unittest.main()
