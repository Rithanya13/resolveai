"""Central runtime configuration, provider selection via env vars.

Every external dependency (LLM, embeddings, vector store) is chosen here from
an env var and resolved behind an interface. That's what lets the whole graph
run fully offline in CI/tests (provider=fake) while the exact same code path
runs against real providers in production -- no test-only branches inside the
graph logic itself.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESOLVEAI_", env_file=".env", extra="ignore")

    llm_provider: str = "fake"  # "fake" | "anthropic"
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str | None = None

    embedding_provider: str = "fake"  # "fake" | "azure_openai"
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    vector_store: str = "memory"  # "memory" | "pgvector"
    database_url: str | None = None

    confidence_threshold: float = 0.72
    retrieval_top_k: int = 5


settings = Settings()
