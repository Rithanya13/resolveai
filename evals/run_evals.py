"""Run the eval dataset against the graph and print a report.

    python -m evals.run_evals

Uses FakeLLM/in-memory retrieval by default (same as tests/CI -- no API key
needed). Set RESOLVEAI_LLM_PROVIDER=anthropic (with an API key configured) to
eval against the real model instead; the harness code is identical either way.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from evals.metrics import CaseResult, EvalReport
from resolveai.graph.build import build_graph
from resolveai.graph.nodes import GraphDeps
from resolveai.graph.serde import build_serializer
from resolveai.knowledge_base.seed_docs import SEED_DOCS
from resolveai.llm import get_llm_client
from resolveai.retrieval.bm25_index import BM25Index
from resolveai.retrieval.embeddings import get_embedding_provider
from resolveai.retrieval.hybrid_retriever import HybridRetriever
from resolveai.retrieval.vector_store import get_vector_store
from resolveai.schemas import Incident
from resolveai.tools.mcp_client import call_mcp_tool

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


async def run_case(graph, case: dict) -> CaseResult:
    incident = Incident(
        incident_id=case["case_id"],
        customer_id=case["customer_id"],
        subject=case["subject"],
        description=case["description"],
    )
    config = {"configurable": {"thread_id": f"eval-{case['case_id']}"}}
    result = await graph.ainvoke({"incident": incident, "trace": []}, config=config)

    interrupted = bool(result.get("__interrupt__"))
    actual_outcome = "human_review" if interrupted else "auto_resolved"
    classification = result.get("classification")
    decision = result.get("decision")
    grounded = bool(decision and decision.citations)

    return CaseResult(
        case_id=case["case_id"],
        expected_category=case["expected_category"],
        actual_category=classification.category.value if classification else None,
        expected_outcome=case["expected_outcome"],
        actual_outcome=actual_outcome,
        grounded=grounded,
    )


async def main() -> EvalReport:
    embeddings = get_embedding_provider()
    vector_store = get_vector_store(dim=embeddings.dim)
    retriever = HybridRetriever(embeddings, vector_store, BM25Index())
    retriever.index(SEED_DOCS)
    deps = GraphDeps(llm=get_llm_client(), retriever=retriever, call_mcp_tool=call_mcp_tool)
    graph = build_graph(deps, checkpointer=InMemorySaver(serde=build_serializer()))

    results = [await run_case(graph, case) for case in load_dataset()]
    return EvalReport(results=results)


if __name__ == "__main__":
    report = asyncio.run(main())
    print(report.to_markdown())
