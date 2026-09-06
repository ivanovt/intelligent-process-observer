"""Deterministic freeze and final-result construction boundaries."""

# ruff: noqa: E501
from __future__ import annotations

from app.knowledge.contracts import KnowledgeReference
from app.reasoning.contracts import (
    EvidenceCatalogEntry,
    Finding,
    FindingCompletion,
    Hypothesis,
    HypothesisCompletion,
    ObservationAnalysisResult,
    ObservationReasoningInput,
    OverallStateCompletion,
)


def freeze_findings(
    completion: FindingCompletion, catalog: tuple[EvidenceCatalogEntry, ...]
) -> tuple[Finding, ...]:
    """Resolve unique model catalog IDs into immutable structured findings."""
    known = {entry.id: entry.reference for entry in catalog}
    if len({finding.id for finding in completion.findings}) != len(completion.findings):
        raise ValueError("finding ids must be unique")
    frozen = []
    for finding in completion.findings:
        if len(finding.evidence_ids) != len(set(finding.evidence_ids)) or any(
            item not in known for item in finding.evidence_ids
        ):
            raise ValueError("finding evidence ids must be unique catalog entries")
        frozen.append(
            Finding(
                id=finding.id,
                statement=finding.statement,
                evidence_refs=tuple(known[item] for item in finding.evidence_ids),
            )
        )
    return tuple(frozen)


def validate_hypotheses(
    completion: HypothesisCompletion,
    findings: tuple[Finding, ...],
    available_references: tuple[KnowledgeReference, ...],
) -> tuple[Hypothesis, ...]:
    """Retain only hypotheses exactly grounded in frozen findings and returned knowledge."""
    if len({item.id for item in completion.hypotheses}) != len(completion.hypotheses):
        raise ValueError("hypothesis ids must be unique")
    finding_ids = {item.id for item in findings}
    allowed = set(available_references)
    for hypothesis in completion.hypotheses:
        if not set(hypothesis.supported_by).issubset(finding_ids) or not set(
            hypothesis.knowledge_refs
        ).issubset(allowed):
            raise ValueError("hypothesis grounding is not available in this run")
    return completion.hypotheses


def build_result(
    value: ObservationReasoningInput,
    findings: tuple[Finding, ...],
    hypotheses: tuple[Hypothesis, ...],
    overall: OverallStateCompletion,
    limitations: tuple,
) -> ObservationAnalysisResult:
    """Build the sole strict persistent-safe ObservationAnalysisResult artifact."""
    return ObservationAnalysisResult(
        identity=value.context.identity,
        overall_state=overall.overall_state,
        findings=findings,
        hypotheses=hypotheses,
        limitations=limitations,
    )
