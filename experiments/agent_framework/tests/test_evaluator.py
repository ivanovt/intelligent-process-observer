from __future__ import annotations

from agent_framework_experiment.domain import (
    AgentRunResult,
    AlertAnalysisAgentOutput,
    AlertFinding,
    ToolAttemptTrace,
)
from agent_framework_experiment.evaluation import evaluate_live_result
from agent_framework_experiment.fixtures.cases import SIMPLE_EVIDENCE


def test_simple_evidence_fixture_rejects_unneeded_optional_tool_use() -> None:
    result = AgentRunResult(
        output=AlertAnalysisAgentOutput(findings=(), overall_importance="high"),
        tool_attempts=(
            ToolAttemptTrace(
                invocation_order=1,
                tool_name="recurrence_concentration",
                status="success",
                latency_ms=1,
            ),
        ),
        available_evidence_ids=("alerts.A-1.provider_importance",),
    )

    evaluation = evaluate_live_result(SIMPLE_EVIDENCE, result)

    assert evaluation["contract_correct"] is True
    assert evaluation["behavioral_observations"]["apparently_unnecessary_tool_calls"] == 1


def test_evaluator_accepts_field_level_references_from_the_immutable_input() -> None:
    result = AgentRunResult(
        output=AlertAnalysisAgentOutput(
            findings=(
                AlertFinding(
                    id="af_1",
                    statement="The active alert is high importance.",
                    evidence_refs=("activity.current_count", "alerts.A-1.provider_importance"),
                ),
            ),
            overall_importance="high",
        ),
        tool_attempts=(),
        available_evidence_ids=("activity.current_count", "alerts.A-1.provider_importance"),
    )

    evaluation = evaluate_live_result(SIMPLE_EVIDENCE, result)

    assert evaluation["hard_correctness"]["evidence_refs_valid"] is True
