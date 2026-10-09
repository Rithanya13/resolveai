"""HTTP surface for ResolveAI.

POST   /incidents                 submit a new incident, runs the graph until
                                   it resolves or pauses for human review
GET    /incidents                 list known incident ids + status
GET    /incidents/{id}            current state of one incident
POST   /incidents/{id}/approve    resume a paused incident with a human decision
GET    /evals                     run the labeled eval set, return metrics as JSON
GET    /health                    liveness check
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command
from pydantic import BaseModel

from resolveai.config import settings
from resolveai.schemas import Incident

router = APIRouter()


class SubmitIncidentRequest(BaseModel):
    customer_id: str
    subject: str
    description: str


class ApprovalRequest(BaseModel):
    approved: bool
    note: str = ""
    action: str | None = None  # only used when no `decision` existed yet (pure low-confidence case)
    customer_message: str | None = None


def _serialize(value):
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _pending_review_from_result(result: dict):
    """Interrupt payload from a graph.ainvoke() result (present only when the run paused)."""
    interrupts = result.get("__interrupt__")
    return interrupts[0].value if interrupts else None


def _pending_review_from_snapshot(snapshot):
    """Interrupt payload from a checkpointed snapshot.

    A stored snapshot exposes pending interrupts on `snapshot.interrupts`, not
    as an `__interrupt__` key in `snapshot.values` (that key only exists on the
    return value of `ainvoke`). Reading the wrong one 500s every GET of a
    paused incident.
    """
    return snapshot.interrupts[0].value if snapshot.interrupts else None


def _response_from_state(incident_id: str, state: dict, pending_review) -> dict:
    interrupted = pending_review is not None
    incident = state.get("incident")
    body = {
        "incident_id": incident_id,
        "status": "pending_human_review" if interrupted else state.get("status", "unknown"),
        "incident": _serialize(incident),
        "trace": state.get("trace", []),
        # Exposed so a reviewer can trace every citation in `decision` back to
        # the exact policy passage or MCP tool result it came from.
        "retrieved_passages": _serialize(state.get("retrieved_passages", [])),
        "tool_evidence": _serialize(state.get("tool_evidence", [])),
        "order_amount_usd": state.get("order_amount_usd"),
        "confidence_threshold": settings.confidence_threshold,
        "classification": _serialize(state.get("classification")),
        "assessment": _serialize(state.get("assessment")),
        "decision": _serialize(state.get("decision")),
        "escalation": _serialize(state.get("escalation")),
    }
    if interrupted:
        body["pending_review"] = pending_review
    return body


@router.get("/evals")
async def run_evals() -> dict:
    """Run the labeled eval set through a fresh graph and return the metrics.

    Uses its own graph + checkpointer (via `evals.run_evals.main`) so eval
    threads never mix with live incidents.
    """
    from evals.run_evals import main as run_eval_suite

    report = await run_eval_suite()
    return report.to_dict()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/incidents")
async def submit_incident(payload: SubmitIncidentRequest, request: Request) -> dict:
    incident_id = f"inc_{uuid.uuid4().hex[:12]}"
    incident = Incident(
        incident_id=incident_id,
        customer_id=payload.customer_id,
        subject=payload.subject,
        description=payload.description,
    )
    config = {"configurable": {"thread_id": incident_id}}
    graph = request.app.state.graph
    result = await graph.ainvoke({"incident": incident, "trace": []}, config=config)
    request.app.state.incident_index.add(incident_id)
    return _response_from_state(incident_id, result, _pending_review_from_result(result))


@router.get("/incidents")
async def list_incidents(request: Request) -> dict:
    graph = request.app.state.graph
    out = []
    for incident_id in request.app.state.incident_index.list_ids():
        config = {"configurable": {"thread_id": incident_id}}
        snapshot = await graph.aget_state(config)
        out.append(_response_from_state(incident_id, snapshot.values, _pending_review_from_snapshot(snapshot)))
    return {"incidents": out}


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, request: Request) -> dict:
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": incident_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"No incident found with id {incident_id!r}")
    return _response_from_state(incident_id, snapshot.values, _pending_review_from_snapshot(snapshot))


@router.post("/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str, payload: ApprovalRequest, request: Request) -> dict:
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": incident_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"No incident found with id {incident_id!r}")
    if not snapshot.interrupts:
        raise HTTPException(status_code=409, detail=f"Incident {incident_id!r} is not awaiting human review")

    resume_payload = payload.model_dump(exclude_none=True)
    result = await graph.ainvoke(Command(resume=resume_payload), config=config)
    return _response_from_state(incident_id, result, _pending_review_from_result(result))
