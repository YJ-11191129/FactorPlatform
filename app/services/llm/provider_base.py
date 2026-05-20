from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMProviderStatus:
    name: str
    model: str
    ready: bool
    endpoint: str
    reason: str | None = None


class BaseLLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def status(self) -> LLMProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def complete_json(self, system: str, user: str, timeout_s: int | None = None) -> dict[str, Any]:
        raise NotImplementedError


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise LLMProviderError("model returned empty content")

    fenced = _FENCED_JSON_RE.search(raw)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise LLMProviderError("model response did not contain a JSON object")
        data = json.loads(raw[start : end + 1])

    if not isinstance(data, dict):
        raise LLMProviderError("model JSON response must be an object")
    return data
