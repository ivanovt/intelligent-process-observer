"""Small deterministic Observation evidence and knowledge corpus for the spike."""

from __future__ import annotations

from dataclasses import dataclass

from agent_framework_experiment.observation_reasoning.domain import (
    EvidenceItem,
    Identity,
    KnowledgeReference,
    ObservationReasoningInput,
    UnavailableLens,
    UpstreamKnowledge,
)
from agent_framework_experiment.observation_reasoning.retrieval import (
    KnowledgeItem,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResult,
)


def _input(*evidence: EvidenceItem, unavailable: tuple[UnavailableLens, ...] = (), upstream=()):
    return ObservationReasoningInput(
        identity=Identity(observation_id="obs-1", observation_run_id="run-1"),
        context_description="Bounded structured Observation evidence only.",
        usable_evidence=evidence,
        unavailable_lenses=unavailable,
        upstream_log_knowledge=upstream,
    )


CALM = _input(EvidenceItem(evidence_id="lenses.pressure.current_state", statement="Stable."))
EVIDENCE_ONLY = _input(
    EvidenceItem(
        evidence_id="lenses.alerts.findings.alert_1", statement="High importance alert active."
    )
)
ONE_RETRIEVAL = _input(
    EvidenceItem(
        evidence_id="lenses.logs.findings.log_1", statement="Connection pool exhaustion observed."
    )
)
REFINEMENT = _input(
    EvidenceItem(
        evidence_id="relationships.flow_pressure.observed",
        statement="Expected flow-pressure relation is violated.",
    )
)
INSUFFICIENT = _input(
    EvidenceItem(
        evidence_id="lenses.logs.findings.log_2", statement="Unknown controller code observed."
    )
)
DEGRADED = _input(
    EvidenceItem(evidence_id="lenses.alerts.findings.alert_2", statement="Repeated active alert."),
    unavailable=(UnavailableLens(lens_id="logs", lens_type="log", reason_code="timeout"),),
)
RELATIONSHIP = _input(
    EvidenceItem(
        evidence_id="relationships.temperature_pressure.observed",
        statement="Relationship state uncertain.",
    ),
)
UPSTREAM = _input(
    EvidenceItem(
        evidence_id="lenses.logs.findings.log_3",
        statement="Known connection-pool template observed.",
    ),
    upstream=(
        UpstreamKnowledge(
            id="log_annotation_1",
            statement="The template documents connection-pool exhaustion.",
            knowledge_refs=(KnowledgeReference(source_id="log-doc", reference="pool-exhaustion"),),
        ),
    ),
)


@dataclass(frozen=True)
class ReasoningCase:
    name: str
    input_data: ObservationReasoningInput


LIVE_CASES = (
    ReasoningCase("no_significant_findings", CALM),
    ReasoningCase("finding_without_knowledge_need", EVIDENCE_ONLY),
    ReasoningCase("one_retrieval_sufficient", ONE_RETRIEVAL),
    ReasoningCase("second_retrieval_refinement", REFINEMENT),
    ReasoningCase("insufficient_knowledge", INSUFFICIENT),
    ReasoningCase("degraded_observation", DEGRADED),
    ReasoningCase("relationship_driven_finding", RELATIONSHIP),
    ReasoningCase("upstream_log_knowledge_reuse", UPSTREAM),
)


def deterministic_retriever(request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:
    query = request.query.lower()
    if "connection" in query and "pool" in query:
        return KnowledgeRetrievalResult(
            status="success",
            knowledge=(
                KnowledgeItem(
                    statement="Pool exhaustion can prevent new connections.",
                    knowledge_ref=KnowledgeReference(source_id="doc", reference="connection-pool"),
                ),
            ),
        )
    if "flow" in query or "pressure" in query:
        if request.refines_attempt is None:
            return KnowledgeRetrievalResult(
                status="insufficient",
                knowledge=(
                    KnowledgeItem(
                        statement="A mismatch may require valve-state context.",
                        knowledge_ref=KnowledgeReference(
                            source_id="doc", reference="flow-pressure-overview"
                        ),
                    ),
                ),
            )
        return KnowledgeRetrievalResult(
            status="success",
            knowledge=(
                KnowledgeItem(
                    statement="A closed restriction can explain the documented mismatch.",
                    knowledge_ref=KnowledgeReference(
                        source_id="doc", reference="flow-pressure-refinement"
                    ),
                ),
            ),
        )
    if "unknown" in query or "controller" in query:
        return KnowledgeRetrievalResult(status="insufficient")
    return KnowledgeRetrievalResult(status="no_match")
