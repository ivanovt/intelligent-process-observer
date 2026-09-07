"""Caller-owned post-JOIN Relationship and Observation reasoning stages."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.execution.contracts import (
    CollectedLensOutcome,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensExecutionAssignment,
    LensOutcomePartition,
    ObservationExecutionSnapshot,
)
from app.execution.fanout import verify_and_partition_lens_outcomes
from app.execution.ordering import canonical_lens_order
from app.execution.projectors import (
    admissible_artifacts,
    build_observation_reasoning_input,
    relationship_definitions,
    validate_reasoning_success,
    validate_relationship_batch,
)
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    ObservationAnalysisResultInput,
    ObservationRunStatus,
    RelationshipEvaluationInput,
)
from app.reasoning.contracts import ReasoningFailure, ReasoningSuccess


class StageSessionFactory(Protocol):
    """Open a caller-owned short transaction for one persisted stage."""

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return a transaction context manager."""


class RelationshipEvaluatorPort(Protocol):
    """Evaluate ordered Relationship definitions without side effects."""

    def evaluate(self, relationships, results):
        """Return one evaluation per configured Relationship."""


async def evaluate_and_persist_relationships(
    *,
    session_factory: StageSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    evaluator: RelationshipEvaluatorPort,
    snapshot: ObservationExecutionSnapshot,
    outcomes: tuple[CollectedLensOutcome, ...],
    assignments,
) -> tuple[object, ...] | FailedObservationExecutionOutcome:
    """Evaluate once outside a transaction, then atomically persist the validated batch."""
    run_id = _run_id(outcomes)
    try:
        _validate_assignments(snapshot, assignments, outcomes, run_id)
        verify_and_partition_lens_outcomes(assignments, outcomes)
    except Exception:
        return FailedObservationExecutionOutcome(
            observation_run_id=run_id,
            reason=ExecutionReason("relationship_evaluation_failed", "relationship_evaluator"),
        )
    try:
        definitions = relationship_definitions(snapshot)
        evaluations = evaluator.evaluate(definitions, admissible_artifacts(outcomes, snapshot))
        validate_relationship_batch(
            snapshot,
            evaluations,
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
        )
        persistence_inputs = tuple(
            RelationshipEvaluationInput(
                relationship_id=evaluation.relationship_id,
                payload=evaluation.model_dump(mode="json"),
            )
            for evaluation in evaluations
        )
    except Exception:
        return FailedObservationExecutionOutcome(
            observation_run_id=run_id,
            reason=ExecutionReason("relationship_evaluation_failed", "relationship_evaluator"),
        )
    async with session_factory.begin() as session:
        run = await _current_run(session, run_id, snapshot.observation_id)
        for persistence_input in persistence_inputs:
            await runtime_repository.persist_relationship_evaluation(
                session,
                run,
                persistence_input,
            )
    return tuple(evaluations)


def _validate_assignments(snapshot, assignments, outcomes, run_id) -> None:
    """Require the initialized assignment topology to equal frozen Lens topology."""
    expected = tuple((lens.lens_type, lens.lens_id) for lens in canonical_lens_order(snapshot))
    if len(assignments) != len(expected):
        raise ValueError("initialized assignment topology is invalid")
    actual: list[tuple[str, str]] = []
    lens_run_ids = set()
    for assignment in assignments:
        if not isinstance(assignment, LensExecutionAssignment):
            raise ValueError("initialized assignment topology is invalid")
        if assignment.observation_id != snapshot.observation_id:
            raise ValueError("initialized assignment observation identity is invalid")
        if assignment.observation_run_id != run_id:
            raise ValueError("initialized assignment run identity is invalid")
        actual.append((assignment.lens.lens_type, assignment.lens.lens_id))
        lens_run_ids.add(assignment.lens_run_id)
    if (
        tuple(actual) != expected
        or len(set(actual)) != len(actual)
        or len(lens_run_ids) != len(actual)
    ):
        raise ValueError("initialized assignment topology is invalid")


async def invoke_and_persist_reasoning(
    *,
    session_factory: StageSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    executor,
    snapshot: ObservationExecutionSnapshot,
    partition: LensOutcomePartition,
    evaluations: tuple[object, ...],
) -> ReasoningSuccess | ReasoningFailure:
    """Invoke reasoning once outside a transaction and atomically persist valid success."""
    try:
        run_id = _run_id((*partition.usable, *partition.unavailable))
        value = build_observation_reasoning_input(snapshot, partition, evaluations)
    except (AttributeError, TypeError, ValueError):
        return ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
    outcome = await executor.execute(value)
    if isinstance(outcome, ReasoningFailure):
        return outcome
    if not isinstance(outcome, ReasoningSuccess):
        return ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
    try:
        result = validate_reasoning_success(
            outcome.result,
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
        )
    except (TypeError, ValueError):
        return ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
    async with session_factory.begin() as session:
        run = await _current_run(session, run_id, snapshot.observation_id)
        await runtime_repository.persist_observation_analysis_result(
            session,
            run,
            ObservationAnalysisResultInput(
                schema_version=result.schema_version,
                identity=result.identity,
                payload=result.model_dump(mode="json"),
            ),
        )
    return ReasoningSuccess(result=result)


async def _current_run(session, run_id, observation_id):
    run = await session.get(ObservationRunModel, run_id)
    if (
        run is None
        or run.id != run_id
        or run.observation_id != observation_id
        or run.status != ObservationRunStatus.RUNNING.value
    ):
        raise ValueError("stage parent does not match current ObservationRun")
    return run


def _run_id(outcomes):
    if not outcomes:
        raise ValueError("post-JOIN stage requires a non-empty outcome set")
    run_id = outcomes[0].assignment.observation_run_id
    if any(item.assignment.observation_run_id != run_id for item in outcomes):
        raise ValueError("outcomes span multiple ObservationRuns")
    return run_id
