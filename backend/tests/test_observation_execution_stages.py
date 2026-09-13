from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.alerts.contracts import (
    AlertIdentity,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertProviderScope,
)
from app.alerts.result_builder import AlertResultBuilder
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
    build_observation_reasoning_input,
    relationship_definitions,
    validate_relationship_batch,
)
from app.execution.stages import (
    evaluate_and_persist_relationships,
    generate_and_persist_report,
    invoke_and_persist_reasoning,
)
from app.infrastructure.persistence.models import (
    ObservationAnalysisResultModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.runtime_contracts import ObservationAnalysisIdentity
from app.knowledge.management_contracts import KnowledgeScope
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
from app.reasoning.contracts import (
    ObservationAnalysisResult,
    ObservationIdentity,
    ReasoningFailure,
    ReasoningSuccess,
)
from app.relationships.contracts import UnknownRelationshipEvaluation
from app.reporting.contracts import ObservationReport, ReportFailure, ReportSuccess


def _stage_snapshot(*, relationships=(), include_alert=True) -> ObservationExecutionSnapshot:
    """Build a frozen stage scope with canonical metric-then-alert ordering."""
    return ObservationExecutionSnapshot(
        observation_id=uuid4(),
        schema_version=1,
        analysis_window=AnalysisWindow(
            from_=datetime(2026, 1, 1, tzinfo=UTC), to=datetime(2026, 1, 2, tzinfo=UTC)
        ),
        name="Stage observation",
        description="semantic description",
        objective="explain evidence",
        metric_lenses=tuple(
            MetricLensSnapshot(
                lens_id=lid,
                name=lid,
                description=None,
                metric_id=f"metric.{lid}",
                adapter_type="prometheus",
                source_id="plant",
                query=f"query.{lid}",
                unit="C",
                analysis_objectives=("objective",),
                reference_periods=(),
            )
            for lid in ("metric-a", "metric-b")
        ),
        alert_lenses=(
            AlertLensSnapshot(
                lens_id="alert-z",
                name="alert-z",
                description=None,
                source="jira",
                selector_query="project = plant",
                analysis_objectives=("objective",),
                reference_periods=(),
            ),
        )
        if include_alert
        else (),
        relationships=relationships,
    )


def _metric_artifact(snapshot, assignment, *, insufficient=False):
    """Create a real Metric result and persistence envelope through its builder."""
    context = MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=snapshot.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=assignment.lens.lens_id,
            lens_run_id=assignment.lens_run_id,
            metric_ref=assignment.lens.metric_id,
            unit=assignment.lens.unit,
        ),
        provider_scope=MetricProviderScope(
            adapter_type=assignment.lens.adapter_type,
            source_id=assignment.lens.source_id,
            query=assignment.lens.query,
        ),
        analysis_window={"from": snapshot.analysis_window.from_, "to": snapshot.analysis_window.to},
        analysis_objectives=assignment.lens.analysis_objectives,
        reference_periods=(),
    )
    builder = MetricResultBuilder(clock=lambda: snapshot.analysis_window.to)
    if insufficient:
        result, envelope = builder.completed_insufficient(context)
    else:
        result, envelope = builder.completed_sufficient(
            context,
            PreparedGoodSeries(
                data_quality="good",
                samples=(),
                evidence=MetricEvidence(mean=1, std=0, min=1, max=1, slope=0),
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
            observation_id=snapshot.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=assignment.lens.lens_id,
            lens_run_id=assignment.lens_run_id,
            metric_ref=assignment.lens.metric_id,
            unit=assignment.lens.unit,
        ),
    )
    object.__setattr__(artifact, "provenance", result.provenance.model_dump(mode="json"))
    object.__setattr__(artifact, "payload", result.model_dump(mode="json", by_alias=True))
    return artifact


def _alert_artifact(snapshot, assignment, *, partial=False):
    """Build a strict Alert artifact through the production result builder."""
    context = AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=snapshot.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=assignment.lens.lens_id,
            lens_run_id=assignment.lens_run_id,
        ),
        provider_scope=AlertProviderScope(
            source=assignment.lens.source, query=assignment.lens.selector_query
        ),
        analysis_window={"from": snapshot.analysis_window.from_, "to": snapshot.analysis_window.to},
        lens_name=assignment.lens.name,
    )
    builder = AlertResultBuilder(clock=lambda: snapshot.analysis_window.to)
    if partial:
        result, terminal = builder.usable(
            context,
            (),
            AlertMandatoryEvidence(),
            None,
            current_rejected=True,
            reference_unavailable=False,
            zero=True,
        )
    else:
        result, terminal = builder.completed_zero(context, AlertMandatoryEvidence())
    return CollectedLensArtifact.from_persistence_envelope(terminal.artifact)


def _assignment(snapshot, lens):
    return LensExecutionAssignment(
        observation_id=snapshot.observation_id,
        observation_run_id=uuid4(),
        lens_run_id=uuid4(),
        analysis_window=snapshot.analysis_window,
        lens=lens,
    )


class _StageTransaction:
    def __init__(self, run, *, analysis=None, fail_exit=None):
        self.run, self.analysis, self.fail_exit = run, analysis, fail_exit
        self.committed = self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, _value, _tb):
        if self.fail_exit is not None:
            raise self.fail_exit
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return False

    async def get(self, model, identity):
        return self.run

    async def scalar(self, _query):
        return self.analysis


class _StageFactory:
    def __init__(self, tx):
        self.tx = tx

    def begin(self):
        return self.tx


class _StageRepository:
    def __init__(self):
        self.calls = []

    async def advance_observation_run(self, _session, run, status, reason=None):
        self.calls.append(("advance", status.value, reason))
        run.status = status.value

    async def persist_relationship_evaluation(self, _session, _run, value):
        self.calls.append(("relationship", value.relationship_id))

    async def persist_observation_analysis_result(self, _session, _run, value):
        self.calls.append(("analysis", value))

    async def persist_observation_report(self, _session, _run, _analysis, value):
        self.calls.append(("report", value))


def _stored_analysis(result: ObservationAnalysisResult) -> ObservationAnalysisResultModel:
    """Build the persisted analysis envelope used by stage transaction fakes."""
    return ObservationAnalysisResultModel(
        observation_run_id=result.identity.observation_run_id,
        schema_version=result.schema_version,
        payload=result.model_dump(mode="json"),
    )


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
    def __init__(self, observation_id, run_id):
        self.observation_id = observation_id
        self.run_id = run_id

    def begin(self):
        factory = self

        class Transaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, _exc, _tb):
                return False

            async def get(self, model, identity):
                return ObservationRunModel(
                    id=factory.run_id,
                    observation_id=factory.observation_id,
                    status="running",
                )

        return Transaction()


class _NoopRuntimeRepository:
    async def advance_observation_run(self, session, run, status, reason=None):
        run.status = status.value


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
            session_factory=_NoopSessionFactory(
                snapshot.observation_id, assignment.observation_run_id
            ),
            runtime_repository=_NoopRuntimeRepository(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
            observation_run_id=assignment.observation_run_id,
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
            session_factory=_NoopSessionFactory(
                snapshot.observation_id, changed_assignment.observation_run_id
            ),
            runtime_repository=_NoopRuntimeRepository(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(changed_outcome,),
            assignments=(changed_assignment,),
            observation_run_id=changed_assignment.observation_run_id,
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
            session_factory=_NoopSessionFactory(
                snapshot.observation_id, assignment.observation_run_id
            ),
            runtime_repository=_NoopRuntimeRepository(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
            observation_run_id=assignment.observation_run_id,
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
            session_factory=_NoopSessionFactory(
                snapshot.observation_id, assignment.observation_run_id
            ),
            runtime_repository=_NoopRuntimeRepository(),
            evaluator=evaluator,
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
            observation_run_id=assignment.observation_run_id,
        )
    )
    assert isinstance(result, FailedObservationExecutionOutcome)
    assert evaluator.calls == 1

    cancelled = _CountingEvaluator(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            evaluate_and_persist_relationships(
                session_factory=_NoopSessionFactory(
                    snapshot.observation_id, assignment.observation_run_id
                ),
                runtime_repository=_NoopRuntimeRepository(),
                evaluator=cancelled,
                snapshot=snapshot,
                outcomes=(outcome,),
                assignments=(assignment,),
                observation_run_id=assignment.observation_run_id,
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
            return ObservationRunModel(id=run_id, observation_id=observation_id, status="running")

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
                observation_run_id=run_id,
            )
        )

    assert raised.value is error
    assert transaction.rolled_back
    assert not transaction.committed


def test_reasoning_success_persists_persistence_identity_and_correlated_payload() -> None:
    """A valid reasoning success persists an explicit persistence identity envelope."""
    base_snapshot = _stage_snapshot(include_alert=False)
    snapshot = replace(base_snapshot, metric_lenses=(base_snapshot.metric_lenses[0],))
    run_id = uuid4()
    assignment = LensExecutionAssignment(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
        lens_run_id=uuid4(),
        analysis_window=snapshot.analysis_window,
        lens=snapshot.metric_lenses[0],
    )
    partition = LensOutcomePartition(
        usable=(
            CollectedLensOutcome(
                assignment=assignment,
                status="completed",
                artifact=_metric_artifact(snapshot, assignment),
            ),
        ),
        unavailable=(),
    )
    domain_identity = ObservationIdentity(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
    )
    result = ObservationAnalysisResult(
        identity=domain_identity,
        overall_state="no_significant_findings",
        findings=(),
        hypotheses=(),
        limitations=(),
    )
    persisted = []

    class Executor:
        async def execute(self, _value):
            return ReasoningSuccess(result=result)

    class Repository:
        async def persist_observation_analysis_result(self, _session, _run, value):
            persisted.append(value)

    transaction = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )
    outcome = asyncio.run(
        invoke_and_persist_reasoning(
            session_factory=_StageFactory(transaction),
            runtime_repository=Repository(),
            executor=Executor(),
            snapshot=snapshot,
            partition=partition,
            evaluations=(),
            observation_run_id=run_id,
        )
    )

    assert outcome == ReasoningSuccess(result=result)
    assert len(persisted) == 1
    envelope = persisted[0]
    assert isinstance(envelope.identity, ObservationAnalysisIdentity)
    assert envelope.identity.observation_id == snapshot.observation_id
    assert envelope.identity.observation_run_id == run_id
    assert envelope.payload["identity"] == domain_identity.model_dump(mode="json")


def test_relationship_stage_accepts_empty_ordered_batch_and_evaluator_sees_complete_artifacts() -> (
    None
):
    """An empty Relationship set still invokes the evaluator once with canonical evidence."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    assignments = tuple(
        LensExecutionAssignment(
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
            lens_run_id=uuid4(),
            analysis_window=snapshot.analysis_window,
            lens=lens,
        )
        for lens in snapshot.metric_lenses
    )
    outcomes = tuple(
        CollectedLensOutcome(
            assignment=a, status="completed", artifact=_metric_artifact(snapshot, a)
        )
        for a in assignments
    )
    seen = []

    class Evaluator:
        def evaluate(self, definitions, artifacts):
            seen.append((definitions, artifacts))
            return ()

    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )
    result = asyncio.run(
        evaluate_and_persist_relationships(
            session_factory=_StageFactory(tx),
            runtime_repository=_StageRepository(),
            evaluator=Evaluator(),
            snapshot=snapshot,
            outcomes=outcomes,
            assignments=assignments,
            observation_run_id=run_id,
        )
    )
    assert result == () and tx.committed
    assert seen[0][0] == ()
    assert tuple(item.identity.lens_id for item in seen[0][1]) == ("metric-a", "metric-b")


def test_relationship_stage_maps_malformed_reordered_batch_without_partial_persistence() -> None:
    """A malformed evaluator batch fails the parent before any Relationship write."""
    relationship = RelationshipSnapshot(
        relationship_id="r-a",
        name="R",
        description=None,
        participants=("metric-a",),
        conditions=(),
        expected=(),
    )
    snapshot = _stage_snapshot(relationships=(relationship,), include_alert=False)
    run_id = uuid4()
    assignment = LensExecutionAssignment(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
        lens_run_id=uuid4(),
        analysis_window=snapshot.analysis_window,
        lens=snapshot.metric_lenses[0],
    )
    outcome = CollectedLensOutcome(
        assignment=assignment, status="completed", artifact=_metric_artifact(snapshot, assignment)
    )
    repo = _StageRepository()
    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )

    class Evaluator:
        def evaluate(self, *_):
            return (
                UnknownRelationshipEvaluation(
                    relationship_id="wrong",
                    name="R",
                    description=None,
                    conditions=(),
                    expectations=(),
                ),
            )

    result = asyncio.run(
        evaluate_and_persist_relationships(
            session_factory=_StageFactory(tx),
            runtime_repository=repo,
            evaluator=Evaluator(),
            snapshot=snapshot,
            outcomes=(outcome,),
            assignments=(assignment,),
            observation_run_id=run_id,
        )
    )
    assert isinstance(result, FailedObservationExecutionOutcome)
    assert result.reason == ExecutionReason(
        "relationship_evaluation_failed", "relationship_evaluator"
    )
    assert not any(call[0] == "relationship" for call in repo.calls)
    assert repo.calls[-1][0:2] == ("advance", "failed")


def test_reasoning_input_is_canonical_and_excludes_provider_and_runtime_configuration() -> None:
    """The executor receives only semantic context, results, and unavailable reasons."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    assignments = tuple(
        LensExecutionAssignment(
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
            lens_run_id=uuid4(),
            analysis_window=snapshot.analysis_window,
            lens=lens,
        )
        for lens in snapshot.metric_lenses
    )
    partition = LensOutcomePartition(
        usable=(
            CollectedLensOutcome(
                assignment=assignments[1],
                status="completed",
                artifact=_metric_artifact(snapshot, assignments[1]),
            ),
        ),
        unavailable=(
            CollectedLensOutcome(
                assignment=assignments[0],
                status="completed",
                artifact=_metric_artifact(snapshot, assignments[0], insufficient=True),
            ),
        ),
    )
    # Completed-insufficient must be represented as unavailable; at least one usable result remains.
    captured = []

    class Executor:
        async def execute(self, value):
            captured.append(value)
            return ReasoningFailure(code="reasoning_model_failed", component="finding_phase")

    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )
    repo = _StageRepository()
    result = asyncio.run(
        invoke_and_persist_reasoning(
            session_factory=_StageFactory(tx),
            runtime_repository=repo,
            executor=Executor(),
            snapshot=snapshot,
            partition=partition,
            evaluations=(),
            observation_run_id=run_id,
        )
    )
    assert isinstance(result, ReasoningFailure)
    value = captured[0]
    assert tuple(item.identity.lens_id for item in value.usable_results) == ("metric-b",)
    assert value.unavailable_lenses[0].origin == "completed_insufficient_metric"
    dumped = value.model_dump(mode="json")
    for forbidden in (
        "query",
        "source_id",
        "adapter_type",
        "policy",
        "deadline",
        "raw",
        "persistence",
    ):
        assert forbidden not in str(dumped)


@pytest.mark.parametrize("alert_partial", [False, True])
def test_reasoning_projector_reconstructs_json_metric_and_alert_payloads(
    alert_partial: bool,
) -> None:
    """The public reasoning projector strictly rebuilds JSONB-like native results."""
    base = _stage_snapshot(include_alert=True)
    snapshot = replace(base, metric_lenses=(base.metric_lenses[0],))
    run_id = uuid4()
    metric_assignment = _assignment(snapshot, snapshot.metric_lenses[0])
    metric_assignment = replace(metric_assignment, observation_run_id=run_id)
    alert_assignment = replace(
        _assignment(snapshot, snapshot.alert_lenses[0]), observation_run_id=run_id
    )
    metric = _metric_artifact(snapshot, metric_assignment)
    alert = _alert_artifact(snapshot, alert_assignment, partial=alert_partial)
    metric = replace(metric, payload=json.loads(json.dumps(metric.payload)))
    alert = replace(
        alert,
        payload=json.loads(json.dumps(alert.to_persistence_envelope().payload)),
    )
    partition = LensOutcomePartition(
        usable=(
            CollectedLensOutcome(assignment=metric_assignment, status="completed", artifact=metric),
            CollectedLensOutcome(
                assignment=alert_assignment,
                status="partial" if alert_partial else "completed",
                artifact=alert,
                reason=ExecutionReason("invalid_records", "current_normalization")
                if alert_partial
                else None,
            ),
        ),
        unavailable=(),
    )

    value = build_observation_reasoning_input(snapshot, partition, (), observation_run_id=run_id)

    assert {item.lens_type for item in value.usable_results} == {"metric", "alert"}
    assert any(item.status == "partial" for item in value.usable_results) is alert_partial


def test_reasoning_projector_excludes_retriever_scope_from_model_input() -> None:
    """Frozen scope filters retrieval only and cannot become analytical evidence."""
    base = _stage_snapshot(include_alert=False)
    snapshot = replace(
        base,
        metric_lenses=(base.metric_lenses[0],),
        knowledge_scope=KnowledgeScope(service_ids=("mprm-server",), service_version="2.x"),
    )
    run_id = uuid4()
    assignment = replace(
        _assignment(snapshot, snapshot.metric_lenses[0]), observation_run_id=run_id
    )
    partition = LensOutcomePartition(
        usable=(
            CollectedLensOutcome(
                assignment=assignment,
                status="completed",
                artifact=_metric_artifact(snapshot, assignment),
            ),
        ),
        unavailable=(),
    )

    value = build_observation_reasoning_input(snapshot, partition, (), observation_run_id=run_id)

    assert "knowledge_scope" not in value.model_dump()


def test_reasoning_projector_rejects_malformed_json_payload() -> None:
    """JSON fallback must not turn malformed persisted evidence into a usable result."""
    base = _stage_snapshot(include_alert=False)
    snapshot = replace(base, metric_lenses=(base.metric_lenses[0],))
    assignment = _assignment(snapshot, snapshot.metric_lenses[0])
    artifact = _metric_artifact(snapshot, assignment)
    malformed = dict(artifact.to_persistence_envelope().payload)
    malformed["unexpected"] = "must be rejected by strict result contract"
    outcome = CollectedLensOutcome(
        assignment=assignment,
        status="completed",
        artifact=replace(
            artifact,
            payload=json.loads(json.dumps(malformed)),
        ),
    )

    with pytest.raises(ValueError, match="persisted Lens result payload is invalid"):
        build_observation_reasoning_input(
            snapshot,
            LensOutcomePartition(usable=(outcome,), unavailable=()),
            (),
            observation_run_id=assignment.observation_run_id,
        )


def test_report_stage_isolates_minimal_request_and_persists_report_then_completion() -> None:
    """A successful report executor is called once with exact identity and commits both writes."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    identity = ObservationIdentity(
        observation_id=snapshot.observation_id, observation_run_id=run_id
    )
    analysis = ObservationAnalysisResult(
        identity=identity,
        overall_state="no_significant_findings",
        findings=(),
        hypotheses=(),
        limitations=(),
    )
    report = ObservationReport(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
        generated_at=datetime(2026, 1, 2, tzinfo=UTC),
        content="# Report",
    )
    captured = []

    class Executor:
        async def execute(self, request):
            captured.append(request)
            return ReportSuccess(report=report)

    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running"),
        analysis=_stored_analysis(analysis),
    )
    repo = _StageRepository()
    result = asyncio.run(
        generate_and_persist_report(
            session_factory=_StageFactory(tx),
            runtime_repository=repo,
            executor=Executor(),
            snapshot=snapshot,
            analysis_result=analysis,
            observation_run_id=run_id,
        )
    )
    assert result.observation_run_id == run_id and tx.committed
    assert captured[0].context.identity == identity
    assert "query" not in str(captured[0].model_dump()) and "source_id" not in str(
        captured[0].model_dump()
    )
    assert [call[0] for call in repo.calls] == ["report", "advance"]


def test_report_stage_uses_committed_analysis_instead_of_caller_analysis() -> None:
    """The report executor receives the committed analysis, not a caller replacement."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    stored = ObservationAnalysisResult(
        identity=ObservationIdentity(
            observation_id=snapshot.observation_id, observation_run_id=run_id
        ),
        overall_state="significant_findings_present",
        findings=(),
        hypotheses=(),
        limitations=(),
    )
    caller = stored.model_copy(update={"overall_state": "uncertain"})
    report = ObservationReport(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
        generated_at=datetime(2026, 1, 2, tzinfo=UTC),
        content="# Report",
    )
    captured = []

    class Executor:
        async def execute(self, request):
            captured.append(request)
            return ReportSuccess(report=report)

    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running"),
        analysis=_stored_analysis(stored),
    )
    result = asyncio.run(
        generate_and_persist_report(
            session_factory=_StageFactory(tx),
            runtime_repository=_StageRepository(),
            executor=Executor(),
            snapshot=snapshot,
            analysis_result=caller,
            observation_run_id=run_id,
        )
    )

    assert result.observation_run_id == run_id
    assert captured[0].analysis_result == stored


@pytest.mark.parametrize(
    "stored_analysis",
    [
        None,
        ObservationAnalysisResultModel(
            observation_run_id=uuid4(), schema_version="1.0", payload={}
        ),
    ],
)
def test_report_stage_maps_missing_or_invalid_committed_analysis(
    stored_analysis,
) -> None:
    """Missing or malformed committed analysis fails before report invocation."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    if stored_analysis is not None:
        stored_analysis.observation_run_id = run_id
    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running"),
        analysis=stored_analysis,
    )

    class Executor:
        async def execute(self, _request):
            pytest.fail("executor must not run")

    result = asyncio.run(
        generate_and_persist_report(
            session_factory=_StageFactory(tx),
            runtime_repository=_StageRepository(),
            executor=Executor(),
            snapshot=snapshot,
            analysis_result=None,
            observation_run_id=run_id,
        )
    )
    assert result.reason == ExecutionReason("report_result_invalid", "report_builder")


def test_report_stage_propagates_committed_analysis_query_failure() -> None:
    """Persistence query failures remain infrastructure errors."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    error = RuntimeError("analysis query failed")

    class Transaction(_StageTransaction):
        async def scalar(self, _query):
            raise error

    tx = Transaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(
            generate_and_persist_report(
                session_factory=_StageFactory(tx),
                runtime_repository=_StageRepository(),
                executor=object(),
                snapshot=snapshot,
                analysis_result=None,
                observation_run_id=run_id,
            )
        )
    assert raised.value is error


def test_report_failure_preserves_analysis_and_guarded_failure_reason() -> None:
    """Typed report failure leaves committed analysis untouched and only fails a running parent."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    identity = ObservationIdentity(
        observation_id=snapshot.observation_id, observation_run_id=run_id
    )
    analysis = ObservationAnalysisResult(
        identity=identity, overall_state="uncertain", findings=(), hypotheses=(), limitations=()
    )

    class Executor:
        calls = 0

        async def execute(self, request):
            self.calls += 1
            return ReportFailure(code="report_model_failed", component="report_generation")

    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running"),
        analysis=_stored_analysis(analysis),
    )
    repo = _StageRepository()
    executor = Executor()
    result = asyncio.run(
        generate_and_persist_report(
            session_factory=_StageFactory(tx),
            runtime_repository=repo,
            executor=executor,
            snapshot=snapshot,
            analysis_result=analysis,
            observation_run_id=run_id,
        )
    )
    assert result.reason == ExecutionReason("report_model_failed", "report_generation")
    assert executor.calls == 1 and not any(call[0] == "report" for call in repo.calls)


def test_controlled_failure_propagates_guarded_transition_error_without_rewriting_parent() -> None:
    """Failure helpers do not swallow repository concurrency/terminalization errors."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()

    class Repository(_StageRepository):
        async def advance_observation_run(self, *_args, **_kwargs):
            raise RuntimeError("guarded transition rejected")

    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )

    class Executor:
        async def execute(self, _request):
            return ReportFailure(code="report_model_failed", component="report_generation")

    analysis = ObservationAnalysisResult(
        identity=ObservationIdentity(
            observation_id=snapshot.observation_id, observation_run_id=run_id
        ),
        overall_state="uncertain",
        findings=(),
        hypotheses=(),
        limitations=(),
    )
    with pytest.raises(RuntimeError, match="guarded transition"):
        asyncio.run(
            generate_and_persist_report(
                session_factory=_StageFactory(tx),
                runtime_repository=Repository(),
                executor=Executor(),
                snapshot=snapshot,
                analysis_result=analysis,
                observation_run_id=run_id,
            )
        )
    assert tx.rolled_back


def test_report_invalid_identity_fails_parent_before_executor_and_report_write() -> None:
    """Mismatched analysis is rejected at the stage boundary and never reaches the report agent."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    other = ObservationAnalysisResult(
        identity=ObservationIdentity(observation_id=uuid4(), observation_run_id=run_id),
        overall_state="uncertain",
        findings=(),
        hypotheses=(),
        limitations=(),
    )

    class Executor:
        async def execute(self, _request):
            pytest.fail("executor must not run")

    repo = _StageRepository()
    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running")
    )
    result = asyncio.run(
        generate_and_persist_report(
            session_factory=_StageFactory(tx),
            runtime_repository=repo,
            executor=Executor(),
            snapshot=snapshot,
            analysis_result=other,
            observation_run_id=run_id,
        )
    )
    assert result.reason == ExecutionReason("report_result_invalid", "report_builder")
    assert not any(call[0] == "report" for call in repo.calls)


def test_report_final_transaction_exit_error_is_propagated_without_claiming_completion() -> None:
    """A commit/exit failure propagates and does not return a completed outcome."""
    snapshot = _stage_snapshot(include_alert=False)
    run_id = uuid4()
    identity = ObservationIdentity(
        observation_id=snapshot.observation_id, observation_run_id=run_id
    )
    analysis = ObservationAnalysisResult(
        identity=identity, overall_state="uncertain", findings=(), hypotheses=(), limitations=()
    )
    report = ObservationReport(
        observation_id=snapshot.observation_id,
        observation_run_id=run_id,
        generated_at=datetime(2026, 1, 2, tzinfo=UTC),
        content="# Report",
    )

    class Executor:
        async def execute(self, _request):
            return ReportSuccess(report=report)

    error = RuntimeError("commit failed")
    tx = _StageTransaction(
        ObservationRunModel(id=run_id, observation_id=snapshot.observation_id, status="running"),
        analysis=_stored_analysis(analysis),
        fail_exit=error,
    )
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(
            generate_and_persist_report(
                session_factory=_StageFactory(tx),
                runtime_repository=_StageRepository(),
                executor=Executor(),
                snapshot=snapshot,
                analysis_result=analysis,
                observation_run_id=run_id,
            )
        )
    assert raised.value is error
