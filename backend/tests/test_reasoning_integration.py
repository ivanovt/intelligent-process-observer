"""Representative in-memory integration coverage for Observation reasoning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.alerts.analyzer import analyze_current
from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderRecord,
    AlertProviderScope,
)
from app.alerts.normalization import normalize_current
from app.alerts.result_builder import AlertResultBuilder
from app.infrastructure.persistence.runtime_contracts import StructuredReason
from app.knowledge.contracts import (
    KnowledgeReference,
    KnowledgeRetrievalRequest,
    RetrievedKnowledgeItem,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricEvidence,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.result_builder import MetricResultBuilder
from app.reasoning.contracts import (
    FindingCompletion,
    FindingDraft,
    Hypothesis,
    HypothesisCompletion,
    ObservationIdentity,
    ObservationReasoningInput,
    ObservationSemanticContext,
    OverallStateCompletion,
    ReasoningLens,
    UnavailableLens,
)
from app.reasoning.executor import ObservationReasoningExecutor
from app.reasoning.input import insufficient_metric_as_unavailable
from app.relationships.contracts import ApplicableRelationshipEvaluation, DirectionEvidence

NOW = datetime(2026, 9, 1, tzinfo=UTC)


class InMemoryRetriever:
    """Return a fixed knowledge item while recording the frozen-finding request."""

    def __init__(self, reference: KnowledgeReference) -> None:
        self.reference = reference
        self.requests: list[KnowledgeRetrievalRequest] = []

    async def retrieve(
        self, request: KnowledgeRetrievalRequest
    ) -> tuple[RetrievedKnowledgeItem, ...]:
        """Record one retrieval request and return its grounded knowledge item."""
        self.requests.append(request)
        return (
            RetrievedKnowledgeItem(
                statement="Operating guide supports this explanation.", references=(self.reference,)
            ),
        )


class InMemoryAgent:
    """Make the three isolated reasoning invocations observable and deterministic."""

    def __init__(self, knowledge_reference: KnowledgeReference) -> None:
        self.knowledge_reference = knowledge_reference
        self.calls: list[str] = []
        self.finding_request = None
        self.hypothesis_request = None
        self.overall_request = None

    async def form_findings(self, request):
        """Ground one draft finding in metric evidence only."""
        self.calls.append("findings")
        self.finding_request = request
        metric_entry = next(
            item for item in request.catalog if item.reference.source_type == "metric_result"
        )
        return FindingCompletion(
            findings=(
                FindingDraft(
                    id="temperature-finding",
                    statement="Temperature evidence warrants investigation.",
                    evidence_ids=(metric_entry.id,),
                ),
            )
        )

    async def form_hypotheses(self, request, retrieval):
        """Retrieve knowledge after freeze and return a grounded hypothesis."""
        self.calls.append("hypotheses")
        self.hypothesis_request = request
        await retrieval.execute(
            KnowledgeRetrievalRequest(
                query="temperature investigation guidance", finding_ids=("temperature-finding",)
            )
        )
        return HypothesisCompletion(
            hypotheses=(
                Hypothesis(
                    id="temperature-hypothesis",
                    statement="The temperature signal may require operator investigation.",
                    supported_by=("temperature-finding",),
                    knowledge_refs=(self.knowledge_reference,),
                ),
            )
        )

    async def determine_overall_state(self, request):
        """Classify evidence without access to hypothesis or retrieval state."""
        self.calls.append("overall")
        self.overall_request = request
        return OverallStateCompletion(overall_state="significant_findings_present")


def _input() -> ObservationReasoningInput:
    """Build correlated Metric, Alert, and Relationship evidence in memory."""
    observation_id, run_id = uuid4(), uuid4()
    metric_id, alert_id = uuid4(), uuid4()
    metric_context = MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="temperature",
            lens_run_id=metric_id,
            metric_ref="plant.temperature",
            unit="C",
        ),
        provider_scope=MetricProviderScope(
            adapter_type="prometheus", source_id="plant", query="temperature"
        ),
        analysis_window=MetricAnalysisWindow(**{"from": NOW, "to": NOW + timedelta(minutes=5)}),
        analysis_objectives=("Detect changes.",),
        reference_periods=(),
    )
    metric, _ = MetricResultBuilder(clock=lambda: NOW).completed_sufficient(
        metric_context,
        PreparedGoodSeries(
            data_quality="good",
            samples=(),
            evidence=MetricEvidence(mean=84.0, std=1.0, min=82.0, max=86.0, slope=0.4),
            residuals=(),
        ),
        MetricSemantics(
            trend=MetricTrend(direction="increasing", rate="moderate"),
            variability=MetricVariability(state="low"),
        ),
    )
    alert_context = AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="alerts",
            lens_run_id=alert_id,
        ),
        provider_scope=AlertProviderScope(source="fixture", query="active alerts"),
        analysis_window=AlertAnalysisWindow(**{"from": NOW, "to": NOW + timedelta(minutes=5)}),
        lens_name="Alerts",
    )
    records = normalize_current(
        type(
            "Response",
            (),
            {
                "records": (
                    AlertProviderRecord(
                        id="a-1", title="Temperature alarm", started_at=NOW, source_status="active"
                    ),
                )
            },
        )(),
        alert_context.analysis_window,
        alert_context.analysis_window.to,
    )
    alert, _ = AlertResultBuilder(clock=lambda: NOW).completed(
        alert_context,
        records,
        analyze_current(records),
        AlertAgentCompletion(
            findings=(
                AlertFinding(
                    id="alert-finding",
                    statement="Alarm is active.",
                    evidence_refs=("alert://aggregate/alert_activity/record_count",),
                ),
            ),
            overall_importance="high",
        ),
    )
    relationship = ApplicableRelationshipEvaluation(
        relationship_id="temperature-alarm",
        name="Temperature alarm relationship",
        description=None,
        conditions=(),
        expectations=(
            DirectionEvidence(
                lens_id="temperature", expected="increasing", observed="increasing", match=True
            ),
        ),
        state="consistent",
    )
    return ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Plant health",
            lenses=(
                ReasoningLens(lens_id="temperature", lens_type="metric"),
                ReasoningLens(lens_id="alerts", lens_type="alert"),
            ),
        ),
        usable_results=(metric, alert),
        relationships=(relationship,),
    )


def _degraded_input() -> ObservationReasoningInput:
    """Build partial, insufficient, and unavailable Lens evidence for one run."""
    observation_id, run_id = uuid4(), uuid4()
    partial_context = MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="partial-temperature",
            lens_run_id=uuid4(),
            metric_ref="plant.temperature",
            unit="C",
        ),
        provider_scope=MetricProviderScope(
            adapter_type="prometheus", source_id="plant", query="temperature"
        ),
        analysis_window=MetricAnalysisWindow(**{"from": NOW, "to": NOW + timedelta(minutes=5)}),
        analysis_objectives=(),
        reference_periods=(),
    )
    insufficient_context = partial_context.model_copy(
        update={
            "identity": partial_context.identity.model_copy(
                update={"lens_id": "insufficient-pressure", "lens_run_id": uuid4()}
            )
        }
    )
    prepared = PreparedGoodSeries(
        data_quality="good",
        samples=(),
        evidence=MetricEvidence(mean=84.0, std=1.0, min=82.0, max=86.0, slope=0.4),
        residuals=(),
    )
    semantics = MetricSemantics(
        trend=MetricTrend(direction="increasing", rate="moderate"),
        variability=MetricVariability(state="low"),
    )
    builder = MetricResultBuilder(clock=lambda: NOW)
    partial, _ = builder.partial_reference_unavailable(partial_context, prepared, semantics, (), ())
    insufficient, _ = builder.completed_insufficient(insufficient_context)
    return ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Degraded plant health",
            lenses=(
                ReasoningLens(lens_id="partial-temperature", lens_type="metric"),
                ReasoningLens(lens_id="insufficient-pressure", lens_type="metric"),
                ReasoningLens(lens_id="alerts", lens_type="alert"),
            ),
        ),
        usable_results=(partial,),
        unavailable_lenses=(
            insufficient_metric_as_unavailable(insufficient),
            UnavailableLens(
                lens_id="alerts",
                lens_type="alert",
                reason=StructuredReason(code="provider_unavailable", component="current"),
            ),
        ),
    )


@pytest.mark.anyio
async def test_reasoning_end_to_end_with_mixed_evidence_and_isolated_phases() -> None:
    """Reasoning produces a strict result from mixed evidence without data-channel leaks."""
    knowledge_reference = KnowledgeReference(
        source_id="operations-manual", reference="temperature-3"
    )
    agent = InMemoryAgent(knowledge_reference)
    retriever = InMemoryRetriever(knowledge_reference)

    outcome = await ObservationReasoningExecutor(agent, retriever).execute(_input())

    assert outcome.outcome == "success"
    assert agent.calls == ["findings", "hypotheses", "overall"]
    assert outcome.result.identity == agent.finding_request.context.identity
    assert [entry.reference.source_type for entry in agent.finding_request.catalog] == sorted(
        [entry.reference.source_type for entry in agent.finding_request.catalog],
        key=("metric_result", "alert_result", "relationship_evaluation").index,
    )
    assert agent.finding_request.limitations == ()
    assert outcome.result.findings[0].id == "temperature-finding"
    assert outcome.result.hypotheses[0].knowledge_refs == (knowledge_reference,)
    assert retriever.requests[0].finding_ids == ("temperature-finding",)
    assert agent.hypothesis_request.findings == outcome.result.findings
    assert not hasattr(agent.overall_request, "hypotheses")
    assert not hasattr(agent.overall_request, "retrieval")
    assert agent.overall_request.findings == outcome.result.findings
    payload = outcome.result.model_dump(mode="json")
    assert UUID(payload["identity"]["observation_id"]) == outcome.result.identity.observation_id
    assert "catalog" not in payload and "knowledge" not in payload


@pytest.mark.anyio
async def test_reasoning_integrates_partial_unavailable_and_insufficient_limitations() -> None:
    """Final reasoning preserves deterministic availability limits from native Lens results."""
    knowledge_reference = KnowledgeReference(source_id="operations-manual", reference="partial-3")
    agent = InMemoryAgent(knowledge_reference)

    outcome = await ObservationReasoningExecutor(
        agent, InMemoryRetriever(knowledge_reference)
    ).execute(_degraded_input())

    assert outcome.outcome == "success"
    assert [
        (item.code, item.lens_id, getattr(item, "component", None))
        for item in outcome.result.limitations
    ] == [
        ("partial_lens_analysis", "partial-temperature", "reference_periods"),
        ("insufficient_lens_evidence", "insufficient-pressure", None),
        ("missing_lens_evidence", "alerts", None),
    ]
    assert agent.finding_request.limitations == outcome.result.limitations
    assert agent.overall_request.limitations == outcome.result.limitations


@pytest.mark.anyio
async def test_reasoning_integrates_empty_findings_without_hypothesis_work() -> None:
    """An empty finding phase skips retrieval and hypothesis reasoning but still assesses state."""

    class EmptyFindingAgent(InMemoryAgent):
        async def form_findings(self, request):
            self.calls.append("findings")
            self.finding_request = request
            return FindingCompletion()

    reference = KnowledgeReference(source_id="operations-manual", reference="unused")
    agent = EmptyFindingAgent(reference)
    retriever = InMemoryRetriever(reference)
    outcome = await ObservationReasoningExecutor(agent, retriever).execute(_input())

    assert outcome.outcome == "success"
    assert outcome.result.findings == () and outcome.result.hypotheses == ()
    assert agent.calls == ["findings", "overall"]
    assert retriever.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize("retrieval_failure", [(), TimeoutError(), RuntimeError("unavailable")])
async def test_reasoning_integrates_empty_or_failed_retrieval_without_hypotheses(
    retrieval_failure: object,
) -> None:
    """Empty and failed retrieval leave a valid finding-only result without hypotheses."""

    class EmptyHypothesisAgent(InMemoryAgent):
        async def form_hypotheses(self, request, retrieval):
            self.calls.append("hypotheses")
            self.hypothesis_request = request
            await retrieval.execute(
                KnowledgeRetrievalRequest(
                    query="temperature investigation guidance", finding_ids=("temperature-finding",)
                )
            )
            return HypothesisCompletion()

    class ConfiguredRetriever:
        async def retrieve(self, request):
            if isinstance(retrieval_failure, BaseException):
                raise retrieval_failure
            return retrieval_failure

    reference = KnowledgeReference(source_id="operations-manual", reference="unused")
    agent = EmptyHypothesisAgent(reference)
    outcome = await ObservationReasoningExecutor(agent, ConfiguredRetriever()).execute(_input())

    assert outcome.outcome == "success"
    assert outcome.result.hypotheses == ()
    assert agent.calls == ["findings", "hypotheses", "overall"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failed_phase", "expected_calls", "component"),
    [
        ("findings", ["findings"], "finding_phase"),
        ("hypotheses", ["findings", "hypotheses"], "hypothesis_phase"),
        ("overall", ["findings", "hypotheses", "overall"], "overall_state_phase"),
    ],
)
async def test_reasoning_required_invocation_failure_produces_no_result(
    failed_phase: str, expected_calls: list[str], component: str
) -> None:
    """Each required invocation fails closed without publishing a partial result."""

    class RequiredPhaseFailureAgent:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def form_findings(self, request):
            self.calls.append("findings")
            if failed_phase == "findings":
                raise RuntimeError("finding failure")
            metric_entry = next(
                item for item in request.catalog if item.reference.source_type == "metric_result"
            )
            return FindingCompletion(
                findings=(
                    FindingDraft(
                        id="temperature-finding",
                        statement="Temperature evidence warrants investigation.",
                        evidence_ids=(metric_entry.id,),
                    ),
                )
            )

        async def form_hypotheses(self, request, retrieval):
            self.calls.append("hypotheses")
            if failed_phase == "hypotheses":
                raise RuntimeError("hypothesis failure")
            return HypothesisCompletion()

        async def determine_overall_state(self, request):
            self.calls.append("overall")
            if failed_phase == "overall":
                raise RuntimeError("overall failure")
            return OverallStateCompletion(overall_state="significant_findings_present")

    agent = RequiredPhaseFailureAgent()
    outcome = await ObservationReasoningExecutor(
        agent, InMemoryRetriever(KnowledgeReference(source_id="manual", reference="unused"))
    ).execute(_input())

    assert outcome.outcome == "failure"
    assert outcome.component == component
    assert not hasattr(outcome, "result")
    assert agent.calls == expected_calls
