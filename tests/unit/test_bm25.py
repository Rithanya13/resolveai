from resolveai.retrieval.bm25_index import BM25Document, BM25Index


def test_bm25_ranks_exact_keyword_match_first():
    index = BM25Index()
    index.build(
        [
            BM25Document("a", "Refund Policy", "Customers get a refund within 30 days for defective items."),
            BM25Document("b", "Shipping SLA", "Standard shipping SLA is 3-7 business days."),
            BM25Document("c", "Account Lockouts", "Accounts lock after 5 failed login attempts."),
        ]
    )
    hits = index.search("refund policy defective", top_k=2)
    assert hits[0][0].doc_id == "a"
    assert hits[0][1] > 0


def test_bm25_empty_index_returns_no_hits():
    index = BM25Index()
    index.build([])
    assert index.search("anything", top_k=5) == []


def test_bm25_no_keyword_overlap_returns_no_hits():
    index = BM25Index()
    index.build([BM25Document("a", "Refund Policy", "Customers get a refund within 30 days.")])
    assert index.search("zzz_no_overlap_qqq", top_k=5) == []
