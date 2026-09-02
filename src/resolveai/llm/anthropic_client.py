"""Production LLM client, backed by the Anthropic API.

Not exercised by the test suite (no API key in CI) -- covered instead by
`tests/unit/test_llm_provider_selection.py`, which asserts the factory wires
this class up correctly. Structured output is enforced by forcing a single
tool call whose input schema is the target Pydantic model's JSON schema, then
validating the tool call's arguments back into that model. If validation
fails, we retry once with the validation error appended to the prompt --
real models occasionally emit a field with the wrong type, and a single
retry resolves the overwhelming majority of those without masking a genuine
prompt bug.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from resolveai.config import settings

T = TypeVar("T", bound=BaseModel)

_TOOL_NAME = "emit_structured_output"


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        import anthropic  # imported lazily so `fake` mode never requires the package config

        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    def complete_structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        tool = {
            "name": _TOOL_NAME,
            "description": f"Emit the result as {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }
        messages = [{"role": "user", "content": prompt}]

        last_error: Exception | None = None
        for _attempt in range(2):
            if last_error is not None:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Your previous output failed validation: {last_error}. Please call {_TOOL_NAME} again with corrected arguments.",
                    }
                )
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=messages,
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == _TOOL_NAME:
                    try:
                        return schema.model_validate(block.input)
                    except ValidationError as exc:
                        last_error = exc
                        break
        raise RuntimeError(f"AnthropicLLM failed to produce a valid {schema.__name__} after retry") from last_error
