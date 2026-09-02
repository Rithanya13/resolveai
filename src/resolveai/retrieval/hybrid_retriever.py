"""Hybrid retrieval: BM25 + dense vector search, fused with Reciprocal Rank Fusion.

RRF is used instead of a learned reranker because it needs no training data
and no extra model call, while still reliably outperforming either signal
alone -- a well-documented result in IR literature, and a defensible default
until enough query/click data exists to justify a cross-encoder reranker
(tracked in the README roadmap).
"""

from __future__ import annotations

from dataclasses import dataclass

from resolveai.retrieval.bm25_index import BM25Document, BM25Index
from resolveai.retrieval.embeddings import EmbeddingProvider
from resolveai.retrieval.vector_store import VectorRecord, VectorStore
from resolveai.schemas import RetrievedPassage

_RRF_K = 60  # standard smoothing constant from the original RRF paper


@dataclass
class KnowledgeDoc:
    doc_id: str
    title: str
    text: str


class HybridRetriever:
    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore, bm25_index: BM25Index) -> None:
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._bm25 = bm25_index

    def index(self, docs: list[KnowledgeDoc]) -> None:
        self._bm25.build([BM25Document(d.doc_id, d.title, d.text) for d in docs])
        vectors = self._embeddings.embed_batch([f"{d.title}\n{d.text}" for d in docs])
        records = [
            VectorRecord(doc_id=d.doc_id, title=d.title, text=d.text, embedding=vectors[i]) for i, d in enumerate(docs)
        ]
        self._vector_store.upsert(records)

    def retrieve(self, query: str, top_k: int = 5, fetch_k: int = 20) -> list[RetrievedPassage]:
        bm25_hits = self._bm25.search(query, top_k=fetch_k)
        query_vec = self._embeddings.embed(query)
        vector_hits = self._vector_store.search(query_vec, top_k=fetch_k)

        rrf_scores: dict[str, float] = {}
        doc_lookup: dict[str, tuple[str, str]] = {}  # doc_id -> (title, text)

        for rank, (doc, _score) in enumerate(bm25_hits):
            rrf_scores[doc.doc_id] = rrf_scores.get(doc.doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            doc_lookup[doc.doc_id] = (doc.title, doc.text)

        for rank, (record, _score) in enumerate(vector_hits):
            rrf_scores[record.doc_id] = rrf_scores.get(record.doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            doc_lookup[record.doc_id] = (record.title, record.text)

        ranked = sorted(rrf_scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]
        return [
            RetrievedPassage(doc_id=doc_id, title=doc_lookup[doc_id][0], text=doc_lookup[doc_id][1], score=score)
            for doc_id, score in ranked
        ]
