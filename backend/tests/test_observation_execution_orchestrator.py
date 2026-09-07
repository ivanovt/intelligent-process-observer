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
from app.execution.orchestrator import (
    _PersistenceAwareTransaction,
    _TypeRoutedLensAdapter,
)


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


class _UnexpectedBaseException(BaseException):
    pass


class _Transaction:
    def __init__(
        self,
        exit_error: BaseException | None = None,
        enter_error: BaseException | None = None,
    ) -> None:
        self.exit_error = exit_error
        self.enter_error = enter_error

    async def __aenter__(self) -> object:
        if self.enter_error is not None:
            raise self.enter_error
        return object()

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        if self.exit_error is not None:
            raise self.exit_error
        return False


class _Factory:
    def begin(self) -> _Transaction:
        return _Transaction()


def test_persistence_wrapper_does_not_tag_semantic_body_failure() -> None:
    error = ValueError("semantic failure")

    async def run() -> None:
        async with _PersistenceAwareTransaction(_Transaction()):
            raise error

    with pytest.raises(ValueError, match="semantic failure"):
        asyncio.run(run())
    assert not getattr(error, "persistence_failure", False)


def test_persistence_wrapper_tags_and_propagates_exit_failure() -> None:
    error = RuntimeError("commit failed")

    async def run() -> None:
        async with _PersistenceAwareTransaction(_Transaction(error)):
            pass

    with pytest.raises(RuntimeError, match="commit failed") as raised:
        asyncio.run(run())
    assert raised.value is error
    assert error.persistence_failure is True


def test_persistence_wrapper_tags_and_propagates_enter_failure() -> None:
    error = RuntimeError("connection failed")

    async def run() -> None:
        async with _PersistenceAwareTransaction(_Transaction(enter_error=error)):
            pass

    with pytest.raises(RuntimeError, match="connection failed") as raised:
        asyncio.run(run())
    assert raised.value is error
    assert error.persistence_failure is True


@pytest.mark.parametrize(
    "error_type", [_UnexpectedBaseException, ValueError, KeyboardInterrupt, SystemExit]
)
def test_outer_base_exception_boundary_preserves_special_process_exits_and_aborts_other_errors(
    monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    initialized = type(
        "InitializedFake",
        (),
        {"assignments": (), "snapshot": None, "observation_run_id": uuid4()},
    )()
    abort_stages: list[str] = []

    async def initialize(*args, **kwargs):
        return initialized

    async def fanout(*args, **kwargs):
        raise error_type()

    async def abort(value, stage: str) -> None:
        assert value is initialized
        abort_stages.append(stage)

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)
    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)
    orchestrator = ObservationExecutionOrchestrator(
        session_factory=_Factory(),
        definition_loader=None,
        runtime_repository=None,
        metric_adapter=None,
        alert_adapter=None,
        relationship_evaluator=None,
        reasoning_executor=None,
        report_executor=None,
    )
    monkeypatch.setattr(orchestrator, "_abort_after_failure", abort)

    async def run():
        return await orchestrator.execute(None, None)

    if error_type in {_UnexpectedBaseException, ValueError}:
        outcome = asyncio.run(run())
        assert outcome.reason.code == "execution_failed"
        assert outcome.reason.component == "fanout"
        assert abort_stages == ["fanout"]
    else:
        with pytest.raises(error_type):
            asyncio.run(run())
        assert abort_stages == []
