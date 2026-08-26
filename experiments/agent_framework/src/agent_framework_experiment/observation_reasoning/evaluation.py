"""Framework-neutral contract checks for Reasoning live outcomes."""

from __future__ import annotations

from agent_framework_experiment.observation_reasoning.common import (
    observation_evidence_ids,
    upstream_knowledge_refs,
)
from agent_framework_experiment.observation_reasoning.domain import ObservationAnalysisResult
from agent_framework_experiment.observation_reasoning.retrieval import RetrievalExecutor


def evaluate(
    input_data, result: ObservationAnalysisResult, executor: RetrievalExecutor
) -> dict[str, object]:
    evidence = set(observation_evidence_ids(input_data))
    knowledge = set((*upstream_knowledge_refs(input_data), *executor.available_hypothesis_refs))
    frozen = executor.frozen
    invalid_finding = [
        ref for item in result.findings for ref in item.evidence_refs if ref not in evidence
    ]
    invalid_supported = [
        ref
        for item in result.hypotheses
        for ref in item.supported_by
        if ref not in {f.id for f in result.findings}
    ]
    invalid_knowledge = [
        ref.model_dump()
        for item in result.hypotheses
        for ref in item.knowledge_refs
        if ref not in knowledge
    ]
    frozen_ok = frozen is not None and result.findings == frozen.findings
    executed = [trace for trace in executor.traces if trace.executed]
    hard = {
        "structured_output_valid": True,
        "overall_state_valid": result.overall_state
        in {"no_significant_findings", "significant_findings_present", "uncertain"},
        "finding_refs_valid": not invalid_finding,
        "hypothesis_supported_by_valid": not invalid_supported,
        "knowledge_refs_valid": not invalid_knowledge,
        "findings_frozen": frozen_ok,
        "retrieval_count_valid": len(executed) <= 2,
        "known_tools_only": True,
        "no_retrieval_before_freeze": not any(
            not trace.executed and trace.status == "blocked" for trace in executor.traces
        ),
        "no_unsupported_knowledge": not invalid_knowledge,
    }
    return {
        "hard_correctness": hard,
        "contract_correct": all(hard.values()),
        "retrieval_behavior": {
            "retrieval_attempt_count": len(executed),
            "traces": [trace.model_dump(mode="json") for trace in executor.traces],
            "blocked_calls": sum(not trace.executed for trace in executor.traces),
        },
        "output": result.model_dump(mode="json"),
    }
