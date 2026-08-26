"""Framework-neutral hard correctness, behavioral, and semantic live observations."""

from __future__ import annotations

from agent_framework_experiment.domain.contracts import AgentRunResult
from agent_framework_experiment.fixtures.cases import ExperimentCase
from agent_framework_experiment.tools.executor import TOOL_NAMES

FORBIDDEN_REASONING_TERMS = (
    "root cause",
    "caused by",
    "cause is",
    "recommend",
    "recommendation",
    "should ",
    "must be",
    "retrieve ",
    "rag ",
    "metric analysis",
    "log analysis",
    "cross-lens",
)


def _has_forbidden_reasoning(result: AgentRunResult) -> bool:
    text = " ".join(finding.statement.lower() for finding in result.output.findings)
    return any(term in text for term in FORBIDDEN_REASONING_TERMS)


def evaluate_live_result(case: ExperimentCase, result: AgentRunResult) -> dict[str, object]:
    """Assess contracts separately from optional-tool choices and prose variability."""

    invalid_refs = [
        reference
        for finding in result.output.findings
        for reference in finding.evidence_refs
        if reference not in result.available_evidence_ids
    ]
    trace_orders = [attempt.invocation_order for attempt in result.tool_attempts]
    forbidden_reasoning = _has_forbidden_reasoning(result)
    hard_correctness = {
        "structured_output_valid": True,
        "controlled_vocabulary_valid": result.output.overall_importance
        in {"low", "moderate", "high", "critical"},
        "evidence_refs_valid": not invalid_refs,
        "known_tools_only": all(
            attempt.tool_name in TOOL_NAMES for attempt in result.tool_attempts
        ),
        "budget_compliant": len(result.tool_attempts) <= 10
        and trace_orders == list(range(1, len(trace_orders) + 1)),
        "scope_compliant": not forbidden_reasoning,
        "failure_handling_valid": all(
            attempt.status in {"success", "failed", "timeout", "not_applicable"}
            for attempt in result.tool_attempts
        ),
        "no_fabricated_evidence": not invalid_refs,
        "no_forbidden_reasoning": not forbidden_reasoning,
    }
    tool_names = [attempt.tool_name for attempt in result.tool_attempts]
    behavioral_observations = {
        "tool_attempt_count": len(result.tool_attempts),
        "tool_invocation_order": tool_names,
        "tool_statuses": [attempt.status for attempt in result.tool_attempts],
        "repeated_tool_calls": len(tool_names) - len(set(tool_names)),
        "blocked_tool_calls": result.blocked_tool_calls,
        "unused_optional_tool_opportunity": (
            case.expected_tool is not None and case.expected_tool not in tool_names
        ),
        "apparently_unnecessary_tool_calls": len(tool_names) if case.expected_tool is None else 0,
        "finding_count": len(result.output.findings),
        "empty_findings": not result.output.findings,
    }
    semantic_quality = {
        "descriptive_lens_local_output": not forbidden_reasoning,
        "no_fabricated_provider_data": not invalid_refs,
        "overall_importance_contract_valid": hard_correctness["controlled_vocabulary_valid"],
    }
    return {
        "case": case.name,
        "hard_correctness": hard_correctness,
        "contract_correct": all(hard_correctness.values()),
        "behavioral_observations": behavioral_observations,
        "semantic_quality": semantic_quality,
        "semantic_quality_passed": all(semantic_quality.values()),
        "invalid_evidence_refs": invalid_refs,
        "available_evidence_ids": list(result.available_evidence_ids),
        "tool_attempts": [attempt.model_dump(mode="json") for attempt in result.tool_attempts],
        "blocked_tool_calls": result.blocked_tool_calls,
        "output": result.output.model_dump(mode="json"),
    }
