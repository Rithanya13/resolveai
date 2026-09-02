"""Graph node implementations.

Each node is a small, testable function: `(state, deps) -> partial state
update`. Dependencies (LLM client, retriever, MCP caller) are passed in
explicitly rather than imported as globals, so `tests/unit/test_graph_nodes.py`
can swap in fakes/stubs per-test without any monkeypatching.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from resolveai.config import settings
from resolveai.graph.state import IncidentState
from resolveai.llm.base import LLMClient
from resolveai.retrieval.hybrid_retriever import HybridRetriever
from resolveai.schemas import (
    EscalationRequest,
    EvidenceAssessment,
    IncidentClassification,
    ResolutionAction,
    ResolutionDecision,
    ToolEvidence,
)

logger = logging.getLogger("resolveai.graph")

McpCaller = Callable[[str, str, dict], Awaitable[dict]]

REFUND_AUTO_APPROVE_LIMIT_USD = 500.0


@dataclass
class GraphDeps:
    """Bundle of collaborators every node needs. One instance per graph build."""

    llm: LLMClient
    retriever: HybridRetriever
    call_mcp_tool: McpCaller


def _trace(state: IncidentState, node_name: str) -> list[str]:
    return [*state.get("trace", []), node_name]


async def classify_node(state: IncidentState, deps: GraphDeps) -> dict:
    incident = state["incident"]
    prompt = f"SUBJECT: {incident.subject}\nDESCRIPTION: {incident.description}"
    classification = deps.llm.complete_structured(
        system="You classify customer support incidents into a fixed set of categories.",
        prompt=prompt,
        schema=IncidentClassification,
    )
    logger.info("incident=%s classified as %s", incident.incident_id, classification.category)
    return {"classification": classification, "trace": _trace(state, "classify")}


async def retrieve_node(state: IncidentState, deps: GraphDeps) -> dict:
    incident = state["incident"]
    query = f"{incident.subject} {incident.description}"
    passages = deps.retriever.retrieve(query, top_k=settings.retrieval_top_k)
    return {"retrieved_passages": passages, "trace": _trace(state, "retrieve")}


async def gather_evidence_node(state: IncidentState, deps: GraphDeps) -> dict:
    """Call MCP tools (CRM + ticketing) to pull evidence relevant to this incident."""
    incident = state["incident"]
    evidence: list[ToolEvidence] = []
    order_amount_usd: float | None = None

    customer = await deps.call_mcp_tool("crm", "get_customer", {"customer_id": incident.customer_id})
    if customer.get("found"):
        evidence.append(
            ToolEvidence(
                source_tool="crm.get_customer",
                summary=f"Customer {customer['name']} on file with {len(customer.get('orders', []))} order(s).",
                raw=customer,
            )
        )
        for order_id in customer.get("orders", []):
            order = await deps.call_mcp_tool("crm", "get_order", {"order_id": order_id})
            if order.get("found"):
                evidence.append(
                    ToolEvidence(
                        source_tool="crm.get_order",
                        summary=(
                            f"Order {order['order_id']}: status={order['status']}, "
                            f"tracking={order['tracking_status']}, amount=${order['amount_usd']}"
                        ),
                        raw=order,
                    )
                )
                order_amount_usd = order["amount_usd"]
    else:
        evidence.append(
            ToolEvidence(
                source_tool="crm.get_customer",
                summary=f"No CRM record found for customer_id={incident.customer_id}.",
                raw=customer,
            )
        )

    tickets = await deps.call_mcp_tool("ticketing", "get_ticket_history", {"customer_id": incident.customer_id})
    if tickets.get("tickets"):
        evidence.append(
            ToolEvidence(
                source_tool="ticketing.get_ticket_history",
                summary=f"{len(tickets['tickets'])} prior ticket(s) on file.",
                raw=tickets,
            )
        )

    update: dict = {"tool_evidence": evidence, "trace": _trace(state, "gather_evidence")}
    if order_amount_usd is not None:
        update["order_amount_usd"] = order_amount_usd
    return update


def _is_grounding(evidence: ToolEvidence) -> bool:
    """Only tool calls that actually confirmed a customer/order record count as
    grounding evidence -- a 'no record found' result is a gap, not proof."""
    return evidence.raw.get("found", True) is not False


async def assess_node(state: IncidentState, deps: GraphDeps) -> dict:
    passages = state.get("retrieved_passages", [])
    tool_evidence = state.get("tool_evidence", [])
    grounding = [e for e in tool_evidence if _is_grounding(e)]
    gaps = [e for e in tool_evidence if not _is_grounding(e)]

    evidence_bullets = [f"- [tool:{e.source_tool}] {e.summary}" for e in grounding]
    reference_bullets = [f"- [kb:{p.doc_id}] {p.title}: {p.text[:160]}" for p in passages]
    gap_bullets = [f"- [gap:{e.source_tool}] {e.summary}" for e in gaps]

    prompt = (
        f"EVIDENCE_COUNT: {len(evidence_bullets)}\n"
        + "\n".join(evidence_bullets)
        + "\n\nREFERENCE (policy/runbook context, not case-specific proof):\n"
        + "\n".join(reference_bullets)
        + ("\n\nGAPS:\n" + "\n".join(gap_bullets) if gap_bullets else "")
        + f"\n\nIncident: {state['incident'].subject} -- {state['incident'].description}"
    )
    assessment = deps.llm.complete_structured(
        system="You judge whether retrieved evidence is sufficient to act on a support incident.",
        prompt=prompt,
        schema=EvidenceAssessment,
    )
    return {"assessment": assessment, "trace": _trace(state, "assess")}


def route_after_assess(state: IncidentState) -> str:
    assessment = state["assessment"]
    if assessment.is_sufficient and assessment.confidence >= settings.confidence_threshold:
        return "resolve"
    return "human_review"


async def resolve_node(state: IncidentState, deps: GraphDeps) -> dict:
    classification = state["classification"]
    passages = state.get("retrieved_passages", [])
    citations = [p.doc_id for p in passages]
    prompt = f"CATEGORY: {classification.category.value}\nCITATIONS: {', '.join(citations)}"
    decision = deps.llm.complete_structured(
        system="You decide and articulate the resolution for a support incident with sufficient evidence.",
        prompt=prompt,
        schema=ResolutionDecision,
    )
    return {"decision": decision, "trace": _trace(state, "resolve")}


def route_after_resolve(state: IncidentState) -> str:
    decision = state["decision"]
    amount = state.get("order_amount_usd")
    if (
        decision.action == ResolutionAction.ISSUE_REFUND
        and amount is not None
        and amount > REFUND_AUTO_APPROVE_LIMIT_USD
    ):
        return "human_review"
    return "execute_action"


async def human_review_node(state: IncidentState, deps: GraphDeps) -> dict:
    """Pause the graph for a human decision.

    Uses LangGraph's `interrupt()` -- execution genuinely suspends here (the
    checkpointer persists state) until something resumes the graph with
    `Command(resume=...)`. See `resolveai.api.routes` for the endpoint that
    does that resume in response to a human clicking approve/reject.
    """
    from langgraph.types import interrupt

    decision = state.get("decision")
    assessment = state["assessment"]
    if decision is not None:
        reason = (
            f"Proposed action '{decision.action.value}' requires human approval: "
            f"order value ${state.get('order_amount_usd')} exceeds the ${REFUND_AUTO_APPROVE_LIMIT_USD} autonomous limit."
        )
    else:
        reason = "Evidence was insufficient for the agent to act autonomously."

    escalation = EscalationRequest(
        incident_id=state["incident"].incident_id,
        reason=reason,
        assessment=assessment,
        recommended_action=decision.action if decision else None,
    )

    human_response = interrupt(
        {
            "incident_id": state["incident"].incident_id,
            "reason": reason,
            "assessment": assessment.model_dump(),
            "recommended_action": decision.action.value if decision else None,
            "proposed_customer_message": decision.customer_message if decision else None,
        }
    )
    # Execution resumes here once `Command(resume=human_response)` is sent in.
    approved = bool(human_response.get("approved", False))
    note = human_response.get("note", "")

    update: dict = {"escalation": escalation, "trace": _trace(state, "human_review")}
    if approved and decision is not None:
        update["human_approved"] = True
    elif approved and decision is None:
        chosen_action = ResolutionAction(human_response.get("action", ResolutionAction.NO_ACTION_NEEDED.value))
        update["decision"] = ResolutionDecision(
            action=chosen_action,
            customer_message=human_response.get("customer_message", note or "A support agent has reviewed your case."),
            internal_notes=f"Human-resolved after escalation. Note: {note}",
            citations=[],
        )
        update["human_approved"] = True
    else:
        update["human_approved"] = False
        update["status"] = "escalated"
    return update


def route_after_human_review(state: IncidentState) -> str:
    if state.get("human_approved"):
        return "execute_action"
    return "finalize"


async def execute_action_node(state: IncidentState, deps: GraphDeps) -> dict:
    """Carry out the side-effecting part of a resolution decision (if any) via MCP tools."""
    decision = state["decision"]
    incident = state["incident"]

    if decision.action == ResolutionAction.ISSUE_REFUND:
        customer = await deps.call_mcp_tool("crm", "get_customer", {"customer_id": incident.customer_id})
        order_id = customer.get("orders", [None])[0]
        amount = state.get("order_amount_usd", 0.0)
        if order_id:
            result = await deps.call_mcp_tool(
                "ticketing",
                "create_refund",
                {"order_id": order_id, "amount_usd": amount, "reason": decision.internal_notes},
            )
            decision.internal_notes += f" | refund confirmation={result.get('confirmation_id')}"

    return {"decision": decision, "status": "resolved", "trace": _trace(state, "execute_action")}


async def finalize_node(state: IncidentState, deps: GraphDeps) -> dict:
    status = state.get("status")
    if status not in ("resolved", "escalated"):
        status = "escalated" if state.get("escalation") else "resolved"
    return {"status": status, "trace": _trace(state, "finalize")}
