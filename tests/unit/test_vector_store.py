import numpy as np

from resolveai.retrieval.vector_store import InMemoryVectorStore, VectorRecord


def _vec(*components: float) -> np.ndarray:
    return np.array(components, dtype=np.float32)


def test_in_memory_vector_store_ranks_by_cosine_similarity():
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord("a", "A", "text a", _vec(1.0, 0.0)),
            VectorRecord("b", "B", "text b", _vec(0.0, 1.0)),
        ]
    )
    hits = store.search(_vec(1.0, 0.01), top_k=2)
    assert hits[0][0].doc_id == "a"
    assert hits[0][1] > hits[1][1]


def test_upsert_overwrites_existing_doc_id():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord("a", "old title", "old text", _vec(1.0, 0.0))])
    store.upsert([VectorRecord("a", "new title", "new text", _vec(1.0, 0.0))])
    hits = store.search(_vec(1.0, 0.0), top_k=5)
    assert len(hits) == 1
    assert hits[0][0].title == "new title"


def test_empty_store_returns_no_hits():
    store = InMemoryVectorStore()
    assert store.search(_vec(1.0, 0.0), top_k=5) == []
