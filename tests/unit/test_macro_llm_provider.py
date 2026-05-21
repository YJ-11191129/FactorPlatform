import unittest
from unittest.mock import patch

from app.services.llm.provider_base import LLMProviderStatus
from app.services.macro_intelligence_service import MacroInputs, generate_topic_report, llm_ready


class _ReadyProvider:
    def status(self) -> LLMProviderStatus:
        return LLMProviderStatus(
            name="local",
            model="qwen3:14b",
            ready=True,
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
        )

    def complete_json(self, system: str, user: str, timeout_s: int | None = None) -> dict:
        return {
            "executive_summary": "LLM generated summary",
            "drivers": ["Supply/Demand"],
            "supply_chain": [],
            "regional_supply_demand": [],
            "geopolitics": [],
            "logistics_storage": [],
            "market_dashboard": [],
            "watchlist": [],
            "disclaimer": "Research use only; not investment advice.",
        }


class TestMacroLLMProvider(unittest.TestCase):
    def test_macro_report_uses_unified_llm_provider(self) -> None:
        with patch("app.services.macro_intelligence_service.build_llm_provider", lambda: _ReadyProvider()):
            self.assertTrue(llm_ready())
            out = generate_topic_report(MacroInputs(topic="oil"), {"signals": {}})

        self.assertEqual(out["executive_summary"], "LLM generated summary")
        self.assertNotIn("error", out)


if __name__ == "__main__":
    unittest.main()
