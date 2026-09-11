"""Single-process ownership for detached Observation execution tasks."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter
from app.execution.contracts import (
    ExecutionPolicy,
    ObservationExecutionOutcome,
    ObservationExecutionRequest,
    ObservationRunAcceptanceSummary,
    RejectedObservationExecutionOutcome,
)
from app.execution.initialization import InitializedObservationExecution

_ACTIVE_RUN_INDEX_NAME = "uq_observation_runs_one_active_per_observation"


class ObservationRunManagerState(StrEnum):
    """Lifecycle states controlling whether this process may admit launches."""

    READY = "ready"
    RECOVERY_REQUIRED = "recovery_required"
    SHUTTING_DOWN = "shutting_down"


@dataclass(frozen=True, slots=True)
class LaunchAccepted:
    """One detached continuation and its immutable initialization snapshot."""

    summary: ObservationRunAcceptanceSummary


@dataclass(frozen=True, slots=True)
class LaunchConflict:
    """A stable identity for an already active run of the selected Observation."""

    observation_run_id: UUID


@dataclass(frozen=True, slots=True)
class LaunchUnavailable:
    """A safe refusal while durable execution state is being recovered or stopped."""

    code: str = "execution_recovery_pending"


type ObservationRunLaunchOutcome = (
    LaunchAccepted | LaunchConflict | LaunchUnavailable | RejectedObservationExecutionOutcome
)


class ManagedExecutionOrchestrator(Protocol):
    """Expose the durable initialization and detached continuation operations."""

    async def initialize(
        self, request: ObservationExecutionRequest, policy: ExecutionPolicy
    ) -> InitializedObservationExecution | RejectedObservationExecutionOutcome:
        """Create a durable running graph or return a controlled preparation rejection."""

    async def continue_execution(
        self, initialized: InitializedObservationExecution, policy: ExecutionPolicy
    ) -> ObservationExecutionOutcome:
        """Perform the remaining pipeline for one already initialized graph."""


class ActiveRunLookup(Protocol):
    """Look up the durable active run used by serialized launch admission."""

    async def get_active_observation_run_id(self, observation_id: UUID) -> UUID | None:
        """Return the active run identity, if one exists for the Observation."""


class ActiveRunReconciler(Protocol):
    """Durably cancel interrupted work and verify that no active records remain."""

    async def reconcile_active_observation_runs(self) -> None:
        """Cancel every durable active runtime aggregate in fresh transaction scope."""

    async def has_active_observation_runs(self) -> bool:
        """Return whether durable pending or running ObservationRuns still exist."""


@dataclass(frozen=True, slots=True)
class _Admission:
    identifier: UUID
    observation_id: UUID
    generation: int


@dataclass(frozen=True, slots=True)
class _ManagedTask:
    task: asyncio.Task[object]
    generation: int


@dataclass(slots=True)
class _ObservationLock:
    lock: asyncio.Lock
    users: int = 0


class ObservationRunManager:
    """Manage single-process launch admission, detached work, recovery, and shutdown."""

    def __init__(
        self,
        *,
        orchestrator: ManagedExecutionOrchestrator,
        active_run_lookup: ActiveRunLookup,
        reconciler: ActiveRunReconciler,
        policy: ExecutionPolicy,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reconciliation_retry_seconds: float = 5,
        emitter: OperationalEventEmitter | None = None,
    ) -> None:
        if reconciliation_retry_seconds <= 0:
            raise ValueError("reconciliation retry interval must be positive")
        self._orchestrator = orchestrator
        self._active_run_lookup = active_run_lookup
        self._reconciler = reconciler
        self._policy = policy
        self._sleep = sleep
        self._retry_seconds = reconciliation_retry_seconds
        self._emitter = emitter or OperationalEventEmitter()
        self._state_lock = asyncio.Lock()
        self._state = ObservationRunManagerState.READY
        self._generation = 0
        self._admissions: dict[UUID, _Admission] = {}
        self._initializers: dict[UUID, _ManagedTask] = {}
        self._continuations: dict[UUID, _ManagedTask] = {}
        self._observation_locks: dict[UUID, _ObservationLock] = {}
        self._recovery_task: asyncio.Task[None] | None = None

    @property
    def state(self) -> ObservationRunManagerState:
        """Return the current admission state without changing it."""

        return self._state

    @property
    def recovery_generation(self) -> int:
        """Return the monotonic generation used to fence older admissions."""

        return self._generation

    async def launch(self, request: ObservationExecutionRequest) -> ObservationRunLaunchOutcome:
        """Durably initialize one run and atomically hand it to one continuation."""

        observation_lock = await self._acquire_observation_lock(request.observation_id)
        try:
            async with observation_lock:
                async with self._state_lock:
                    if self._state is not ObservationRunManagerState.READY:
                        return LaunchUnavailable()
                    admission = _Admission(uuid4(), request.observation_id, self._generation)
                    task = asyncio.create_task(self._run_initializer(admission, request))
                    self._admissions[admission.identifier] = admission
                    self._initializers[admission.identifier] = _ManagedTask(
                        task, admission.generation
                    )
                return await task
        finally:
            await self._release_observation_lock(request.observation_id)

    async def request_recovery(self) -> None:
        """Fence admission and wait for verified cancellation reconciliation."""

        task = await self._ensure_recovery(shutting_down=False)
        if task is not None:
            await asyncio.shield(task)

    async def shutdown(self) -> None:
        """Stop admission and return only after durable active-state reconciliation verifies."""

        task = await self._ensure_recovery(shutting_down=True)
        if task is not None:
            await asyncio.shield(task)

    async def _run_initializer(
        self, admission: _Admission, request: ObservationExecutionRequest
    ) -> ObservationRunLaunchOutcome:
        try:
            active_run_id = await self._active_run_lookup.get_active_observation_run_id(
                admission.observation_id
            )
            if active_run_id is not None:
                return LaunchConflict(active_run_id)
            initialized = await self._orchestrator.initialize(request, self._policy)
            if isinstance(initialized, RejectedObservationExecutionOutcome):
                return initialized
            return await self._register_continuation(admission, initialized)
        except asyncio.CancelledError:
            if self._state is not ObservationRunManagerState.SHUTTING_DOWN:
                self._schedule_recovery()
            raise
        except IntegrityError as error:
            if _is_active_run_index_conflict(error):
                return await self._resolve_defensive_index_loser(admission.observation_id)
            self._emit_failure(
                "execution_initialization_failed",
                "persistence_failure",
                error,
                observation_run_id=None,
                stage="initialization",
            )
            self._schedule_recovery()
            return LaunchUnavailable()
        except BaseException as error:
            self._emit_failure(
                "execution_initialization_failed",
                "initialization_failed",
                error,
                observation_run_id=None,
                stage="initialization",
            )
            self._schedule_recovery()
            return LaunchUnavailable()
        finally:
            async with self._state_lock:
                self._initializers.pop(admission.identifier, None)
                self._admissions.pop(admission.identifier, None)

    async def _resolve_defensive_index_loser(
        self, observation_id: UUID
    ) -> LaunchConflict | LaunchUnavailable:
        """Map one fully rolled-back active-index loser without retrying initialization."""

        try:
            active_run_id = await self._active_run_lookup.get_active_observation_run_id(
                observation_id
            )
        except BaseException as error:
            self._emit_failure(
                "launch_conflict_resolution_failed",
                "persistence_failure",
                error,
                observation_run_id=None,
                stage="launch_admission",
            )
            self._schedule_recovery()
            return LaunchUnavailable()
        if active_run_id is not None:
            return LaunchConflict(active_run_id)
        return LaunchUnavailable(code="launch_admission_uncertain")

    async def _register_continuation(
        self, admission: _Admission, initialized: InitializedObservationExecution
    ) -> LaunchAccepted | LaunchUnavailable:
        async with self._state_lock:
            if (
                self._state is not ObservationRunManagerState.READY
                or admission.generation != self._generation
            ):
                return LaunchUnavailable()
            continuation = asyncio.create_task(
                self._orchestrator.continue_execution(initialized, self._policy)
            )
            self._continuations[initialized.observation_run_id] = _ManagedTask(
                continuation, admission.generation
            )
            continuation.add_done_callback(
                lambda completed: asyncio.create_task(
                    self._observe_continuation(initialized.observation_run_id, completed)
                )
            )
            return LaunchAccepted(initialized.acceptance_summary)

    async def _observe_continuation(
        self, observation_run_id: UUID, task: asyncio.Task[object]
    ) -> None:
        requires_recovery = False
        try:
            task.result()
        except asyncio.CancelledError:
            requires_recovery = self._state is ObservationRunManagerState.READY
        except BaseException as error:
            self._emit_failure(
                "managed_execution_failed",
                "execution_failed",
                error,
                observation_run_id=observation_run_id,
                stage="managed_continuation",
            )
            requires_recovery = True
        finally:
            async with self._state_lock:
                self._continuations.pop(observation_run_id, None)
        if requires_recovery:
            self._schedule_recovery()

    def _schedule_recovery(self) -> None:
        """Start recovery asynchronously so a failing owned task can settle first."""

        asyncio.create_task(self._ensure_recovery(shutting_down=False))

    async def _ensure_recovery(self, *, shutting_down: bool) -> asyncio.Task[None] | None:
        async with self._state_lock:
            if self._state is ObservationRunManagerState.SHUTTING_DOWN and not shutting_down:
                return self._recovery_task
            if shutting_down:
                if self._state is not ObservationRunManagerState.SHUTTING_DOWN:
                    self._state = ObservationRunManagerState.SHUTTING_DOWN
                    self._generation += 1
            elif self._state is ObservationRunManagerState.READY:
                self._state = ObservationRunManagerState.RECOVERY_REQUIRED
                self._generation += 1
            if self._recovery_task is None or self._recovery_task.done():
                self._recovery_task = asyncio.create_task(self._recover(self._generation))
            return self._recovery_task

    async def _recover(self, fenced_generation: int) -> None:
        await self._quiesce_older_generation(fenced_generation)
        while True:
            try:
                await self._reconciler.reconcile_active_observation_runs()
                if await self._reconciler.has_active_observation_runs():
                    raise RuntimeError("active ObservationRuns remain after reconciliation")
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                self._emit_failure(
                    "execution_recovery_failed",
                    "persistence_failure",
                    error,
                    observation_run_id=None,
                    stage="recovery",
                )
                await self._sleep(self._retry_seconds)
                continue
            async with self._state_lock:
                if (
                    self._state is ObservationRunManagerState.RECOVERY_REQUIRED
                    and self._generation == fenced_generation
                ):
                    self._state = ObservationRunManagerState.READY
                return

    async def _quiesce_older_generation(self, fenced_generation: int) -> None:
        current = asyncio.current_task()
        async with self._state_lock:
            tasks = [
                record.task
                for record in (*self._initializers.values(), *self._continuations.values())
                if record.generation < fenced_generation and record.task is not current
            ]
            for task in tasks:
                if not task.done():
                    task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _acquire_observation_lock(self, observation_id: UUID) -> asyncio.Lock:
        async with self._state_lock:
            managed = self._observation_locks.get(observation_id)
            if managed is None:
                managed = _ObservationLock(asyncio.Lock())
                self._observation_locks[observation_id] = managed
            managed.users += 1
            return managed.lock

    async def _release_observation_lock(self, observation_id: UUID) -> None:
        async with self._state_lock:
            managed = self._observation_locks[observation_id]
            managed.users -= 1
            if managed.users == 0 and not managed.lock.locked():
                self._observation_locks.pop(observation_id, None)

    def _emit_failure(
        self,
        event: str,
        category: str,
        error: BaseException,
        *,
        observation_run_id: UUID | None,
        stage: str,
    ) -> None:
        """Emit a safe lifecycle failure event without affecting manager recovery."""
        self._emitter.emit(
            DiagnosticEvent(
                event=event,
                category=category,
                observation_run_id=observation_run_id,
                component="observation_run_manager",
                stage=stage,
            ),
            error=error,
        )


def _is_active_run_index_conflict(error: IntegrityError) -> bool:
    """Return whether a database integrity error came from the named active-run index."""

    diagnostic = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diagnostic, "constraint_name", None) == _ACTIVE_RUN_INDEX_NAME
