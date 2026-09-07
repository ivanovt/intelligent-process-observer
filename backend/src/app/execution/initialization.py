"""Atomic construction of one complete Observation runtime graph."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from app.execution.contracts import (
    LensExecutionAssignment,
    ObservationDefinitionLoader,
    ObservationExecutionRequest,
    ObservationExecutionSnapshot,
    RejectedObservationExecutionOutcome,
    project_observation_execution,
)
from app.execution.ordering import canonical_lens_order
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensRunInput,
    LensType,
    ObservationRunInput,
    ObservationRunStatus,
)


class TransactionSessionFactory(Protocol):
    """Open a short transaction for initialization-owned persistence work."""

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return the context manager that commits or rolls back one transaction."""


@dataclass(frozen=True, slots=True)
class InitializedObservationExecution:
    """Committed runtime identities and frozen inputs for a future Lens fan-out."""

    snapshot: ObservationExecutionSnapshot
    observation_run_id: UUID
    assignments: tuple[LensExecutionAssignment, ...]


async def initialize_observation_execution(
    session_factory: TransactionSessionFactory,
    definition_loader: ObservationDefinitionLoader,
    runtime_repository: RuntimePersistenceRepository,
    request: object,
    policy: object,
) -> InitializedObservationExecution | RejectedObservationExecutionOutcome:
    """Load, validate, and commit one complete running runtime graph before analysis."""

    preflight = project_observation_execution(request, policy, object())
    if (
        isinstance(preflight, RejectedObservationExecutionOutcome)
        and preflight.reason.code == "invalid_execution_request"
    ):
        return preflight
    async with session_factory.begin() as session:
        assert isinstance(request, ObservationExecutionRequest)
        definition = await definition_loader.get(session, request.observation_id)
        preparation = project_observation_execution(request, policy, definition)
        if isinstance(preparation, RejectedObservationExecutionOutcome):
            return preparation
        return await _create_runtime_graph(session, runtime_repository, preparation)


async def _create_runtime_graph(
    session: object,
    runtime_repository: RuntimePersistenceRepository,
    snapshot: ObservationExecutionSnapshot,
) -> InitializedObservationExecution:
    """Persist the pending parent and exact pending child topology, then start the parent."""

    observation_run_id = uuid4()
    assignments = tuple(
        LensExecutionAssignment(
            observation_id=snapshot.observation_id,
            observation_run_id=observation_run_id,
            lens_run_id=uuid4(),
            analysis_window=snapshot.analysis_window,
            lens=lens,
        )
        for lens in canonical_lens_order(snapshot)
    )
    observation_run = await runtime_repository.create_observation_run(
        session,  # type: ignore[arg-type]
        ObservationRunInput(
            id=observation_run_id,
            observation_id=snapshot.observation_id,
            execution_context=_parent_execution_context(snapshot),
        ),
    )
    for assignment in assignments:
        await runtime_repository.create_lens_run(
            session,  # type: ignore[arg-type]
            observation_run,
            LensRunInput(
                id=assignment.lens_run_id,
                lens_id=assignment.lens.lens_id,
                lens_type=LensType(assignment.lens.lens_type),
                execution_context=_lens_execution_context(snapshot),
            ),
        )
    await runtime_repository.advance_observation_run(
        session,  # type: ignore[arg-type]
        observation_run,
        ObservationRunStatus.RUNNING,
    )
    return InitializedObservationExecution(
        snapshot=snapshot,
        observation_run_id=observation_run_id,
        assignments=assignments,
    )


def _parent_execution_context(snapshot: ObservationExecutionSnapshot) -> dict[str, object]:
    """Project only durable parent execution metadata, never Lens provider configuration."""

    return {
        "definition_schema_version": snapshot.schema_version,
        "analysis_window": _analysis_window_payload(snapshot),
    }


def _lens_execution_context(snapshot: ObservationExecutionSnapshot) -> dict[str, object]:
    """Project only shared durable Lens execution metadata."""

    return {"analysis_window": _analysis_window_payload(snapshot)}


def _analysis_window_payload(snapshot: ObservationExecutionSnapshot) -> dict[str, str]:
    """Serialize the frozen UTC window for runtime provenance without definition copying."""

    return {
        "from": snapshot.analysis_window.from_.isoformat(),
        "to": snapshot.analysis_window.to.isoformat(),
    }
