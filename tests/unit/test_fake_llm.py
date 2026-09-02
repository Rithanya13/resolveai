from resolveai.llm.fake import FakeLLM
from resolveai.schemas import (
    EvidenceAssessment,
    IncidentCategory,
    IncidentClassification,
    ResolutionAction,
    ResolutionDecision,
)


def test_classify_detects_refund_keyword():
    llm = FakeLLM()
    result = llm.complete_structured(
        system="",
        prompt="SUBJECT: Refund needed\nDESCRIPTION: Please issue a refund for my order.",
        schema=IncidentClassification,
    )
    assert result.category == IncidentCategory.REFUND_REQUEST


def test_classify_detects_urgency_words():
    llm = FakeLLM()
    result = llm.complete_structured(
        system="",
        prompt="SUBJECT: help\nDESCRIPTION: This is urgent, please help asap.",
        schema=IncidentClassification,
    )
    assert result.urgency == 5


def test_classify_defaults_to_other():
    llm = FakeLLM()
    result = llm.complete_structured(
        system="", prompt="SUBJECT: hi\nDESCRIPTION: just saying hello", schema=IncidentClassification
    )
    assert result.category == IncidentCategory.OTHER


def test_assess_zero_evidence_is_insufficient():
    llm = FakeLLM()
    result = llm.complete_structured(system="", prompt="EVIDENCE_COUNT: 0\n\nREFERENCE\n", schema=EvidenceAssessment)
    assert result.is_sufficient is False
    assert result.confidence < 0.3


def test_assess_multiple_evidence_is_sufficient():
    prompt = "EVIDENCE_COUNT: 3\n- item one\n- item two\n- item three\n\nREFERENCE\n"
    llm = FakeLLM()
    result = llm.complete_structured(system="", prompt=prompt, schema=EvidenceAssessment)
    assert result.is_sufficient is True
    assert len(result.grounded_claims) == 3


def test_resolve_maps_category_to_action():
    llm = FakeLLM()
    result = llm.complete_structured(
        system="", prompt="CATEGORY: refund_request\nCITATIONS: policy-refunds-001", schema=ResolutionDecision
    )
    assert result.action == ResolutionAction.ISSUE_REFUND
    assert result.citations == ["policy-refunds-001"]
