from __future__ import annotations

import asyncio

import pytest

from agent_framework_experiment.observation_reasoning.domain import (
    Finding,
    FindingFormationOutput,
    Hypothesis,
    HypothesisFormationOutput,
    KnowledgeReference,
)
from agent_framework_experiment.observation_reasoning.fixtures import (
    REFINEMENT,
    deterministic_retriever,
)
from agent_framework_experiment.observation_reasoning.phase import build_result, freeze_findings
from agent_framework_experiment.observation_reasoning.retrieval import (
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResult,
    RetrievalExecutor,
)


def _draft() -> FindingFormationOutput:
    return FindingFormationOutput(
        findings=(
            Finding(
                id="finding_1",
                statement="Flow-pressure relation is violated.",
                evidence_refs=("relationships.flow_pressure.observed",),
            ),
        ),
        overall_state="significant_findings_present",
    )


def test_freeze_and_two_call_refinement_boundary() -> None:
    async def exercise() -> None:
        executor = RetrievalExecutor(retriever=deterministic_retriever)
        request = KnowledgeRetrievalRequest(
            query="flow pressure", supported_finding_ids=("finding_1",)
        )
        assert (await executor.invoke(request))["reason"] == "findings_not_frozen"

        frozen = freeze_findings(
            _draft(), allowed_evidence_refs=("relationships.flow_pressure.observed",)
        )
        executor.set_frozen_findings(frozen)
        first = await executor.invoke(request)
        assert first.status == "insufficient"
        assert executor.available_hypothesis_refs == ()
        assert executor.available_refinement_refs

        second = await executor.invoke(
            KnowledgeRetrievalRequest(
                query="flow pressure valve state",
                supported_finding_ids=("finding_1",),
                refines_attempt=1,
                unresolved_gap="valve state",
            )
        )
        assert second.status == "success"
        assert executor.available_hypothesis_refs
        assert (await executor.invoke(request))["reason"] == "retrieval_budget_exhausted"
        assert [trace.status for trace in executor.traces] == [
            "blocked",
            "insufficient",
            "success",
            "blocked",
        ]

    asyncio.run(exercise())


def test_insufficient_alone_cannot_ground_hypothesis() -> None:
    frozen = freeze_findings(
        _draft(), allowed_evidence_refs=("relationships.flow_pressure.observed",)
    )
    hypothesis = HypothesisFormationOutput(
        hypotheses=(
            Hypothesis(
                id="h1",
                statement="Unsupported explanation.",
                supported_by=("finding_1",),
                knowledge_refs=(
                    KnowledgeReference(source_id="doc", reference="flow-pressure-overview"),
                ),
            ),
        )
    )
    with pytest.raises(ValueError, match="unavailable knowledge"):
        build_result(REFINEMENT, frozen, hypothesis, available_knowledge_refs=())


def test_second_retrieval_need_not_be_a_refinement_and_failure_states_have_no_knowledge() -> None:
    async def no_match(_request):
        return KnowledgeRetrievalResult(status="no_match")

    async def exercise() -> None:
        frozen = freeze_findings(
            _draft(), allowed_evidence_refs=("relationships.flow_pressure.observed",)
        )
        executor = RetrievalExecutor(retriever=no_match)
        executor.set_frozen_findings(frozen)
        for query in ("first independent gap", "second independent gap"):
            result = await executor.invoke(
                KnowledgeRetrievalRequest(query=query, supported_finding_ids=("finding_1",))
            )
            assert result.status == "no_match"
        assert not executor.available_refinement_refs
        assert not executor.available_hypothesis_refs

    asyncio.run(exercise())


def test_upstream_knowledge_may_ground_hypothesis_but_not_finding_evidence() -> None:
    draft = FindingFormationOutput(
        findings=(
            Finding(
                id="finding_1",
                statement="Known template observed.",
                evidence_refs=("lenses.logs.findings.log_3",),
            ),
        ),
        overall_state="significant_findings_present",
    )
    frozen = freeze_findings(draft, allowed_evidence_refs=("lenses.logs.findings.log_3",))
    result = build_result(
        __import__(
            "agent_framework_experiment.observation_reasoning.fixtures", fromlist=["UPSTREAM"]
        ).UPSTREAM,
        frozen,
        HypothesisFormationOutput(
            hypotheses=(
                Hypothesis(
                    id="h1",
                    statement="Pool exhaustion is a possible explanation.",
                    supported_by=("finding_1",),
                    knowledge_refs=(
                        KnowledgeReference(source_id="log-doc", reference="pool-exhaustion"),
                    ),
                ),
            )
        ),
        available_knowledge_refs=(
            KnowledgeReference(source_id="log-doc", reference="pool-exhaustion"),
        ),
    )
    assert result.findings == frozen.findings
