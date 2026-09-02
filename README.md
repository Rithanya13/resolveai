# ResolveAI

**An agentic incident-resolution platform for customer support/ops teams.** It investigates a support incident the way a competent human agent would — pull the customer record, check order/ticket history, cross-reference policy, decide whether the evidence actually supports acting — and it only acts autonomously when the evidence and the dollar value both clear a bar. Below that bar, it pauses and hands off to a human, with its reasoning attached.

This is **not a chatbot**. There's no chat UI and no "have a conversation with your data." It's a graph of specialized steps — classify, retrieve, gather evidence, assess, decide, act-or-escalate — each one testable in isolation, wired together with [LangGraph](https://github.com/langchain-ai/langgraph). That distinction is the whole point: a chatbot that sounds confident is a demo; a system that knows when *not* to act on its own is closer to something you could actually put in front of production traffic.

## Why this exists

Support/ops teams don't need another wrapper around a chat completion. They need something that can be trusted to: pull real evidence before making a claim, say "I'm not sure" instead of hallucinating a resolution, and route the expensive or ambiguous cases to a person — automatically, with full context, not as an afterthought. ResolveAI is a from-scratch implementation of that pattern, built to be read end-to-end by an engineer evaluating it, not just run.

## Architecture

```mermaid
flowchart TD
    START([Incident submitted]) --> CLASSIFY[classify<br/><small>LLM: structured category + urgency</small>]
    CLASSIFY --> RETRIEVE[retrieve<br/><small>hybrid RAG: BM25 + vector, RRF fusion</small>]
    RETRIEVE --> GATHER[gather_evidence<br/><small>MCP tools: CRM + ticketing</small>]
    GATHER --> ASSESS[assess<br/><small>LLM: is evidence sufficient? confidence?</small>]
    ASSESS -->|confidence &gt;= threshold| RESOLVE[resolve<br/><small>LLM: structured decision + citations</small>]
    ASSESS -->|confidence &lt; threshold| REVIEW
    RESOLVE -->|refund over $500| REVIEW[human_review<br/><small>LangGraph interrupt() — graph genuinely pauses</small>]
    RESOLVE -->|else| EXECUTE[execute_action<br/><small>MCP tool call, e.g. issue refund</small>]
    REVIEW -->|approved| EXECUTE
    REVIEW -->|rejected| FINALIZE
    EXECUTE --> FINALIZE[finalize]
    FINALIZE --> END([resolved / escalated])
```

Two different triggers — thin evidence, or a high-value action — route through the **same** human-in-the-loop node instead of two divergent code paths. `human_review` calls LangGraph's `interrupt()`, which really does suspend graph execution (the checkpointer persists state); a `POST /incidents/{id}/approve` call later resumes it with `Command(resume=...)`. This isn't a status flag simulating a pause — it's the actual mechanism production LangGraph deployments use for durable human approval steps.

## Engineering decisions worth knowing about

**Everything an LLM returns is a validated Pydantic model, never free text.** `IncidentClassification`, `EvidenceAssessment`, `ResolutionDecision` — the graph's routing logic (`route_after_assess`, `route_after_resolve`) reads fields off these, not regexes over prose. See `resolveai/schemas.py`.

**Every external dependency is swappable behind an interface, chosen by env var.** LLM (`fake` / `anthropic`), embeddings (`fake` / `azure_openai`), vector store (`memory` / `pgvector`). The `fake` providers are deterministic, offline, and used by default — that's what lets the entire test suite and CI run with zero API keys and zero external services, while the exact same graph code runs unchanged against real providers in production. See `resolveai/config.py` and `resolveai/llm/`, `resolveai/retrieval/`.

**Hybrid retrieval, not vector-only.** BM25 (exact keyword match — SKU numbers, error codes) and dense vector search are fused with Reciprocal Rank Fusion, a zero-training-data technique that reliably beats either signal alone. See `resolveai/retrieval/hybrid_retriever.py`.

**Evidence is separated from reference material.** A retrieved policy passage tells you what the *rule* is; it doesn't prove anything about *this* customer. Only confirmed CRM/order/ticket lookups count as grounding evidence for the confidence gate — a policy doc alone can't push a case over the auto-resolve threshold. See `_is_grounding()` in `resolveai/graph/nodes.py`.

**Real MCP, not a mocked interface.** The CRM and ticketing tools are actual [MCP](https://modelcontextprotocol.io/) servers (`resolveai/tools/mcp_*_server.py`), spawned as subprocesses and called over the real JSON-RPC/stdio wire protocol (`resolveai/tools/mcp_client.py`). Only the *data* behind them is mocked (`resolveai/tools/mock_data.py`) — swapping that module for a real CRM/ticketing API client is the only change needed to point this at production systems.

**A structured eval harness, not vibes.** `evals/` runs a labeled set of incidents through the graph and reports classification accuracy, escalation precision/recall, and a groundedness rate (did every auto-resolution actually cite a source?) — see [Evals](#evals) below.

## Quickstart

Requires **Python 3.11+** — LangGraph's `interrupt()` relies on `contextvars` propagation through `asyncio` that isn't reliable before 3.11 when called from an async node (exactly what `human_review_node` does). If your default `python3` is 3.10 (e.g. Ubuntu 22.04), install 3.11 with [`uv`](https://docs.astral.sh/uv/) (`uv python install 3.11`, no sudo needed) or `pyenv`, then point the venv at it.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# runs entirely offline (fake LLM + embeddings, in-memory vector store)
uvicorn resolveai.api.main:app --reload
```

```bash
# submit an incident
curl -s -X POST localhost:8000/incidents -H "Content-Type: application/json" -d '{
  "customer_id": "cust_1002",
  "subject": "Charged twice for one order",
  "description": "I was charged twice for order_5002, please refund the duplicate charge."
}' | python3 -m json.tool

# a high-value refund pauses for human review -- approve it:
curl -s -X POST localhost:8000/incidents/<incident_id>/approve -H "Content-Type: application/json" \
  -d '{"approved": true, "note": "confirmed with finance"}'
```

Mock customers to try: `cust_1001`..`cust_1004` (in `resolveai/tools/mock_data.py`) exist with orders/tickets; `cust_1004`'s order is $899 (above the $500 auto-approve limit, so a refund pauses for review); any other customer id has no CRM record (triggers the low-confidence escalation path).

### Docker

```bash
docker compose up --build         # api on :8000, fake providers, in-memory store
RESOLVEAI_VECTOR_STORE=pgvector docker compose up --build   # + real Postgres/pgvector
```

### Going to real providers

Copy `.env.example` to `.env` and set `RESOLVEAI_LLM_PROVIDER=anthropic` (+ an API key) and/or `RESOLVEAI_EMBEDDING_PROVIDER=azure_openai` (+ Azure OpenAI credentials). Nothing else changes — same graph, same routes, same tests structure.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/incidents` | Submit an incident; runs the graph until it resolves or pauses for human review |
| `GET` | `/incidents` | List known incidents + status |
| `GET` | `/incidents/{id}` | Current state of one incident |
| `POST` | `/incidents/{id}/approve` | Resume a paused incident with a human decision (`{"approved": bool, "note": str}`) |
| `GET` | `/health` | Liveness check |

## Testing

```bash
pytest tests/unit -q          # ~30 tests, milliseconds -- stubbed MCP calls, no subprocess
pytest tests/integration -q   # ~90s -- real MCP subprocess spawns, real FastAPI app, full graph runs
```

45 tests total. `tests/unit` covers retrieval (BM25, vector store, RRF fusion), the deterministic fake LLM's prompt-parsing conventions, schema validation, and each graph node in isolation with stubbed dependencies. `tests/integration` covers the real MCP wire protocol, the full graph end-to-end (all three routing outcomes: auto-resolve, value-gated HITL, low-confidence HITL), and the FastAPI layer via Starlette's `TestClient`.

## Evals

```bash
python -m evals.run_evals
```

Runs 10 hand-labeled incidents (`evals/dataset.jsonl`) through the graph and reports:

| metric | what it checks |
|---|---|
| category accuracy | did classification match the expected category? |
| outcome accuracy | did the system correctly auto-resolve vs. escalate? |
| escalation precision | of the cases it escalated, how many *should* have been? |
| escalation recall | of the cases that *should* have escalated, how many did it catch? |
| groundedness rate | did every auto-resolved case cite at least one source? |

This is a small, hand-curated regression suite that validates the graph's *routing logic* against known-correct expectations — it's wired into CI (`tests/integration/test_evals.py`) as a floor (each metric ≥ 90%) so a routing regression fails the build. It is deliberately not a claim of "production accuracy on real traffic" — see Roadmap.

## Roadmap (honest about what V1 doesn't cover)

- **Reranking**: currently RRF fusion of BM25 + vector; a cross-encoder reranker is the natural next step once there's query/click data to justify it.
- **LLM-graded evals**: today's eval harness checks routing correctness against ground truth; a RAGAS-style faithfulness/relevance judge (using a real LLM) would complement it, especially for judging the *quality* of `customer_message` text rather than just the routing decision.
- **Observability**: structured logging exists (`resolveai.graph` logger); LangSmith/Langfuse tracing is not yet wired in.
- **MCP connection pooling**: `mcp_client.py` spawns one subprocess per tool call for correctness/simplicity; a pooled `AsyncExitStack`-based client would cut latency under load.
- **Real knowledge base ingestion**: `knowledge_base/seed_docs.py` is static; a real deployment needs a sync pipeline from the actual docs source.
- **Cloud deploy config**: Dockerized; a Terraform/Cloud Run or ECS config for an actual deployment isn't included yet.

## Stack

LangGraph (orchestration, structured routing, `interrupt()`-based HITL) · FastAPI · MCP (real tool servers, not mocked) · hybrid RAG (BM25 + vector + RRF) · Pydantic structured outputs · pgvector (production vector store option) · Docker Compose · GitHub Actions CI · pytest
