"""Bounded Lens fan-out and strict normal JOIN helpers."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Protocol, cast

from app.execution.contracts import (
    AlertLensSnapshot,
    CollectedLensOutcome,
    ExecutionPolicy,
    LensExecutionAdapter,
    LensExecutionAssignment,
    LensOutcomePartition,
    MetricLensSnapshot,
)
from app.infrastructure.persistence.models import LensRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import LensRunStatus


class AdmissionSessionFactory(Protocol):
    """Open isolated short transactions for durable Lens admission."""

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return the context manager for one admission transaction."""


async def fan_out_lens_runs(
    *,
    session_factory: AdmissionSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    adapter: LensExecutionAdapter,
    assignments: tuple[LensExecutionAssignment, ...],
    policy: ExecutionPolicy,
) -> tuple[CollectedLensOutcome, ...]:
    """Durably admit and execute assignments with fixed work-conserving workers."""

    if not assignments:
        return ()
    results: list[CollectedLensOutcome | None] = [None] * len(assignments)
    next_index = 0
    stopping = False
    workers: list[asyncio.Task[None]] = []

    def stop_workers() -> None:
        """Prevent more claims and cancel every still-active owned worker."""

        nonlocal stopping
        stopping = True
        current_worker = asyncio.current_task()
        for worker_task in workers:
            if worker_task is not current_worker and not worker_task.done():
                worker_task.cancel()

    async def worker() -> None:
        nonlocal next_index
        try:
            while not stopping and next_index < len(assignments):
                index = next_index
                next_index += 1
                assignment = assignments[index]
                await _admit_lens_run(session_factory, runtime_repository, assignment)
                if stopping:
                    return
                results[index] = await adapter.execute(assignment, policy)
        except BaseException:
            stop_workers()
            raise

    workers.extend(
        asyncio.create_task(worker())
        for _ in range(min(policy.max_parallel_lens_runs, len(assignments)))
    )
    try:
        await asyncio.gather(*workers)
    except BaseException:
        stop_workers()
        await asyncio.gather(*workers, return_exceptions=True)
        raise
    if any(result is None for result in results):
        raise RuntimeError("fan-out completed without every collected Lens outcome")
    return tuple(cast(CollectedLensOutcome, result) for result in results)


async def _admit_lens_run(
    session_factory: AdmissionSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    assignment: LensExecutionAssignment,
) -> None:
    """Commit the assigned pending LensRun transition before adapter invocation."""

    async with session_factory.begin() as session:
        lens_run = await session.get(LensRunModel, assignment.lens_run_id)
        if (
            lens_run is None
            or lens_run.observation_run_id != assignment.observation_run_id
            or lens_run.lens_id != assignment.lens.lens_id
            or lens_run.lens_type != assignment.lens.lens_type
            or lens_run.status != LensRunStatus.PENDING.value
        ):
            raise ValueError("assigned LensRun is not the expected pending runtime record")
        await runtime_repository.advance_lens_run(
            cast(object, session), lens_run, LensRunStatus.RUNNING
        )


def verify_and_partition_lens_outcomes(
    assignments: tuple[LensExecutionAssignment, ...],
    outcomes: tuple[CollectedLensOutcome, ...],
) -> LensOutcomePartition:
    """Strictly verify one normal JOIN and classify its canonical Lens outcomes."""

    if len(outcomes) != len(assignments):
        raise ValueError("collected Lens outcome cardinality differs from initialized topology")
    usable: list[CollectedLensOutcome] = []
    unavailable: list[CollectedLensOutcome] = []
    seen: set[object] = set()
    for assignment, outcome in zip(assignments, outcomes, strict=True):
        if not isinstance(outcome, CollectedLensOutcome) or outcome.assignment != assignment:
            raise ValueError("collected Lens outcome differs from initialized topology")
        if outcome.assignment.lens_run_id in seen:
            raise ValueError("collected Lens outcomes contain a duplicate LensRun")
        seen.add(outcome.assignment.lens_run_id)
        if isinstance(assignment.lens, MetricLensSnapshot):
            if outcome.status == "failed":
                unavailable.append(outcome)
                continue
            assert outcome.artifact is not None
            quality = outcome.artifact.to_persistence_envelope().payload.get("data_quality")
            if quality in {"good", "degraded"}:
                usable.append(outcome)
            elif outcome.status == "completed" and quality == "insufficient":
                unavailable.append(outcome)
            else:
                raise ValueError("Metric JOIN outcome has an invalid data-quality classification")
        elif isinstance(assignment.lens, AlertLensSnapshot):
            if outcome.status in {"completed", "partial"}:
                usable.append(outcome)
            elif outcome.status == "failed":
                unavailable.append(outcome)
            else:
                raise ValueError("Alert JOIN outcome has an invalid terminal status")
        else:
            raise ValueError("initialized topology contains an unsupported Lens type")
    return LensOutcomePartition(usable=tuple(usable), unavailable=tuple(unavailable))
