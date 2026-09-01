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
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.settings import get_settings
from app.infrastructure.persistence.models import (
    AlertLensModel,
    MetricLensModel,
    ObservationAnalysisResultModel,
    ObservationModel,
    ObservationRelationshipModel,
    ObservationReportModel,
    ObservationRunModel,
    RelationshipEvaluationModel,
)
from app.infrastructure.persistence.repository import (
    ObservationRepository,
    RuntimePersistenceRepository,
)
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunInput,
    LensRunStatus,
    LensType,
    ObservationAnalysisIdentity,
    ObservationAnalysisResultInput,
    ObservationReportInput,
    ObservationRunInput,
    ObservationRunStatus,
    RelationshipEvaluationInput,
    StructuredReason,
)
from app.main import app
from app.observations.api import get_service, get_session
from app.observations.contracts import ObservationCreate
from app.observations.service import ObservationDefinitionService

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_url() -> str:
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
def session_factory(postgres_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def _result_input(
    lens_run_id: UUID,
    observation_id: UUID,
    observation_run_id: UUID,
    lens_id: str,
    lens_type: LensType,
    status: LensRunStatus,
    partial_reason: StructuredReason | None = None,
) -> LensAnalysisResultInput:
    identity = LensResultIdentity(
        observation_id=observation_id,
        observation_run_id=observation_run_id,
        lens_id=lens_id,
        lens_run_id=lens_run_id,
        metric_ref="coolant_temperature" if lens_type is LensType.METRIC else None,
        unit="celsius" if lens_type is LensType.METRIC else None,
    )
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "identity": identity.model_dump(mode="json", exclude_none=True),
        "lens_type": lens_type.value,
        "status": {"state": status.value} if lens_type is LensType.METRIC else status.value,
        "provenance": {
            "source": "integration-test",
            "generated_at": "2026-08-23T01:00:00Z",
        },
        "optional_sections": [],
        "nested": {"jsonb": ["round-trip", {"value": 1}]},
    }
    if status is LensRunStatus.PARTIAL:
        reason = partial_reason or StructuredReason(code="optional_analysis_failed")
        payload["reason"] = reason.model_dump(mode="json", exclude_none=True)
    if lens_type is LensType.METRIC and status is LensRunStatus.FAILED:
        payload["analysis_window"] = {
            "from": "2026-08-23T00:00:00Z",
            "to": "2026-08-23T01:00:00Z",
        }
        payload["status"] = {
            "state": "failed",
            "error": {"code": "acquisition_failed", "message": "Source unavailable"},
        }
    return LensAnalysisResultInput(
        result_type=lens_type,
        status=status,
        schema_version="1.0",
        identity=identity,
        provenance={
            "source": "integration-test",
            "generated_at": "2026-08-23T01:00:00Z",
        },
        payload=payload,
    )


def _observation_analysis_input(
    observation_id: UUID, observation_run_id: UUID
) -> ObservationAnalysisResultInput:
    return ObservationAnalysisResultInput(
        schema_version="1.0",
        identity=ObservationAnalysisIdentity(
            observation_id=observation_id,
            observation_run_id=observation_run_id,
        ),
        payload={
            "schema_version": "1.0",
            "identity": {
                "observation_id": str(observation_id),
                "observation_run_id": str(observation_run_id),
            },
            "overall_state": "no_significant_findings",
            "findings": [],
            "hypotheses": [],
            "limitations": [],
        },
    )


def _relationship_evaluation() -> RelationshipEvaluationInput:
    return RelationshipEvaluationInput(
        relationship_id="temperature-pressure-link",
        payload={
            "relationship": {
                "id": "temperature-pressure-link",
                "name": "Temperature and pressure link",
                "description": "Pressure follows temperature changes",
                "participants": ["coolant-temperature", "line-pressure"],
            },
            "applicability": "applicable",
            "expected": {"condition": "pressure follows temperature"},
            "observed": {
                "participant_states": {
                    "coolant-temperature": "elevated",
                    "line-pressure": "elevated",
                },
                "evidence_refs": ["metric:coolant-temperature"],
            },
            "evaluation": {"state": "consistent"},
        },
    )


async def _seed_observation(session: AsyncSession) -> ObservationModel:
    observation = ObservationModel(
        id=uuid4(),
        name=f"Runtime persistence integration {uuid4()}",
        objective="Verify runtime persistence.",
        schema_version=1,
    )
    session.add(observation)
    await session.flush()
    return observation


def test_runtime_persistence_round_trip_and_artifact_absence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)

            metric_complete = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="metric-complete", lens_type=LensType.METRIC),
            )
            metric_partial = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="metric-partial", lens_type=LensType.METRIC),
            )
            metric_failed = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="metric-failed", lens_type=LensType.METRIC),
            )
            alert_failed = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="alert-failed", lens_type=LensType.ALERT),
            )
            log_failed = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="log-failed", lens_type=LensType.LOG),
            )
            log_completed = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="log-completed", lens_type=LensType.LOG),
            )

            await repository.advance_lens_run(session, metric_complete, LensRunStatus.RUNNING)
            await repository.advance_lens_run(session, metric_complete, LensRunStatus.COMPLETED)
            await repository.persist_lens_analysis_result(
                session,
                metric_complete,
                _result_input(
                    metric_complete.id,
                    observation.id,
                    run.id,
                    metric_complete.lens_id,
                    LensType.METRIC,
                    LensRunStatus.COMPLETED,
                ),
            )

            await repository.advance_lens_run(session, metric_partial, LensRunStatus.RUNNING)
            await repository.advance_lens_run(
                session,
                metric_partial,
                LensRunStatus.PARTIAL,
                reason=StructuredReason(code="optional_analysis_failed", component="oscillation"),
            )
            await repository.persist_lens_analysis_result(
                session,
                metric_partial,
                _result_input(
                    metric_partial.id,
                    observation.id,
                    run.id,
                    metric_partial.lens_id,
                    LensType.METRIC,
                    LensRunStatus.PARTIAL,
                    StructuredReason(code="optional_analysis_failed", component="oscillation"),
                ),
            )

            for lens_run, lens_type in (
                (metric_failed, LensType.METRIC),
                (alert_failed, LensType.ALERT),
                (log_failed, LensType.LOG),
            ):
                await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
                await repository.advance_lens_run(
                    session,
                    lens_run,
                    LensRunStatus.FAILED,
                    reason=StructuredReason(code="data_source_unavailable"),
                )
                if lens_type is LensType.METRIC:
                    await repository.persist_lens_analysis_result(
                        session,
                        lens_run,
                        _result_input(
                            lens_run.id,
                            observation.id,
                            run.id,
                            lens_run.lens_id,
                            lens_type,
                            LensRunStatus.FAILED,
                        ),
                    )

            await repository.advance_lens_run(session, log_completed, LensRunStatus.RUNNING)
            await repository.advance_lens_run(session, log_completed, LensRunStatus.COMPLETED)
            await repository.persist_lens_analysis_result(
                session,
                log_completed,
                _result_input(
                    log_completed.id,
                    observation.id,
                    run.id,
                    log_completed.lens_id,
                    LensType.LOG,
                    LensRunStatus.COMPLETED,
                ),
            )
            await repository.persist_relationship_evaluation(
                session, run, _relationship_evaluation()
            )
            analysis = await repository.persist_observation_analysis_result(
                session, run, _observation_analysis_input(observation.id, run.id)
            )
            await repository.persist_observation_report(
                session,
                run,
                analysis,
                ObservationReportInput(
                    generated_at=datetime(2026, 8, 23, tzinfo=UTC),
                    format="markdown",
                    content="# Runtime persistence",
                ),
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.COMPLETED)
            run_id = run.id
            await session.commit()

        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            assert restored.status == "completed"
            by_lens_id = {lens_run.lens_id: lens_run for lens_run in restored.lens_runs}
            assert by_lens_id["metric-complete"].analysis_result is not None
            assert by_lens_id["metric-complete"].analysis_result.is_usable
            assert by_lens_id["metric-partial"].analysis_result is not None
            assert by_lens_id["metric-partial"].analysis_result.is_usable
            failed_metric_result = by_lens_id["metric-failed"].analysis_result
            assert failed_metric_result is not None
            assert failed_metric_result.is_usable is False
            assert failed_metric_result.payload["status"] == {
                "state": "failed",
                "error": {"code": "acquisition_failed", "message": "Source unavailable"},
            }
            assert by_lens_id["alert-failed"].analysis_result is None
            assert by_lens_id["log-failed"].analysis_result is None
            assert by_lens_id["log-completed"].analysis_result is not None
            assert by_lens_id["log-completed"].analysis_result.payload["optional_sections"] == []
            assert by_lens_id["log-completed"].analysis_result.payload["nested"] == {
                "jsonb": ["round-trip", {"value": 1}]
            }
            assert restored.observation_analysis_result is not None
            assert restored.observation_analysis_result.report is not None
            assert len(restored.relationship_evaluations) == 1

    asyncio.run(scenario())


def test_postgresql_alert_definition_walking_skeleton_and_empty_rejection(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        service = ObservationDefinitionService(ObservationRepository())
        definition = ObservationCreate.model_validate(
            {
                "name": f"Release health {uuid4()}",
                "objective": "Observe release alerts.",
                "alert_lenses": [
                    {
                        "id": "release-alerts",
                        "type": "alert",
                        "name": "Release alerts",
                        "source": "jira_track_and_release",
                        "selector": {"query": "project = REL", "future_field": "ignored"},
                        "future_field": "ignored",
                    }
                ],
            }
        )
        async with session_factory() as session:
            created = await service.create(session, definition)
            assert created.schema_version == 1
            assert created.lenses == []
            assert created.relationships == []
            assert created.alert_lenses[0].id == "release-alerts"
            assert created.alert_lenses[0].type == "alert"
            assert created.alert_lenses[0].analysis_objectives == []
            assert created.alert_lenses[0].reference_periods == []
            assert created.alert_lenses[0].href == (f"{created.href}/alert-lenses/release-alerts")

            detail = await service.get(session, created.id)
            nested = await service.get_alert_lens(session, created.id, "release-alerts")
            assert detail.alert_lenses[0] == nested
            assert "future_field" not in nested.model_dump_json()

        async def count_definition_rows() -> list[int]:
            async with session_factory() as count_session:
                return [
                    await count_session.scalar(select(func.count()).select_from(model))
                    for model in (
                        ObservationModel,
                        MetricLensModel,
                        AlertLensModel,
                        ObservationRelationshipModel,
                    )
                ]

        async def postgres_session() -> AsyncIterator[AsyncSession]:
            async with session_factory() as request_session:
                yield request_session

        async def postgres_service() -> ObservationDefinitionService:
            return service

        rows_before = await count_definition_rows()
        app.dependency_overrides[get_session] = postgres_session
        app.dependency_overrides[get_service] = postgres_service
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                for payload in ({}, {"lenses": [], "alert_lenses": []}):
                    response = await client.post(
                        "/api/v1/observations",
                        json={
                            "name": "No lenses",
                            "objective": "Must be rejected.",
                            **payload,
                        },
                    )
                    assert response.status_code == 422
                    assert response.json()["code"] == "validation_error"
                    assert await count_definition_rows() == rows_before
        finally:
            app.dependency_overrides.clear()

    asyncio.run(scenario())


def test_postgresql_mixed_definition_order_navigation_and_late_failure_are_atomic(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def count_definition_rows() -> list[int]:
        async with session_factory() as session:
            return [
                await session.scalar(select(func.count()).select_from(model))
                for model in (
                    ObservationModel,
                    MetricLensModel,
                    AlertLensModel,
                    ObservationRelationshipModel,
                )
            ]

    async def scenario() -> None:
        repository = ObservationRepository()
        service = ObservationDefinitionService(repository)
        definition = ObservationCreate.model_validate(
            {
                "name": f"Mixed definition {uuid4()}",
                "objective": "Prove type-local navigation and order.",
                "lenses": [
                    {
                        "id": "shared",
                        "name": "Shared metric",
                        "type": "metric",
                        "metric_id": "shared_metric",
                        "adapter_type": "prometheus",
                        "source_id": "production-prometheus",
                        "query": "avg(shared_metric)",
                        "unit": "count",
                        "analysis_objectives": ["spike"],
                        "reference_periods": ["1d"],
                    },
                    {
                        "id": "pressure",
                        "name": "Pressure",
                        "type": "metric",
                        "metric_id": "pressure",
                        "adapter_type": "prometheus",
                        "source_id": "production-prometheus",
                        "query": "avg(pressure)",
                        "unit": "bar",
                        "analysis_objectives": ["drift"],
                        "reference_periods": [],
                    },
                ],
                "alert_lenses": [
                    {
                        "id": "alert-second",
                        "name": "Second alert",
                        "type": "alert",
                        "source": "jira_track_and_release",
                        "selector": {"query": " project = REL-2 "},
                        "analysis_objectives": ["Second", "First"],
                        "reference_periods": ["7d", "1d"],
                    },
                    {
                        "id": "shared",
                        "name": "Shared alert",
                        "type": "alert",
                        "source": "jira_track_and_release",
                        "selector": {"query": "project = REL-1"},
                    },
                ],
                "relationships": [
                    {
                        "id": "zeta-first",
                        "name": "Pressure and shared metric",
                        "participants": ["pressure", "shared"],
                        "conditions": {},
                        "expected": {
                            "pressure": {"trend": {"direction": "increasing"}},
                            "shared": {"variability": {"state": "low"}},
                        },
                    },
                    {
                        "id": "alpha-second",
                        "name": "Shared metric and pressure",
                        "participants": ["shared", "pressure"],
                        "conditions": {},
                        "expected": {
                            "shared": {"trend": {"direction": "increasing"}},
                            "pressure": {"variability": {"state": "low"}},
                        },
                    },
                ],
            }
        )
        async with session_factory() as session:
            async with session.begin():
                model = await repository.create(session, definition)
            created = service.observation_response(model)
            observation_id = created.id

        async with session_factory() as session:
            restored = await service.get(session, observation_id)
            summaries = await service.list(session)
            metric = await service.get_lens(session, observation_id, "shared")
            alert = await service.get_alert_lens(session, observation_id, "shared")
            assert [lens.id for lens in restored.lenses] == ["shared", "pressure"]
            assert [lens.id for lens in restored.alert_lenses] == ["alert-second", "shared"]
            assert [relationship.id for relationship in restored.relationships] == [
                "zeta-first",
                "alpha-second",
            ]
            assert restored.alert_lenses[0].selector.query == " project = REL-2 "
            assert restored.alert_lenses[0].analysis_objectives == ["Second", "First"]
            assert restored.alert_lenses[0].reference_periods == ["7d", "1d"]
            assert summaries[-1].lenses[0].href == metric.href
            assert summaries[-1].alert_lenses[1].href == alert.href
            assert metric.type == "metric"
            assert alert.type == "alert"
            assert metric.href != alert.href

        definition_before = restored.model_dump()
        rows_before_unknown_alert = await count_definition_rows()

        async def postgres_session() -> AsyncIterator[AsyncSession]:
            async with session_factory() as request_session:
                yield request_session

        async def postgres_service() -> ObservationDefinitionService:
            return service

        app.dependency_overrides[get_session] = postgres_session
        app.dependency_overrides[get_service] = postgres_service
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/observations/{observation_id}/alert-lenses/unknown-alert"
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404
        assert response.json() == {
            "code": "alert_lens_not_found",
            "message": "Alert Lens definition was not found",
        }
        assert await count_definition_rows() == rows_before_unknown_alert
        async with session_factory() as session:
            assert (await service.get(session, observation_id)).model_dump() == definition_before

        before_failure = await count_definition_rows()

        class FailingAfterFlushRepository(ObservationRepository):
            async def create(self, session, definition):
                await super().create(session, definition)
                raise RuntimeError("deliberate late persistence failure")

        failing_service = ObservationDefinitionService(FailingAfterFlushRepository())
        failing_definition = ObservationCreate.model_validate(
            {
                "name": f"Late failure {uuid4()}",
                "objective": "Prove rollback.",
                "alert_lenses": [
                    {
                        "id": "rollback-alert",
                        "name": "Rollback alert",
                        "type": "alert",
                        "source": "jira_track_and_release",
                        "selector": {"query": "project = ROLLBACK"},
                    }
                ],
            }
        )
        async with session_factory() as session:
            with pytest.raises(RuntimeError, match="deliberate late persistence failure"):
                await failing_service.create(session, failing_definition)
        assert await count_definition_rows() == before_failure

    asyncio.run(scenario())


def test_postgresql_alert_definition_ownership_cascade_and_runtime_restriction(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def create_observation_with_alerts() -> UUID:
        async with session_factory() as session:
            observation = ObservationModel(
                name=f"Deletion ownership {uuid4()}",
                objective="Prove Alert child ownership.",
                schema_version=1,
                alert_lenses=[
                    AlertLensModel(
                        lens_id="first-alert",
                        lens_type="alert",
                        name="First alert",
                        source="jira_track_and_release",
                        selector_query="project = FIRST",
                        analysis_objectives=[],
                        reference_periods=[],
                        position=0,
                    ),
                    AlertLensModel(
                        lens_id="second-alert",
                        lens_type="alert",
                        name="Second alert",
                        source="jira_track_and_release",
                        selector_query="project = SECOND",
                        analysis_objectives=[],
                        reference_periods=[],
                        position=1,
                    ),
                ],
            )
            session.add(observation)
            await session.commit()
            return observation.id

    async def count_rows(
        model: type[ObservationModel] | type[AlertLensModel], identifier: UUID
    ) -> int:
        column = model.id if model is ObservationModel else model.observation_id
        async with session_factory() as session:
            return (
                await session.scalar(
                    select(func.count()).select_from(model).where(column == identifier)
                )
                or 0
            )

    async def assert_definition_and_alerts_exist(observation_id: UUID) -> None:
        assert await count_rows(ObservationModel, observation_id) == 1
        assert await count_rows(AlertLensModel, observation_id) == 2

    async def scenario() -> None:
        alert_foreign_key = next(iter(AlertLensModel.__table__.foreign_key_constraints))
        runtime_foreign_key = next(iter(ObservationRunModel.__table__.foreign_key_constraints))
        assert alert_foreign_key.referred_table.name == "observation_definitions"
        assert alert_foreign_key.ondelete == "CASCADE"
        assert runtime_foreign_key.referred_table.name == "observation_definitions"
        assert runtime_foreign_key.ondelete == "RESTRICT"

        async with session_factory() as session:
            connection = await session.connection()
            migrated_alert_foreign_key = await connection.run_sync(
                lambda connection: inspect(connection).get_foreign_keys("alert_lens_definitions")
            )
            migrated_runtime_foreign_key = await connection.run_sync(
                lambda connection: inspect(connection).get_foreign_keys("observation_runs")
            )
        assert migrated_alert_foreign_key == [
            {
                **migrated_alert_foreign_key[0],
                "constrained_columns": ["observation_id"],
                "referred_table": "observation_definitions",
                "referred_columns": ["id"],
                "options": {"ondelete": "CASCADE"},
            }
        ]
        assert migrated_runtime_foreign_key == [
            {
                **migrated_runtime_foreign_key[0],
                "constrained_columns": ["observation_id"],
                "referred_table": "observation_definitions",
                "referred_columns": ["id"],
                "options": {"ondelete": "RESTRICT"},
            }
        ]

        orm_observation_id = await create_observation_with_alerts()
        async with session_factory() as session:
            parent = await session.scalar(
                select(ObservationModel)
                .where(ObservationModel.id == orm_observation_id)
                .options(selectinload(ObservationModel.alert_lenses))
            )
            assert parent is not None
            assert [alert.lens_id for alert in parent.alert_lenses] == [
                "first-alert",
                "second-alert",
            ]
            await session.delete(parent)
            await session.commit()
        assert await count_rows(ObservationModel, orm_observation_id) == 0
        assert await count_rows(AlertLensModel, orm_observation_id) == 0

        sql_observation_id = await create_observation_with_alerts()
        async with session_factory() as session:
            await session.execute(
                delete(ObservationModel).where(ObservationModel.id == sql_observation_id)
            )
            await session.commit()
        assert await count_rows(ObservationModel, sql_observation_id) == 0
        assert await count_rows(AlertLensModel, sql_observation_id) == 0

        restricted_observation_id = await create_observation_with_alerts()
        async with session_factory() as session:
            session.add(
                ObservationRunModel(
                    observation_id=restricted_observation_id,
                    status=ObservationRunStatus.PENDING.value,
                    provenance={},
                    execution_context={},
                )
            )
            await session.commit()

        async with session_factory() as session:
            parent = await session.scalar(
                select(ObservationModel)
                .where(ObservationModel.id == restricted_observation_id)
                .options(selectinload(ObservationModel.alert_lenses))
            )
            assert parent is not None
            await session.delete(parent)
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
        await assert_definition_and_alerts_exist(restricted_observation_id)

        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    delete(ObservationModel).where(ObservationModel.id == restricted_observation_id)
                )
                await session.commit()
            await session.rollback()
        await assert_definition_and_alerts_exist(restricted_observation_id)

    asyncio.run(scenario())


def test_runtime_cardinality_constraints_reject_duplicate_writes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            analysis = await repository.persist_observation_analysis_result(
                session, run, _observation_analysis_input(observation.id, run.id)
            )
            await repository.persist_observation_report(
                session,
                run,
                analysis,
                ObservationReportInput(
                    generated_at=datetime(2026, 8, 23, tzinfo=UTC),
                    format="markdown",
                    content="# First report",
                ),
            )
            await repository.persist_relationship_evaluation(
                session, run, _relationship_evaluation()
            )
            observation_run_id, analysis_id = run.id, analysis.id
            await session.commit()

        async with session_factory() as session:
            session.add(
                ObservationAnalysisResultModel(
                    observation_run_id=observation_run_id,
                    schema_version="1.0",
                    payload={"duplicate": True},
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

            session.add(
                ObservationReportModel(
                    observation_analysis_result_id=analysis_id,
                    generated_at=datetime(2026, 8, 23, tzinfo=UTC),
                    format="markdown",
                    content="# Duplicate report",
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

            session.add(
                RelationshipEvaluationModel(
                    observation_run_id=observation_run_id,
                    relationship_id="temperature-pressure-link",
                    payload={"duplicate": True},
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

    asyncio.run(scenario())
