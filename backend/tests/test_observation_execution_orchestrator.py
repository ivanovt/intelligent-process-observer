from __future__ import annotations

# ruff: noqa: E501
import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
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
from app.execution.contracts import CompletedObservationExecutionOutcome
from app.execution.orchestrator import (
    _PersistenceAwareTransaction,
    _TypeRoutedLensAdapter,
)
from app.reasoning.contracts import ObservationAnalysisResult, ObservationIdentity, ReasoningSuccess


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


class _RecordingTransaction:
    def __init__(self, session: object, events: list[str]) -> None:
        self.session = session
        self.events = events

    async def __aenter__(self) -> object:
        self.events.append("cleanup_begin")
        return self.session

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is None:
            self.events.append("cleanup_commit")
        else:
            self.events.append("cleanup_rollback")
        return False


class _RecordingSession:
    def __init__(self, run: object) -> None:
        self.run = run

    async def get(self, model: object, run_id):
        return self.run


class _CancellationRepository:
    def __init__(self, run: object, events: list[str]) -> None:
        self.run = run
        self.events = events

    async def cancel_observation_execution(self, session, run) -> None:
        assert run is self.run
        if run.status == "running":
            self.events.append("cleanup_terminalize")
            run.status = "cancelled"
            for child in run.lens_runs:
                if child.status in {"pending", "running"}:
                    child.status = "cancelled"


def _initialized(run_id=None, *, run=None):
    return SimpleNamespace(
        assignments=(),
        snapshot=None,
        observation_run_id=run_id or uuid4(),
        run=run,
    )


def _cancellation_orchestrator(events: list[str], run: object) -> ObservationExecutionOrchestrator:
    session = _RecordingSession(run)
    repository = _CancellationRepository(run, events)
    factory = type(
        "Factory",
        (),
        {"begin": lambda self: _RecordingTransaction(session, events)},
    )()
    return ObservationExecutionOrchestrator(
        session_factory=factory,
        definition_loader=None,
        runtime_repository=repository,
        metric_adapter=None,
        alert_adapter=None,
        relationship_evaluator=None,
        reasoning_executor=None,
        report_executor=None,
    )


def _analysis_result(observation_id, observation_run_id):
    return ObservationAnalysisResult.model_construct(
        identity=ObservationIdentity(
            observation_id=observation_id, observation_run_id=observation_run_id
        ),
        overall_state="uncertain",
        findings=(),
        hypotheses=(),
        limitations=(),
    )


def test_cancellation_during_fanout_settles_children_before_shielded_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    run = SimpleNamespace(status="running", lens_runs=[])
    initialized = _initialized(run=run)
    release = asyncio.Event()
    worker_started = asyncio.Event()
    worker_tasks: list[asyncio.Task[None]] = []

    async def initialize(*args, **kwargs):
        return initialized

    async def fanout(*args, **kwargs):
        async def completed():
            events.append("worker_completed")

        async def running():
            worker_started.set()
            await release.wait()

        async def pending():
            await asyncio.Event().wait()

        worker_tasks.extend(
            [
                asyncio.create_task(completed()),
                asyncio.create_task(running()),
                asyncio.create_task(pending()),
            ]
        )
        try:
            await worker_started.wait()
            await release.wait()
        finally:
            for task in worker_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*worker_tasks, return_exceptions=True)
            events.append("workers_settled")
            raise

    stages: list[str] = []
    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)
    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)
    monkeypatch.setattr(
        "app.execution.orchestrator.enforce_usable_results_gate",
        lambda *args, **kwargs: stages.append("gate"),
    )
    orchestrator = _cancellation_orchestrator(events, run)

    async def execute_and_cancel():
        task = asyncio.create_task(orchestrator.execute(None, None))
        await worker_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(execute_and_cancel())
    assert events.index("workers_settled") < events.index("cleanup_begin")
    assert events.index("cleanup_terminalize") < events.index("cleanup_commit")
    assert run.status == "cancelled"
    assert stages == []
    assert all(task.done() for task in worker_tasks)


@pytest.mark.parametrize("stage", ["reasoning", "reporting"])
def test_cancellation_during_later_stage_preserves_committed_artifacts_and_stops_downstream(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    events: list[str] = []
    run = SimpleNamespace(status="running", lens_runs=[])
    initialized = _initialized(run=run)
    entered = asyncio.Event()
    release = asyncio.Event()
    committed = {
        "lens": True,
        "relationship": True,
        "analysis": stage == "reporting",
        "report": False,
    }

    async def initialize(*args, **kwargs):
        return initialized

    async def fanout(*args, **kwargs):
        return ()

    async def gate(*args, **kwargs):
        return SimpleNamespace(usable=(), unavailable=())

    async def relationships(*args, **kwargs):
        return ()

    async def reasoning(*args, **kwargs):
        if stage == "reasoning":
            entered.set()
            await release.wait()
        committed["analysis"] = True
        return ReasoningSuccess(result=_analysis_result(uuid4(), initialized.observation_run_id))

    async def reporting(*args, **kwargs):
        assert stage == "reporting"
        entered.set()
        await release.wait()
        committed["report"] = True
        return CompletedObservationExecutionOutcome(initialized.observation_run_id)

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)
    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)
    monkeypatch.setattr("app.execution.orchestrator.enforce_usable_results_gate", gate)
    monkeypatch.setattr(
        "app.execution.orchestrator.evaluate_and_persist_relationships", relationships
    )
    monkeypatch.setattr("app.execution.orchestrator.invoke_and_persist_reasoning", reasoning)
    monkeypatch.setattr("app.execution.orchestrator.generate_and_persist_report", reporting)
    orchestrator = _cancellation_orchestrator(events, run)

    async def execute_and_cancel():
        task = asyncio.create_task(orchestrator.execute(None, None))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(execute_and_cancel())
    assert committed["lens"] and committed["relationship"]
    if stage == "reporting":
        assert committed["analysis"]
    assert not committed["report"]
    assert run.status == "cancelled"


def test_cancellation_racing_final_transaction_preserves_one_completed_terminal_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    run = SimpleNamespace(status="running", lens_runs=[])
    initialized = _initialized(run=run)
    entered = asyncio.Event()

    async def initialize(*args, **kwargs):
        return initialized

    async def reporting(*args, **kwargs):
        entered.set()
        run.status = "completed"
        events.append("final_commit")
        raise asyncio.CancelledError

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)

    async def fanout(*args, **kwargs):
        return ()

    async def gate(*args, **kwargs):
        return SimpleNamespace(usable=(), unavailable=())

    async def relationships(*args, **kwargs):
        return ()

    async def reasoning(*args, **kwargs):
        return ReasoningSuccess(result=_analysis_result(uuid4(), initialized.observation_run_id))

    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)
    monkeypatch.setattr(
        "app.execution.orchestrator.enforce_usable_results_gate",
        gate,
    )
    monkeypatch.setattr(
        "app.execution.orchestrator.evaluate_and_persist_relationships", relationships
    )
    monkeypatch.setattr("app.execution.orchestrator.invoke_and_persist_reasoning", reasoning)
    monkeypatch.setattr("app.execution.orchestrator.generate_and_persist_report", reporting)
    orchestrator = _cancellation_orchestrator(events, run)

    async def run_once():
        with pytest.raises(asyncio.CancelledError):
            await orchestrator.execute(None, None)

    asyncio.run(run_once())
    assert run.status == "completed"
    assert "cleanup_terminalize" not in events
    assert events[0] == "final_commit"


def test_cancellation_cleanup_failure_is_visible_and_does_not_claim_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(status="running", lens_runs=[])
    initialized = _initialized(run=run)
    error = RuntimeError("cleanup commit failed")
    error.persistence_failure = True

    class FailingTransaction(_RecordingTransaction):
        async def __aexit__(self, exc_type, exc, traceback) -> bool:
            run.status = "running"
            raise error

    session = _RecordingSession(run)
    factory = type("Factory", (), {"begin": lambda self: FailingTransaction(session, [])})()
    repository = _CancellationRepository(run, [])
    orchestrator = ObservationExecutionOrchestrator(
        session_factory=factory,
        definition_loader=None,
        runtime_repository=repository,
        metric_adapter=None,
        alert_adapter=None,
        relationship_evaluator=None,
        reasoning_executor=None,
        report_executor=None,
    )

    async def initialize(*args, **kwargs):
        return initialized

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)

    async def fanout(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)

    with pytest.raises(RuntimeError, match="cleanup commit failed"):
        asyncio.run(orchestrator.execute(None, None))
    assert run.status == "running"


@pytest.mark.parametrize(
    ("stage", "component"),
    [
        ("fanout", "fanout"),
        ("usable_results_gate", "usable_results_gate"),
        ("relationship_evaluator", "relationship_evaluator"),
        ("observation_reasoning", "observation_reasoning"),
        ("report_generation", "report_generation"),
    ],
)
def test_unexpected_stage_failures_map_to_exact_stage_and_stop_later_calls(
    monkeypatch: pytest.MonkeyPatch, stage: str, component: str
) -> None:
    initialized = _initialized()
    calls: list[str] = []
    aborts: list[str] = []

    async def initialize(*args, **kwargs):
        return initialized

    async def invoke(name: str, *args, **kwargs):
        calls.append(name)
        if name == stage:
            raise ValueError("unexpected")
        if name == "usable_results_gate":
            return SimpleNamespace(usable=(), unavailable=())
        if name == "relationship_evaluator":
            return ()
        if name == "observation_reasoning":
            return ReasoningSuccess(
                result=_analysis_result(uuid4(), initialized.observation_run_id)
            )
        if name == "report_generation":
            return CompletedObservationExecutionOutcome(initialized.observation_run_id)
        return ()

    async def abort(value, failed_stage):
        aborts.append(failed_stage)

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)

    async def fanout(*args, **kwargs):
        return await invoke("fanout")

    async def gate(*args, **kwargs):
        return await invoke("usable_results_gate")

    async def relationships(*args, **kwargs):
        return await invoke("relationship_evaluator")

    async def reasoning(*args, **kwargs):
        return await invoke("observation_reasoning")

    async def report(*args, **kwargs):
        return await invoke("report_generation")

    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)
    monkeypatch.setattr("app.execution.orchestrator.enforce_usable_results_gate", gate)
    monkeypatch.setattr(
        "app.execution.orchestrator.evaluate_and_persist_relationships", relationships
    )
    monkeypatch.setattr("app.execution.orchestrator.invoke_and_persist_reasoning", reasoning)
    monkeypatch.setattr("app.execution.orchestrator.generate_and_persist_report", report)
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

    outcome = asyncio.run(orchestrator.execute(None, None))
    assert outcome.reason.code == "execution_failed"
    assert outcome.reason.component == component
    assert aborts == [stage]
    expected = [
        "fanout",
        "usable_results_gate",
        "relationship_evaluator",
        "observation_reasoning",
        "report_generation",
    ]
    assert calls == expected[: expected.index(stage) + 1]


@pytest.mark.parametrize(
    "stage",
    [
        "fanout",
        "usable_results_gate",
        "relationship_evaluator",
        "observation_reasoning",
        "report_generation",
    ],
)
def test_persistence_failures_at_each_stage_propagate_without_fabricated_outcome(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    initialized = _initialized()
    error = RuntimeError(f"{stage} persistence unavailable")
    error.persistence_failure = True
    abort_called = False

    async def initialize(*args, **kwargs):
        return initialized

    async def failure(*args, **kwargs):
        raise error

    async def empty(*args, **kwargs):
        return ()

    async def usable(*args, **kwargs):
        return SimpleNamespace(usable=(), unavailable=())

    async def reasoning(*args, **kwargs):
        return ReasoningSuccess(result=_analysis_result(uuid4(), initialized.observation_run_id))

    async def report(*args, **kwargs):
        return CompletedObservationExecutionOutcome(initialized.observation_run_id)

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)
    monkeypatch.setattr(
        "app.execution.orchestrator.fan_out_lens_runs", failure if stage == "fanout" else empty
    )
    monkeypatch.setattr(
        "app.execution.orchestrator.enforce_usable_results_gate",
        failure if stage == "usable_results_gate" else usable,
    )
    monkeypatch.setattr(
        "app.execution.orchestrator.evaluate_and_persist_relationships",
        failure if stage == "relationship_evaluator" else empty,
    )
    monkeypatch.setattr(
        "app.execution.orchestrator.invoke_and_persist_reasoning",
        failure if stage == "observation_reasoning" else reasoning,
    )
    monkeypatch.setattr(
        "app.execution.orchestrator.generate_and_persist_report",
        failure if stage == "report_generation" else report,
    )
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

    async def unexpected_abort(*args, **kwargs):
        nonlocal abort_called
        abort_called = True

    monkeypatch.setattr(orchestrator, "_abort_after_failure", unexpected_abort)
    with pytest.raises(RuntimeError, match=stage):
        asyncio.run(orchestrator.execute(None, None))
    assert not abort_called


def test_explicit_reruns_after_failure_and_cancellation_create_fresh_graphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized_runs = [_initialized() for _ in range(4)]
    preparation_calls: list[object] = []
    invocation = 0

    async def initialize(*args, **kwargs):
        value = initialized_runs[len(preparation_calls)]
        preparation_calls.append(value.observation_run_id)
        return value

    async def fanout(*args, **kwargs):
        nonlocal invocation
        invocation += 1
        if invocation == 1:
            raise ValueError("first run failed")
        if invocation == 3:
            await asyncio.Event().wait()
        return ()

    monkeypatch.setattr("app.execution.orchestrator.initialize_observation_execution", initialize)
    monkeypatch.setattr("app.execution.orchestrator.fan_out_lens_runs", fanout)

    async def gate(*args, **kwargs):
        return SimpleNamespace(usable=(), unavailable=())

    async def relationships(*args, **kwargs):
        return ()

    async def reasoning(*args, **kwargs):
        return ReasoningSuccess(
            result=_analysis_result(
                uuid4(), initialized_runs[len(preparation_calls) - 1].observation_run_id
            )
        )

    async def report(*args, **kwargs):
        return CompletedObservationExecutionOutcome(
            initialized_runs[len(preparation_calls) - 1].observation_run_id
        )

    monkeypatch.setattr("app.execution.orchestrator.enforce_usable_results_gate", gate)
    monkeypatch.setattr(
        "app.execution.orchestrator.evaluate_and_persist_relationships", relationships
    )
    monkeypatch.setattr("app.execution.orchestrator.invoke_and_persist_reasoning", reasoning)
    monkeypatch.setattr("app.execution.orchestrator.generate_and_persist_report", report)
    orchestrator = _cancellation_orchestrator([], SimpleNamespace(status="running", lens_runs=[]))
    monkeypatch.setattr(orchestrator, "_abort_after_failure", lambda *a, **k: asyncio.sleep(0))

    first = asyncio.run(orchestrator.execute(None, None))
    second = asyncio.run(orchestrator.execute(None, None))

    async def cancelled_then_return():
        task = asyncio.create_task(orchestrator.execute(None, None))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancelled_then_return())
    fourth = asyncio.run(orchestrator.execute(None, None))
    assert first.reason.code == "execution_failed"
    assert isinstance(second, CompletedObservationExecutionOutcome)
    assert isinstance(fourth, CompletedObservationExecutionOutcome)
    assert len(preparation_calls) == 4
    assert len(set(preparation_calls)) == 4
    assert invocation == 4
