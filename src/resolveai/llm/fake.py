"""Deterministic stand-in LLM used for tests, CI, and local demo runs.

Nodes build prompts with a small set of conventions (see docstrings below) so
this class can produce *consistent, explainable* structured outputs without
calling out to a real model. It implements the same `LLMClient` protocol as
`AnthropicLLM`, so swapping `RESOLVEAI_LLM_PROVIDER=anthropic` in the
environment is the only change needed to go from "runs anywhere, no API key"
to "runs against a real model" -- nothing in graph/nodes.py changes.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from resolveai.schemas import (
    EvidenceAssessment,
    IncidentCategory,
    IncidentClassification,
    ResolutionAction,
    ResolutionDecision,
)

_CATEGORY_KEYWORDS: dict[IncidentCategory, tuple[str, ...]] = {
    IncidentCategory.REFUND_REQUEST: ("refund", "money back", "chargeback"),
    IncidentCategory.ORDER_NOT_RECEIVED: (
        "never arrived",
        "didn't receive",
        "did not receive",
        "not arrived",
        "missing package",
        "tracking",
        "hasn't shown up",
    ),
    IncidentCategory.ACCOUNT_ACCESS: ("locked out", "can't log in", "cannot log in", "password", "access my account"),
    IncidentCategory.BILLING_DISCREPANCY: ("charged twice", "overcharged", "double charge", "wrong amount", "invoice"),
}

_URGENT_WORDS = ("urgent", "asap", "immediately", "right now", "emergency")

_CATEGORY_TO_ACTION: dict[IncidentCategory, ResolutionAction] = {
    IncidentCategory.REFUND_REQUEST: ResolutionAction.ISSUE_REFUND,
    IncidentCategory.ORDER_NOT_RECEIVED: ResolutionAction.RESEND_ORDER,
    IncidentCategory.ACCOUNT_ACCESS: ResolutionAction.RESET_ACCOUNT_ACCESS,
    IncidentCategory.BILLING_DISCREPANCY: ResolutionAction.CORRECT_BILLING,
    IncidentCategory.OTHER: ResolutionAction.NO_ACTION_NEEDED,
}


class FakeLLM:
    """Rule-based `LLMClient`. See module docstring for the prompt conventions it relies on."""

    def complete_structured(self, *, system: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is IncidentClassification:
            return self._classify(prompt)
        if schema is EvidenceAssessment:
            return self._assess(prompt)
        if schema is ResolutionDecision:
            return self._resolve(prompt)
        raise NotImplementedError(f"FakeLLM has no handler for schema {schema!r}")

    # -- handlers -----------------------------------------------------------

    def _classify(self, prompt: str) -> IncidentClassification:
        """Expects `SUBJECT: ...` and `DESCRIPTION: ...` lines in the prompt."""
        text = prompt.lower()
        category = IncidentCategory.OTHER
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                category = cat
                break
        urgency = 5 if any(w in text for w in _URGENT_WORDS) else 3
        return IncidentClassification(
            category=category,
            urgency=urgency,
            rationale=f"Matched category '{category.value}' via keyword heuristics over subject/description.",
        )

    def _assess(self, prompt: str) -> EvidenceAssessment:
        """Expects an `EVIDENCE_COUNT: <n>` line followed by `- ...` bullets, then a
        `REFERENCE` section boundary -- only bullets before that boundary count as
        grounding evidence."""
        match = re.search(r"EVIDENCE_COUNT:\s*(\d+)", prompt)
        count = int(match.group(1)) if match else 0
        evidence_section = prompt.split("REFERENCE")[0]
        bullets = re.findall(r"^- (.+)$", evidence_section, flags=re.MULTILINE)

        if count == 0:
            return EvidenceAssessment(
                is_sufficient=False,
                confidence=0.15,
                grounded_claims=[],
                unsupported_claims=["No supporting evidence was retrieved for this incident."],
                missing_evidence=["customer/order records", "relevant policy documentation"],
            )
        if count == 1:
            return EvidenceAssessment(
                is_sufficient=False,
                confidence=0.5,
                grounded_claims=bullets[:1],
                unsupported_claims=[],
                missing_evidence=["a second independent source to corroborate the single evidence item"],
            )
        return EvidenceAssessment(
            is_sufficient=True,
            confidence=min(0.95, 0.6 + 0.1 * count),
            grounded_claims=bullets,
            unsupported_claims=[],
            missing_evidence=[],
        )

    def _resolve(self, prompt: str) -> ResolutionDecision:
        """Expects a `CATEGORY: <value>` line and `CITATIONS: a, b, c` line."""
        cat_match = re.search(r"CATEGORY:\s*(\w+)", prompt)
        category = IncidentCategory(cat_match.group(1)) if cat_match else IncidentCategory.OTHER
        action = _CATEGORY_TO_ACTION[category]
        cite_match = re.search(r"CITATIONS:\s*(.*)", prompt)
        citations = [c.strip() for c in cite_match.group(1).split(",") if c.strip()] if cite_match else []

        message_by_action = {
            ResolutionAction.ISSUE_REFUND: "We've reviewed your order and confirmed a refund is warranted. It's been issued and should post within 3-5 business days.",
            ResolutionAction.RESEND_ORDER: "We confirmed your order never arrived. A replacement has been shipped at no cost, with expedited delivery.",
            ResolutionAction.RESET_ACCOUNT_ACCESS: "We've reset your account access. You'll receive a secure link to set a new password.",
            ResolutionAction.CORRECT_BILLING: "We found the billing discrepancy you reported and corrected your account. An updated invoice is attached.",
            ResolutionAction.NO_ACTION_NEEDED: "We reviewed your case and didn't find an account issue on our end -- details are in the notes below.",
        }
        return ResolutionDecision(
            action=action,
            customer_message=message_by_action[action],
            internal_notes=f"Auto-resolved as '{action.value}' for category '{category.value}' based on grounded evidence.",
            citations=citations,
        )
