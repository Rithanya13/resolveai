"""Runs the eval harness (evals/run_evals.py) as part of the suite and asserts
a floor on each metric -- catches routing/classification regressions, not
just crashes. Slower than the unit tests (real MCP subprocess calls per
case), which is why it lives in tests/integration rather than tests/unit.
"""

import pytest

from evals.run_evals import main as run_evals_main


@pytest.mark.asyncio
async def test_eval_suite_meets_quality_floor():
    report = await run_evals_main()
    assert report.n > 0
    assert report.category_accuracy >= 0.9
    assert report.outcome_accuracy >= 0.9
    assert report.escalation_precision >= 0.9
    assert report.escalation_recall >= 0.9
    assert report.groundedness_rate >= 0.9
