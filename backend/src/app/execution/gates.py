"""Post-JOIN guards for Observation execution."""

from __future__ import annotations

from uuid import UUID

from app.execution.contracts import (
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensOutcomePartition,
)
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import ObservationRunStatus, StructuredReason


async def enforce_usable_results_gate(
    session: object,
    runtime_repository: RuntimePersistenceRepository,
    *,
    observation_id: UUID,
    observation_run_id: UUID,
    partition: LensOutcomePartition,
) -> FailedObservationExecutionOutcome | None:
    """Fail a verified running parent when its complete JOIN has no usable results.

    The caller owns the short transaction containing this guarded parent transition.
    A non-empty usable partition passes without a parent write.
    """

    if not isinstance(partition, LensOutcomePartition):
        raise ValueError("usable-results gate requires a verified Lens outcome partition")
    if partition.usable:
        return None
    observation_run = await session.get(ObservationRunModel, observation_run_id)  # type: ignore[attr-defined]
    if (
        observation_run is None
        or observation_run.id != observation_run_id
        or observation_run.observation_id != observation_id
        or observation_run.status != ObservationRunStatus.RUNNING.value
    ):
        raise ValueError("usable-results gate parent is not the expected running ObservationRun")
    reason = ExecutionReason(
        code="no_usable_lens_results",
        component="usable_results_gate",
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
