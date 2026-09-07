"""Caller-owned post-JOIN Relationship and Observation reasoning stages."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from sqlalchemy import select

from app.execution.contracts import (
    CollectedLensOutcome,
    CompletedObservationExecutionOutcome,
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
    report_generation_request,
    validate_reasoning_success,
    validate_relationship_batch,
)
from app.infrastructure.persistence.models import (
    ObservationAnalysisResultModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    ObservationAnalysisResultInput,
    ObservationReportInput,
    ObservationRunStatus,
    RelationshipEvaluationInput,
    StructuredReason,
)
from app.reasoning.contracts import ObservationAnalysisResult, ReasoningFailure, ReasoningSuccess
from app.reporting.contracts import ObservationReport, ReportFailure, ReportSuccess


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
    observation_run_id,
) -> tuple[object, ...] | FailedObservationExecutionOutcome:
    """Evaluate once outside a transaction, then atomically persist the validated batch."""
    run_id = observation_run_id
    try:
        _validate_assignments(snapshot, assignments, outcomes, run_id)
        verify_and_partition_lens_outcomes(assignments, outcomes)
    except Exception:
        return await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason("relationship_evaluation_failed", "relationship_evaluator"),
        )
    try:
        definitions = relationship_definitions(snapshot)
        evaluations = evaluator.evaluate(definitions, admissible_artifacts(outcomes, snapshot))
        validated_evaluations = validate_relationship_batch(
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
            for evaluation in validated_evaluations
        )
    except Exception:
        return await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
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
    return validated_evaluations


def _validate_assignments(snapshot, assignments, outcomes, run_id) -> None:
    """Require the initialized assignment topology to equal frozen Lens topology."""
    expected_lenses = canonical_lens_order(snapshot)
    expected = tuple((lens.lens_type, lens.lens_id) for lens in expected_lenses)
    if len(assignments) != len(expected):
        raise ValueError("initialized assignment topology is invalid")
    actual: list[tuple[str, str]] = []
    lens_run_ids = set()
    for assignment, expected_lens in zip(assignments, expected_lenses, strict=True):
        if not isinstance(assignment, LensExecutionAssignment):
            raise ValueError("initialized assignment topology is invalid")
        if assignment.observation_id != snapshot.observation_id:
            raise ValueError("initialized assignment observation identity is invalid")
        if assignment.observation_run_id != run_id:
            raise ValueError("initialized assignment run identity is invalid")
        if assignment.analysis_window != snapshot.analysis_window:
            raise ValueError("initialized assignment analysis window is invalid")
        if assignment.lens != expected_lens:
            raise ValueError("initialized assignment Lens snapshot is invalid")
        actual.append((assignment.lens.lens_type, assignment.lens.lens_id))
        lens_run_ids.add(assignment.lens_run_id)
    if (
        tuple(actual) != expected
        or len(set(actual)) != len(actual)
        or len(lens_run_ids) != len(actual)
    ):
        raise ValueError("initialized assignment topology is invalid")
    if len(outcomes) != len(assignments):
        raise ValueError("initialized outcome topology is invalid")
    for outcome, assignment in zip(outcomes, assignments, strict=True):
        if not isinstance(outcome, CollectedLensOutcome) or outcome.assignment != assignment:
            raise ValueError("initialized outcome topology is invalid")


def _validate_partition(snapshot, partition, run_id) -> None:
    """Require a non-contradictory current-run reasoning partition."""
    all_outcomes = (*partition.usable, *partition.unavailable)
    if not all_outcomes:
        raise ValueError("reasoning partition cannot be empty")
    assignments = tuple(item.assignment for item in all_outcomes)
    _validate_assignments(snapshot, assignments, all_outcomes, run_id)


async def invoke_and_persist_reasoning(
    *,
    session_factory: StageSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    executor,
    snapshot: ObservationExecutionSnapshot,
    partition: LensOutcomePartition,
    evaluations: tuple[object, ...],
    observation_run_id,
) -> ReasoningSuccess | ReasoningFailure:
    """Invoke reasoning once outside a transaction and atomically persist valid success."""
    run_id = observation_run_id
    try:
        validated_evaluations = validate_relationship_batch(
            snapshot,
            evaluations,
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
        )
        _validate_partition(snapshot, partition, run_id)
        value = build_observation_reasoning_input(
            snapshot, partition, validated_evaluations, observation_run_id=run_id
        )
    except (AttributeError, TypeError, ValueError):
        failure = ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
        await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason(failure.code, failure.component),
        )
        return failure
    outcome = await executor.execute(value)
    if isinstance(outcome, ReasoningFailure):
        await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason(outcome.code, outcome.component),
        )
        return outcome
    if not isinstance(outcome, ReasoningSuccess):
        failure = ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
        await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason(failure.code, failure.component),
        )
        return failure
    try:
        result = validate_reasoning_success(
            outcome.result,
            observation_id=snapshot.observation_id,
            observation_run_id=run_id,
        )
    except (AttributeError, TypeError, ValueError):
        failure = ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
        await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason(failure.code, failure.component),
        )
        return failure
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


async def generate_and_persist_report(
    *,
    session_factory: StageSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    executor,
    snapshot: ObservationExecutionSnapshot,
    analysis_result,
    observation_run_id,
) -> CompletedObservationExecutionOutcome | FailedObservationExecutionOutcome:
    """Generate one report, then atomically persist it with parent completion."""
    run_id = observation_run_id
    try:
        if (
            not isinstance(analysis_result, ObservationAnalysisResult)
            or analysis_result.identity.observation_id != snapshot.observation_id
            or analysis_result.identity.observation_run_id != run_id
        ):
            raise ValueError("analysis result observation identity does not match snapshot")
        request = report_generation_request(snapshot, analysis_result)
    except (AttributeError, TypeError, ValueError):
        return await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason("report_result_invalid", "report_builder"),
        )
    outcome = await executor.execute(request)
    if isinstance(outcome, ReportFailure):
        return await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason(outcome.code, outcome.component),
        )
    if not isinstance(outcome, ReportSuccess):
        return await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason("report_result_invalid", "report_builder"),
        )
    report = outcome.report
    if (
        not isinstance(report, ObservationReport)
        or report.observation_id != snapshot.observation_id
        or report.observation_run_id != run_id
        or report.format != "markdown"
        or not report.content.strip()
    ):
        return await fail_observation_execution(
            session_factory=session_factory,
            runtime_repository=runtime_repository,
            observation_run_id=run_id,
            observation_id=snapshot.observation_id,
            reason=ExecutionReason("report_result_invalid", "report_builder"),
        )
    async with session_factory.begin() as session:
        run = await _current_run(session, run_id, snapshot.observation_id)
        analysis = await session.scalar(
            select(ObservationAnalysisResultModel).where(
                ObservationAnalysisResultModel.observation_run_id == run_id
            )
        )
        if analysis is None:
            raise ValueError("committed ObservationAnalysisResult is missing")
        await runtime_repository.persist_observation_report(
            session,
            run,
            analysis,
            ObservationReportInput(
                generated_at=report.generated_at, format="markdown", content=report.content
            ),
        )
        await runtime_repository.advance_observation_run(
            session, run, ObservationRunStatus.COMPLETED
        )
    return CompletedObservationExecutionOutcome(observation_run_id=run_id)


async def fail_observation_execution(
    *,
    session_factory: StageSessionFactory,
    runtime_repository: RuntimePersistenceRepository,
    observation_run_id,
    observation_id,
    reason: ExecutionReason,
) -> FailedObservationExecutionOutcome:
    """Guardedly persist a controlled parent failure after committed artifacts."""
    async with session_factory.begin() as session:
        run = await _current_run(session, observation_run_id, observation_id)
        await runtime_repository.advance_observation_run(
            session,
            run,
            ObservationRunStatus.FAILED,
            reason=StructuredReason(code=reason.code, component=reason.component),
        )
    return FailedObservationExecutionOutcome(observation_run_id=observation_run_id, reason=reason)


invoke_and_persist_report = generate_and_persist_report


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
