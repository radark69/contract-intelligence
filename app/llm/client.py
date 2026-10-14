"""LLM client abstraction (plan section 10).

Deterministic Python handles all arithmetic (contract value, dates,
percentages, LD and exposure calculations). The LLM is used only for
interpretation tasks — and the pipeline must work offline: when no API
key is configured a deterministic mock client is returned so tests and
local runs never depend on a network call.
"""

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Minimal chat interface shared by all implementations."""

    name: str = "abstract"

    @abstractmethod
    async def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> str:
        """Return the model's completion for a system + user message pair."""


class MockLLMClient(LLMClient):
    """Deterministic offline client.

    Returns empty JSON arrays for extraction-style prompts so callers
    treat 'no interpretation available' as a valid, testable outcome.
    """

    name = "mock"

    def __init__(self, response: str = "[]"):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> str:
        self.calls.append((system, user))
        return self.response


class OpenAIClient(LLMClient):
    """OpenAI chat client (requires settings.openai_api_key)."""

    name = "openai"

    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Return the configured client; mock when no real key is present."""
    key = settings.openai_api_key
    if key and len(key) > 20:
        logger.info("LLM client: openai (%s)", settings.openai_model)
        return OpenAIClient(api_key=key, model=settings.openai_model)
    logger.info("LLM client: mock (no OPENAI_API_KEY configured)")
    return MockLLMClient()


def reset_llm_client_cache() -> None:
    get_llm_client.cache_clear()
