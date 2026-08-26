"""Mechanically enforced findings freeze and final result construction."""

from __future__ import annotations

from dataclasses import dataclass

from agent_framework_experiment.observation_reasoning.domain import (
    Finding,
    FindingFormationOutput,
    HypothesisFormationOutput,
    ObservationAnalysisResult,
    ObservationReasoningInput,
)


@dataclass(frozen=True)
class FrozenFindingsState:
    findings: tuple[Finding, ...]
    overall_state: str
    limitations: tuple

    @property
    def finding_ids(self) -> tuple[str, ...]:
        return tuple(finding.id for finding in self.findings)


def freeze_findings(
    draft: FindingFormationOutput, *, allowed_evidence_refs: tuple[str, ...]
) -> FrozenFindingsState:
    allowed = set(allowed_evidence_refs)
    invalid = [ref for item in draft.findings for ref in item.evidence_refs if ref not in allowed]
    if invalid:
        raise ValueError(f"finding references unavailable Observation evidence: {invalid}")
    if len({item.id for item in draft.findings}) != len(draft.findings):
        raise ValueError("finding IDs must be unique before freeze")
    # Overall state and limitations are phase-one experiment-local conveniences;
    # only findings are a normative cross-retrieval freeze invariant.
    return FrozenFindingsState(draft.findings, draft.overall_state, draft.limitations)


def build_result(
    input_data: ObservationReasoningInput,
    frozen: FrozenFindingsState,
    hypotheses: HypothesisFormationOutput,
    *,
    available_knowledge_refs: tuple,
) -> ObservationAnalysisResult:
    finding_ids = set(frozen.finding_ids)
    knowledge_refs = set(available_knowledge_refs)
    for hypothesis in hypotheses.hypotheses:
        if not set(hypothesis.supported_by) <= finding_ids:
            raise ValueError("hypothesis references a non-frozen finding")
        if not set(hypothesis.knowledge_refs) <= knowledge_refs:
            raise ValueError("hypothesis references unavailable knowledge")
    return ObservationAnalysisResult(
        identity=input_data.identity,
        overall_state=frozen.overall_state,
        findings=frozen.findings,
        hypotheses=hypotheses.hypotheses,
        limitations=frozen.limitations,
    )
