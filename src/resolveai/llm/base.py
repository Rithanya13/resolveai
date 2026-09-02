"""LLM provider interface.

Every node in the graph calls `LLMClient.complete_structured(prompt, schema)`
and gets back a validated Pydantic instance -- never raw text it has to parse
itself. This is what lets `FakeLLM` and `AnthropicLLM` be interchangeable, and
what lets the graph's unit tests run in milliseconds with no network or API
key.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def complete_structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Run a prompt and return a validated instance of `schema`."""
        ...
