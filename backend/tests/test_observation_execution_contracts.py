from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.execution.contracts import (
    AnalysisWindow,
    ExecutionPolicy,
    ObservationExecutionRequest,
    RejectedObservationExecutionOutcome,
    project_observation_execution,
)


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


def _definition() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        schema_version=1,
        name="Host health",
        description=None,
        objective="Observe host health",
        lenses=[
            SimpleNamespace(
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
            ),
            SimpleNamespace(
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
            ),
        ],
        alert_lenses=[
            SimpleNamespace(
                lens_id="deployments",
                lens_type="alert",
                name="Deployments",
                description=None,
                source="jira_track_and_release",
                selector_query="project = OPS",
                analysis_objectives=["detect regressions"],
                reference_periods=["1d"],
            )
        ],
        relationships=[
            SimpleNamespace(
                relationship_id="cpu_pressure",
                name="CPU pressure",
                description=None,
                participants=["cpu", "memory"],
                conditions={},
                expected={
                    "cpu": {"trend": {"direction": "increasing"}},
                    "memory": {"variability": {"state": "moderate"}},
                },
            )
        ],
    )
