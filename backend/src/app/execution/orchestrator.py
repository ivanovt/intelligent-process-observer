"""Top-level deterministic Observation execution composition."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.execution.contracts import (
    AlertLensSnapshot,
    CompletedObservationExecutionOutcome,
    ExecutionPolicy,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensExecutionAdapter,
    MetricLensSnapshot,
    ObservationDefinitionLoader,
    ObservationExecutionOutcome,
    ObservationExecutionRequest,
    RejectedObservationExecutionOutcome,
)
from app.execution.fanout import fan_out_lens_runs
from app.execution.gates import enforce_usable_results_gate
from app.execution.initialization import (
    InitializedObservationExecution,
    initialize_observation_execution,
)
from app.execution.stages import (
    evaluate_and_persist_relationships,
    generate_and_persist_report,
    invoke_and_persist_reasoning,
)
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensRunStatus,
    ObservationRunStatus,
    StructuredReason,
)
from app.reasoning.contracts import ReasoningFailure, ReasoningSuccess
from app.reporting.contracts import ReportFailure


class ExecutionSessionFactory(Protocol):
    """Open short caller-owned transactions for execution lifecycle writes."""

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return a transaction context manager."""


class ObservationExecutionOrchestrator:
    """Execute one fresh Observation runtime graph through its fixed stage sequence."""

    def __init__(
        self,
        *,
        session_factory: ExecutionSessionFactory,
        definition_loader: ObservationDefinitionLoader,
        runtime_repository: RuntimePersistenceRepository,
        metric_adapter: LensExecutionAdapter,
        alert_adapter: LensExecutionAdapter,
        relationship_evaluator,
        reasoning_executor,
        report_executor,
    ) -> None:
        self._session_factory = session_factory
        self._definition_loader = definition_loader
        self._runtime_repository = runtime_repository
        self._lens_adapter = _TypeRoutedLensAdapter(metric_adapter, alert_adapter)
        self._relationship_evaluator = relationship_evaluator
        self._reasoning_executor = reasoning_executor
        self._report_executor = report_executor
        self._persistence_aware_factory = _PersistenceAwareSessionFactory(session_factory)

    async def execute(
        self, request: ObservationExecutionRequest, policy: ExecutionPolicy
    ) -> ObservationExecutionOutcome:
        """Prepare and execute one fresh run, propagating cancellation and persistence errors."""

        initialized = await initialize_observation_execution(
            self._persistence_aware_factory,
            self._definition_loader,
            self._runtime_repository,
            request,
            policy,
        )
        if isinstance(initialized, RejectedObservationExecutionOutcome):
            return initialized

        stage = "fanout"
        try:
            outcomes = await fan_out_lens_runs(
                session_factory=self._persistence_aware_factory,
                runtime_repository=self._runtime_repository,
                adapter=self._lens_adapter,
                assignments=initialized.assignments,
                policy=policy,
            )

            stage = "usable_results_gate"
            partition = await enforce_usable_results_gate(
                session_factory=self._persistence_aware_factory,
                runtime_repository=self._runtime_repository,
                assignments=initialized.assignments,
                outcomes=outcomes,
            )
            if isinstance(partition, FailedObservationExecutionOutcome):
                return partition

            stage = "relationship_evaluator"
            relationships = await evaluate_and_persist_relationships(
                session_factory=self._persistence_aware_factory,
                runtime_repository=self._runtime_repository,
                evaluator=self._relationship_evaluator,
                snapshot=initialized.snapshot,
                outcomes=outcomes,
                assignments=initialized.assignments,
                observation_run_id=initialized.observation_run_id,
            )
            if isinstance(relationships, FailedObservationExecutionOutcome):
                return relationships

            stage = "observation_reasoning"
            reasoning = await invoke_and_persist_reasoning(
                session_factory=self._persistence_aware_factory,
                runtime_repository=self._runtime_repository,
                executor=self._reasoning_executor,
                snapshot=initialized.snapshot,
                partition=partition,
                evaluations=relationships,
                observation_run_id=initialized.observation_run_id,
            )
            if isinstance(reasoning, ReasoningFailure):
                return FailedObservationExecutionOutcome(
                    observation_run_id=initialized.observation_run_id,
                    reason=ExecutionReason(reasoning.code, reasoning.component),
                )
            if not isinstance(reasoning, ReasoningSuccess):
                return FailedObservationExecutionOutcome(
                    observation_run_id=initialized.observation_run_id,
                    reason=ExecutionReason("reasoning_result_invalid", "result_builder"),
                )

            stage = "report_generation"
            report = await generate_and_persist_report(
                session_factory=self._persistence_aware_factory,
                runtime_repository=self._runtime_repository,
                executor=self._report_executor,
                snapshot=initialized.snapshot,
                analysis_result=reasoning.result,
                observation_run_id=initialized.observation_run_id,
            )
            if isinstance(report, FailedObservationExecutionOutcome):
                return report
            if isinstance(report, CompletedObservationExecutionOutcome):
                return report
            if isinstance(report, ReportFailure):
                return FailedObservationExecutionOutcome(
                    observation_run_id=initialized.observation_run_id,
                    reason=ExecutionReason(report.code, report.component),
                )
            return FailedObservationExecutionOutcome(
                observation_run_id=initialized.observation_run_id,
                reason=ExecutionReason("report_result_invalid", "report_builder"),
            )
        except asyncio.CancelledError as cancellation:
            await self._cancel_after_initialization(initialized, cancellation)
            raise
        except Exception as error:
            if _is_persistence_error(error):
                raise
            await self._abort_after_failure(initialized, stage)
            return FailedObservationExecutionOutcome(
                observation_run_id=initialized.observation_run_id,
                reason=ExecutionReason("execution_failed", stage),
            )

    async def _abort_after_failure(
        self, initialized: InitializedObservationExecution, stage: str
    ) -> None:
        """Persist safe failure reasons for unfinished children and the running parent."""

        async with self._persistence_aware_factory.begin() as session:
            run = await session.get(ObservationRunModel, initialized.observation_run_id)
            if run is None:
                raise ValueError("execution failure parent is missing")
            refresh = getattr(session, "refresh", None)
            if refresh is not None:
                await refresh(run, ["lens_runs"])
            reason = StructuredReason(code="execution_aborted", component=stage)
            for lens_run in getattr(run, "lens_runs", ()):
                if lens_run.status in {
                    LensRunStatus.PENDING.value,
                    LensRunStatus.RUNNING.value,
                }:
                    await self._runtime_repository.advance_lens_run(
                        session, lens_run, LensRunStatus.FAILED, reason=reason
                    )
            if run.status == ObservationRunStatus.RUNNING.value:
                await self._runtime_repository.advance_observation_run(
                    session,
                    run,
                    ObservationRunStatus.FAILED,
                    reason=StructuredReason(code="execution_failed", component=stage),
                )

    async def _cancel_after_initialization(
        self, initialized: InitializedObservationExecution, cancellation: BaseException
    ) -> None:
        """Commit cancellation terminalization in a separately owned shielded task."""

        cleanup = asyncio.create_task(self._cancel_transaction(initialized))
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        try:
            cleanup.result()
        except BaseException as error:
            raise error from cancellation

    async def _cancel_transaction(self, initialized: InitializedObservationExecution) -> None:
        """Terminalize only pending/running runtime records in one transaction."""

        async with self._persistence_aware_factory.begin() as session:
            run = await session.get(ObservationRunModel, initialized.observation_run_id)
            if run is None:
                raise ValueError("cancellation parent is missing")
            await self._runtime_repository.cancel_observation_execution(session, run)


class _TypeRoutedLensAdapter:
    """Dispatch an admitted assignment to the adapter for its frozen Lens type."""

    def __init__(
        self,
        metric_adapter: LensExecutionAdapter,
        alert_adapter: LensExecutionAdapter,
    ) -> None:
        self._metric_adapter = metric_adapter
        self._alert_adapter = alert_adapter

    async def execute(self, assignment, policy: ExecutionPolicy):
        """Invoke exactly the adapter matching the assignment's frozen snapshot type."""

        if isinstance(assignment.lens, MetricLensSnapshot):
            return await self._metric_adapter.execute(assignment, policy)
        if isinstance(assignment.lens, AlertLensSnapshot):
            return await self._alert_adapter.execute(assignment, policy)
        raise ValueError("unsupported Lens assignment type")


def _is_persistence_error(error: BaseException) -> bool:
    """Identify infrastructure failures without treating ordinary stage errors as durable ones."""

    if getattr(error, "persistence_failure", False):
        return True
    module = type(error).__module__
    return module.startswith(("sqlalchemy", "psycopg", "asyncpg"))


class _PersistenceAwareSessionFactory:
    """Mark exceptions escaping a transaction so the outer boundary preserves them."""

    def __init__(self, factory: ExecutionSessionFactory) -> None:
        self._factory = factory

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return a transaction wrapper that identifies persistence-boundary failures."""

        return _PersistenceAwareTransaction(self._factory.begin())


class _PersistenceAwareTransaction:
    """Delegate a transaction while tagging errors raised by its body or commit."""

    def __init__(self, transaction: AbstractAsyncContextManager[object]) -> None:
        self._transaction = transaction

    async def __aenter__(self) -> object:
        try:
            return await self._transaction.__aenter__()
        except BaseException as error:
            _mark_persistence_error(error)
            raise

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        if exc is not None:
            _mark_persistence_error(exc)
        try:
            return await self._transaction.__aexit__(exc_type, exc, traceback)
        except BaseException as error:
            _mark_persistence_error(error)
            raise


def _mark_persistence_error(error: BaseException) -> None:
    """Attach an internal marker without changing the original exception or traceback."""

    try:
        error.persistence_failure = True
    except (AttributeError, TypeError):
        pass
