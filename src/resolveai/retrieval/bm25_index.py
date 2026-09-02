"""Sparse (keyword) side of hybrid retrieval, via rank_bm25.

Dense embeddings alone miss exact-match signals that matter a lot in support
knowledge bases -- SKU numbers, error codes, policy section numbers. BM25
catches those; the hybrid retriever fuses both rankings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class BM25Document:
    doc_id: str
    title: str
    text: str


class BM25Index:
    def __init__(self) -> None:
        self._docs: list[BM25Document] = []
        self._bm25: BM25Okapi | None = None

    def build(self, docs: list[BM25Document]) -> None:
        self._docs = docs
        corpus = [_tokenize(f"{d.title} {d.text}") for d in docs]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int) -> list[tuple[BM25Document, float]]:
        if self._bm25 is None or not self._docs:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._docs, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        return [(doc, float(score)) for doc, score in ranked[:top_k] if score > 0]
