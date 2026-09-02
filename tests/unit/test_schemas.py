import pytest
from pydantic import ValidationError

from resolveai.schemas import EvidenceAssessment, Incident, IncidentClassification


def test_incident_requires_all_fields():
    with pytest.raises(ValidationError):
        Incident(incident_id="i1", customer_id="c1")  # missing subject/description


def test_incident_classification_urgency_bounds():
    with pytest.raises(ValidationError):
        IncidentClassification(category="refund_request", urgency=6, rationale="x")


def test_evidence_assessment_confidence_bounds():
    with pytest.raises(ValidationError):
        EvidenceAssessment(is_sufficient=True, confidence=1.5)


def test_evidence_assessment_defaults_to_empty_lists():
    a = EvidenceAssessment(is_sufficient=False, confidence=0.1)
    assert a.grounded_claims == []
    assert a.unsupported_claims == []
