"""Full graph runs through the real MCP servers (subprocess) and FakeLLM.
Covers all three routing outcomes: clean auto-resolve, value-gated HITL, and
low-confidence HITL.
"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from resolveai.graph.build import build_graph
from resolveai.graph.nodes import GraphDeps
from resolveai.graph.serde import build_serializer
from resolveai.knowledge_base.seed_docs import SEED_DOCS
from resolveai.llm.fake import FakeLLM
from resolveai.retrieval.bm25_index import BM25Index
from resolveai.retrieval.embeddings import FakeEmbedding
from resolveai.retrieval.hybrid_retriever import HybridRetriever
from resolveai.retrieval.vector_store import InMemoryVectorStore
from resolveai.schemas import Incident
from resolveai.tools.mcp_client import call_mcp_tool


def _build_app():
    retriever = HybridRetriever(FakeEmbedding(), InMemoryVectorStore(), BM25Index())
    retriever.index(SEED_DOCS)
    deps = GraphDeps(llm=FakeLLM(), retriever=retriever, call_mcp_tool=call_mcp_tool)
    return build_graph(deps, checkpointer=InMemorySaver(serde=build_serializer()))


@pytest.mark.asyncio
async def test_small_refund_auto_resolves():
    app = _build_app()
    incident = Incident(
        incident_id="e2e-1",
        customer_id="cust_1002",
        subject="Charged twice",
        description="I was charged twice for order_5002, please refund the duplicate charge.",
    )
    config = {"configurable": {"thread_id": "e2e-1"}}
    result = await app.ainvoke({"incident": incident, "trace": []}, config=config)
    assert result["status"] == "resolved"
    assert "__interrupt__" not in result
    assert result["decision"].citations


@pytest.mark.asyncio
async def test_high_value_refund_pauses_then_resolves_on_approval():
    app = _build_app()
    incident = Incident(
        incident_id="e2e-2",
        customer_id="cust_1004",
        subject="Order never arrived, need refund",
        description="My order never arrived per tracking, I want a refund immediately.",
    )
    config = {"configurable": {"thread_id": "e2e-2"}}
    paused = await app.ainvoke({"incident": incident, "trace": []}, config=config)
    assert paused.get("__interrupt__")
    assert "human_review" not in paused.get("trace", [])  # interrupted mid-node, before trace append
    assert paused["__interrupt__"][0].value["reason"].startswith("Proposed action")

    resumed = await app.ainvoke(Command(resume={"approved": True, "note": "ok"}), config=config)
    assert resumed["status"] == "resolved"
    assert "human_review" in resumed["trace"]


@pytest.mark.asyncio
async def test_high_value_refund_stays_escalated_on_rejection():
    app = _build_app()
    incident = Incident(
        incident_id="e2e-3",
        customer_id="cust_1004",
        subject="Order never arrived, need refund",
        description="My order never arrived per tracking, I want a refund immediately.",
    )
    config = {"configurable": {"thread_id": "e2e-3"}}
    await app.ainvoke({"incident": incident, "trace": []}, config=config)
    resumed = await app.ainvoke(
        Command(resume={"approved": False, "note": "denied, needs manual review"}), config=config
    )
    assert resumed["status"] == "escalated"


@pytest.mark.asyncio
async def test_unknown_customer_escalates_for_insufficient_evidence():
    app = _build_app()
    incident = Incident(
        incident_id="e2e-4",
        customer_id="cust_totally_unknown",
        subject="Something weird happened",
        description="Not sure what is going on.",
    )
    config = {"configurable": {"thread_id": "e2e-4"}}
    paused = await app.ainvoke({"incident": incident, "trace": []}, config=config)
    assert paused.get("__interrupt__")
    assert paused["__interrupt__"][0].value["assessment"]["is_sufficient"] is False
