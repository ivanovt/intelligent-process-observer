"""PostgreSQL coverage for atomic Observation execution initialization."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.execution import (
    AnalysisWindow,
    ExecutionPolicy,
    ObservationExecutionRequest,
    RejectedObservationExecutionOutcome,
    initialize_observation_execution,
)
from app.infrastructure.persistence.models import (
    AlertLensModel,
    LensAnalysisResultModel,
    LensRunModel,
    MetricLensModel,
    ObservationModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.repository import (
    ObservationRepository,
    RuntimePersistenceRepository,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    """Provide a migrated opt-in PostgreSQL database for integration tests."""

    database_url = os.environ.get("IPO_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set IPO_TEST_DATABASE_URL to run PostgreSQL integration tests")

    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    command.upgrade(config, "head")
    yield database_url
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url
    get_settings.cache_clear()


@pytest.fixture
def session_factory(postgres_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Create isolated async sessions backed by the configured PostgreSQL database."""

    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def test_initialization_persists_complete_mixed_type_aware_graph(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Initialization commits the exact mixed topology and minimal durable context."""

    async def scenario() -> None:
        observation_id = await _seed_mixed_observation(session_factory)
        initialized = await initialize_observation_execution(
            session_factory,
            ObservationRepository(),
            RuntimePersistenceRepository(),
            _request(observation_id),
            _policy(),
        )

        assert not isinstance(initialized, RejectedObservationExecutionOutcome)
        assert initialized.observation_run_id != observation_id
        assert [(item.lens.lens_type, item.lens.lens_id) for item in initialized.assignments] == [
            ("metric", "cpu"),
            ("metric", "same"),
            ("alert", "same"),
        ]
        assert len({item.lens_run_id for item in initialized.assignments}) == 3

        async with session_factory() as session:
            restored = await RuntimePersistenceRepository().get_observation_run(
                session, initialized.observation_run_id
            )
            assert restored is not None
            assert restored.observation_id == observation_id
            assert restored.status == "running"
            assert restored.execution_context == {
                "definition_schema_version": 7,
                "analysis_window": {
                    "from": "2026-09-07T11:55:00+00:00",
                    "to": "2026-09-07T12:00:00+00:00",
                },
            }
            assert {(item.lens_type, item.lens_id) for item in restored.lens_runs} == {
                ("metric", "cpu"),
                ("metric", "same"),
                ("alert", "same"),
            }
            assert {item.id for item in restored.lens_runs} == {
                item.lens_run_id for item in initialized.assignments
            }
            assert all(item.status == "pending" for item in restored.lens_runs)
            assert all(
                item.execution_context
                == {
                    "analysis_window": {
                        "from": "2026-09-07T11:55:00+00:00",
                        "to": "2026-09-07T12:00:00+00:00",
                    }
                }
                for item in restored.lens_runs
            )

    asyncio.run(scenario())


def test_initialization_rolls_back_flushed_runtime_rows_on_child_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A failure after a child flush leaves no durable runtime or analytical rows."""

    class FailingAfterFirstChildRepository(RuntimePersistenceRepository):
        def __init__(self) -> None:
            self.child_creations = 0

        async def create_lens_run(self, *args: object, **kwargs: object) -> LensRunModel:
            self.child_creations += 1
            lens_run = await super().create_lens_run(*args, **kwargs)  # type: ignore[arg-type]
            if self.child_creations == 1:
                raise RuntimeError("child persistence failure")
            return lens_run

    async def scenario() -> None:
        observation_id = await _seed_mixed_observation(session_factory)
        repository = FailingAfterFirstChildRepository()
        with pytest.raises(RuntimeError, match="child persistence failure"):
            await initialize_observation_execution(
                session_factory,
                ObservationRepository(),
                repository,
                _request(observation_id),
                _policy(),
            )
        assert repository.child_creations == 1
        await _assert_no_runtime_rows(session_factory, observation_id)

    asyncio.run(scenario())


def test_initialization_propagates_commit_failure_and_rolls_back_runtime_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A real SQLAlchemy commit hook failure propagates and leaves no durable graph."""

    async def scenario() -> None:
        observation_id = await _seed_mixed_observation(session_factory)
        with pytest.raises(RuntimeError, match="commit boundary unavailable"):
            await initialize_observation_execution(
                CommitFailingSessionFactory(session_factory),
                ObservationRepository(),
                RuntimePersistenceRepository(),
                _request(observation_id),
                _policy(),
            )
        await _assert_no_runtime_rows(session_factory, observation_id)

    asyncio.run(scenario())


class CommitFailingSessionFactory:
    """Inject one SQLAlchemy before-commit failure while retaining a real transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def begin(self) -> CommitFailingTransaction:
        """Return a transaction that fails at the real SQLAlchemy commit boundary."""

        return CommitFailingTransaction(self._session_factory)


class CommitFailingTransaction(AbstractAsyncContextManager[AsyncSession]):
    """Async transaction wrapper that registers a one-shot SQLAlchemy commit failure."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._transaction: AbstractAsyncContextManager[AsyncSession] | None = None

    async def __aenter__(self) -> AsyncSession:
        """Open a real session and transaction before installing the commit hook."""

        self._session = self._session_factory()
        event.listen(self._session.sync_session, "before_commit", _raise_commit_failure)
        self._transaction = self._session.begin()
        return await self._transaction.__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None:
        """Delegate commit/rollback, then remove the hook and close the session."""

        assert self._session is not None
        assert self._transaction is not None
        try:
            return await self._transaction.__aexit__(exc_type, exc, traceback)
        finally:
            event.remove(self._session.sync_session, "before_commit", _raise_commit_failure)
            await self._session.close()


def _raise_commit_failure(_: object) -> None:
    raise RuntimeError("commit boundary unavailable")


async def _seed_mixed_observation(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with session_factory.begin() as session:
        observation = ObservationModel(
            id=uuid4(),
            name=f"Initialization integration {uuid4()}",
            objective="Verify atomic initialization.",
            schema_version=7,
            lenses=[
                _metric_lens("same", 0),
                _metric_lens("cpu", 1),
            ],
            alert_lenses=[_alert_lens("same", 0)],
        )
        session.add(observation)
        await session.flush()
        return observation.id


def _metric_lens(lens_id: str, position: int) -> MetricLensModel:
    return MetricLensModel(
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
        position=position,
    )


def _alert_lens(lens_id: str, position: int) -> AlertLensModel:
    return AlertLensModel(
        lens_id=lens_id,
        lens_type="alert",
        name=lens_id,
        description=None,
        source="jira_track_and_release",
        selector_query="project = IPO",
        analysis_objectives=["detect anomalies"],
        reference_periods=["1h"],
        position=position,
    )


def _request(observation_id: UUID) -> ObservationExecutionRequest:
    end = datetime(2026, 9, 7, 12, tzinfo=UTC)
    return ObservationExecutionRequest(
        observation_id=observation_id,
        analysis_window=AnalysisWindow(from_=end - timedelta(minutes=5), to=end),
    )


def _policy() -> ExecutionPolicy:
    return ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=30)


async def _assert_no_runtime_rows(
    session_factory: async_sessionmaker[AsyncSession], observation_id: UUID
) -> None:
    async with session_factory() as session:
        observation_run_count = await session.scalar(
            select(func.count())
            .select_from(ObservationRunModel)
            .where(ObservationRunModel.observation_id == observation_id)
        )
        lens_run_count = await session.scalar(
            select(func.count())
            .select_from(LensRunModel)
            .join(ObservationRunModel)
            .where(ObservationRunModel.observation_id == observation_id)
        )
        analytical_result_count = await session.scalar(
            select(func.count())
            .select_from(LensAnalysisResultModel)
            .join(LensRunModel)
            .join(ObservationRunModel)
            .where(ObservationRunModel.observation_id == observation_id)
        )
        assert observation_run_count == 0
        assert lens_run_count == 0
        assert analytical_result_count == 0
