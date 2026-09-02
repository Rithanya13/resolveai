from __future__ import annotations

from resolveai.config import settings
from resolveai.llm.base import LLMClient
from resolveai.llm.fake import FakeLLM


def get_llm_client() -> LLMClient:
    """Factory: resolves the configured LLM provider to a concrete client."""
    if settings.llm_provider == "fake":
        return FakeLLM()
    if settings.llm_provider == "anthropic":
        from resolveai.llm.anthropic_client import AnthropicLLM

        return AnthropicLLM()
    raise ValueError(f"Unknown RESOLVEAI_LLM_PROVIDER: {settings.llm_provider!r}")


__all__ = ["LLMClient", "FakeLLM", "get_llm_client"]
