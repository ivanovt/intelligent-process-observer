from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.execution import (
    ExecutionReason,
    FailedObservationExecutionOutcome,
    LensOutcomePartition,
    enforce_usable_results_gate,
)
from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.runtime_contracts import ObservationRunStatus, StructuredReason


class GateSession:
    """Small caller-owned transaction fake for the post-JOIN gate."""

    def __init__(self, observation_run: ObservationRunModel | None) -> None:
        self.observation_run = observation_run
        self.get_calls = 0

    async def get(self, model: type[object], identity: object) -> ObservationRunModel | None:
        assert model is ObservationRunModel
        self.get_calls += 1
        if self.observation_run is not None and identity == self.observation_run.id:
            return self.observation_run
        return None


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


def test_zero_usable_gate_fails_only_the_running_parent_with_exact_reason() -> None:
    observation_id = uuid4()
    parent = _running_parent(observation_id)
    session = GateSession(parent)
    repository = GateRepository()
    unavailable = object()
    partition = LensOutcomePartition(usable=(), unavailable=(unavailable,))  # type: ignore[arg-type]

    outcome = asyncio.run(
        enforce_usable_results_gate(
            session,
            repository,  # type: ignore[arg-type]
            observation_id=observation_id,
            observation_run_id=parent.id,
            partition=partition,
        )
    )

    assert outcome == FailedObservationExecutionOutcome(
        observation_run_id=parent.id,
        reason=ExecutionReason(code="no_usable_lens_results", component="usable_results_gate"),
    )
    assert session.get_calls == 1
    assert repository.transitions == [
        (
            ObservationRunStatus.FAILED,
            StructuredReason(code="no_usable_lens_results", component="usable_results_gate"),
        )
    ]
    assert parent.reason == {
        "code": "no_usable_lens_results",
        "component": "usable_results_gate",
    }
    assert partition.unavailable == (unavailable,)


def test_nonzero_usable_gate_leaves_parent_and_partition_untouched() -> None:
    parent = _running_parent(uuid4())
    session = GateSession(parent)
    repository = GateRepository()
    usable = object()
    partition = LensOutcomePartition(usable=(usable,), unavailable=())  # type: ignore[arg-type]

    outcome = asyncio.run(
        enforce_usable_results_gate(
            session,
            repository,  # type: ignore[arg-type]
            observation_id=parent.observation_id,
            observation_run_id=parent.id,
            partition=partition,
        )
    )

    assert outcome is None
    assert session.get_calls == 0
    assert repository.transitions == []
    assert parent.status == ObservationRunStatus.RUNNING.value
    assert partition.usable == (usable,)


def test_zero_usable_gate_propagates_parent_persistence_failure() -> None:
    parent = _running_parent(uuid4())
    error = RuntimeError("parent transition failed")

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(
            enforce_usable_results_gate(
                GateSession(parent),
                GateRepository(error),  # type: ignore[arg-type]
                observation_id=parent.observation_id,
                observation_run_id=parent.id,
                partition=LensOutcomePartition(usable=(), unavailable=()),
            )
        )

    assert caught.value is error
    assert parent.status == ObservationRunStatus.RUNNING.value


def _running_parent(observation_id: object) -> ObservationRunModel:
    return ObservationRunModel(
        id=uuid4(),
        observation_id=observation_id,
        status=ObservationRunStatus.RUNNING.value,
        provenance={},
        execution_context={},
    )
