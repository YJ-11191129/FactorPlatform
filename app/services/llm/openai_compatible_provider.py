from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from app.services.llm.provider_base import BaseLLMProvider, LLMProviderError, LLMProviderStatus, extract_json_object


def normalize_chat_completions_endpoint(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return "https://api.openai.com/v1/chat/completions"
    if raw.endswith("/chat/completions") or raw.endswith("/v1/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return raw + "/chat/completions"
    p = urlparse(raw)
    if p.scheme in {"http", "https"} and p.netloc and (not p.path or p.path == "/"):
        return raw.rstrip("/") + "/v1/chat/completions"
    return raw


@dataclass
class OpenAICompatibleProvider(BaseLLMProvider):
    name: str
    model: str
    endpoint: str
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int | None = 2000
    timeout_s: int = 60
    require_api_key: bool = True

    def status(self) -> LLMProviderStatus:
        ready = bool(self.endpoint) and (bool(self.api_key) or not self.require_api_key)
        reason = None if ready else "missing api key" if self.require_api_key else "missing endpoint"
        return LLMProviderStatus(
            name=self.name,
            model=self.model,
            ready=ready,
            endpoint=self.endpoint,
            reason=reason,
        )

    def complete_json(self, system: str, user: str, timeout_s: int | None = None) -> dict[str, Any]:
        st = self.status()
        if not st.ready:
            raise LLMProviderError(st.reason or "provider is not ready")

        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": float(self.temperature),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = int(self.max_tokens)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            res = requests.post(
                normalize_chat_completions_endpoint(self.endpoint),
                headers=headers,
                json=payload,
                timeout=int(timeout_s or self.timeout_s),
            )
        except Exception as e:
            raise LLMProviderError(str(e)) from e

        if res.status_code >= 400:
            raise LLMProviderError(f"{self.name} error: status={res.status_code} body={res.text[:400]}")

        try:
            data = res.json()
        except Exception as e:
            raise LLMProviderError(f"{self.name} returned non-JSON response") from e

        content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
        return extract_json_object(content)
