from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import Never
from uuid import UUID, uuid4

import pytest

from app.execution import (
    AnalysisWindow,
    ExecutionPolicy,
    ObservationExecutionRequest,
    RejectedObservationExecutionOutcome,
    canonical_lens_order,
    initialize_observation_execution,
    project_observation_execution,
)
from app.infrastructure.persistence.models import AlertLensModel, MetricLensModel, ObservationModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.statements: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        return type("UpdateResult", (), {"rowcount": 1})()


class RecordingTransaction(AbstractAsyncContextManager[RecordingSession]):
    def __init__(self, session: RecordingSession) -> None:
        self.session = session
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> RecordingSession:
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return False


class RecordingSessionFactory:
    def __init__(self) -> None:
        self.session = RecordingSession()
        self.transaction = RecordingTransaction(self.session)

    def begin(self) -> RecordingTransaction:
        return self.transaction


class Loader:
    def __init__(self, definition: ObservationModel | None) -> None:
        self.definition = definition
        self.calls = 0
        self.sessions: list[object] = []

    async def get(self, session: object, observation_id: UUID) -> ObservationModel | None:
        self.calls += 1
        self.sessions.append(session)
        if self.definition is not None:
            assert observation_id == self.definition.id
        return self.definition


def test_canonical_order_uses_literal_type_rank_and_lexical_lens_id() -> None:
    definition = _definition(metric_ids=("zeta", "alpha"), alert_ids=("alpha", "beta"))
    snapshot = project_observation_execution(_request(definition.id), _policy(), definition)

    assert not isinstance(snapshot, RejectedObservationExecutionOutcome)
    assert [(lens.lens_type, lens.lens_id) for lens in canonical_lens_order(snapshot)] == [
        ("metric", "alpha"),
        ("metric", "zeta"),
        ("alert", "alpha"),
        ("alert", "beta"),
    ]


def test_initialization_commits_complete_type_aware_runtime_graph() -> None:
    definition = _definition(metric_ids=("same", "cpu"), alert_ids=("same",))
    factory = RecordingSessionFactory()
    loader = Loader(definition)

    initialized = asyncio.run(
        initialize_observation_execution(
            factory, loader, RuntimePersistenceRepository(), _request(definition.id), _policy()
        )
    )

    assert not isinstance(initialized, RejectedObservationExecutionOutcome)
    assert loader.calls == 1
    assert loader.sessions == [factory.session]
    assert factory.transaction.committed is True
    assert factory.transaction.rolled_back is False
    assert len(factory.session.added) == 4
    assert [(item.lens.lens_type, item.lens.lens_id) for item in initialized.assignments] == [
        ("metric", "cpu"),
        ("metric", "same"),
        ("alert", "same"),
    ]
    assert len({item.lens_run_id for item in initialized.assignments}) == 3
    assert initialized.assignments[1].lens.lens_id == initialized.assignments[2].lens.lens_id


def test_initialization_rolls_back_the_graph_when_child_creation_fails() -> None:
    class FailingRepository(RuntimePersistenceRepository):
        async def create_lens_run(self, *args: object, **kwargs: object) -> Never:
            raise RuntimeError("storage unavailable")

    definition = _definition(metric_ids=("cpu",), alert_ids=())
    factory = RecordingSessionFactory()

    with pytest.raises(RuntimeError, match="storage unavailable"):
        asyncio.run(
            initialize_observation_execution(
                factory, Loader(definition), FailingRepository(), _request(definition.id), _policy()
            )
        )

    assert factory.transaction.rolled_back is True
    assert factory.transaction.committed is False


def test_controlled_pre_initialization_rejection_creates_no_runtime_records() -> None:
    factory = RecordingSessionFactory()
    observation_id = uuid4()

    outcome = asyncio.run(
        initialize_observation_execution(
            factory,
            Loader(None),
            RuntimePersistenceRepository(),
            _request(observation_id),
            _policy(),
        )
    )

    assert isinstance(outcome, RejectedObservationExecutionOutcome)
    assert outcome.reason.code == "observation_not_found"
    assert factory.session.added == []


def _request(observation_id: UUID) -> ObservationExecutionRequest:
    end = datetime(2026, 9, 7, 12, tzinfo=UTC)
    return ObservationExecutionRequest(
        observation_id=observation_id,
        analysis_window=AnalysisWindow(from_=end - timedelta(minutes=5), to=end),
    )


def _policy() -> ExecutionPolicy:
    return ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=30)


def _definition(*, metric_ids: tuple[str, ...], alert_ids: tuple[str, ...]) -> ObservationModel:
    observation_id = uuid4()
    return ObservationModel(
        id=observation_id,
        schema_version=1,
        name="Host health",
        description=None,
        objective="Observe host health",
        lenses=[
            MetricLensModel(
                observation_id=observation_id,
                lens_id=lens_id,
                name=lens_id,
                description=None,
                adapter_type="prometheus",
                source_id="prometheus",
                metric_id=lens_id,
                query=f"rate({lens_id}[5m])",
                unit="percent",
                analysis_objectives=["detect anomalies"],
                reference_periods=["1h"],
                position=index,
            )
            for index, lens_id in enumerate(metric_ids)
        ],
        alert_lenses=[
            AlertLensModel(
                observation_id=observation_id,
                lens_id=lens_id,
                lens_type="alert",
                name=lens_id,
                description=None,
                source="jira_track_and_release",
                selector_query="project = IPO",
                analysis_objectives=["detect anomalies"],
                reference_periods=["1h"],
                position=index,
            )
            for index, lens_id in enumerate(alert_ids)
        ],
        relationships=[],
    )
