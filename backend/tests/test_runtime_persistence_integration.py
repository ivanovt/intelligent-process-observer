from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.infrastructure.persistence.models import (
    AlertLensModel,
    MetricLensModel,
    ObservationAnalysisResultModel,
    ObservationModel,
    ObservationRelationshipModel,
    ObservationReportModel,
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

            rows_before = [
                await session.scalar(select(func.count()).select_from(model))
                for model in (
                    ObservationModel,
                    MetricLensModel,
                    AlertLensModel,
                    ObservationRelationshipModel,
                )
            ]
            with pytest.raises(ValueError, match="at least one Lens"):
                ObservationCreate.model_validate(
                    {"name": "No lenses", "objective": "Must be rejected.", "lenses": []}
                )
            rows_after = [
                await session.scalar(select(func.count()).select_from(model))
                for model in (
                    ObservationModel,
                    MetricLensModel,
                    AlertLensModel,
                    ObservationRelationshipModel,
                )
            ]
            assert rows_before == rows_after

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
