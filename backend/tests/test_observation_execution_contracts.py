from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.execution.contracts import (
    AlertLensSnapshot,
    AnalysisWindow,
    CollectedLensOutcome,
    CompletedObservationExecutionOutcome,
    ExecutionPolicy,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensExecutionAssignment,
    MetricLensSnapshot,
    ObservationExecutionRequest,
    RejectedObservationExecutionOutcome,
    project_observation_execution,
)
from app.infrastructure.persistence.models import (
    AlertLensModel,
    MetricLensModel,
    ObservationModel,
    ObservationRelationshipModel,
)
from app.metrics.contracts import MetricMandatoryAnalysisFailure
from app.metrics.result_builder import MetricResultBuilder


def test_projection_detaches_the_complete_mixed_definition() -> None:
    definition = _definition()

    snapshot = project_observation_execution(_request(definition.id), _policy(), definition)

    assert not isinstance(snapshot, RejectedObservationExecutionOutcome)
    definition.lenses[0].query = "changed"
    definition.alert_lenses[0].analysis_objectives.append("changed")
    definition.relationships[0].expected["cpu"]["trend"]["direction"] = "stable"
    assert snapshot.metric_lenses[0].query == "rate(cpu[5m])"
    assert snapshot.alert_lenses[0].analysis_objectives == ("detect regressions",)
    assert snapshot.relationships[0].expected[0][1].trend_direction == "increasing"
    with pytest.raises(FrozenInstanceError):
        snapshot.name = "changed"  # type: ignore[misc]


def test_projection_accepts_persisted_optional_relationship_nulls_for_long_window() -> None:
    """A saved valid descriptor remains executable when absent properties are JSON null."""
    definition = _definition()
    definition.relationships[0].conditions = {
        "cpu": {"trend": {"direction": "increasing", "rate": None}, "variability": None},
    }
    definition.relationships[0].expected = {
        "cpu": {"trend": {"direction": "increasing", "rate": None}, "variability": None},
        "memory": {"trend": None, "variability": {"state": "moderate"}},
    }
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    request = ObservationExecutionRequest(
        observation_id=definition.id,
        analysis_window=AnalysisWindow(from_=now - timedelta(hours=3), to=now),
    )

    snapshot = project_observation_execution(request, _policy(), definition)

    assert not isinstance(snapshot, RejectedObservationExecutionOutcome)
    assert snapshot.relationships[0].conditions[0][1].trend_direction == "increasing"
    assert snapshot.relationships[0].conditions[0][1].trend_rate is None
    assert snapshot.analysis_window == request.analysis_window


def test_projection_still_rejects_blank_relationship_properties() -> None:
    definition = _definition()
    definition.relationships[0].expected["cpu"]["trend"]["rate"] = " "

    outcome = project_observation_execution(_request(definition.id), _policy(), definition)

    _assert_rejected(outcome, "invalid_observation_definition")


def test_projection_freezes_json_scope_as_retriever_only_metadata() -> None:
    """A run retains the strict scope visible at launch despite later definition mutation."""
    definition = _definition()
    definition.knowledge_scope = {
        "service_ids": ["mprm-server", "cooling-loop"],
        "service_version": "2.x",
    }

    snapshot = project_observation_execution(_request(definition.id), _policy(), definition)

    assert not isinstance(snapshot, RejectedObservationExecutionOutcome)
    assert snapshot.knowledge_scope is not None
    assert tuple(service.service_id for service in snapshot.knowledge_scope.services) == (
        "mprm-server",
        "cooling-loop",
    )
    assert all(service.service_version == "2.x" for service in snapshot.knowledge_scope.services)
    definition.knowledge_scope["service_ids"].append("later-definition-change")
    assert tuple(service.service_id for service in snapshot.knowledge_scope.services) == (
        "mprm-server",
        "cooling-loop",
    )


@pytest.mark.parametrize(
    "scope",
    (
        {"service_ids": []},
        {"service_ids": ["mprm-server", "mprm-server"]},
        {"service_ids": ["mprm-server"], "service_version": " "},
        {"service_ids": "mprm-server"},
    ),
)
def test_projection_rejects_malformed_persisted_knowledge_scope(scope: object) -> None:
    """Malformed JSONB scope cannot create a partially scoped run snapshot."""
    definition = _definition()
    definition.knowledge_scope = scope

    outcome = project_observation_execution(_request(definition.id), _policy(), definition)

    _assert_rejected(outcome, "invalid_observation_definition")


def test_preparation_uses_only_controlled_no_run_rejections() -> None:
    cases = (
        (None, _policy(), _definition(), "invalid_execution_request"),
        (_request(uuid4()), _policy(), None, "observation_not_found"),
        (_request(uuid4()), ExecutionPolicy(0, 1), _definition(), "invalid_execution_request"),
    )

    for request, policy, definition, code in cases:
        outcome = project_observation_execution(request, policy, definition)

        assert isinstance(outcome, RejectedObservationExecutionOutcome)
        assert outcome.kind == "rejected"
        assert outcome.reason.code == code
        assert outcome.reason.component == "execution_preparation"
        assert not hasattr(outcome, "observation_run_id")
        assert not hasattr(outcome, "status")


@pytest.mark.parametrize(
    "window",
    (
        AnalysisWindow(from_=datetime(2026, 9, 7, 11, 55), to=datetime(2026, 9, 7, 12)),
        AnalysisWindow(
            from_=datetime(2026, 9, 7, 11, 55, tzinfo=timezone(timedelta(hours=3))),
            to=datetime(2026, 9, 7, 12, tzinfo=UTC),
        ),
        AnalysisWindow(
            from_=datetime(2026, 9, 7, 12, tzinfo=UTC),
            to=datetime(2026, 9, 7, 11, 55, tzinfo=UTC),
        ),
        AnalysisWindow(
            from_=datetime(2026, 9, 7, 12, tzinfo=UTC),
            to=datetime(2026, 9, 7, 12, tzinfo=UTC),
        ),
    ),
)
def test_projection_requires_a_strictly_forward_utc_window(window: AnalysisWindow) -> None:
    definition = _definition()
    request = ObservationExecutionRequest(observation_id=definition.id, analysis_window=window)

    outcome = project_observation_execution(request, _policy(), definition)

    _assert_rejected(outcome, "invalid_execution_request")


@pytest.mark.parametrize(
    "deadline", (True, False, 0, -1, float("nan"), float("inf"), float("-inf"))
)
def test_projection_requires_a_positive_finite_non_boolean_deadline(deadline: object) -> None:
    definition = _definition()
    policy = ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=deadline)  # type: ignore[arg-type]

    outcome = project_observation_execution(_request(definition.id), policy, definition)

    _assert_rejected(outcome, "invalid_execution_request")


@pytest.mark.parametrize("max_parallel_lens_runs", (-1, 0, True, False))
def test_projection_requires_a_positive_non_boolean_parallel_lens_run_limit(
    max_parallel_lens_runs: object,
) -> None:
    definition = _definition()
    policy = ExecutionPolicy(
        max_parallel_lens_runs=max_parallel_lens_runs,  # type: ignore[arg-type]
        lens_deadline_seconds=30,
    )

    outcome = project_observation_execution(_request(definition.id), policy, definition)

    _assert_rejected(outcome, "invalid_execution_request")


def test_projection_accepts_a_positive_parallel_lens_run_limit() -> None:
    definition = _definition()
    policy = ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=30)

    outcome = project_observation_execution(_request(definition.id), policy, definition)

    assert not isinstance(outcome, RejectedObservationExecutionOutcome)


def test_projection_maps_empty_and_invalid_real_orm_aggregates_to_controlled_rejections() -> None:
    empty = ObservationModel(
        id=uuid4(),
        schema_version=1,
        name="Empty",
        description=None,
        objective="Observe nothing",
    )
    invalid = _definition(schema_version=0)

    empty_outcome = project_observation_execution(_request(empty.id), _policy(), empty)
    invalid_outcome = project_observation_execution(_request(invalid.id), _policy(), invalid)

    _assert_rejected(empty_outcome, "empty_lens_topology")
    _assert_rejected(invalid_outcome, "invalid_observation_definition")


def test_projection_keeps_equal_metric_and_alert_ids_as_distinct_types() -> None:
    definition = _definition()

    snapshot = project_observation_execution(_request(definition.id), _policy(), definition)

    assert not isinstance(snapshot, RejectedObservationExecutionOutcome)
    assert snapshot.metric_lenses[0].lens_id == snapshot.alert_lenses[0].lens_id == "cpu"
    assert snapshot.metric_lenses[0].lens_type == "metric"
    assert snapshot.alert_lenses[0].lens_type == "alert"


def test_closed_outcome_variants_enforce_their_required_shape() -> None:
    run_id = uuid4()
    reason = ExecutionReason(code="execution_failed", component="execution")
    completed = CompletedObservationExecutionOutcome(observation_run_id=run_id)
    failed = FailedObservationExecutionOutcome(observation_run_id=run_id, reason=reason)
    rejected = RejectedObservationExecutionOutcome(
        reason=ExecutionReason(code="invalid_execution_request", component="execution_preparation")
    )

    assert completed.observation_run_id == run_id
    assert completed.status == "completed"
    assert not hasattr(completed, "reason")
    assert failed.observation_run_id == run_id
    assert failed.status == "failed"
    assert failed.reason is reason
    assert rejected.kind == "rejected"
    assert not hasattr(rejected, "observation_run_id")
    assert not hasattr(rejected, "status")
    with pytest.raises(TypeError):
        CompletedObservationExecutionOutcome()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        FailedObservationExecutionOutcome(observation_run_id=run_id)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        CompletedObservationExecutionOutcome(observation_run_id=run_id, status="failed")
    with pytest.raises(ValueError):
        FailedObservationExecutionOutcome(
            observation_run_id=run_id, reason=reason, kind="completed"
        )
    with pytest.raises(ValueError):
        CompletedObservationExecutionOutcome(observation_run_id="not-a-uuid")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        FailedObservationExecutionOutcome(
            observation_run_id="not-a-uuid",
            reason=reason,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        FailedObservationExecutionOutcome(
            observation_run_id=run_id,
            reason="not-a-reason",  # type: ignore[arg-type]
        )
    with pytest.raises(FrozenInstanceError):
        completed.status = "failed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        failed.reason = ExecutionReason(code="changed")  # type: ignore[misc]


def test_rejected_outcome_requires_an_actual_execution_reason() -> None:
    with pytest.raises(ValueError, match="requires an execution reason"):
        RejectedObservationExecutionOutcome(
            reason=SimpleNamespace(
                code="invalid_execution_request", component="execution_preparation"
            )
        )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires an execution reason"):
        RejectedObservationExecutionOutcome(reason="invalid_execution_request")  # type: ignore[arg-type]


def test_collected_lens_outcome_requires_assignment_and_actual_reason() -> None:
    assignment = _assignment()
    partial_reason = ExecutionReason(code="reference_unavailable", component="metric")

    context = _metric_context(assignment)
    _, completed_artifact = MetricResultBuilder().completed_insufficient(context)
    _, failed_artifact = MetricResultBuilder().failed(
        context, MetricMandatoryAnalysisFailure(diagnostic="test")
    )
    completed = CollectedLensOutcome(
        assignment=assignment, status="completed", artifact=completed_artifact
    )
    failed = CollectedLensOutcome(
        assignment=assignment, status="failed", artifact=failed_artifact, reason=partial_reason
    )

    assert completed.reason is None
    assert failed.reason is partial_reason
    with pytest.raises(ValueError, match="requires a Lens execution assignment"):
        CollectedLensOutcome(  # type: ignore[arg-type]
            assignment=SimpleNamespace(), status="completed"
        )
    with pytest.raises(ValueError, match="require an execution reason"):
        CollectedLensOutcome(  # type: ignore[arg-type]
            assignment=assignment, status="partial", artifact=completed_artifact, reason="raw"
        )
    with pytest.raises(ValueError, match="require an execution reason"):
        CollectedLensOutcome(
            assignment=assignment,
            status="failed",
            artifact=failed_artifact,
            reason=SimpleNamespace(code="analysis_failed", component="metric"),
        )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cannot carry a reason"):
        CollectedLensOutcome(
            assignment=assignment,
            status="completed",
            artifact=completed_artifact,
            reason=partial_reason,
        )


@pytest.mark.parametrize("status", ("completed", "partial", "failed"))
def test_collected_metric_outcome_requires_an_artifact_for_every_terminal_status(
    status: str,
) -> None:
    with pytest.raises(ValueError, match="requires its terminal artifact"):
        CollectedLensOutcome(
            assignment=_assignment(),
            status=status,  # type: ignore[arg-type]
            reason=ExecutionReason(code="test") if status != "completed" else None,
        )


def test_collected_alert_failure_requires_artifact_absence() -> None:
    metric_assignment = _assignment()
    assignment = LensExecutionAssignment(
        observation_id=metric_assignment.observation_id,
        observation_run_id=metric_assignment.observation_run_id,
        lens_run_id=metric_assignment.lens_run_id,
        analysis_window=metric_assignment.analysis_window,
        lens=AlertLensSnapshot(
            lens_id="alerts",
            name="Alerts",
            description=None,
            source="jira_track_and_release",
            selector_query="project = OPS",
            analysis_objectives=(),
            reference_periods=(),
        ),
    )
    reason = ExecutionReason(code="analysis_failed", component="alert")
    failed = CollectedLensOutcome(assignment=assignment, status="failed", reason=reason)

    assert failed.artifact is None


def test_collected_artifact_is_a_recursively_immutable_detached_snapshot() -> None:
    assignment = _assignment()
    context = _metric_context(assignment)
    _, source = MetricResultBuilder().failed(
        context, MetricMandatoryAnalysisFailure(diagnostic="test")
    )

    outcome = CollectedLensOutcome(
        assignment=assignment,
        status="failed",
        artifact=source,
        reason=ExecutionReason(code="analysis_failed", component="metric"),
    )

    assert outcome.artifact is not None
    source.payload["status"]["error"]["code"] = "mutated-source"  # type: ignore[index]
    source.provenance["source"] = "mutated-source"
    assert outcome.artifact.payload["status"]["error"]["code"] == (  # type: ignore[index]
        "mandatory_metric_analysis_failed"
    )
    assert outcome.artifact.provenance["source"] == "prometheus"
    with pytest.raises(TypeError):
        outcome.artifact.payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        outcome.artifact.payload["status"]["error"]["code"] = "mutated"  # type: ignore[index]

    projected = outcome.artifact.to_persistence_envelope()
    projected.payload["status"]["error"]["code"] = "mutated-projection"  # type: ignore[index]
    assert outcome.artifact.payload["status"]["error"]["code"] == (  # type: ignore[index]
        "mandatory_metric_analysis_failed"
    )


def test_projection_rejects_log_or_other_unsupported_lenses() -> None:
    definition = _definition()
    definition.log_lenses = [SimpleNamespace()]

    outcome = project_observation_execution(_request(definition.id), _policy(), definition)

    assert isinstance(outcome, RejectedObservationExecutionOutcome)
    assert outcome.reason.code == "unsupported_lens_type"


def _request(observation_id):
    end = datetime(2026, 9, 7, 12, tzinfo=UTC)
    return ObservationExecutionRequest(
        observation_id=observation_id,
        analysis_window=AnalysisWindow(from_=end - timedelta(minutes=5), to=end),
    )


def _policy() -> ExecutionPolicy:
    return ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=30)


def _assignment() -> LensExecutionAssignment:
    return LensExecutionAssignment(
        observation_id=uuid4(),
        observation_run_id=uuid4(),
        lens_run_id=uuid4(),
        analysis_window=_request(uuid4()).analysis_window,
        lens=MetricLensSnapshot(
            lens_id="cpu",
            name="CPU",
            description=None,
            metric_id="node_cpu",
            adapter_type="prometheus",
            source_id="prometheus",
            query="rate(cpu[5m])",
            unit="percent",
            analysis_objectives=("spike",),
            reference_periods=("1h",),
        ),
    )


def _metric_context(assignment: LensExecutionAssignment):
    from app.execution.adapters import metric_execution_context

    return metric_execution_context(assignment)


def _definition(schema_version: int = 1) -> ObservationModel:
    observation_id = uuid4()
    return ObservationModel(
        id=observation_id,
        schema_version=schema_version,
        name="Host health",
        description=None,
        objective="Observe host health",
        lenses=[
            MetricLensModel(
                observation_id=observation_id,
                lens_id="cpu",
                name="CPU",
                description=None,
                adapter_type="prometheus",
                source_id="prometheus",
                metric_id="node_cpu",
                query="rate(cpu[5m])",
                unit="percent",
                analysis_objectives=["spike"],
                reference_periods=["1h"],
                position=0,
            ),
            MetricLensModel(
                observation_id=observation_id,
                lens_id="memory",
                name="Memory",
                description=None,
                adapter_type="prometheus",
                source_id="prometheus",
                metric_id="node_memory",
                query="node_memory_MemAvailable_bytes",
                unit="bytes",
                analysis_objectives=["drift"],
                reference_periods=[],
                position=1,
            ),
        ],
        alert_lenses=[
            AlertLensModel(
                observation_id=observation_id,
                lens_id="cpu",
                lens_type="alert",
                name="CPU alerts",
                description=None,
                source="jira_track_and_release",
                selector_query="project = OPS",
                analysis_objectives=["detect regressions"],
                reference_periods=["1d"],
                position=0,
            )
        ],
        relationships=[
            ObservationRelationshipModel(
                observation_id=observation_id,
                relationship_id="cpu_pressure",
                name="CPU pressure",
                description=None,
                participants=["cpu", "memory"],
                conditions={},
                expected={
                    "cpu": {"trend": {"direction": "increasing"}},
                    "memory": {"variability": {"state": "moderate"}},
                },
                position=0,
            )
        ],
    )


def _assert_rejected(outcome: object, code: str) -> None:
    assert isinstance(outcome, RejectedObservationExecutionOutcome)
    assert outcome.reason.code == code
    assert outcome.reason.component == "execution_preparation"
