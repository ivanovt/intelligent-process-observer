"""PostgreSQL coverage for atomic Observation aggregate replacement."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
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
    MetricLensModel,
    ObservationModel,
    ObservationRelationshipModel,
)
from app.infrastructure.persistence.repository import (
    ObservationRepository,
    RuntimePersistenceRepository,
)
from app.knowledge.management_contracts import KnowledgeScope
from app.main import app
from app.observations.api import get_service, get_session
from app.observations.contracts import ObservationCreate
from app.observations.errors import ApiError
from app.observations.service import ObservationDefinitionService

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_url() -> AsyncIterator[str]:
    """Provide a migrated opt-in PostgreSQL database for replacement tests."""
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
    """Create isolated sessions for one opted-in PostgreSQL database."""
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def test_replace_reconciles_owned_collections_and_preserves_retained_row_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Replacement applies one ordered snapshot and deletes every omitted owned row."""

    async def scenario() -> None:
        repository = ObservationRepository()
        observation_id = await _create_definition(session_factory, repository)
        async with session_factory.begin() as session:
            before = await repository.get(session, observation_id)
            assert before is not None
            retained_ids = {
                "metric-b": next(item.id for item in before.lenses if item.lens_id == "metric-b"),
                "alert-b": next(
                    item.id for item in before.alert_lenses if item.lens_id == "alert-b"
                ),
                "relationship-b": next(
                    item.id
                    for item in before.relationships
                    if item.relationship_id == "relationship-b"
                ),
            }
            replaced = await repository.replace(session, observation_id, _replacement_definition())
            assert replaced is not None

        async with session_factory.begin() as session:
            restored = await repository.get(session, observation_id)
            assert restored is not None
            assert restored.name == "Replacement definition"
            assert [item.lens_id for item in restored.lenses] == ["metric-b", "metric-c"]
            assert [item.lens_id for item in restored.alert_lenses] == ["alert-b", "alert-c"]
            assert [item.relationship_id for item in restored.relationships] == [
                "relationship-b",
                "relationship-c",
            ]
            retained_metric = next(item for item in restored.lenses if item.lens_id == "metric-b")
            assert retained_metric.id == retained_ids["metric-b"]
            assert (
                next(item.id for item in restored.alert_lenses if item.lens_id == "alert-b")
                == retained_ids["alert-b"]
            )
            assert (
                next(
                    item.id
                    for item in restored.relationships
                    if item.relationship_id == "relationship-b"
                )
                == retained_ids["relationship-b"]
            )
            for model, public_id, column in (
                (MetricLensModel, "metric-a", MetricLensModel.lens_id),
                (AlertLensModel, "alert-a", AlertLensModel.lens_id),
                (
                    ObservationRelationshipModel,
                    "relationship-a",
                    ObservationRelationshipModel.relationship_id,
                ),
            ):
                orphan = await session.scalar(
                    select(model.id).where(
                        model.observation_id == observation_id,
                        column == public_id,
                    )
                )
                assert orphan is None

    asyncio.run(scenario())


def test_replace_persists_or_clears_optional_knowledge_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Replacement changes retriever-only metadata without changing owned Lens semantics."""

    async def scenario() -> None:
        repository = ObservationRepository()
        observation_id = await _create_definition(session_factory, repository)
        async with session_factory() as session:
            sql_null_id = await session.scalar(
                select(ObservationModel.id).where(
                    ObservationModel.id == observation_id,
                    ObservationModel.knowledge_scope.is_(None),
                )
            )
            assert sql_null_id == observation_id
        scoped = _replacement_definition().model_copy(
            update={
                "knowledge_scope": KnowledgeScope(
                    service_ids=("cooling-loop",), service_version="2.x"
                )
            }
        )
        async with session_factory.begin() as session:
            assert await repository.replace(session, observation_id, scoped) is not None
        async with session_factory.begin() as session:
            restored = await repository.get(session, observation_id)
            assert restored is not None
            assert restored.knowledge_scope == {
                "service_ids": ["cooling-loop"],
                "service_version": "2.x",
            }

        async with session_factory.begin() as session:
            replaced = await repository.replace(session, observation_id, _replacement_definition())
            assert replaced is not None
        async with session_factory.begin() as session:
            restored = await repository.get(session, observation_id)
            assert restored is not None
            assert restored.knowledge_scope is None
            sql_null_id = await session.scalar(
                select(ObservationModel.id).where(
                    ObservationModel.id == observation_id,
                    ObservationModel.knowledge_scope.is_(None),
                )
            )
            assert sql_null_id == observation_id

    asyncio.run(scenario())


def test_replace_rollback_preserves_complete_definition_after_flush_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A persistence failure after reconciliation leaves the prior snapshot untouched."""

    class FailingRepository(ObservationRepository):
        async def replace(self, *args: object, **kwargs: object) -> ObservationModel | None:
            await super().replace(*args, **kwargs)  # type: ignore[arg-type]
            raise RuntimeError("replacement persistence failed")

    async def scenario() -> None:
        observation_id = await _create_definition(session_factory, ObservationRepository())
        before = await _definition_payload(session_factory, observation_id)
        service = ObservationDefinitionService(FailingRepository())
        async with session_factory() as session:
            with pytest.raises(RuntimeError, match="replacement persistence failed"):
                await service.replace(session, observation_id, _alert_only_replacement())
        assert await _definition_payload(session_factory, observation_id) == before

    asyncio.run(scenario())


def test_replace_source_rejection_preserves_complete_definition(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Enabled-source validation rejects a replacement before any aggregate mutation."""

    async def scenario() -> None:
        observation_id = await _create_definition(session_factory, ObservationRepository())
        before = await _definition_payload(session_factory, observation_id)
        invalid_source = _replacement_definition().model_copy(deep=True)
        invalid_source.lenses[0].source_id = "not-an-enabled-source"
        async with session_factory() as session:
            with pytest.raises(ApiError) as raised:
                await ObservationDefinitionService().replace(
                    session, observation_id, invalid_source
                )
        assert raised.value.code == "source_not_enabled"
        assert await _definition_payload(session_factory, observation_id) == before

    asyncio.run(scenario())


def test_invalid_replace_api_request_preserves_complete_persisted_definition(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Aggregate validation rejects an invalid PUT before it can change a persisted definition."""

    async def postgres_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def postgres_service() -> ObservationDefinitionService:
        return ObservationDefinitionService(ObservationRepository())

    async def scenario() -> None:
        observation_id = await _create_definition(session_factory, ObservationRepository())
        before = await _definition_payload(session_factory, observation_id)
        app.dependency_overrides[get_session] = postgres_session
        app.dependency_overrides[get_service] = postgres_service
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    f"/api/v1/observations/{observation_id}",
                    json={
                        "name": "Invalid replacement",
                        "objective": "This aggregate has no Lens.",
                        "lenses": [],
                        "alert_lenses": [],
                        "relationships": [],
                    },
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        assert await _definition_payload(session_factory, observation_id) == before

    asyncio.run(scenario())


def test_definition_read_keeps_a_complete_snapshot_during_concurrent_replacement(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """One definition read retains a whole pre-update aggregate after replacement commits."""

    async def scenario() -> None:
        repository = ObservationRepository()
        observation_id = await _create_definition(session_factory, repository)
        writer_started = asyncio.Event()

        async def replace_in_parallel() -> None:
            async with session_factory.begin() as session:
                writer_started.set()
                await repository.replace(session, observation_id, _replacement_definition())

        async with session_factory.begin() as reader_session:
            snapshot = await repository.get(reader_session, observation_id)
            assert snapshot is not None
            writer = asyncio.create_task(replace_in_parallel())
            await writer_started.wait()
            await writer
            assert [item.lens_id for item in snapshot.lenses] == ["metric-a", "metric-b"]
            assert [item.lens_id for item in snapshot.alert_lenses] == ["alert-a", "alert-b"]

        async with session_factory.begin() as session:
            replacement = await repository.get(session, observation_id)
            assert replacement is not None
            assert [item.lens_id for item in replacement.lenses] == ["metric-b", "metric-c"]

    asyncio.run(scenario())


def test_run_initialization_freezes_complete_pre_update_snapshot_during_replacement(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A real concurrent run initialization keeps one complete pre-update snapshot."""

    class PausingDefinitionLoader:
        def __init__(self) -> None:
            self.definition_loaded = asyncio.Event()
            self.resume_initialization = asyncio.Event()
            self._repository = ObservationRepository()

        async def get(self, session: AsyncSession, observation_id: UUID) -> ObservationModel | None:
            definition = await self._repository.get(session, observation_id)
            self.definition_loaded.set()
            await self.resume_initialization.wait()
            return definition

    async def scenario() -> None:
        definition_repository = ObservationRepository()
        observation_id = await _create_execution_definition(session_factory)
        definition_loader = PausingDefinitionLoader()
        initialization = asyncio.create_task(
            initialize_observation_execution(
                session_factory,
                definition_loader,
                RuntimePersistenceRepository(),
                ObservationExecutionRequest(
                    observation_id=observation_id,
                    analysis_window=AnalysisWindow(
                        from_=datetime(2026, 9, 7, 11, 55, tzinfo=UTC),
                        to=datetime(2026, 9, 7, 12, tzinfo=UTC),
                    ),
                ),
                ExecutionPolicy(max_parallel_lens_runs=2, lens_deadline_seconds=30),
            )
        )
        await definition_loader.definition_loaded.wait()

        replacement_started = asyncio.Event()

        async def replace_concurrently() -> None:
            async with session_factory.begin() as session:
                replacement_started.set()
                await definition_repository.replace(
                    session, observation_id, _execution_replacement_definition()
                )

        replacement = asyncio.create_task(replace_concurrently())
        await replacement_started.wait()
        await replacement
        definition_loader.resume_initialization.set()
        initialized = await initialization

        assert not isinstance(initialized, RejectedObservationExecutionOutcome)
        assert initialized.snapshot.name.startswith("Original definition")
        assert [lens.lens_id for lens in initialized.snapshot.metric_lenses] == [
            "metric-a",
            "metric-b",
        ]
        assert [lens.lens_id for lens in initialized.snapshot.alert_lenses] == [
            "alert-a",
            "alert-b",
        ]
        assert [
            relationship.relationship_id for relationship in initialized.snapshot.relationships
        ] == [
            "relationship-a",
            "relationship-b",
        ]
        assert [(item.lens.lens_type, item.lens.lens_id) for item in initialized.assignments] == [
            ("metric", "metric-a"),
            ("metric", "metric-b"),
            ("alert", "alert-a"),
            ("alert", "alert-b"),
        ]
        async with session_factory.begin() as session:
            persisted = await definition_repository.get(session, observation_id)
            assert persisted is not None
            assert persisted.name == "Replacement definition"
            assert [lens.lens_id for lens in persisted.lenses] == ["metric-b", "metric-c"]
            assert [lens.lens_id for lens in persisted.alert_lenses] == ["alert-b", "alert-c"]
            assert persisted.relationships == []

    asyncio.run(scenario())


async def _create_definition(
    session_factory: async_sessionmaker[AsyncSession], repository: ObservationRepository
) -> UUID:
    async with session_factory.begin() as session:
        created = await repository.create(session, _original_definition())
        return created.id


async def _create_execution_definition(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    """Seed an execution-valid aggregate with descriptors that omit null-valued fields."""
    async with session_factory.begin() as session:
        observation = ObservationModel(
            name=f"Original definition {uuid4()}",
            description="Original description",
            objective="Observe original topology.",
            schema_version=1,
            lenses=[
                MetricLensModel(
                    lens_id="metric-a",
                    name="metric-a",
                    adapter_type="prometheus",
                    source_id="production-prometheus",
                    metric_id="metric-a",
                    query="avg(metric-a)",
                    unit="count",
                    analysis_objectives=["spike"],
                    reference_periods=[],
                    position=0,
                ),
                MetricLensModel(
                    lens_id="metric-b",
                    name="metric-b",
                    adapter_type="prometheus",
                    source_id="production-prometheus",
                    metric_id="metric-b",
                    query="avg(metric-b)",
                    unit="count",
                    analysis_objectives=["spike"],
                    reference_periods=[],
                    position=1,
                ),
            ],
            alert_lenses=[
                AlertLensModel(
                    lens_id="alert-a",
                    lens_type="alert",
                    name="alert-a",
                    source="jira_track_and_release",
                    selector_query="project = alert-a",
                    analysis_objectives=[],
                    reference_periods=[],
                    position=0,
                ),
                AlertLensModel(
                    lens_id="alert-b",
                    lens_type="alert",
                    name="alert-b",
                    source="jira_track_and_release",
                    selector_query="project = alert-b",
                    analysis_objectives=[],
                    reference_periods=[],
                    position=1,
                ),
            ],
            relationships=[
                ObservationRelationshipModel(
                    relationship_id="relationship-a",
                    name="relationship-a",
                    participants=["metric-a", "metric-b"],
                    conditions={},
                    expected={
                        "metric-a": {"trend": {"direction": "stable"}},
                        "metric-b": {"trend": {"direction": "stable"}},
                    },
                    position=0,
                ),
                ObservationRelationshipModel(
                    relationship_id="relationship-b",
                    name="relationship-b",
                    participants=["metric-b", "metric-a"],
                    conditions={},
                    expected={
                        "metric-b": {"trend": {"direction": "stable"}},
                        "metric-a": {"trend": {"direction": "stable"}},
                    },
                    position=1,
                ),
            ],
        )
        session.add(observation)
        await session.flush()
        return observation.id


async def _definition_payload(
    session_factory: async_sessionmaker[AsyncSession], observation_id: UUID
) -> dict[str, object]:
    async with session_factory.begin() as session:
        definition = await ObservationRepository().get(session, observation_id)
        assert definition is not None
        return {
            "name": definition.name,
            "description": definition.description,
            "objective": definition.objective,
            "lenses": [(item.lens_id, item.name, item.position) for item in definition.lenses],
            "alerts": [
                (item.lens_id, item.name, item.selector_query, item.position)
                for item in definition.alert_lenses
            ],
            "relationships": [
                (item.relationship_id, item.name, item.participants, item.position)
                for item in definition.relationships
            ],
        }


def _original_definition() -> ObservationCreate:
    return ObservationCreate.model_validate(
        {
            "name": f"Original definition {uuid4()}",
            "description": "Original description",
            "objective": "Observe original topology.",
            "lenses": [_metric("metric-a"), _metric("metric-b")],
            "alert_lenses": [_alert("alert-a"), _alert("alert-b")],
            "relationships": [
                _relationship("relationship-a", ["metric-a", "metric-b"]),
                _relationship("relationship-b", ["metric-b", "metric-a"]),
            ],
        }
    )


def _replacement_definition() -> ObservationCreate:
    return ObservationCreate.model_validate(
        {
            "name": "Replacement definition",
            "description": "Replacement description",
            "objective": "Observe replacement topology.",
            "lenses": [_metric("metric-b", name="Retained metric updated"), _metric("metric-c")],
            "alert_lenses": [_alert("alert-b", name="Retained alert updated"), _alert("alert-c")],
            "relationships": [
                _relationship("relationship-b", ["metric-b", "metric-c"]),
                _relationship("relationship-c", ["metric-c", "metric-b"]),
            ],
        }
    )


def _execution_replacement_definition() -> ObservationCreate:
    replacement = _replacement_definition().model_copy(deep=True)
    replacement.relationships = []
    return replacement


def _alert_only_replacement() -> ObservationCreate:
    return ObservationCreate.model_validate(
        {
            "name": "Alert-only replacement",
            "objective": "Prove rollback.",
            "alert_lenses": [_alert("only-alert")],
        }
    )


def _metric(identifier: str, *, name: str | None = None) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name or identifier,
        "type": "metric",
        "metric_id": identifier,
        "adapter_type": "prometheus",
        "source_id": "production-prometheus",
        "query": f"avg({identifier})",
        "unit": "count",
        "analysis_objectives": ["spike"],
        "reference_periods": [],
    }


def _alert(identifier: str, *, name: str | None = None) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name or identifier,
        "type": "alert",
        "source": "jira_track_and_release",
        "selector": {"query": f"project = {identifier}"},
    }


def _relationship(identifier: str, participants: list[str]) -> dict[str, object]:
    return {
        "id": identifier,
        "name": identifier,
        "participants": participants,
        "conditions": {},
        "expected": {
            participant: {"trend": {"direction": "stable"}} for participant in participants
        },
    }
