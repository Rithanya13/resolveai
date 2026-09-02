"""Embedding provider interface.

`FakeEmbedding` is a deterministic hashing-trick embedding (no model
download, no network) used in tests, CI, and local demo runs. It's a real
bag-of-words vector -- cosine similarity over it behaves sensibly for the
retrieval tests -- it's just not semantically rich the way a trained model's
embedding would be. `AzureOpenAIEmbedding` is the production path, matching
the Azure OpenAI embeddings ResolveAI's author has shipped in production
elsewhere.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from resolveai.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, text: str) -> np.ndarray: ...

    def embed_batch(self, texts: list[str]) -> np.ndarray: ...


class FakeEmbedding:
    """Deterministic hashing-trick bag-of-words embedding. No network, no model weights."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = _TOKEN_RE.findall(text.lower())
        for tok in tokens:
            h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        return np.stack([self.embed(t) for t in texts]) if texts else np.zeros((0, self.dim), dtype=np.float32)


class AzureOpenAIEmbedding:
    """Production embedding provider. Requires RESOLVEAI_AZURE_OPENAI_* env vars."""

    def __init__(self) -> None:
        from openai import AzureOpenAI  # imported lazily

        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            raise RuntimeError(
                "RESOLVEAI_AZURE_OPENAI_ENDPOINT and RESOLVEAI_AZURE_OPENAI_API_KEY must be set "
                "to use the azure_openai embedding provider."
            )
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version="2024-06-01",
        )
        self._deployment = settings.azure_openai_embedding_deployment
        self.dim = 1536

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        response = self._client.embeddings.create(model=self._deployment, input=texts)
        return np.array([d.embedding for d in response.data], dtype=np.float32)


def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbedding()
    if settings.embedding_provider == "azure_openai":
        return AzureOpenAIEmbedding()
    raise ValueError(f"Unknown RESOLVEAI_EMBEDDING_PROVIDER: {settings.embedding_provider!r}")
