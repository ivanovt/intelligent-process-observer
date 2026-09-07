from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.execution.contracts import (
    AlertLensSnapshot,
    AnalysisWindow,
    CollectedLensArtifact,
    CollectedLensOutcome,
    CollectedLensResultIdentity,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensExecutionAssignment,
    LensOutcomePartition,
    MetricLensSnapshot,
    ObservationExecutionSnapshot,
    RelationshipSnapshot,
    SemanticDescriptorSnapshot,
)
from app.execution.projectors import (
    relationship_definitions,
    validate_relationship_batch,
)
from app.execution.stages import evaluate_and_persist_relationships, invoke_and_persist_reasoning
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.runtime_contracts import ObservationAnalysisIdentity
from app.metrics.contracts import (
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
from app.reasoning.contracts import ObservationAnalysisResult, ReasoningSuccess


def _snapshot() -> ObservationExecutionSnapshot:
    return ObservationExecutionSnapshot(
        observation_id=uuid4(),
        schema_version=1,
        analysis_window=AnalysisWindow(
            from_=datetime(2026, 1, 1, tzinfo=UTC),
            to=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        name="Observation",
        description=None,
        objective="detect drift",
        metric_lenses=(),
        alert_lenses=(),
        relationships=(
            RelationshipSnapshot(
                relationship_id="first",
                name="First",
                description=None,
                participants=("m1", "m2"),
                conditions=(("m1", SemanticDescriptorSnapshot("increasing", None, None)),),
                expected=(("m2", SemanticDescriptorSnapshot(None, None, "high")),),
            ),
        ),
    )


def test_relationship_projection_preserves_definition_order_and_semantics() -> None:
    relationship = relationship_definitions(_snapshot())[0]

    assert relationship.id == "first"
    assert relationship.participants == ["m1", "m2"]
    assert relationship.conditions["m1"].trend.direction == "increasing"
    assert relationship.expected["m2"].variability.state == "high"


def test_relationship_batch_rejects_missing_duplicate_or_reordered_identity() -> None:
    snapshot = _snapshot()
    observation_id = snapshot.observation_id
    run_id = uuid4()

    with pytest.raises(ValueError, match="cardinality"):
        validate_relationship_batch(
            snapshot, (), observation_id=observation_id, observation_run_id=run_id
        )

    class Evaluation:
        relationship_id = "other"

    with pytest.raises(ValueError, match="identity or order"):
        validate_relationship_batch(
            snapshot,
            (Evaluation(),),
            observation_id=observation_id,
            observation_run_id=run_id,
        )


def _alert_snapshot() -> ObservationExecutionSnapshot:
    return replace(
        _snapshot(),
        alert_lenses=(
            AlertLensSnapshot(
                lens_id="alert-a",
                name="Alert",
                description=None,
                source="jira_track_and_release",
                selector_query="project = plant",
                analysis_objectives=("detect drift",),
                reference_periods=(),
            ),
        ),
        metric_lenses=(
            MetricLensSnapshot(
                lens_id="metric-z",
                name="Metric",
                description=None,
                metric_id="temperature",
                adapter_type="prometheus",
                source_id="plant",
                query="temperature",
                unit="C",
                analysis_objectives=("detect drift",),
                reference_periods=(),
            ),
        ),
    )


def _failed_alert(
    snapshot: ObservationExecutionSnapshot,
) -> tuple[LensExecutionAssignment, CollectedLensOutcome]:
    run_id = uuid4()
    assignment = LensExecutionAssignment(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
        lens_run_id=uuid4(),
        analysis_window=snapshot.analysis_window,
        lens=snapshot.alert_lenses[0],
    )
    return assignment, CollectedLensOutcome(
        assignment=assignment,
        status="failed",
        reason=ExecutionReason("caller_unavailable", "alert_provider"),
    )


class _NoopSessionFactory:
    def begin(self):
        raise AssertionError("persistence must not be reached")


class _CountingEvaluator:
    def __init__(self, error: BaseException) -> None:
        self.calls = 0
        self.error = error

    def evaluate(self, relationships, results):
        self.calls += 1
        raise self.error


class _ReturningEvaluator:
    def __init__(self, value) -> None:
        self.calls = 0
        self.value = value

    def evaluate(self, relationships, results):
        self.calls += 1
        return self.value


def test_relationship_stage_rejects_reordered_or_incomplete_topology_before_evaluator() -> None:
    snapshot = _alert_snapshot()
    assignment, outcome = _failed_alert(snapshot)
    evaluator = _CountingEvaluator(RuntimeError("must not run"))

    result = asyncio.run(
        evaluate_and_persist_relationships(
            session_factory=_NoopSessionFactory(),
            runtime_repository=object(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
        )
    )

    assert isinstance(result, FailedObservationExecutionOutcome)
    assert result.reason.code == "relationship_evaluation_failed"
    assert evaluator.calls == 0


@pytest.mark.parametrize("change", ["lens", "window"])
def test_relationship_stage_rejects_same_lens_identity_with_changed_frozen_configuration(
    change: str,
) -> None:
    snapshot = replace(_alert_snapshot(), metric_lenses=())
    expected_assignment, outcome = _failed_alert(snapshot)
    if change == "lens":
        changed_lens = replace(snapshot.alert_lenses[0], selector_query="project = other")
        changed_assignment = replace(expected_assignment, lens=changed_lens)
    else:
        changed_window = replace(
            snapshot.analysis_window,
            to=snapshot.analysis_window.to.replace(day=3),
        )
        changed_assignment = replace(expected_assignment, analysis_window=changed_window)
    changed_outcome = replace(outcome, assignment=changed_assignment)
    evaluator = _CountingEvaluator(RuntimeError("must not run"))

    result = asyncio.run(
        evaluate_and_persist_relationships(
            session_factory=_NoopSessionFactory(),
            runtime_repository=object(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(changed_outcome,),
            assignments=(changed_assignment,),
        )
    )

    assert isinstance(result, FailedObservationExecutionOutcome)
    assert evaluator.calls == 0


def test_relationship_stage_rejects_invalid_evaluator_value_before_persistence() -> None:
    snapshot = replace(_alert_snapshot(), metric_lenses=())
    assignment, outcome = _failed_alert(snapshot)

    class DuckEvaluation:
        relationship_id = "first"

    evaluator = _ReturningEvaluator((DuckEvaluation(),))
    result = asyncio.run(
        evaluate_and_persist_relationships(
            session_factory=_NoopSessionFactory(),
            runtime_repository=object(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
        )
    )

    assert isinstance(result, FailedObservationExecutionOutcome)
    assert evaluator.calls == 1


def test_relationship_stage_maps_evaluator_runtime_error_but_not_cancellation() -> None:
    snapshot = replace(_alert_snapshot(), metric_lenses=())
    assignment, outcome = _failed_alert(snapshot)
    evaluator = _CountingEvaluator(RuntimeError("evaluator failed"))
    result = asyncio.run(
        evaluate_and_persist_relationships(
            session_factory=_NoopSessionFactory(),
            runtime_repository=object(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
        )
    )
    assert isinstance(result, FailedObservationExecutionOutcome)
    assert evaluator.calls == 1

    cancelled = _CountingEvaluator(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            evaluate_and_persist_relationships(
                session_factory=_NoopSessionFactory(),
                runtime_repository=object(),
                evaluator=cancelled,
                snapshot=snapshot,
                outcomes=(outcome,),
                assignments=(assignment,),
            )
        )


def test_reasoning_persistence_error_rolls_back_and_does_not_claim_success() -> None:
    """A valid reasoning success must propagate an exact persistence failure unchanged."""
    observation_id, run_id, lens_run_id = uuid4(), uuid4(), uuid4()
    snapshot = ObservationExecutionSnapshot(
        observation_id=observation_id,
        schema_version=1,
        analysis_window=AnalysisWindow(
            from_=datetime(2026, 1, 1, tzinfo=UTC),
            to=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        name="Observation",
        description=None,
        objective="detect drift",
        metric_lenses=(
            MetricLensSnapshot(
                lens_id="metric",
                name="Metric",
                description=None,
                metric_id="process.temperature",
                adapter_type="prometheus",
                source_id="plant",
                query="temperature",
                unit="C",
                analysis_objectives=(),
                reference_periods=(),
            ),
        ),
        alert_lenses=(),
        relationships=(),
    )
    assignment = LensExecutionAssignment(
        observation_id=observation_id,
        observation_run_id=run_id,
        lens_run_id=lens_run_id,
        analysis_window=snapshot.analysis_window,
        lens=snapshot.metric_lenses[0],
    )
    context = MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="metric",
            lens_run_id=lens_run_id,
            metric_ref="process.temperature",
            unit="C",
        ),
        provider_scope=MetricProviderScope(
            adapter_type="prometheus", source_id="plant", query="temperature"
        ),
        analysis_window={"from": snapshot.analysis_window.from_, "to": snapshot.analysis_window.to},
        analysis_objectives=(),
        reference_periods=(),
    )
    metric_result, envelope = MetricResultBuilder(
        clock=lambda: snapshot.analysis_window.to
    ).completed_sufficient(
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
    artifact = object.__new__(CollectedLensArtifact)
    object.__setattr__(artifact, "result_type", envelope.result_type)
    object.__setattr__(artifact, "status", envelope.status)
    object.__setattr__(artifact, "schema_version", envelope.schema_version)
    object.__setattr__(
        artifact,
        "identity",
        CollectedLensResultIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="metric",
            lens_run_id=lens_run_id,
            metric_ref="process.temperature",
            unit="C",
        ),
    )
    object.__setattr__(artifact, "provenance", metric_result.provenance.model_dump(mode="python"))
    object.__setattr__(artifact, "payload", metric_result.model_dump(mode="python", by_alias=True))
    partition = LensOutcomePartition(
        usable=(
            CollectedLensOutcome(assignment=assignment, status="completed", artifact=artifact),
        ),
        unavailable=(),
    )
    success = ReasoningSuccess.model_construct(
        result=ObservationAnalysisResult.model_construct(
            identity=ObservationAnalysisIdentity(
                observation_id=observation_id, observation_run_id=run_id
            ),
            overall_state="no_significant_findings",
            findings=(),
            hypotheses=(),
            limitations=(),
        )
    )
    error = RuntimeError("injected analysis persistence failure")

    class Transaction:
        committed = False
        rolled_back = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, _exc, _tb):
            if exc_type is None:
                self.committed = True
            else:
                self.rolled_back = True
            return False

        async def get(self, model, identity):
            assert model is ObservationRunModel and identity == run_id
            return ObservationRunModel(
                id=run_id, observation_id=observation_id, status="running"
            )

    transaction = Transaction()

    class SessionFactory:
        def begin(self):
            return transaction

    class Executor:
        async def execute(self, value):
            assert value.context.identity.observation_run_id == run_id
            return success

    class Repository:
        async def persist_observation_analysis_result(self, session, run, result):
            assert session is transaction and run.id == run_id
            raise error

    with pytest.raises(RuntimeError) as raised:
        asyncio.run(
            invoke_and_persist_reasoning(
                session_factory=SessionFactory(),
                runtime_repository=Repository(),
                executor=Executor(),
                snapshot=snapshot,
                partition=partition,
                evaluations=(),
            )
        )

    assert raised.value is error
    assert transaction.rolled_back
    assert not transaction.committed
