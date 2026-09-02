"""Graph state definition.

A `TypedDict` rather than a Pydantic model because LangGraph's state updates
are partial dict merges between nodes -- TypedDict is the documented, most
ergonomic fit for that pattern. All the *payloads* carried inside the state
(classification, assessment, decision) are still fully validated Pydantic
models; only the outer container is a dict.
"""

from __future__ import annotations

from typing import TypedDict

from resolveai.schemas import (
    EscalationRequest,
    EvidenceAssessment,
    Incident,
    IncidentClassification,
    ResolutionDecision,
    RetrievedPassage,
    ToolEvidence,
)


class IncidentState(TypedDict, total=False):
    incident: Incident
    classification: IncidentClassification | None
    retrieved_passages: list[RetrievedPassage]
    tool_evidence: list[ToolEvidence]
    assessment: EvidenceAssessment | None
    decision: ResolutionDecision | None
    escalation: EscalationRequest | None
    status: str  # "resolved" | "escalated" | "error"
    trace: list[str]
    error: str | None
    order_amount_usd: float | None
    human_approved: bool | None
