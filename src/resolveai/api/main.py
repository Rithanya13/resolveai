"""FastAPI entrypoint.

Run locally:
    uvicorn resolveai.api.main:app --reload

Wires the graph's dependencies (LLM, retriever, MCP tool caller) once at
startup from `resolveai.config.settings`, so every request reuses the same
compiled graph and checkpointer. See `resolveai/api/routes.py` for the actual
endpoints.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from resolveai.api.store import IncidentIndex
from resolveai.config import settings
from resolveai.graph.build import build_graph
from resolveai.graph.nodes import GraphDeps
from resolveai.graph.serde import build_serializer
from resolveai.knowledge_base.seed_docs import SEED_DOCS
from resolveai.llm import get_llm_client
from resolveai.retrieval.bm25_index import BM25Index
from resolveai.retrieval.embeddings import get_embedding_provider
from resolveai.retrieval.hybrid_retriever import HybridRetriever
from resolveai.retrieval.vector_store import get_vector_store
from resolveai.tools.mcp_client import call_mcp_tool

logging.basicConfig(level=logging.INFO)


def _build_retriever() -> HybridRetriever:
    embeddings = get_embedding_provider()
    vector_store = get_vector_store(dim=embeddings.dim)
    retriever = HybridRetriever(embeddings, vector_store, BM25Index())
    retriever.index(SEED_DOCS)
    return retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    from langgraph.checkpoint.memory import InMemorySaver

    deps = GraphDeps(llm=get_llm_client(), retriever=_build_retriever(), call_mcp_tool=call_mcp_tool)
    checkpointer = InMemorySaver(serde=build_serializer())
    app.state.graph = build_graph(deps, checkpointer=checkpointer)
    app.state.incident_index = IncidentIndex()
    logging.getLogger("resolveai.api").info(
        "ResolveAI started (llm_provider=%s, embedding_provider=%s, vector_store=%s)",
        settings.llm_provider,
        settings.embedding_provider,
        settings.vector_store,
    )
    yield


app = FastAPI(title="ResolveAI", version="0.1.0", lifespan=lifespan)

from resolveai.api.routes import router  # noqa: E402  (after `app` exists, to avoid circular import)

app.include_router(router)
