"""Checkpoint serializer configuration.

LangGraph's default `JsonPlusSerializer` will happily msgpack-serialize our
Pydantic schema types, but as of langgraph>=1.2 it warns (and, in strict mode,
blocks) deserialization of any type it doesn't recognize -- a deliberate
security default, since deserializing arbitrary types from a checkpoint store
is a code-execution risk if that store is ever attacker-writable. We
allowlist our own schema classes explicitly rather than leaving the
permissive "allow everything with a warning" default in place.
"""

from __future__ import annotations

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from resolveai import schemas

_ALLOWED_TYPES = [
    obj
    for name in dir(schemas)
    if isinstance(obj := getattr(schemas, name), type) and obj.__module__ == schemas.__name__
]


def build_serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_TYPES)
