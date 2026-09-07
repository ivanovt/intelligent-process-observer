from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.execution import (
    AlertLensSnapshot,
    AnalysisWindow,
    ExecutionPolicy,
    LensExecutionAssignment,
    MetricLensSnapshot,
    ObservationExecutionOrchestrator,
)
from app.execution.orchestrator import _TypeRoutedLensAdapter


class RecordingAdapter:
    def __init__(self, value: str) -> None:
        self.value = value
        self.assignments: list[LensExecutionAssignment] = []

    async def execute(self, assignment: LensExecutionAssignment, policy: ExecutionPolicy) -> str:
        self.assignments.append(assignment)
        return self.value


def _assignment(lens: object) -> LensExecutionAssignment:
    now = datetime.now(UTC)
    return LensExecutionAssignment(
        observation_id=uuid4(),
        observation_run_id=uuid4(),
        lens_run_id=uuid4(),
        analysis_window=AnalysisWindow(now, now + timedelta(minutes=1)),
        lens=lens,  # type: ignore[arg-type]
    )


def _metric() -> MetricLensSnapshot:
    return MetricLensSnapshot(
        lens_id="metric-1",
        name="Metric",
        description=None,
        metric_id="cpu",
        adapter_type="prometheus",
        source_id="source",
        query="up",
        unit="count",
        analysis_objectives=(),
        reference_periods=(),
    )


def _alert() -> AlertLensSnapshot:
    return AlertLensSnapshot(
        lens_id="alert-1",
        name="Alert",
        description=None,
        source="jira_track_and_release",
        selector_query="project = IPO",
        analysis_objectives=(),
        reference_periods=(),
    )


def test_router_dispatches_mixed_assignments_by_exact_snapshot_type() -> None:
    metric = RecordingAdapter("metric")
    alert = RecordingAdapter("alert")
    router = _TypeRoutedLensAdapter(metric, alert)
    policy = ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=1)

    metric_assignment = _assignment(_metric())
    alert_assignment = _assignment(_alert())

    async def run() -> tuple[str, str]:
        return (
            await router.execute(metric_assignment, policy),
            await router.execute(alert_assignment, policy),
        )

    assert asyncio.run(run()) == ("metric", "alert")
    assert metric.assignments == [metric_assignment]
    assert alert.assignments == [alert_assignment]


def test_router_rejects_unsupported_snapshot_before_invoking_an_adapter() -> None:
    metric = RecordingAdapter("metric")
    alert = RecordingAdapter("alert")
    router = _TypeRoutedLensAdapter(metric, alert)
    policy = ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=1)

    async def run() -> None:
        await router.execute(_assignment(object()), policy)

    with pytest.raises(ValueError, match="unsupported Lens assignment type"):
        asyncio.run(run())
    assert metric.assignments == []
    assert alert.assignments == []


def test_public_execute_has_only_fresh_request_and_policy_inputs() -> None:
    parameters = inspect.signature(ObservationExecutionOrchestrator.execute).parameters
    assert tuple(parameters) == ("self", "request", "policy")
    assert not any(
        name in parameters
        for name in ("run_id", "resume", "stage", "replay", "idempotency", "retry")
    )
