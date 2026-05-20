from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from app.services.llm.local_provider import LocalOpenAICompatibleProvider
from app.services.llm.openai_compatible_provider import OpenAICompatibleProvider, normalize_chat_completions_endpoint


def _float_env(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _int_env(name: str, default: int | None) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))
    except Exception:
        return default


def _deepseek_provider() -> OpenAICompatibleProvider:
    base = (os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com").strip()
    return OpenAICompatibleProvider(
        name="deepseek",
        model=(os.getenv("LLM_MODEL") or os.getenv("FACTOR_PLATFORM_LLM_MODEL") or "deepseek-chat").strip(),
        endpoint=normalize_chat_completions_endpoint(base),
        api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
        temperature=_float_env("LLM_TEMPERATURE", 0.2),
        max_tokens=_int_env("LLM_MAX_TOKENS", 2000),
        timeout_s=_int_env("LLM_TIMEOUT_SECONDS", 60) or 60,
        require_api_key=True,
    )


def _local_provider() -> LocalOpenAICompatibleProvider:
    base = (
        os.getenv("LOCAL_LLM_BASE_URL")
        or (os.getenv("LLM_BASE_URL") if (os.getenv("LLM_PROVIDER") or "").strip().lower() == "local" else "")
        or "http://127.0.0.1:11434/v1"
    ).strip()
    return LocalOpenAICompatibleProvider(
        name="local",
        model=(os.getenv("LOCAL_LLM_MODEL") or os.getenv("LLM_MODEL") or "qwen2.5:7b").strip(),
        endpoint=normalize_chat_completions_endpoint(base),
        api_key=(os.getenv("LOCAL_LLM_API_KEY") or "").strip(),
        temperature=_float_env("LOCAL_LLM_TEMPERATURE", _float_env("LLM_TEMPERATURE", 0.2)),
        max_tokens=_int_env("LOCAL_LLM_MAX_TOKENS", _int_env("LLM_MAX_TOKENS", 2000)),
        timeout_s=_int_env("LOCAL_LLM_TIMEOUT_SECONDS", _int_env("LLM_TIMEOUT_SECONDS", 60)) or 60,
        require_api_key=False,
    )


def build_llm_provider(preferred: str | None = None):
    name = (preferred or os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()
    if name in {"local", "ollama", "lmstudio", "local_openai"}:
        return _local_provider()
    return _deepseek_provider()


def llm_provider_status() -> dict[str, Any]:
    default_provider = (os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()
    providers = [_deepseek_provider().status(), _local_provider().status()]
    return {
        "default_provider": default_provider,
        "providers": [asdict(p) for p in providers],
    }
