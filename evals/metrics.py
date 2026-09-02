"""Metrics computed over a batch of eval-run outcomes.

Kept deliberately simple (no external eval framework) so the whole harness
runs in milliseconds against `FakeLLM` in CI. Swapping in RAGAS-style metrics
against a real LLM judge is a documented V2 step (see README roadmap) --
these metrics are still meaningful now: they check the graph's *routing*
logic (did it escalate when it should have?) against ground truth, which a
purely LLM-graded eval wouldn't even test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaseResult:
    case_id: str
    expected_category: str
    actual_category: str | None
    expected_outcome: str  # "auto_resolved" | "human_review"
    actual_outcome: str
    grounded: bool  # True if a resolved case cited at least one source


@dataclass
class EvalReport:
    results: list[CaseResult]

    @property
    def n(self) -> int:
        return len(self.results)

    @property
    def category_accuracy(self) -> float:
        if not self.results:
            return 0.0
        correct = sum(1 for r in self.results if r.actual_category == r.expected_category)
        return correct / self.n

    @property
    def outcome_accuracy(self) -> float:
        if not self.results:
            return 0.0
        correct = sum(1 for r in self.results if r.actual_outcome == r.expected_outcome)
        return correct / self.n

    @property
    def escalation_precision(self) -> float:
        """Of cases the system escalated, how many *should* have been escalated?"""
        predicted_escalations = [r for r in self.results if r.actual_outcome == "human_review"]
        if not predicted_escalations:
            return 1.0
        correct = sum(1 for r in predicted_escalations if r.expected_outcome == "human_review")
        return correct / len(predicted_escalations)

    @property
    def escalation_recall(self) -> float:
        """Of cases that *should* have been escalated, how many did the system catch?"""
        should_escalate = [r for r in self.results if r.expected_outcome == "human_review"]
        if not should_escalate:
            return 1.0
        correct = sum(1 for r in should_escalate if r.actual_outcome == "human_review")
        return correct / len(should_escalate)

    @property
    def groundedness_rate(self) -> float:
        """Of cases the system auto-resolved, how many cited at least one source?"""
        resolved = [r for r in self.results if r.actual_outcome == "auto_resolved"]
        if not resolved:
            return 1.0
        grounded = sum(1 for r in resolved if r.grounded)
        return grounded / len(resolved)

    def to_markdown(self) -> str:
        lines = [
            "| metric | value |",
            "|---|---|",
            f"| cases | {self.n} |",
            f"| category accuracy | {self.category_accuracy:.0%} |",
            f"| outcome accuracy | {self.outcome_accuracy:.0%} |",
            f"| escalation precision | {self.escalation_precision:.0%} |",
            f"| escalation recall | {self.escalation_recall:.0%} |",
            f"| groundedness rate (resolved cases) | {self.groundedness_rate:.0%} |",
            "",
            "| case | expected cat | actual cat | expected outcome | actual outcome | grounded |",
            "|---|---|---|---|---|---|",
        ]
        for r in self.results:
            lines.append(
                f"| {r.case_id} | {r.expected_category} | {r.actual_category} | "
                f"{r.expected_outcome} | {r.actual_outcome} | {r.grounded} |"
            )
        return "\n".join(lines)
