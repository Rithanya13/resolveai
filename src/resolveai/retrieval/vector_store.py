"""Vector store interface: in-memory (default/tests) and pgvector (production).

Swapping `RESOLVEAI_VECTOR_STORE=pgvector` + `RESOLVEAI_DATABASE_URL=...` is
the only change needed to move from local dev to the Postgres/pgvector
instance defined in docker-compose.yml -- `HybridRetriever` never imports
either backend directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class VectorRecord:
    doc_id: str
    title: str
    text: str
    embedding: np.ndarray


class VectorStore(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[VectorRecord, float]]: ...


class InMemoryVectorStore:
    """Brute-force cosine similarity. O(n) per query -- fine for a knowledge base
    of the size a single support-ops team needs (hundreds to low thousands of docs).
    """

    def __init__(self) -> None:
        self._records: list[VectorRecord] = []

    def upsert(self, records: list[VectorRecord]) -> None:
        by_id = {r.doc_id: r for r in self._records}
        for r in records:
            by_id[r.doc_id] = r
        self._records = list(by_id.values())

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[VectorRecord, float]]:
        if not self._records:
            return []
        scored = []
        for record in self._records:
            denom = np.linalg.norm(query_embedding) * np.linalg.norm(record.embedding)
            sim = float(np.dot(query_embedding, record.embedding) / denom) if denom > 0 else 0.0
            scored.append((record, sim))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


class PgVectorStore:
    """Production vector store backed by Postgres + the pgvector extension.

    See docker-compose.yml for the `postgres` service (pgvector/pgvector image)
    and `scripts/init_pgvector.sql` for the table/index DDL. Not exercised in
    the default test suite (no Postgres in CI) -- covered by
    `tests/integration/test_pgvector_store.py`, which is skipped unless
    `RESOLVEAI_DATABASE_URL` is set (see that file's `pytest.mark.skipif`).
    """

    def __init__(self, database_url: str, dim: int) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self._dim = dim
        self._conn = psycopg.connect(database_url, autocommit=True)
        register_vector(self._conn)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS resolveai_documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding vector({dim}) NOT NULL
            )
            """
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        with self._conn.cursor() as cur:
            for r in records:
                cur.execute(
                    """
                    INSERT INTO resolveai_documents (doc_id, title, text, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (doc_id) DO UPDATE
                    SET title = EXCLUDED.title, text = EXCLUDED.text, embedding = EXCLUDED.embedding
                    """,
                    (r.doc_id, r.title, r.text, r.embedding),
                )

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[VectorRecord, float]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_id, title, text, embedding, 1 - (embedding <=> %s) AS score
                FROM resolveai_documents
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()
        return [
            (VectorRecord(doc_id=row[0], title=row[1], text=row[2], embedding=row[3]), float(row[4])) for row in rows
        ]


def get_vector_store(dim: int) -> VectorStore:
    from resolveai.config import settings

    if settings.vector_store == "memory":
        return InMemoryVectorStore()
    if settings.vector_store == "pgvector":
        if not settings.database_url:
            raise RuntimeError("RESOLVEAI_DATABASE_URL must be set to use the pgvector vector store.")
        return PgVectorStore(settings.database_url, dim=dim)
    raise ValueError(f"Unknown RESOLVEAI_VECTOR_STORE: {settings.vector_store!r}")
