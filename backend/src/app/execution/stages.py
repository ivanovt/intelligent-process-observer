"""Caller-owned post-JOIN Relationship and Observation reasoning stages."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.execution.contracts import (
    CollectedLensOutcome,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensOutcomePartition,
    ObservationExecutionSnapshot,
)
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
        definitions = relationship_definitions(snapshot)
        evaluations = evaluator.evaluate(definitions, admissible_artifacts(outcomes))
        validate_relationship_batch(
            snapshot,
            evaluations,
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
        )
        async with session_factory.begin() as session:
            run = await _current_run(session, run_id, snapshot.observation_id)
            for evaluation in evaluations:
                payload = evaluation.model_dump(mode="json")
                await runtime_repository.persist_relationship_evaluation(
                    session,
                    run,
                    RelationshipEvaluationInput(
                        relationship_id=evaluation.relationship_id,
                        payload=payload,
                    ),
                )
        return tuple(evaluations)
    except Exception:
        return FailedObservationExecutionOutcome(
            observation_run_id=run_id,
            reason=ExecutionReason("relationship_evaluation_failed", "relationship_evaluator"),
        )


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
    run_id = _run_id((*partition.usable, *partition.unavailable))
    try:
        value = build_observation_reasoning_input(snapshot, partition, evaluations)
    except Exception:
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
    except Exception:
        return ReasoningFailure(code="reasoning_result_invalid", component="result_builder")


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
