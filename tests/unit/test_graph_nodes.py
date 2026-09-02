"""Node-level unit tests. `call_mcp_tool` is stubbed here (no subprocess) so
these run in milliseconds -- the real MCP wire protocol is covered instead by
`tests/integration/test_mcp_servers.py`.
"""

from __future__ import annotations

import pytest

from resolveai.graph.nodes import (
    REFUND_AUTO_APPROVE_LIMIT_USD,
    GraphDeps,
    assess_node,
    classify_node,
    gather_evidence_node,
    resolve_node,
    route_after_assess,
    route_after_resolve,
)
from resolveai.llm.fake import FakeLLM
from resolveai.retrieval.bm25_index import BM25Index
from resolveai.retrieval.embeddings import FakeEmbedding
from resolveai.retrieval.hybrid_retriever import HybridRetriever
from resolveai.retrieval.vector_store import InMemoryVectorStore
from resolveai.schemas import Incident, IncidentCategory, ResolutionAction, ResolutionDecision


def _stub_mcp(responses: dict):
    async def call(server_key: str, tool_name: str, arguments: dict) -> dict:
        return responses.get((server_key, tool_name), {"found": False})

    return call


def _deps(mcp_responses: dict) -> GraphDeps:
    retriever = HybridRetriever(FakeEmbedding(dim=32), InMemoryVectorStore(), BM25Index())
    return GraphDeps(llm=FakeLLM(), retriever=retriever, call_mcp_tool=_stub_mcp(mcp_responses))


def _incident(**overrides) -> Incident:
    base = dict(incident_id="t1", customer_id="cust_x", subject="Refund needed", description="Please refund me")
    base.update(overrides)
    return Incident(**base)


@pytest.mark.asyncio
async def test_classify_node_sets_classification():
    update = await classify_node({"incident": _incident(), "trace": []}, deps=_deps({}))
    assert update["classification"].category == IncidentCategory.REFUND_REQUEST
    assert update["trace"] == ["classify"]


@pytest.mark.asyncio
async def test_gather_evidence_node_found_customer_and_order():
    mcp = {
        ("crm", "get_customer"): {"found": True, "name": "Test", "orders": ["order_1"]},
        ("crm", "get_order"): {
            "found": True,
            "order_id": "order_1",
            "status": "shipped",
            "tracking_status": "ok",
            "amount_usd": 42.0,
        },
        ("ticketing", "get_ticket_history"): {"tickets": []},
    }
    update = await gather_evidence_node({"incident": _incident(), "trace": []}, deps=_deps(mcp))
    assert len(update["tool_evidence"]) == 2  # customer + order (no tickets)
    assert update["order_amount_usd"] == 42.0


@pytest.mark.asyncio
async def test_gather_evidence_node_missing_customer_yields_no_grounding_evidence():
    update = await gather_evidence_node({"incident": _incident(), "trace": []}, deps=_deps({}))
    # a "not found" result IS recorded (for audit) but assess_node treats it as a gap, not grounding
    assert len(update["tool_evidence"]) == 1
    assert update["tool_evidence"][0].raw.get("found") is False


@pytest.mark.asyncio
async def test_assess_node_insufficient_when_no_grounding_evidence():
    state = {"incident": _incident(), "retrieved_passages": [], "tool_evidence": [], "trace": []}
    update = await assess_node(state, deps=_deps({}))
    assert update["assessment"].is_sufficient is False


def test_route_after_assess_sufficient_goes_to_resolve():
    from resolveai.schemas import EvidenceAssessment

    state = {"assessment": EvidenceAssessment(is_sufficient=True, confidence=0.9)}
    assert route_after_assess(state) == "resolve"


def test_route_after_assess_low_confidence_goes_to_human_review():
    from resolveai.schemas import EvidenceAssessment

    state = {"assessment": EvidenceAssessment(is_sufficient=True, confidence=0.1)}
    assert route_after_assess(state) == "human_review"


def test_route_after_resolve_large_refund_needs_human_review():
    decision = ResolutionDecision(action=ResolutionAction.ISSUE_REFUND, customer_message="x", internal_notes="y")
    state = {"decision": decision, "order_amount_usd": REFUND_AUTO_APPROVE_LIMIT_USD + 1}
    assert route_after_resolve(state) == "human_review"


def test_route_after_resolve_small_refund_executes_directly():
    decision = ResolutionDecision(action=ResolutionAction.ISSUE_REFUND, customer_message="x", internal_notes="y")
    state = {"decision": decision, "order_amount_usd": REFUND_AUTO_APPROVE_LIMIT_USD - 1}
    assert route_after_resolve(state) == "execute_action"


def test_route_after_resolve_non_refund_action_always_executes():
    decision = ResolutionDecision(
        action=ResolutionAction.RESET_ACCOUNT_ACCESS, customer_message="x", internal_notes="y"
    )
    state = {"decision": decision, "order_amount_usd": 10_000.0}
    assert route_after_resolve(state) == "execute_action"


@pytest.mark.asyncio
async def test_resolve_node_produces_grounded_decision():
    state = {
        "incident": _incident(),
        "classification": (await classify_node({"incident": _incident(), "trace": []}, deps=_deps({})))[
            "classification"
        ],
        "retrieved_passages": [],
        "trace": [],
    }
    update = await resolve_node(state, deps=_deps({}))
    assert update["decision"].action == ResolutionAction.ISSUE_REFUND
