from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.execution import (
    AnalysisWindow,
    CollectedLensOutcome,
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensExecutionAssignment,
    MetricLensSnapshot,
    enforce_usable_results_gate,
)
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.runtime_contracts import ObservationRunStatus, StructuredReason
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricEvidence,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
    MetricProviderScope,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedDegradedSeries,
)
from app.metrics.result_builder import MetricResultBuilder


class GateTransaction(AbstractAsyncContextManager["GateSession"]):
    """Controllable application-owned transaction fake for the usable-results gate."""

    def __init__(self, session: GateSession, *, exit_error: BaseException | None = None) -> None:
        self.session = session
        self.exit_error = exit_error
        self.committed = False

    async def __aenter__(self) -> GateSession:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if self.exit_error is not None:
            raise self.exit_error
        self.committed = exc_type is None
        return False


class GateSession:
    """Expose only the parent lookup required inside the gate transaction."""

    def __init__(self, observation_run: ObservationRunModel | None) -> None:
        self.observation_run = observation_run
        self.get_calls = 0

    async def get(self, model: type[object], identity: object) -> ObservationRunModel | None:
        assert model is ObservationRunModel
        self.get_calls += 1
        if self.observation_run is not None and identity == self.observation_run.id:
            return self.observation_run
        return None


class GateFactory:
    """Record whether a zero-usable path opened and exited its own transaction."""

    def __init__(self, session: GateSession, *, exit_error: BaseException | None = None) -> None:
        self.session = session
        self.exit_error = exit_error
        self.transactions: list[GateTransaction] = []

    def begin(self) -> GateTransaction:
        transaction = GateTransaction(self.session, exit_error=self.exit_error)
        self.transactions.append(transaction)
        return transaction


class GateRepository:
    """Record the one guarded parent transition without touching Lens outcomes."""

    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.transitions: list[tuple[ObservationRunStatus, StructuredReason | None]] = []

    async def advance_observation_run(
        self,
        session: object,
        observation_run: ObservationRunModel,
        target: ObservationRunStatus,
        *,
        reason: StructuredReason | None = None,
    ) -> ObservationRunModel:
        if self.error is not None:
            raise self.error
        self.transitions.append((target, reason))
        observation_run.status = target.value
        observation_run.reason = None if reason is None else reason.model_dump()
        return observation_run


def test_zero_usable_gate_verifies_then_fails_only_the_running_parent_after_commit() -> None:
    assignments = _assignments(1)
    parent = _running_parent(assignments[0])
    factory = GateFactory(GateSession(parent))
    repository = GateRepository()

    outcome = asyncio.run(
        enforce_usable_results_gate(
            session_factory=factory,
            runtime_repository=repository,  # type: ignore[arg-type]
            assignments=assignments,
            outcomes=(_metric_outcome(assignments[0], "failed"),),
        )
    )

    assert outcome == FailedObservationExecutionOutcome(
        observation_run_id=parent.id,
        reason=ExecutionReason(code="no_usable_lens_results", component="usable_results_gate"),
    )
    assert len(factory.transactions) == 1
    assert factory.transactions[0].committed is True
    assert factory.session.get_calls == 1
    assert repository.transitions == [
        (
            ObservationRunStatus.FAILED,
            StructuredReason(code="no_usable_lens_results", component="usable_results_gate"),
        )
    ]


def test_degraded_usable_gate_returns_internal_verified_partition_without_transaction() -> None:
    assignments = _assignments(2)
    parent = _running_parent(assignments[0])
    factory = GateFactory(GateSession(parent))
    outcomes = (
        _metric_outcome(assignments[0], "partial"),
        _metric_outcome(assignments[1], "failed"),
    )

    partition = asyncio.run(
        enforce_usable_results_gate(
            session_factory=factory,
            runtime_repository=GateRepository(),  # type: ignore[arg-type]
            assignments=assignments,
            outcomes=outcomes,
        )
    )

    assert partition.usable == (outcomes[0],)
    assert partition.unavailable == (outcomes[1],)
    assert factory.transactions == []
    assert parent.status == ObservationRunStatus.RUNNING.value


@pytest.mark.parametrize("outcome_order", ("incomplete", "reordered"))
def test_gate_rejects_incomplete_or_reordered_join_before_parent_transaction(
    outcome_order: str,
) -> None:
    assignments = _assignments(2)
    parent = _running_parent(assignments[0])
    factory = GateFactory(GateSession(parent))
    valid = (
        _metric_outcome(assignments[0], "failed"),
        _metric_outcome(assignments[1], "failed"),
    )
    outcomes = valid[:1] if outcome_order == "incomplete" else valid[::-1]

    with pytest.raises(ValueError):
        asyncio.run(
            enforce_usable_results_gate(
                session_factory=factory,
                runtime_repository=GateRepository(),  # type: ignore[arg-type]
                assignments=assignments,
                outcomes=outcomes,
            )
        )
    assert factory.transactions == []
    assert parent.status == ObservationRunStatus.RUNNING.value


def test_zero_usable_gate_propagates_transaction_exit_failure_without_failed_outcome() -> None:
    assignment = _assignments(1)[0]
    parent = _running_parent(assignment)
    error = RuntimeError("parent transition commit failed")
    factory = GateFactory(GateSession(parent), exit_error=error)

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(
            enforce_usable_results_gate(
                session_factory=factory,
                runtime_repository=GateRepository(),  # type: ignore[arg-type]
                assignments=(assignment,),
                outcomes=(_metric_outcome(assignment, "failed"),),
            )
        )

    assert caught.value is error
    assert factory.transactions[0].committed is False


def _assignments(count: int) -> tuple[LensExecutionAssignment, ...]:
    observation_id, observation_run_id = uuid4(), uuid4()
    window_end = datetime(2026, 9, 7, 12, tzinfo=UTC)
    return tuple(
        LensExecutionAssignment(
            observation_id=observation_id,
            observation_run_id=observation_run_id,
            lens_run_id=uuid4(),
            analysis_window=AnalysisWindow(from_=window_end - timedelta(minutes=5), to=window_end),
            lens=MetricLensSnapshot(
                lens_id=f"metric-{index}",
                name=f"Metric {index}",
                description=None,
                metric_id=f"metric-{index}",
                adapter_type="prometheus",
                source_id="source",
                query="up",
                unit="count",
                analysis_objectives=(),
                reference_periods=(),
            ),
        )
        for index in range(count)
    )


def _running_parent(assignment: LensExecutionAssignment) -> ObservationRunModel:
    return ObservationRunModel(
        id=assignment.observation_run_id,
        observation_id=assignment.observation_id,
        status=ObservationRunStatus.RUNNING.value,
        provenance={},
        execution_context={},
    )


def _metric_outcome(assignment: LensExecutionAssignment, status: str) -> CollectedLensOutcome:
    assert isinstance(assignment.lens, MetricLensSnapshot)
    context = MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=assignment.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=assignment.lens.lens_id,
            lens_run_id=assignment.lens_run_id,
            metric_ref=assignment.lens.metric_id,
            unit=assignment.lens.unit,
        ),
        provider_scope=MetricProviderScope(
            adapter_type=assignment.lens.adapter_type,
            source_id=assignment.lens.source_id,
            query=assignment.lens.query,
        ),
        analysis_window=MetricAnalysisWindow(
            **{"from": assignment.analysis_window.from_, "to": assignment.analysis_window.to}
        ),
        analysis_objectives=(),
        reference_periods=(),
    )
    builder = MetricResultBuilder()
    if status == "failed":
        _, artifact = builder.failed(context, MetricMandatoryAnalysisFailure(diagnostic="test"))
    else:
        _, artifact = builder.partial_reference_unavailable(
            context,
            PreparedDegradedSeries(
                data_quality="degraded",
                samples=(),
                evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
                residuals=(),
            ),
            MetricSemantics(
                trend=MetricTrend(direction="stable", rate="not_classified"),
                variability=MetricVariability(state="low"),
            ),
            (),
            (),
        )
    return CollectedLensOutcome(
        assignment=assignment,
        status=status,  # type: ignore[arg-type]
        artifact=artifact,
        reason=ExecutionReason(code="test", component="test") if status != "completed" else None,
    )
