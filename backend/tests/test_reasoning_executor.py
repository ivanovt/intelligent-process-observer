"""Fake-driven behavioral tests for Observation reasoning orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.knowledge.contracts import (
    KnowledgeReference,
    KnowledgeRetrievalRequest,
    RetrievalRefinement,
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
    ReasoningFailure,
    ReasoningLens,
    ReasoningPolicyViolation,
)
from app.reasoning.executor import ObservationReasoningExecutor

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _input() -> ObservationReasoningInput:
    """Build a minimal correlated Metric input with citeable evidence."""
    observation_id, run_id, lens_run_id = uuid4(), uuid4(), uuid4()
    context = MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="metric",
            lens_run_id=lens_run_id,
            metric_ref="process.temperature",
            unit="C",
        ),
        provider_scope=MetricProviderScope(adapter_type="prometheus", source_id="plant", query="q"),
        analysis_window=MetricAnalysisWindow(**{"from": NOW, "to": NOW + timedelta(minutes=1)}),
        analysis_objectives=(),
        reference_periods=(),
    )
    metric, _ = MetricResultBuilder(clock=lambda: NOW).completed_sufficient(
        context,
        PreparedGoodSeries(
            data_quality="good",
            samples=(),
            evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
            residuals=(),
        ),
        MetricSemantics(
            trend=MetricTrend(direction="stable", rate="not_classified"),
            variability=MetricVariability(state="low"),
        ),
    )
    return ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Observation",
            lenses=(ReasoningLens(lens_id="metric", lens_type="metric"),),
        ),
        usable_results=(metric,),
    )


class FakeRetriever:
    """Record retrieval submissions and return configured outcomes."""

    def __init__(self, result: object = ()) -> None:
        self.result = result
        self.calls: list[object] = []

    async def retrieve(self, request: object) -> object:
        """Record the request and return or raise the configured value."""
        self.calls.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class FakeAgent:
    """Record isolated phase inputs while allowing phase-specific behavior."""

    def __init__(
        self,
        findings: Callable[[object], object] | None = None,
        hypotheses: Callable[[object, object], object] | None = None,
        overall: Callable[[object], object] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.finding_requests: list[object] = []
        self.hypothesis_requests: list[object] = []
        self.overall_requests: list[object] = []
        self._findings = findings or (lambda request: FindingCompletion())
        self._hypotheses = hypotheses or (lambda request, retrieval: HypothesisCompletion())
        self._overall = overall or (
            lambda request: OverallStateCompletion(overall_state="no_significant_findings")
        )

    async def form_findings(self, request: object) -> object:
        """Record the evidence-only phase request."""
        self.calls.append("findings")
        self.finding_requests.append(request)
        return await _maybe_await(self._findings(request))

    async def form_hypotheses(self, request: object, retrieval: object) -> object:
        """Record frozen-finding request and invoke its configured behavior."""
        self.calls.append("hypotheses")
        self.hypothesis_requests.append(request)
        return await _maybe_await(self._hypotheses(request, retrieval))

    async def determine_overall_state(self, request: object) -> object:
        """Record the knowledge-isolated state request."""
        self.calls.append("overall")
        self.overall_requests.append(request)
        return await _maybe_await(self._overall(request))


async def _maybe_await(value: object) -> object:
    """Await coroutine fakes while retaining simple synchronous test fixtures."""
    if hasattr(value, "__await__"):
        return await value  # type: ignore[misc]
    return value


def _finding(request: object) -> FindingCompletion:
    """Ground one finding in the first admitted catalog entry."""
    return FindingCompletion(
        findings=(
            FindingDraft(
                id="f-1",
                statement="A signal is present.",
                evidence_ids=(request.catalog[0].id,),  # type: ignore[attr-defined]
            ),
        )
    )


@pytest.mark.anyio
async def test_executor_orders_three_phases_and_skips_hypothesis_for_empty_findings() -> None:
    """Empty evidence findings still receive a fresh overall-state assessment."""
    agent, retriever = FakeAgent(), FakeRetriever()
    outcome = await ObservationReasoningExecutor(agent, retriever).execute(_input())
    assert outcome.outcome == "success"
    assert agent.calls == ["findings", "overall"]
    assert not agent.hypothesis_requests and not retriever.calls
    assert agent.finding_requests[0].catalog == agent.overall_requests[0].catalog  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_executor_freezes_before_retrieval_and_isolates_overall_state() -> None:
    """Retrieval is unavailable to findings and its data cannot enter overall state."""
    seen: dict[str, object] = {}

    async def hypotheses(request: object, retrieval: object) -> HypothesisCompletion:
        seen["retrieval"] = retrieval
        assert request.findings[0].id == "f-1"  # type: ignore[attr-defined]
        await retrieval.execute(  # type: ignore[attr-defined]
            KnowledgeRetrievalRequest(query="q", finding_ids=("f-1",))
        )
        return HypothesisCompletion()

    agent = FakeAgent(findings=_finding, hypotheses=hypotheses)
    retriever = FakeRetriever(())
    outcome = await ObservationReasoningExecutor(agent, retriever).execute(_input())
    assert outcome.outcome == "success" and agent.calls == ["findings", "hypotheses", "overall"]
    overall = agent.overall_requests[0]
    assert not hasattr(overall, "hypotheses") and not hasattr(overall, "retrieval")
    assert len(retriever.calls) == 1 and seen["retrieval"].consumed_slots == 1  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_executor_admits_refinement_and_independent_second_retrieval() -> None:
    """The hypothesis consumer may use both legal second-call trajectories."""

    async def hypotheses(_: object, retrieval: object) -> HypothesisCompletion:
        await retrieval.execute(  # type: ignore[attr-defined]
            KnowledgeRetrievalRequest(query="first", finding_ids=("f-1",))
        )
        await retrieval.execute(
            KnowledgeRetrievalRequest(
                query="second",
                finding_ids=("f-1",),
                refinement=RetrievalRefinement(unresolved_gap="gap"),
            )
        )
        assert retrieval.consumed_slots == 2  # type: ignore[attr-defined]
        return HypothesisCompletion()

    retriever = FakeRetriever(())
    executor = ObservationReasoningExecutor(FakeAgent(_finding, hypotheses), retriever)
    outcome = await executor.execute(_input())
    assert outcome.outcome == "success" and len(retriever.calls) == 2


@pytest.mark.anyio
async def test_executor_preserves_both_call_grounding_and_cannot_reset_budget() -> None:
    """One run-scoped executor admits two calls only and validates their joint grounding."""
    first = KnowledgeReference(source_id="manual", reference="first")
    second = KnowledgeReference(source_id="manual", reference="second")

    class SequencedRetriever(FakeRetriever):
        async def retrieve(self, request: object) -> object:
            self.calls.append(request)
            reference = first if len(self.calls) == 1 else second
            return (RetrievedKnowledgeItem(statement="knowledge", references=(reference,)),)

    async def hypotheses(_: object, retrieval: object) -> HypothesisCompletion:
        await retrieval.execute(KnowledgeRetrievalRequest(query="first", finding_ids=("f-1",)))  # type: ignore[attr-defined]
        await retrieval.execute(KnowledgeRetrievalRequest(query="second", finding_ids=("f-1",)))  # type: ignore[attr-defined]
        rejected = await retrieval.execute(  # type: ignore[attr-defined]
            KnowledgeRetrievalRequest(query="third", finding_ids=("f-1",))
        )
        assert rejected.outcome == "rejected" and rejected.rejection_reason == "over_budget"
        return HypothesisCompletion(
            hypotheses=(
                Hypothesis(
                    id="h-1",
                    statement="The two sources support an explanation.",
                    supported_by=("f-1",),
                    knowledge_refs=(first, second),
                ),
            )
        )

    retriever = SequencedRetriever()
    outcome = await ObservationReasoningExecutor(
        FakeAgent(_finding, hypotheses), retriever
    ).execute(_input())
    assert outcome.outcome == "success"
    assert len(retriever.calls) == 2
    assert outcome.result.hypotheses[0].knowledge_refs == (first, second)  # type: ignore[union-attr]


@pytest.mark.anyio
@pytest.mark.parametrize("retrieval_result", [(), TimeoutError(), RuntimeError("internal")])
async def test_executor_keeps_empty_and_failed_retrieval_non_fatal(
    retrieval_result: object,
) -> None:
    """Typed retrieval emptiness, timeout, and failure do not fail valid hypotheses."""

    async def hypotheses(_: object, retrieval: object) -> HypothesisCompletion:
        outcome = await retrieval.execute(  # type: ignore[attr-defined]
            KnowledgeRetrievalRequest(query="q", finding_ids=("f-1",))
        )
        assert outcome.outcome in {"retrieved", "timed_out", "failed"}
        return HypothesisCompletion()

    outcome = await ObservationReasoningExecutor(
        FakeAgent(_finding, hypotheses), FakeRetriever(retrieval_result)
    ).execute(_input())
    assert outcome.outcome == "success"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error,code,component",
    [
        (TimeoutError(), "reasoning_model_timed_out", "finding_phase"),
        (ValueError(), "reasoning_result_invalid", "finding_phase"),
        (RuntimeError(), "reasoning_model_failed", "finding_phase"),
    ],
)
async def test_executor_normalizes_finding_failures(
    error: Exception, code: str, component: str
) -> None:
    """Finding failures are fail-closed, typed, and do not continue phases."""

    def broken(_: object) -> object:
        raise error

    agent = FakeAgent(findings=broken)
    outcome = await ObservationReasoningExecutor(agent, FakeRetriever()).execute(_input())
    assert isinstance(outcome, ReasoningFailure)
    assert (outcome.code, outcome.component) == (code, component)
    assert agent.calls == ["findings"]


@pytest.mark.anyio
async def test_executor_normalizes_hypothesis_policy_and_overall_failures() -> None:
    """Policy and state errors use their fixed safe phase components."""

    def policy(_: object, __: object) -> object:
        raise ReasoningPolicyViolation("internal")

    policy_outcome = await ObservationReasoningExecutor(
        FakeAgent(_finding, policy), FakeRetriever()
    ).execute(_input())
    assert isinstance(policy_outcome, ReasoningFailure)
    assert (policy_outcome.code, policy_outcome.component) == (
        "reasoning_policy_violated",
        "hypothesis_phase",
    )

    def failed(_: object) -> object:
        raise RuntimeError("secret")

    state_outcome = await ObservationReasoningExecutor(
        FakeAgent(_finding, lambda _r, _t: HypothesisCompletion(), failed), FakeRetriever()
    ).execute(_input())
    assert isinstance(state_outcome, ReasoningFailure)
    assert (state_outcome.code, state_outcome.component) == (
        "reasoning_model_failed",
        "overall_state_phase",
    )


@pytest.mark.anyio
async def test_executor_propagates_cancellation_unchanged() -> None:
    """Caller cancellation creates no typed result and is never retried."""

    async def cancelled(_: object) -> object:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        executor = ObservationReasoningExecutor(FakeAgent(findings=cancelled), FakeRetriever())
        await executor.execute(_input())
