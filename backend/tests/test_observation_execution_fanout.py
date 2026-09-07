from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.execution import (
    AlertLensSnapshot,
    AnalysisWindow,
    CollectedLensOutcome,
    ExecutionPolicy,
    ExecutionReason,
    LensExecutionAssignment,
    MetricLensSnapshot,
    fan_out_lens_runs,
    verify_and_partition_lens_outcomes,
)
from app.infrastructure.persistence.models import LensRunModel
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
)
from app.metrics.contracts import MetricLensExecutionContext, MetricMandatoryAnalysisFailure
from app.metrics.result_builder import MetricResultBuilder


class Transaction(AbstractAsyncContextManager["Session"]):
    def __init__(
        self,
        session: Session,
        *,
        commit_gate: asyncio.Event | None = None,
        exit_error: BaseException | None = None,
    ) -> None:
        self.session = session
        self.commit_gate = commit_gate
        self.exit_error = exit_error
        self.committed = False

    async def __aenter__(self) -> Session:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if self.commit_gate is not None:
            await self.commit_gate.wait()
        if self.exit_error is not None:
            raise self.exit_error
        self.committed = exc_type is None
        return False


class Session:
    def __init__(self, runs: dict[object, LensRunModel]) -> None:
        self.runs = runs

    async def get(self, model: type[object], identity: object) -> object | None:
        assert model is LensRunModel
        return self.runs.get(identity)


class Factory:
    def __init__(
        self,
        runs: dict[object, LensRunModel],
        *,
        first_commit_gate: asyncio.Event | None = None,
        first_exit_error: BaseException | None = None,
        later_commit_gate: asyncio.Event | None = None,
        later_exit_error: BaseException | None = None,
        later_transaction_index: int | None = None,
    ) -> None:
        self.runs = runs
        self.first_commit_gate = first_commit_gate
        self.first_exit_error = first_exit_error
        self.later_commit_gate = later_commit_gate
        self.later_exit_error = later_exit_error
        self.later_transaction_index = later_transaction_index
        self.transactions: list[Transaction] = []

    def begin(self) -> Transaction:
        index = len(self.transactions)
        transaction = Transaction(
            Session(self.runs),
            commit_gate=(
                self.first_commit_gate
                if index == 0
                else self.later_commit_gate
                if index == self.later_transaction_index
                else None
            ),
            exit_error=(
                self.first_exit_error
                if index == 0
                else self.later_exit_error
                if index == self.later_transaction_index
                else None
            ),
        )
        self.transactions.append(transaction)
        return transaction


class Repository:
    async def advance_lens_run(
        self, session: object, lens_run: LensRunModel, target: LensRunStatus
    ) -> LensRunModel:
        lens_run.status = target.value
        return lens_run


class Adapter:
    def __init__(self, *, on_started: asyncio.Event | None = None) -> None:
        self.active = 0
        self.maximum_active = 0
        self.started: list[object] = []
        self.release: dict[object, asyncio.Event] = {}
        self.on_started = on_started
        self.cancelled: list[object] = []

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        release = self.release.setdefault(assignment.lens_run_id, asyncio.Event())
        self.started.append(assignment.lens_run_id)
        if self.on_started is not None:
            self.on_started.set()
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await release.wait()
        except asyncio.CancelledError:
            self.cancelled.append(assignment.lens_run_id)
            raise
        finally:
            self.active -= 1
        return _metric_outcome(assignment, "completed", "good")


class InfrastructureFailingAdapter(Adapter):
    """Raise one exact infrastructure error after a sibling has begun work."""

    def __init__(
        self,
        *,
        failing_lens_run_id: object,
        sibling_started: asyncio.Event,
        error: BaseException,
    ) -> None:
        super().__init__()
        self.failing_lens_run_id = failing_lens_run_id
        self.sibling_started = sibling_started
        self.error = error

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        if assignment.lens_run_id != self.failing_lens_run_id:
            return await super().execute(assignment, policy)
        self.started.append(assignment.lens_run_id)
        await self.sibling_started.wait()
        raise self.error


def test_fan_out_uses_fixed_work_conserving_workers_and_canonical_result_order() -> None:
    assignments = tuple(_metric_assignment(str(index)) for index in range(3))
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    factory = Factory(runs)
    adapter = Adapter()

    async def exercise() -> tuple[CollectedLensOutcome, ...]:
        task = asyncio.create_task(
            fan_out_lens_runs(
                session_factory=factory,
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=assignments,
                policy=ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=1),
            )
        )
        for _ in range(100):
            if len(adapter.started) >= 2:
                break
            await asyncio.sleep(0)
        assert len(adapter.started) == 2
        assert adapter.started == [assignments[0].lens_run_id, assignments[1].lens_run_id]
        adapter.release[assignments[0].lens_run_id].set()
        for _ in range(100):
            if len(adapter.started) >= 3:
                break
            await asyncio.sleep(0)
        assert len(adapter.started) == 3
        adapter.release[assignments[1].lens_run_id].set()
        adapter.release[assignments[2].lens_run_id].set()
        return await task

    outcomes = asyncio.run(exercise())

    assert adapter.maximum_active == 2
    assert tuple(outcome.assignment for outcome in outcomes) == assignments
    assert all(run.status == "running" for run in runs.values())
    assert len(factory.transactions) == 3
    assert all(transaction.committed for transaction in factory.transactions)


def test_fan_out_does_not_call_adapter_when_pending_admission_fails() -> None:
    assignment = _metric_assignment("only")
    run = _run(assignment)
    run.status = "failed"
    adapter = Adapter()

    with pytest.raises(ValueError, match="expected pending"):
        asyncio.run(
            fan_out_lens_runs(
                session_factory=Factory({assignment.lens_run_id: run}),
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=(assignment,),
                policy=ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=1),
            )
        )
    assert adapter.started == []


def test_fan_out_settles_active_siblings_after_admission_commit_failure() -> None:
    assignments = tuple(_metric_assignment(str(index)) for index in range(3))
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    sibling_started = asyncio.Event()
    factory = Factory(
        runs,
        first_commit_gate=sibling_started,
        first_exit_error=RuntimeError("admission commit failed"),
    )
    adapter = Adapter(on_started=sibling_started)

    async def exercise() -> None:
        with pytest.raises(RuntimeError, match="admission commit failed"):
            await fan_out_lens_runs(
                session_factory=factory,
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=assignments,
                policy=ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=1),
            )

    asyncio.run(exercise())

    assert len(factory.transactions) == 2
    assert factory.transactions[0].session is not factory.transactions[1].session
    assert adapter.started == [assignments[1].lens_run_id]
    assert adapter.cancelled == [assignments[1].lens_run_id]
    assert adapter.active == 0
    assert assignments[2].lens_run_id not in adapter.started


def test_fan_out_settles_siblings_after_adapter_infrastructure_error() -> None:
    assignments = tuple(_metric_assignment(str(index)) for index in range(3))
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    sibling_started = asyncio.Event()
    error = RuntimeError("adapter infrastructure failed")
    adapter = InfrastructureFailingAdapter(
        failing_lens_run_id=assignments[0].lens_run_id,
        sibling_started=sibling_started,
        error=error,
    )
    adapter.on_started = sibling_started
    factory = Factory(runs)

    async def exercise() -> None:
        with pytest.raises(RuntimeError) as caught:
            await fan_out_lens_runs(
                session_factory=factory,
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=assignments,
                policy=ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=1),
            )
        assert caught.value is error

    asyncio.run(exercise())

    assert len(factory.transactions) == 2
    assert len({id(transaction.session) for transaction in factory.transactions}) == 2
    assert adapter.started == [assignments[0].lens_run_id, assignments[1].lens_run_id]
    assert adapter.cancelled == [assignments[1].lens_run_id]
    assert adapter.active == 0
    assert runs[assignments[2].lens_run_id].status == "pending"


def test_fan_out_settles_siblings_after_later_admission_commit_failure() -> None:
    assignments = tuple(_metric_assignment(str(index)) for index in range(3))
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    sibling_started = asyncio.Event()
    error = RuntimeError("later admission commit failed")
    adapter = Adapter(on_started=sibling_started)
    factory = Factory(
        runs,
        later_commit_gate=sibling_started,
        later_exit_error=error,
        later_transaction_index=1,
    )

    async def exercise() -> None:
        with pytest.raises(RuntimeError) as caught:
            await fan_out_lens_runs(
                session_factory=factory,
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=assignments,
                policy=ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=1),
            )
        assert caught.value is error

    asyncio.run(exercise())

    assert len(factory.transactions) == 2
    assert len({id(transaction.session) for transaction in factory.transactions}) == 2
    assert adapter.started == [assignments[0].lens_run_id]
    assert adapter.cancelled == [assignments[0].lens_run_id]
    assert adapter.active == 0
    assert runs[assignments[2].lens_run_id].status == "pending"


def test_fan_out_settles_owned_workers_when_caller_cancels() -> None:
    assignments = tuple(_metric_assignment(str(index)) for index in range(2))
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    adapter = Adapter()

    async def exercise() -> None:
        task = asyncio.create_task(
            fan_out_lens_runs(
                session_factory=Factory(runs),
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=assignments,
                policy=ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=1),
            )
        )
        for _ in range(100):
            if len(adapter.started) == 2:
                break
            await asyncio.sleep(0)
        assert len(adapter.started) == 2
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert set(adapter.cancelled) == {assignment.lens_run_id for assignment in assignments}
    assert adapter.active == 0


def test_strict_join_verifies_topology_and_partitions_exact_result_variants() -> None:
    good = _metric_assignment("good")
    partial_good = _metric_assignment("partial-good")
    insufficient = _metric_assignment("insufficient")
    failed = _metric_assignment("failed")
    alert_completed = _alert_assignment("alert-completed")
    alert_partial = _alert_assignment("alert-partial")
    alert_failed = _alert_assignment("alert-failed")
    outcomes = (
        _metric_outcome(good, "completed", "good"),
        _metric_outcome(partial_good, "partial", "degraded"),
        _metric_outcome(insufficient, "completed", "insufficient"),
        _metric_outcome(failed, "failed", None),
        _alert_outcome(alert_completed, "completed"),
        _alert_outcome(alert_partial, "partial"),
        _alert_outcome(alert_failed, "failed"),
    )

    partition = verify_and_partition_lens_outcomes(
        (good, partial_good, insufficient, failed, alert_completed, alert_partial, alert_failed),
        outcomes,
    )

    assert partition.usable == (outcomes[0], outcomes[1], outcomes[4], outcomes[5])
    assert partition.unavailable == (outcomes[2], outcomes[3], outcomes[6])
    assert outcomes[3].artifact is not None
    assert outcomes[6].artifact is None
    with pytest.raises(ValueError, match="differs from initialized topology"):
        verify_and_partition_lens_outcomes((good,), (outcomes[0], outcomes[1]))
    with pytest.raises(ValueError, match="differs from initialized topology"):
        verify_and_partition_lens_outcomes((good, partial_good), (outcomes[1], outcomes[0]))
    with pytest.raises(ValueError, match="invalid data-quality"):
        verify_and_partition_lens_outcomes(
            (partial_good,), (_metric_outcome(partial_good, "partial", "insufficient"),)
        )


def _metric_assignment(lens_id: str) -> LensExecutionAssignment:
    window_end = datetime(2026, 9, 7, 12, tzinfo=UTC)
    return LensExecutionAssignment(
        observation_id=uuid4(),
        observation_run_id=uuid4(),
        lens_run_id=uuid4(),
        analysis_window=AnalysisWindow(from_=window_end - timedelta(minutes=5), to=window_end),
        lens=MetricLensSnapshot(
            lens_id=lens_id,
            name=lens_id,
            description=None,
            metric_id=f"metric-{lens_id}",
            adapter_type="prometheus",
            source_id="source",
            query="up",
            unit="count",
            analysis_objectives=(),
            reference_periods=(),
        ),
    )


def _alert_assignment(lens_id: str) -> LensExecutionAssignment:
    metric = _metric_assignment(lens_id)
    return LensExecutionAssignment(
        observation_id=metric.observation_id,
        observation_run_id=metric.observation_run_id,
        lens_run_id=metric.lens_run_id,
        analysis_window=metric.analysis_window,
        lens=AlertLensSnapshot(
            lens_id=lens_id,
            name=lens_id,
            description=None,
            source="jira_track_and_release",
            selector_query="project = OPS",
            analysis_objectives=(),
            reference_periods=(),
        ),
    )


def _run(assignment: LensExecutionAssignment) -> LensRunModel:
    return LensRunModel(
        id=assignment.lens_run_id,
        observation_run_id=assignment.observation_run_id,
        lens_id=assignment.lens.lens_id,
        lens_type=assignment.lens.lens_type,
        status="pending",
    )


def _metric_outcome(
    assignment: LensExecutionAssignment, status: str, quality: str | None
) -> CollectedLensOutcome:
    context = MetricLensExecutionContext.model_validate(
        {
            "identity": {
                "observation_id": assignment.observation_id,
                "observation_run_id": assignment.observation_run_id,
                "lens_id": assignment.lens.lens_id,
                "lens_run_id": assignment.lens_run_id,
                "metric_ref": assignment.lens.metric_id,
                "unit": assignment.lens.unit,
            },
            "provider_scope": {"adapter_type": "prometheus", "source_id": "source", "query": "up"},
            "analysis_window": {
                "from": assignment.analysis_window.from_,
                "to": assignment.analysis_window.to,
            },
            "analysis_objectives": (),
            "reference_periods": (),
            "history_policy": {},
        }
    )
    builder = MetricResultBuilder()
    if status == "failed":
        _, artifact = builder.failed(context, MetricMandatoryAnalysisFailure(diagnostic="test"))
    else:
        _, artifact = builder.completed_insufficient(context)
        artifact.payload["data_quality"] = quality
        if status == "partial":
            artifact.status = LensRunStatus.PARTIAL
            artifact.payload["status"]["state"] = "partial"
            artifact.payload["reason"] = {"code": "test", "component": "test"}
    return CollectedLensOutcome(
        assignment=assignment,
        status=status,  # type: ignore[arg-type]
        artifact=artifact,
        reason=ExecutionReason(code="test", component="test") if status != "completed" else None,
    )


def _alert_outcome(
    assignment: LensExecutionAssignment, status: str = "failed"
) -> CollectedLensOutcome:
    if status == "failed":
        return CollectedLensOutcome(
            assignment=assignment, status="failed", reason=ExecutionReason(code="test")
        )
    provenance = {"source": "test"}
    identity = LensResultIdentity(
        observation_id=assignment.observation_id,
        observation_run_id=assignment.observation_run_id,
        lens_id=assignment.lens.lens_id,
        lens_run_id=assignment.lens_run_id,
    )
    artifact = LensAnalysisResultInput(
        result_type=LensType.ALERT,
        status=LensRunStatus(status),
        schema_version="1.0",
        identity=identity,
        provenance=provenance,
        payload={
            "schema_version": "1.0",
            "lens_type": "alert",
            "identity": identity.model_dump(mode="json"),
            "provenance": provenance,
            "status": status,
            **({"reason": {"code": "test", "component": "test"}} if status == "partial" else {}),
        },
    )
    return CollectedLensOutcome(
        assignment=assignment,
        status=status,  # type: ignore[arg-type]
        artifact=artifact,
        reason=ExecutionReason(code="test") if status == "partial" else None,
    )
