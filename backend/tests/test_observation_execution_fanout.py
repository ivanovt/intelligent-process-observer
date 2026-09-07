from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertProviderScope,
)
from app.alerts.result_builder import AlertResultBuilder
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
from app.infrastructure.persistence.runtime_contracts import LensRunStatus
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricEvidence,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
    MetricProviderScope,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedDegradedSeries,
    PreparedGoodSeries,
)
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


class NormalFailureAdapter(Adapter):
    """Return one ordinary failed Lens outcome while other workers keep executing."""

    def __init__(self, failing_lens_run_id: object) -> None:
        super().__init__()
        self.failing_lens_run_id = failing_lens_run_id

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        if assignment.lens_run_id != self.failing_lens_run_id:
            return await super().execute(assignment, policy)
        self.started.append(assignment.lens_run_id)
        return _metric_outcome(assignment, "failed", None)


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


def test_strict_join_does_not_continue_when_one_usable_lens_finishes_early() -> None:
    first = _metric_assignment("first")
    second_source = _metric_assignment("second")
    second = LensExecutionAssignment(
        observation_id=first.observation_id,
        observation_run_id=first.observation_run_id,
        lens_run_id=second_source.lens_run_id,
        analysis_window=first.analysis_window,
        lens=second_source.lens,
    )
    assignments = (first, second)
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    adapter = Adapter()
    continuation_started = asyncio.Event()

    async def join_then_continue() -> None:
        outcomes = await fan_out_lens_runs(
            session_factory=Factory(runs),
            runtime_repository=Repository(),  # type: ignore[arg-type]
            adapter=adapter,
            assignments=assignments,
            policy=ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=1),
        )
        partition = verify_and_partition_lens_outcomes(assignments, outcomes)
        assert len(partition.usable) == 2
        continuation_started.set()

    async def exercise() -> None:
        task = asyncio.create_task(join_then_continue())
        for _ in range(100):
            if len(adapter.started) == 2:
                break
            await asyncio.sleep(0)
        assert len(adapter.started) == 2
        adapter.release[first.lens_run_id].set()
        for _ in range(10):
            await asyncio.sleep(0)
        assert not continuation_started.is_set()
        adapter.release[second.lens_run_id].set()
        await task

    asyncio.run(exercise())
    assert continuation_started.is_set()


def test_normal_failed_lens_does_not_stop_peers_or_queued_work_before_terminal_join() -> None:
    first = _metric_assignment("failed")
    assignments = (first,) + tuple(
        LensExecutionAssignment(
            observation_id=first.observation_id,
            observation_run_id=first.observation_run_id,
            lens_run_id=source.lens_run_id,
            analysis_window=first.analysis_window,
            lens=source.lens,
        )
        for source in (_metric_assignment("peer"), _metric_assignment("queued"))
    )
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    adapter = NormalFailureAdapter(assignments[0].lens_run_id)

    async def exercise() -> tuple[CollectedLensOutcome, ...]:
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
            if len(adapter.started) == 3:
                break
            await asyncio.sleep(0)
        assert set(adapter.started) == {assignment.lens_run_id for assignment in assignments}
        for lens_run_id, release in adapter.release.items():
            assert lens_run_id != assignments[0].lens_run_id
            release.set()
        return await task

    outcomes = asyncio.run(exercise())
    partition = verify_and_partition_lens_outcomes(assignments, outcomes)

    assert outcomes[0].status == "failed"
    assert partition.usable == outcomes[1:]
    assert partition.unavailable == (outcomes[0],)


def test_fan_out_does_not_call_adapter_when_pending_admission_fails() -> None:
    assignment = _metric_assignment("only")
    run = _run(assignment)
    adapter = Adapter()
    error = RuntimeError("initial admission commit failed")

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(
            fan_out_lens_runs(
                session_factory=Factory({assignment.lens_run_id: run}, first_exit_error=error),
                runtime_repository=Repository(),  # type: ignore[arg-type]
                adapter=adapter,
                assignments=(assignment,),
                policy=ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=1),
            )
        )
    assert caught.value is error
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
    assignments = tuple(_metric_assignment(str(index)) for index in range(3))
    runs = {assignment.lens_run_id: _run(assignment) for assignment in assignments}
    adapter = Adapter()
    factory = Factory(runs)

    async def exercise() -> None:
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
            if len(adapter.started) == 2:
                break
            await asyncio.sleep(0)
        assert len(adapter.started) == 2
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert set(adapter.cancelled) == {assignment.lens_run_id for assignment in assignments[:2]}
    assert adapter.active == 0
    assert len(factory.transactions) == 2
    assert adapter.started == [assignments[0].lens_run_id, assignments[1].lens_run_id]
    assert runs[assignments[2].lens_run_id].status == "pending"


def test_strict_join_verifies_topology_and_partitions_exact_result_variants() -> None:
    completed_good = _metric_assignment("completed-good")
    completed_degraded = _metric_assignment("completed-degraded")
    partial_good = _metric_assignment("partial-good")
    partial_degraded = _metric_assignment("partial-degraded")
    insufficient = _metric_assignment("completed-insufficient")
    failed = _metric_assignment("failed")
    alert_completed = _alert_assignment("alert-completed")
    alert_partial = _alert_assignment("alert-partial")
    alert_failed = _alert_assignment("alert-failed")
    outcomes = (
        _metric_outcome(completed_good, "completed", "good"),
        _metric_outcome(completed_degraded, "completed", "degraded"),
        _metric_outcome(partial_good, "partial", "good"),
        _metric_outcome(partial_degraded, "partial", "degraded"),
        _metric_outcome(insufficient, "completed", "insufficient"),
        _metric_outcome(failed, "failed", None),
        _alert_outcome(alert_completed, "completed"),
        _alert_outcome(alert_partial, "partial"),
        _alert_outcome(alert_failed, "failed"),
    )

    partition = verify_and_partition_lens_outcomes(
        (
            completed_good,
            completed_degraded,
            partial_good,
            partial_degraded,
            insufficient,
            failed,
            alert_completed,
            alert_partial,
            alert_failed,
        ),
        outcomes,
    )

    assert partition.usable == (
        outcomes[0],
        outcomes[1],
        outcomes[2],
        outcomes[3],
        outcomes[6],
        outcomes[7],
    )
    assert partition.unavailable == (outcomes[4], outcomes[5], outcomes[8])
    assert outcomes[5].artifact is not None
    assert outcomes[8].artifact is None
    with pytest.raises(ValueError, match="differs from initialized topology"):
        verify_and_partition_lens_outcomes((completed_good,), (outcomes[0], outcomes[1]))
    with pytest.raises(ValueError, match="differs from initialized topology"):
        verify_and_partition_lens_outcomes(
            (completed_good, completed_degraded), (outcomes[1], outcomes[0])
        )
    with pytest.raises(ValueError, match="invalid data-quality"):
        verify_and_partition_lens_outcomes(
            (partial_good,), (_boundary_invalid_metric_outcome(partial_good),)
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
    context = _metric_context(assignment)
    builder = MetricResultBuilder()
    if status == "failed":
        _, artifact = builder.failed(context, MetricMandatoryAnalysisFailure(diagnostic="test"))
    elif quality == "insufficient":
        _, artifact = builder.completed_insufficient(context)
    else:
        prepared = _prepared_metric(quality)
        semantics = _metric_semantics()
        if status == "partial":
            _, artifact = builder.partial_reference_unavailable(
                context, prepared, semantics, (), ()
            )
        else:
            _, artifact = builder.completed_sufficient(context, prepared, semantics)
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
    context = _alert_context(assignment)
    builder = AlertResultBuilder()
    if status == "completed":
        _, terminal = builder.completed_zero(context, AlertMandatoryEvidence())
    else:
        _, terminal = builder.usable(
            context,
            (),
            AlertMandatoryEvidence(),
            None,
            current_rejected=True,
            reference_unavailable=False,
            zero=True,
        )
    return CollectedLensOutcome(
        assignment=assignment,
        status=status,  # type: ignore[arg-type]
        artifact=terminal.artifact,
        reason=ExecutionReason(code="test") if status == "partial" else None,
    )


def _metric_context(assignment: LensExecutionAssignment) -> MetricLensExecutionContext:
    assert isinstance(assignment.lens, MetricLensSnapshot)
    return MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=assignment.observation_id,
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
        analysis_window=MetricAnalysisWindow(
            **{"from": assignment.analysis_window.from_, "to": assignment.analysis_window.to}
        ),
        analysis_objectives=assignment.lens.analysis_objectives,
        reference_periods=assignment.lens.reference_periods,
    )


def _prepared_metric(quality: str) -> PreparedGoodSeries | PreparedDegradedSeries:
    prepared_type = PreparedGoodSeries if quality == "good" else PreparedDegradedSeries
    return prepared_type(
        data_quality=quality,
        samples=(),
        evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
        residuals=(),
    )


def _metric_semantics() -> MetricSemantics:
    return MetricSemantics(
        trend=MetricTrend(direction="stable", rate="not_classified"),
        variability=MetricVariability(state="low"),
    )


def _alert_context(assignment: LensExecutionAssignment) -> AlertLensExecutionContext:
    assert isinstance(assignment.lens, AlertLensSnapshot)
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=assignment.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=assignment.lens.lens_id,
            lens_run_id=assignment.lens_run_id,
        ),
        provider_scope=AlertProviderScope(
            source=assignment.lens.source, query=assignment.lens.selector_query
        ),
        analysis_window=AlertAnalysisWindow(
            **{"from": assignment.analysis_window.from_, "to": assignment.analysis_window.to}
        ),
        lens_name=assignment.lens.name,
        analysis_objectives=assignment.lens.analysis_objectives,
        reference_periods=assignment.lens.reference_periods,
    )


def _boundary_invalid_metric_outcome(
    assignment: LensExecutionAssignment,
) -> CollectedLensOutcome:
    """Construct the sole deliberately invalid envelope used by JOIN rejection coverage."""

    valid = _metric_outcome(assignment, "partial", "good")
    assert valid.artifact is not None
    envelope = valid.artifact.to_persistence_envelope()
    envelope.payload["data_quality"] = "insufficient"
    return CollectedLensOutcome(
        assignment=assignment,
        status="partial",
        artifact=envelope,
        reason=ExecutionReason(code="test", component="test"),
    )
