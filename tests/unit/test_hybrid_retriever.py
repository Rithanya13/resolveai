from resolveai.retrieval.bm25_index import BM25Index
from resolveai.retrieval.embeddings import FakeEmbedding
from resolveai.retrieval.hybrid_retriever import HybridRetriever, KnowledgeDoc
from resolveai.retrieval.vector_store import InMemoryVectorStore


def _build_retriever() -> HybridRetriever:
    retriever = HybridRetriever(FakeEmbedding(dim=64), InMemoryVectorStore(), BM25Index())
    retriever.index(
        [
            KnowledgeDoc("refund", "Refund Policy", "Refunds are issued within 3-5 business days for defective items."),
            KnowledgeDoc("shipping", "Shipping SLA", "Standard shipping is 3-7 business days via ground carrier."),
            KnowledgeDoc(
                "account", "Account Lockouts", "Accounts lock after 5 failed login attempts within 15 minutes."
            ),
        ]
    )
    return retriever


def test_hybrid_retrieval_surfaces_relevant_doc_first():
    retriever = _build_retriever()
    results = retriever.retrieve("I need a refund for a defective item", top_k=2)
    assert results
    assert results[0].doc_id == "refund"


def test_hybrid_retrieval_respects_top_k():
    retriever = _build_retriever()
    results = retriever.retrieve("shipping refund account", top_k=1)
    assert len(results) == 1


def test_hybrid_retrieval_on_empty_index_returns_nothing():
    retriever = HybridRetriever(FakeEmbedding(dim=64), InMemoryVectorStore(), BM25Index())
    assert retriever.retrieve("anything", top_k=5) == []
