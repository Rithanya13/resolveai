"""Pydantic contracts shared across the graph, tools, and API.

Every LLM call in this project returns one of these models, never free text.
Structured, validated outputs are what make the graph's routing (confidence
gating, escalation) deterministic and testable instead of regex-parsing prose.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IncidentCategory(str, Enum):
    ORDER_NOT_RECEIVED = "order_not_received"
    REFUND_REQUEST = "refund_request"
    ACCOUNT_ACCESS = "account_access"
    BILLING_DISCREPANCY = "billing_discrepancy"
    OTHER = "other"


class Incident(BaseModel):
    """A support incident submitted to ResolveAI for investigation."""

    incident_id: str
    customer_id: str
    subject: str
    description: str


class IncidentClassification(BaseModel):
    """Structured output of the classify node."""

    category: IncidentCategory
    urgency: int = Field(ge=1, le=5, description="1 = low, 5 = critical")
    rationale: str


class RetrievedPassage(BaseModel):
    doc_id: str
    title: str
    text: str
    score: float


class ToolEvidence(BaseModel):
    """A single piece of evidence pulled from an MCP tool call."""

    source_tool: str
    summary: str
    raw: dict


class EvidenceAssessment(BaseModel):
    """Structured output of the evidence-evaluation node.

    This is the model the confidence gate routes on -- it is the difference
    between an agent that *acts* and one that just narrates a plausible-sounding
    story.
    """

    is_sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)
    grounded_claims: list[str] = Field(
        default_factory=list, description="Claims directly supported by retrieved evidence"
    )
    unsupported_claims: list[str] = Field(
        default_factory=list, description="Claims the model wanted to make but evidence didn't support"
    )
    missing_evidence: list[str] = Field(default_factory=list)


class ResolutionAction(str, Enum):
    ISSUE_REFUND = "issue_refund"
    RESEND_ORDER = "resend_order"
    RESET_ACCOUNT_ACCESS = "reset_account_access"
    CORRECT_BILLING = "correct_billing"
    NO_ACTION_NEEDED = "no_action_needed"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class ResolutionDecision(BaseModel):
    """Structured output of the resolve node -- the final, auditable verdict."""

    action: ResolutionAction
    customer_message: str
    internal_notes: str
    citations: list[str] = Field(default_factory=list, description="doc_ids / tool calls relied on")


class EscalationRequest(BaseModel):
    """Raised when confidence is too low to act autonomously (human-in-the-loop)."""

    incident_id: str
    reason: str
    assessment: EvidenceAssessment
    recommended_action: ResolutionAction | None = None


class IncidentResult(BaseModel):
    """What the API returns once an incident finishes the graph."""

    incident_id: str
    status: str  # "resolved" | "escalated" | "error"
    classification: IncidentClassification | None = None
    assessment: EvidenceAssessment | None = None
    decision: ResolutionDecision | None = None
    escalation: EscalationRequest | None = None
    trace: list[str] = Field(default_factory=list, description="Ordered list of graph nodes visited")
