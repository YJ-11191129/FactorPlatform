from __future__ import annotations

from dataclasses import dataclass

from app.services.llm.openai_compatible_provider import OpenAICompatibleProvider


@dataclass
class LocalOpenAICompatibleProvider(OpenAICompatibleProvider):
    require_api_key: bool = False
