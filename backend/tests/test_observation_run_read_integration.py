"""PostgreSQL integration coverage for safe Observation run reads."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.persistence.models import (
    LensAnalysisResultModel,
    LensRunModel,
    ObservationModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.observation_runs.projection import project_observation_run_detail
from app.observation_runs.read import ObservationRunReadService
from app.overview_runtime.read import OverviewRuntimeReadService

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """Reset and provide an explicitly supplied isolated PostgreSQL URL for this suite."""

    database_url = os.environ.get("IPO_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set IPO_TEST_DATABASE_URL to run PostgreSQL integration tests")
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    command.upgrade(config, "head")

    async def reset_database() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as session:
                await session.execute(text("TRUNCATE TABLE observation_definitions CASCADE"))
        finally:
            await engine.dispose()

    asyncio.run(reset_database())
    yield database_url
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url


@pytest.fixture
def session_factory(postgres_url: str) -> async_sessionmaker[AsyncSession]:
    """Create disposable async sessions against the isolated PostgreSQL database."""

    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def test_postgresql_history_order_and_read_only_detail_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Read complete ordered history and an eager detail projection without writes."""

    async def scenario() -> None:
        now = datetime(2026, 9, 9, 12, tzinfo=UTC)
        first_id, second_id = sorted((uuid4(), uuid4()), key=str)
        async with session_factory.begin() as session:
            first_observation = ObservationModel(
                id=uuid4(), name="First", objective="Integration read test", schema_version=1
            )
            second_observation = ObservationModel(
                id=uuid4(), name="Second", objective="Integration read test", schema_version=1
            )
            session.add_all((first_observation, second_observation))
            await session.flush()
            for run_id, observation in (
                (first_id, first_observation),
                (second_id, second_observation),
            ):
                run = ObservationRunModel(
                    id=run_id,
                    observation_id=observation.id,
                    status="running",
                    provenance={"internal": "not public"},
                    execution_context={
                        "analysis_window": {
                            "from": (now - timedelta(hours=1)).isoformat(),
                            "to": now.isoformat(),
                        },
                        "secret": "never project",
                    },
                    created_at=now,
                    started_at=now,
                )
                session.add(run)
                session.add(
                    LensRunModel(
                        id=uuid4(),
                        observation_run_id=run_id,
                        lens_id="running-metric",
                        lens_type="metric",
                        status="running",
                        provenance={},
                        execution_context={},
                    )
                )

        service = ObservationRunReadService(session_factory, RuntimePersistenceRepository())
        summaries = await service.list_summaries()
        matching = tuple(item for item in summaries if item.id in {first_id, second_id})
        assert tuple(item.id for item in matching) == (second_id, first_id)
        detail = await service.get_detail(second_id)
        assert detail is not None
        assert detail.summary.id == second_id
        assert detail.lens_runs[0].lens_type == "metric"
        assert "secret" not in detail.model_dump_json()

    asyncio.run(scenario())


def test_postgresql_overview_runtime_keeps_legacy_rows_without_mutation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Return valid and invalid legacy records together without repairing either row."""

    async def scenario() -> None:
        now = datetime(2026, 9, 10, 12, tzinfo=UTC)
        valid_id, legacy_id = uuid4(), uuid4()
        async with session_factory.begin() as session:
            observation = ObservationModel(
                id=uuid4(), name="Overview", objective="Projection test", schema_version=1
            )
            session.add(observation)
            session.add_all(
                (
                    ObservationRunModel(
                        id=valid_id,
                        observation_id=observation.id,
                        status="running",
                        provenance={"private": "valid"},
                        execution_context={
                            "analysis_window": {
                                "from": (now - timedelta(hours=1)).isoformat(),
                                "to": now.isoformat(),
                            }
                        },
                        created_at=now,
                        started_at=now,
                    ),
                    ObservationRunModel(
                        id=legacy_id,
                        observation_id=observation.id,
                        status="failed",
                        reason={"code": "private_legacy_diagnostic", "component": "runtime"},
                        provenance={"private": "legacy"},
                        execution_context={"analysis_window": {"from": now.isoformat()}},
                        created_at=now - timedelta(minutes=1),
                        started_at=now - timedelta(minutes=1),
                    ),
                )
            )

        service = OverviewRuntimeReadService(session_factory, RuntimePersistenceRepository())
        response = await service.get_runtime()

        assert [item.availability for item in response.items] == ["available", "limited"]
        assert [
            item.summary.id if item.availability == "available" else item.id
            for item in response.items
        ] == [valid_id, legacy_id]
        assert response.limited_run_count == 1
        limited = response.items[1]
        serialized = limited.model_dump_json()
        assert "analysis_window" not in serialized
        assert "private_legacy_diagnostic" not in serialized
        async with session_factory() as session:
            legacy = await session.get(ObservationRunModel, legacy_id)
            assert legacy is not None
            assert legacy.status == "failed"
            assert legacy.execution_context == {"analysis_window": {"from": now.isoformat()}}
            assert legacy.reason == {"code": "private_legacy_diagnostic", "component": "runtime"}

    asyncio.run(scenario())


def test_postgresql_repeatable_read_hides_terminal_writer_interleaving(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Keep a Lens terminal write and artifact insertion out of an earlier snapshot."""

    async def scenario() -> None:
        now = datetime(2026, 9, 9, 13, tzinfo=UTC)
        observation_id, run_id, lens_run_id = uuid4(), uuid4(), uuid4()
        async with session_factory.begin() as session:
            observation = ObservationModel(
                id=observation_id, name="Snapshot", objective="Snapshot test", schema_version=1
            )
            session.add(observation)
            session.add(
                ObservationRunModel(
                    id=run_id,
                    observation_id=observation_id,
                    status="running",
                    provenance={},
                    execution_context={
                        "analysis_window": {
                            "from": (now - timedelta(hours=1)).isoformat(),
                            "to": now.isoformat(),
                        }
                    },
                    created_at=now,
                    started_at=now,
                )
            )
            session.add(
                LensRunModel(
                    id=lens_run_id,
                    observation_run_id=run_id,
                    lens_id="metric",
                    lens_type="metric",
                    status="running",
                    started_at=now,
                    provenance={},
                    execution_context={},
                )
            )

        repository = RuntimePersistenceRepository()
        async with session_factory() as reader:
            async with reader.begin():
                await reader.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                await reader.scalar(
                    select(ObservationRunModel.id).where(ObservationRunModel.id == run_id)
                )
                async with session_factory.begin() as writer:
                    lens_run = await writer.get(LensRunModel, lens_run_id)
                    assert lens_run is not None
                    lens_run.status = "completed"
                    lens_run.finished_at = now + timedelta(seconds=1)
                    writer.add(
                        LensAnalysisResultModel(
                            id=uuid4(),
                            lens_run_id=lens_run_id,
                            result_type="metric",
                            status="completed",
                            schema_version="1.0",
                            payload={"writer": "inserted after reader snapshot"},
                        )
                    )
                record = await repository.get_observation_run_detail(reader, run_id)
                assert record is not None
                detail = project_observation_run_detail(record, now=now)
                assert detail.lens_runs[0].status == "running"
                assert detail.lens_runs[0].result is None

    asyncio.run(scenario())
