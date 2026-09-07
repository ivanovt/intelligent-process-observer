"""Post-JOIN guards for Observation execution."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from app.execution.contracts import (
    CollectedLensOutcome,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensExecutionAssignment,
    LensOutcomePartition,
)
from app.execution.fanout import verify_and_partition_lens_outcomes
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import ObservationRunStatus, StructuredReason


class UsableResultsGateSessionFactory(Protocol):
    """Open the short transaction used only for a zero-usable parent transition."""

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return the context manager for one parent terminalization transaction."""


async def enforce_usable_results_gate(
    *,
    session_factory: UsableResultsGateSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    assignments: tuple[LensExecutionAssignment, ...],
    outcomes: tuple[CollectedLensOutcome, ...],
) -> LensOutcomePartition | FailedObservationExecutionOutcome:
    """Verify JOIN outcomes, then stop only a zero-usable initialized ObservationRun."""

    observation_id, observation_run_id = _initialized_parent_identity(assignments)
    partition = verify_and_partition_lens_outcomes(assignments, outcomes)
    if partition.usable:
        return partition
    reason = ExecutionReason(
        code="no_usable_lens_results",
        component="usable_results_gate",
    )
    async with session_factory.begin() as session:
        observation_run = await session.get(ObservationRunModel, observation_run_id)  # type: ignore[attr-defined]
        if (
            observation_run is None
            or observation_run.id != observation_run_id
            or observation_run.observation_id != observation_id
            or observation_run.status != ObservationRunStatus.RUNNING.value
        ):
            raise ValueError(
                "usable-results gate parent is not the expected running ObservationRun"
            )
        await runtime_repository.advance_observation_run(
            session,  # type: ignore[arg-type]
            observation_run,
            ObservationRunStatus.FAILED,
            reason=StructuredReason(code=reason.code, component=reason.component),
        )
    return FailedObservationExecutionOutcome(
        observation_run_id=observation_run_id,
        reason=reason,
    )


def _initialized_parent_identity(
    assignments: tuple[LensExecutionAssignment, ...],
) -> tuple[UUID, UUID]:
    """Require one non-empty initialized topology for exactly one parent runtime graph."""

    if not assignments:
        raise ValueError("usable-results gate requires a non-empty initialized topology")
    first = assignments[0]
    if not all(
        assignment.observation_id == first.observation_id
        and assignment.observation_run_id == first.observation_run_id
        for assignment in assignments
    ):
        raise ValueError("usable-results gate topology spans multiple ObservationRuns")
    return first.observation_id, first.observation_run_id
