from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.diagnostics import OperationalEventEmitter
from app.execution import (
    AnalysisWindow,
    ExecutionPolicy,
    ExecutionReason,
    LaunchAccepted,
    LaunchConflict,
    LaunchUnavailable,
    ObservationExecutionRequest,
    ObservationRunAcceptanceSummary,
    ObservationRunManager,
    ObservationRunManagerState,
    RejectedObservationExecutionOutcome,
)


class _Lookup:
    def __init__(self) -> None:
        self.active: dict[UUID, UUID] = {}
        self.calls: list[UUID] = []

    async def get_active_observation_run_id(self, observation_id: UUID) -> UUID | None:
        self.calls.append(observation_id)
        return self.active.get(observation_id)


class _Reconciler:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.reconcile_calls = 0
        self.verify_calls = 0

    async def reconcile_active_observation_runs(self) -> None:
        self.reconcile_calls += 1
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary persistence outage")

    async def has_active_observation_runs(self) -> bool:
        self.verify_calls += 1
        return False


class _Orchestrator:
    def __init__(self, lookup: _Lookup, *, fail_continuation: bool = False) -> None:
        self.lookup = lookup
        self.fail_continuation = fail_continuation
        self.initialize_calls = 0
        self.continue_calls = 0
        self.release_continuation = asyncio.Event()

    async def initialize(self, request, policy):
        self.initialize_calls += 1
        run_id = uuid4()
        self.lookup.active[request.observation_id] = run_id
        now = datetime.now(UTC)
        return SimpleNamespace(
            observation_run_id=run_id,
            acceptance_summary=ObservationRunAcceptanceSummary(
                observation_run_id=run_id,
                observation_id=request.observation_id,
                observation_name="CPU health",
                analysis_window=request.analysis_window,
                created_at=now,
                started_at=now,
                href=f"/api/v1/observation-runs/{run_id}",
            ),
        )

    async def continue_execution(self, initialized, policy):
        self.continue_calls += 1
        if self.fail_continuation:
            raise RuntimeError("continuation persistence failed")
        await self.release_continuation.wait()
        self.lookup.active.pop(initialized.acceptance_summary.observation_id, None)
        return SimpleNamespace(kind="completed")


def _request(observation_id: UUID | None = None) -> ObservationExecutionRequest:
    now = datetime.now(UTC)
    return ObservationExecutionRequest(
        observation_id=observation_id or uuid4(),
        analysis_window=AnalysisWindow(now - timedelta(minutes=5), now),
    )


def _manager(
    orchestrator: _Orchestrator,
    lookup: _Lookup,
    reconciler: _Reconciler,
    *,
    sleeps: list[float] | None = None,
    emitter: OperationalEventEmitter | None = None,
) -> ObservationRunManager:
    async def sleep(delay: float) -> None:
        if sleeps is not None:
            sleeps.append(delay)
        await asyncio.sleep(0)

    return ObservationRunManager(
        orchestrator=orchestrator,
        active_run_lookup=lookup,
        reconciler=reconciler,
        policy=ExecutionPolicy(max_parallel_lens_runs=4, lens_deadline_seconds=300),
        sleep=sleep,
        emitter=emitter,
    )


def test_managed_continuation_failure_is_logged_without_changing_recovery_behavior() -> None:
    """The detached-task observer retains its existing recovery transition."""

    async def run() -> list[str]:
        messages: list[str] = []
        logger = logging.getLogger("test.manager.operational")
        logger.handlers = [_CollectingHandler(messages)]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        lookup = _Lookup()
        manager = _manager(
            _Orchestrator(lookup, fail_continuation=True),
            lookup,
            _Reconciler(),
            emitter=OperationalEventEmitter(logger=logger),
        )

        outcome = await manager.launch(_request())
        assert isinstance(outcome, LaunchAccepted)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert manager.state is ObservationRunManagerState.READY
        return messages

    events = [json.loads(message) for message in asyncio.run(run())]
    assert any(event["event"] == "managed_execution_failed" for event in events)


class _CollectingHandler(logging.Handler):
    """Collect manager events without changing global logging state."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self._messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        """Capture one formatted operational event."""
        self._messages.append(record.getMessage())


def test_launch_registers_one_detached_continuation_and_immutable_running_snapshot() -> None:
    async def run() -> None:
        lookup = _Lookup()
        orchestrator = _Orchestrator(lookup)
        manager = _manager(orchestrator, lookup, _Reconciler())

        outcome = await manager.launch(_request())

        assert isinstance(outcome, LaunchAccepted)
        assert outcome.summary.status == "running"
        assert outcome.summary.reason is None
        assert outcome.summary.analytical_state is None
        assert outcome.summary.finished_at is None
        assert outcome.summary.duration_seconds is None
        assert orchestrator.continue_calls == 1
        with pytest.raises(FrozenInstanceError):
            outcome.summary.status = "completed"  # type: ignore[misc]
        orchestrator.release_continuation.set()
        await asyncio.sleep(0)

    asyncio.run(run())


def test_same_observation_launches_are_serialized_and_keep_conflict_identity() -> None:
    async def run() -> None:
        lookup = _Lookup()
        orchestrator = _Orchestrator(lookup)
        manager = _manager(orchestrator, lookup, _Reconciler())
        request = _request()

        first, second = await asyncio.gather(manager.launch(request), manager.launch(request))

        accepted = first if isinstance(first, LaunchAccepted) else second
        conflict = second if isinstance(second, LaunchConflict) else first
        assert isinstance(accepted, LaunchAccepted)
        assert isinstance(conflict, LaunchConflict)
        assert conflict.observation_run_id == accepted.summary.observation_run_id
        assert orchestrator.initialize_calls == 1
        assert orchestrator.continue_calls == 1
        orchestrator.release_continuation.set()
        await asyncio.sleep(0)

    asyncio.run(run())


def test_preparation_rejection_settles_admission_without_continuation_or_recovery() -> None:
    class RejectingOrchestrator(_Orchestrator):
        async def initialize(self, request, policy):
            self.initialize_calls += 1
            return RejectedObservationExecutionOutcome(
                ExecutionReason("observation_not_found", "execution_preparation")
            )

    async def run() -> None:
        lookup = _Lookup()
        orchestrator = RejectingOrchestrator(lookup)
        reconciler = _Reconciler()
        manager = _manager(orchestrator, lookup, reconciler)

        rejected = await manager.launch(_request())

        assert isinstance(rejected, RejectedObservationExecutionOutcome)
        assert orchestrator.continue_calls == 0
        assert reconciler.reconcile_calls == 0
        assert manager.state is ObservationRunManagerState.READY

    asyncio.run(run())


def test_active_run_index_loser_maps_to_the_one_durable_conflict_lookup() -> None:
    class IndexDiagnostic:
        constraint_name = "uq_observation_runs_one_active_per_observation"

    class IndexFailure(Exception):
        diag = IndexDiagnostic()

    class IndexLosingOrchestrator(_Orchestrator):
        async def initialize(self, request, policy):
            self.initialize_calls += 1
            raise IntegrityError(None, None, IndexFailure())

    class RacingLookup(_Lookup):
        def __init__(self, active_run_id: UUID) -> None:
            super().__init__()
            self.active_run_id = active_run_id

        async def get_active_observation_run_id(self, observation_id: UUID) -> UUID | None:
            self.calls.append(observation_id)
            return None if len(self.calls) == 1 else self.active_run_id

    async def run() -> None:
        request = _request()
        expected_run_id = uuid4()
        lookup = RacingLookup(expected_run_id)
        orchestrator = IndexLosingOrchestrator(lookup)
        manager = _manager(orchestrator, lookup, _Reconciler())

        outcome = await manager.launch(request)

        assert outcome == LaunchConflict(expected_run_id)
        assert lookup.calls == [request.observation_id, request.observation_id]
        assert orchestrator.initialize_calls == 1
        assert orchestrator.continue_calls == 0
        assert manager.state is ObservationRunManagerState.READY

    asyncio.run(run())


def test_active_run_index_loser_with_no_post_rollback_row_is_uncertain() -> None:
    class IndexDiagnostic:
        constraint_name = "uq_observation_runs_one_active_per_observation"

    class IndexFailure(Exception):
        diag = IndexDiagnostic()

    class IndexLosingOrchestrator(_Orchestrator):
        async def initialize(self, request, policy):
            self.initialize_calls += 1
            raise IntegrityError(None, None, IndexFailure())

    async def run() -> None:
        lookup = _Lookup()
        request = _request()
        orchestrator = IndexLosingOrchestrator(lookup)
        manager = _manager(orchestrator, lookup, _Reconciler())

        outcome = await manager.launch(request)

        assert outcome == LaunchUnavailable(code="launch_admission_uncertain")
        assert lookup.calls == [request.observation_id, request.observation_id]
        assert orchestrator.initialize_calls == 1
        assert orchestrator.continue_calls == 0
        assert manager.state is ObservationRunManagerState.READY

    asyncio.run(run())


def test_recovery_fences_a_committed_initializer_before_continuation_registration() -> None:
    class FencedOrchestrator(_Orchestrator):
        manager: ObservationRunManager

        async def initialize(self, request, policy):
            initialized = await super().initialize(request, policy)
            asyncio.create_task(self.manager.request_recovery())
            await asyncio.sleep(0)
            return initialized

    async def run() -> None:
        lookup = _Lookup()
        orchestrator = FencedOrchestrator(lookup)
        reconciler = _Reconciler()
        manager = _manager(orchestrator, lookup, reconciler)
        orchestrator.manager = manager

        result = await manager.launch(_request())

        assert isinstance(result, LaunchUnavailable)
        assert orchestrator.continue_calls == 0
        assert reconciler.reconcile_calls == 1
        assert manager.state is ObservationRunManagerState.READY

    asyncio.run(run())


def test_recovery_cancels_a_registered_initializer_before_any_continuation() -> None:
    class BlockingOrchestrator(_Orchestrator):
        entered = asyncio.Event()

        async def initialize(self, request, policy):
            self.entered.set()
            await asyncio.Event().wait()

    async def run() -> None:
        lookup = _Lookup()
        orchestrator = BlockingOrchestrator(lookup)
        reconciler = _Reconciler()
        manager = _manager(orchestrator, lookup, reconciler)
        launch = asyncio.create_task(manager.launch(_request()))
        await orchestrator.entered.wait()

        await manager.request_recovery()

        with pytest.raises(asyncio.CancelledError):
            await launch
        assert orchestrator.continue_calls == 0
        assert reconciler.reconcile_calls == 1
        assert manager.state is ObservationRunManagerState.READY

    asyncio.run(run())


def test_indeterminate_initialization_failure_blocks_global_admission_until_recovery() -> None:
    class FailingOrchestrator(_Orchestrator):
        async def initialize(self, request, policy):
            self.initialize_calls += 1
            raise RuntimeError("commit outcome is indeterminate")

    async def run() -> None:
        lookup = _Lookup()
        orchestrator = FailingOrchestrator(lookup)
        release_retry = asyncio.Event()
        sleeps: list[float] = []

        async def sleep(delay: float) -> None:
            sleeps.append(delay)
            await release_retry.wait()

        manager = ObservationRunManager(
            orchestrator=orchestrator,
            active_run_lookup=lookup,
            reconciler=_Reconciler(failures=1),
            policy=ExecutionPolicy(max_parallel_lens_runs=4, lens_deadline_seconds=300),
            sleep=sleep,
        )

        assert isinstance(await manager.launch(_request()), LaunchUnavailable)
        await asyncio.sleep(0)
        assert manager.state is ObservationRunManagerState.RECOVERY_REQUIRED
        assert isinstance(await manager.launch(_request()), LaunchUnavailable)
        release_retry.set()
        await manager.request_recovery()

        assert manager.state is ObservationRunManagerState.READY
        assert sleeps == [5]

    asyncio.run(run())


def test_reconciliation_waits_for_cancelled_initializer_session_settlement() -> None:
    class SettlingOrchestrator(_Orchestrator):
        def __init__(self, lookup) -> None:
            super().__init__(lookup)
            self.entered = asyncio.Event()
            self.settled = asyncio.Event()

        async def initialize(self, request, policy):
            self.entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                self.settled.set()

    class SettlementCheckingReconciler(_Reconciler):
        def __init__(self, orchestrator) -> None:
            super().__init__()
            self.orchestrator = orchestrator

        async def reconcile_active_observation_runs(self) -> None:
            assert self.orchestrator.settled.is_set()
            await super().reconcile_active_observation_runs()

    async def run() -> None:
        lookup = _Lookup()
        orchestrator = SettlingOrchestrator(lookup)
        reconciler = SettlementCheckingReconciler(orchestrator)
        manager = _manager(orchestrator, lookup, reconciler)
        launch = asyncio.create_task(manager.launch(_request()))
        await orchestrator.entered.wait()

        await manager.request_recovery()

        with pytest.raises(asyncio.CancelledError):
            await launch
        assert reconciler.reconcile_calls == 1

    asyncio.run(run())


def test_concurrent_recovery_requests_join_one_reconciliation_task() -> None:
    class BlockingReconciler(_Reconciler):
        def __init__(self) -> None:
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def reconcile_active_observation_runs(self) -> None:
            self.reconcile_calls += 1
            self.entered.set()
            await self.release.wait()

    async def run() -> None:
        lookup = _Lookup()
        reconciler = BlockingReconciler()
        manager = _manager(_Orchestrator(lookup), lookup, reconciler)
        first = asyncio.create_task(manager.request_recovery())
        await reconciler.entered.wait()
        second = asyncio.create_task(manager.request_recovery())
        await asyncio.sleep(0)
        assert reconciler.reconcile_calls == 1
        reconciler.release.set()
        await asyncio.gather(first, second)
        assert reconciler.verify_calls == 1

    asyncio.run(run())


def test_recovery_retries_sequentially_and_reopens_only_after_verified_empty_state() -> None:
    async def run() -> None:
        lookup = _Lookup()
        orchestrator = _Orchestrator(lookup)
        sleeps: list[float] = []
        reconciler = _Reconciler(failures=1)
        manager = _manager(orchestrator, lookup, reconciler, sleeps=sleeps)

        await manager.request_recovery()

        assert manager.state is ObservationRunManagerState.READY
        assert manager.recovery_generation == 1
        assert reconciler.reconcile_calls == 2
        assert reconciler.verify_calls == 1
        assert sleeps == [5]

    asyncio.run(run())


def test_failed_continuation_fences_global_admission_until_reconciliation_finishes() -> None:
    async def run() -> None:
        lookup = _Lookup()
        orchestrator = _Orchestrator(lookup, fail_continuation=True)
        reconciler = _Reconciler(failures=1)
        sleeps: list[float] = []
        manager = _manager(orchestrator, lookup, reconciler, sleeps=sleeps)

        accepted = await manager.launch(_request())
        assert isinstance(accepted, LaunchAccepted)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        blocked = await manager.launch(_request())

        assert isinstance(blocked, LaunchUnavailable)
        assert blocked.code == "execution_recovery_pending"
        await manager.request_recovery()
        assert manager.state is ObservationRunManagerState.READY
        assert sleeps == [5]

    asyncio.run(run())


def test_shutdown_blocks_new_admission_and_waits_for_reconciliation() -> None:
    async def run() -> None:
        lookup = _Lookup()
        orchestrator = _Orchestrator(lookup)
        reconciler = _Reconciler()
        manager = _manager(orchestrator, lookup, reconciler)
        accepted = await manager.launch(_request())
        assert isinstance(accepted, LaunchAccepted)

        await manager.shutdown()
        unavailable = await manager.launch(_request())

        assert manager.state is ObservationRunManagerState.SHUTTING_DOWN
        assert isinstance(unavailable, LaunchUnavailable)
        assert reconciler.reconcile_calls == 1
        assert reconciler.verify_calls == 1

    asyncio.run(run())


def test_shutdown_stays_pending_through_a_persistence_outage() -> None:
    async def run() -> None:
        lookup = _Lookup()
        release_retry = asyncio.Event()
        slept = asyncio.Event()

        async def sleep(_: float) -> None:
            slept.set()
            await release_retry.wait()

        manager = ObservationRunManager(
            orchestrator=_Orchestrator(lookup),
            active_run_lookup=lookup,
            reconciler=_Reconciler(failures=1),
            policy=ExecutionPolicy(max_parallel_lens_runs=4, lens_deadline_seconds=300),
            sleep=sleep,
        )
        shutdown = asyncio.create_task(manager.shutdown())
        await slept.wait()

        assert not shutdown.done()
        assert manager.state is ObservationRunManagerState.SHUTTING_DOWN
        assert isinstance(await manager.launch(_request()), LaunchUnavailable)
        release_retry.set()
        await shutdown

    asyncio.run(run())
