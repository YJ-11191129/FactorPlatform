import os
import unittest
from unittest.mock import patch

from app.services.llm.router import build_llm_provider, llm_provider_status


class TestLLMRouter(unittest.TestCase):
    def test_openai_compatible_alias_reports_deepseek_default(self) -> None:
        env = {
            **os.environ,
            "LLM_PROVIDER": "openai_compatible",
            "LLM_BASE_URL": "https://api.deepseek.com/v1",
            "LLM_API_KEY": "test-key",
        }

        with patch.dict(os.environ, env, clear=True):
            status = llm_provider_status()
            provider = build_llm_provider()

        self.assertEqual(status["default_provider"], "deepseek")
        self.assertEqual(provider.status().name, "deepseek")

    def test_local_alias_reports_local_default(self) -> None:
        env = {
            **os.environ,
            "LLM_PROVIDER": "ollama",
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
            "LOCAL_LLM_MODEL": "qwen3:14b",
        }

        with patch.dict(os.environ, env, clear=True):
            status = llm_provider_status()
            provider = build_llm_provider()

        self.assertEqual(status["default_provider"], "local")
        self.assertEqual(provider.status().name, "local")


if __name__ == "__main__":
    unittest.main()
