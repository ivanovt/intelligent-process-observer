# ruff: noqa: E501
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
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderFailure,
    AlertProviderImportance,
    AlertProviderRecord,
    AlertProviderScope,
    AlertProviderTimeout,
    AlertRecordsAvailable,
    AlertTerminalOutcome,
)
from app.alerts.pipeline import AlertAnalysisPipeline
from app.alerts.tools import AlertOptionalToolRegistry
from app.core.settings import get_settings
from app.infrastructure.persistence.alert_runtime import persist_alert_terminal
from app.infrastructure.persistence.models import (
    AlertLensModel,
    LensRunModel,
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


def test_alert_zero_record_walking_skeleton_persists_completed_result(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class EmptyProvider:
        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            assert scope.query == "project = RELEASE"
            assert window.to > window.from_
            return AlertRecordsAvailable(source=scope.source)

    class FailOnCallAgent:
        async def complete(self, *args: object) -> object:
            raise AssertionError("zero record path must not invoke the Alert agent")

    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        phases: list[str] = []
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_run = await repository.create_lens_run(
                session,
                run,
                LensRunInput(lens_id="release-alerts", lens_type=LensType.ALERT),
            )
            await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
            context = AlertLensExecutionContext(
                identity=AlertIdentity(
                    observation_id=observation.id,
                    observation_run_id=run.id,
                    lens_id=lens_run.lens_id,
                    lens_run_id=lens_run.id,
                ),
                provider_scope=AlertProviderScope(
                    source="fake-alert-provider", query="project = RELEASE"
                ),
                analysis_window=AlertAnalysisWindow(
                    **{
                        "from": datetime(2026, 9, 1, tzinfo=UTC),
                        "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                    }
                ),
                lens_name="Release alerts",
            )
            outcome = await AlertAnalysisPipeline(
                provider=EmptyProvider(), agent=FailOnCallAgent(), record_phase=phases.append
            ).analyze(context)
            phases.append("transaction_open")
            await persist_alert_terminal(session, lens_run, outcome, repository)
            run_id = run.id
            await session.commit()

        assert phases == [
            "provider_acquisition",
            "current_normalization",
            "mandatory_analysis",
            "reference_acquisition",
            "zero_record_gate",
            "result_build",
            "transaction_open",
        ]
        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            persisted_run = next(run for run in restored.lens_runs if run.id == lens_run.id)
            assert persisted_run.status == "completed" and persisted_run.reason is None
            assert persisted_run.analysis_result is not None
            artifact = persisted_run.analysis_result
            assert artifact.result_type == "alert" and artifact.status == "completed"
            assert artifact.schema_version == "1.0"
            assert artifact.payload["identity"] == context.identity.model_dump(mode="json")
            assert artifact.payload["lens_type"] == "alert"
            assert artifact.payload["status"] == "completed"
            assert artifact.payload["analysis_timestamp"] == "2026-09-01T01:00:00Z"
            assert artifact.payload["analysis_window"] == {
                "start": "2026-09-01T00:00:00Z",
                "end": "2026-09-01T01:00:00Z",
            }
            assert artifact.payload["provenance"]["source_provider"] == "fake-alert-provider"
            assert "generated_at" in artifact.payload["provenance"]
            assert artifact.payload["alerts"] == []
            assert artifact.payload["alert_activity"] == {
                "record_count": 0,
                "occurrence_count": 0,
            }
            assert artifact.payload["status_distribution"] == {
                "active": 0,
                "resolved": 0,
                "unknown": 0,
            }
            assert artifact.payload["comparisons"] == []
            assert artifact.payload["findings"] == []
            assert artifact.payload["overall_importance"] == "none"
            assert "duration_statistics" not in artifact.payload
            assert "provider_importance_distribution" not in artifact.payload

    asyncio.run(scenario())


def test_every_mandatory_alert_failure_has_no_result_artifact(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        reasons = (
            StructuredReason(code="current_query_failed"),
            StructuredReason(code="current_query_timeout"),
            StructuredReason(code="invalid_records", component="current_normalization"),
            StructuredReason(code="deterministic_analysis_failed"),
            StructuredReason(code="agent_failed"),
            StructuredReason(code="agent_timeout"),
        )
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_runs: list[tuple[UUID, StructuredReason]] = []
            for index, reason in enumerate(reasons):
                lens_run = await repository.create_lens_run(
                    session,
                    run,
                    LensRunInput(lens_id=f"failure-{index}", lens_type=LensType.ALERT),
                )
                await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
                await persist_alert_terminal(
                    session,
                    lens_run,
                    AlertTerminalOutcome(status=LensRunStatus.FAILED, reason=reason),
                    repository,
                )
                lens_runs.append((lens_run.id, reason))
            run_id = run.id
            await session.commit()
        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            by_id = {item.id: item for item in restored.lens_runs}
            for lens_run_id, reason in lens_runs:
                persisted = by_id[lens_run_id]
                assert persisted.status == "failed" and persisted.analysis_result is None
                assert persisted.reason == reason.model_dump(mode="json")

    asyncio.run(scenario())


def test_current_acquisition_failures_persist_exact_reason_without_artifact(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        def __init__(self, response: object) -> None:
            self.response = response

        async def acquire(self, *args: object) -> object:
            if isinstance(self.response, Exception):
                raise self.response
            return self.response

    class Agent:
        async def complete(self, request: object) -> object:
            raise AssertionError("agent must not run")

    def fail_analyzer(records: object) -> object:
        raise AssertionError("current acquisition failures must not invoke the analyzer")

    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        cases = (
            (AlertProviderFailure(diagnostic="typed"), "current_query_failed"),
            (AlertProviderTimeout(diagnostic="typed"), "current_query_timeout"),
            (RuntimeError("thrown"), "current_query_failed"),
            (TimeoutError("thrown"), "current_query_timeout"),
        )
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            persisted: list[tuple[UUID, str]] = []
            for index, (response, code) in enumerate(cases):
                lens_run = await repository.create_lens_run(
                    session, run, LensRunInput(lens_id=f"current-{index}", lens_type=LensType.ALERT)
                )
                await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
                context = AlertLensExecutionContext(
                    identity=AlertIdentity(
                        observation_id=observation.id,
                        observation_run_id=run.id,
                        lens_id=lens_run.lens_id,
                        lens_run_id=lens_run.id,
                    ),
                    provider_scope=AlertProviderScope(source="fake", query="failure"),
                    analysis_window=AlertAnalysisWindow(
                        **{
                            "from": datetime(2026, 9, 1, tzinfo=UTC),
                            "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                        }
                    ),
                    lens_name="Failure",
                )
                outcome = await AlertAnalysisPipeline(
                    provider=Provider(response), agent=Agent(), analyzer=fail_analyzer
                ).analyze(context)
                await persist_alert_terminal(session, lens_run, outcome, repository)
                persisted.append((lens_run.id, code))
            run_id = run.id
            await session.commit()
        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            by_id = {item.id: item for item in restored.lens_runs}
            for lens_run_id, code in persisted:
                assert by_id[lens_run_id].reason == {"code": code, "component": None}
                assert by_id[lens_run_id].analysis_result is None

    asyncio.run(scenario())


async def _persist_failed_alert_pipeline(
    session_factory: async_sessionmaker[AsyncSession],
    provider: object,
    *,
    analyzer: object | None = None,
) -> tuple[str, dict[str, str] | None, bool]:
    repository = RuntimePersistenceRepository()

    class Agent:
        async def complete(self, request: object) -> object:
            raise AssertionError("failed paths must not invoke the agent")

    async with session_factory() as session:
        observation = await _seed_observation(session)
        run = await repository.create_observation_run(
            session, ObservationRunInput(observation_id=observation.id)
        )
        await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
        lens_run = await repository.create_lens_run(
            session, run, LensRunInput(lens_id="failure", lens_type=LensType.ALERT)
        )
        await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
        context = AlertLensExecutionContext(
            identity=AlertIdentity(
                observation_id=observation.id,
                observation_run_id=run.id,
                lens_id=lens_run.lens_id,
                lens_run_id=lens_run.id,
            ),
            provider_scope=AlertProviderScope(source="fake", query="failure"),
            analysis_window=AlertAnalysisWindow(
                **{
                    "from": datetime(2026, 9, 1, tzinfo=UTC),
                    "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                }
            ),
            lens_name="Failure",
        )
        arguments: dict[str, object] = {"provider": provider, "agent": Agent()}
        if analyzer is not None:
            arguments["analyzer"] = analyzer
        outcome = await AlertAnalysisPipeline(**arguments).analyze(context)
        await persist_alert_terminal(session, lens_run, outcome, repository)
        run_id, lens_run_id = run.id, lens_run.id
        await session.commit()
    async with session_factory() as session:
        restored = await repository.get_observation_run(session, run_id)
        assert restored is not None
        persisted = next(item for item in restored.lens_runs if item.id == lens_run_id)
        return persisted.status, persisted.reason, persisted.analysis_result is not None


def test_all_invalid_current_fails_without_artifact(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        async def acquire(self, *args: object) -> AlertRecordsAvailable:
            return AlertRecordsAvailable(
                source="fake",
                records=(
                    {"id": "bad", "started_at": "not-a-time"},
                    {
                        "id": "duplicate",
                        "title": "one",
                        "started_at": "2026-09-01T00:00:00Z",
                        "source_status": "open",
                    },
                    {
                        "id": "duplicate",
                        "title": "two",
                        "started_at": "2026-09-01T00:00:00Z",
                        "source_status": "open",
                    },
                ),
            )

    status, reason, has_artifact = asyncio.run(
        _persist_failed_alert_pipeline(session_factory, Provider())
    )
    assert status == "failed" and reason == {
        "code": "invalid_records",
        "component": "current_normalization",
    }
    assert not has_artifact


def test_mandatory_analysis_failure_is_terminal_without_artifact(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        async def acquire(self, *args: object) -> AlertRecordsAvailable:
            return AlertRecordsAvailable(
                source="fake",
                records=(
                    AlertProviderRecord(
                        id="valid",
                        title="Valid",
                        started_at=datetime(2026, 9, 1, 0, 30, tzinfo=UTC),
                        source_status="Open",
                    ),
                ),
            )

    analyzer_calls = 0

    def fail_analyzer(records: tuple[object, ...]) -> object:
        nonlocal analyzer_calls
        analyzer_calls += 1
        assert len(records) == 1
        raise RuntimeError("mandatory failure")

    status, reason, has_artifact = asyncio.run(
        _persist_failed_alert_pipeline(session_factory, Provider(), analyzer=fail_analyzer)
    )
    assert analyzer_calls == 1
    assert status == "failed" and reason == {
        "code": "deterministic_analysis_failed",
        "component": None,
    }
    assert not has_artifact


def test_nonempty_all_out_of_scope_fails_while_empty_response_completes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        def __init__(self, records: tuple[object, ...]) -> None:
            self.records = records

        async def acquire(self, *args: object) -> AlertRecordsAvailable:
            return AlertRecordsAvailable(source="fake", records=self.records)

    outside = (
        {
            "id": "outside",
            "title": "Outside",
            "started_at": "2026-09-01T01:00:00Z",
            "source_status": "open",
        },
    )
    status, reason, has_artifact = asyncio.run(
        _persist_failed_alert_pipeline(session_factory, Provider(outside))
    )
    assert status == "failed" and reason == {
        "code": "invalid_records",
        "component": "current_normalization",
    }
    assert not has_artifact
    empty_status, empty_reason, empty_has_artifact = asyncio.run(
        _persist_failed_alert_pipeline(session_factory, Provider(()))
    )
    assert empty_status == "completed" and empty_reason is None and empty_has_artifact


def _nonzero_alert_record(*, occurrences: int) -> AlertProviderRecord:
    return AlertProviderRecord(
        id="ALERT-77",
        title="Persisted alert",
        description="canonical",
        started_at=datetime(2026, 8, 31, 23, tzinfo=UTC),
        ended_at=None,
        source_status="Open",
        provider_importance=AlertProviderImportance(type="priority", value="Highest"),
        occurrence_count=occurrences,
        source_ref="jira:ALERT-77",
    )


def _assert_nonzero_alert_persists(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    occurrences: int,
    tool_registry_factory: object | None = None,
) -> dict[str, object]:
    class Provider:
        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            if window.from_ == datetime(2026, 8, 31, tzinfo=UTC):
                raise RuntimeError("reference unavailable")
            return AlertRecordsAvailable(
                source=scope.source, records=(_nonzero_alert_record(occurrences=occurrences),)
            )

    class Agent:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self, request: object, tools: object | None = None
        ) -> AlertAgentCompletion:
            self.calls += 1
            assert (
                request.lens_name == "Persisted alerts"
                and request.lens_description == "exact bounded description"
            )
            assert (
                request.current_records[0].id == "ALERT-77"
                and request.mandatory_evidence.occurrence_count == occurrences
            )
            assert set(request.model_dump()) == {
                "lens_name",
                "lens_description",
                "current_records",
                "mandatory_evidence",
                "comparisons",
            }
            if tools is not None:
                await tools.execute("recurrence_concentration_analysis", {})
                await tools.execute("duration_outlier_analysis", {})
                await tools.execute("reference_pattern_analysis", {})
            return AlertAgentCompletion(
                findings=(
                    AlertFinding(
                        id="persisted", statement="grounded", evidence_refs=("alerts.ALERT-77",)
                    ),
                ),
                overall_importance="high",
            )

    async def scenario() -> None:
        repository, agent = RuntimePersistenceRepository(), Agent()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_run = await repository.create_lens_run(
                session, run, LensRunInput(lens_id="persisted-alerts", lens_type=LensType.ALERT)
            )
            await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
            context = AlertLensExecutionContext(
                identity=AlertIdentity(
                    observation_id=observation.id,
                    observation_run_id=run.id,
                    lens_id=lens_run.lens_id,
                    lens_run_id=lens_run.id,
                ),
                provider_scope=AlertProviderScope(
                    source="fake-alert-provider", query="opaque query"
                ),
                analysis_window=AlertAnalysisWindow(
                    **{
                        "from": datetime(2026, 9, 1, tzinfo=UTC),
                        "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                    }
                ),
                lens_name="Persisted alerts",
                lens_description="exact bounded description",
            )
            outcome = await AlertAnalysisPipeline(
                provider=Provider(), agent=agent, tool_registry_factory=tool_registry_factory
            ).analyze(context)
            await persist_alert_terminal(session, lens_run, outcome, repository)
            run_id, lens_run_id = run.id, lens_run.id
            await session.commit()
        assert agent.calls == 1
        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            artifact = next(
                item for item in restored.lens_runs if item.id == lens_run_id
            ).analysis_result
            assert artifact is not None and artifact.status == "completed"
            assert artifact.payload["alerts"][0]["id"] == "ALERT-77"
            assert artifact.payload["alerts"][0]["source_ref"] == "jira:ALERT-77"
            assert artifact.payload["alert_activity"] == {
                "record_count": 1,
                "occurrence_count": occurrences,
            }
            assert artifact.payload["findings"] == [
                {"id": "persisted", "statement": "grounded", "evidence_refs": ["alerts.ALERT-77"]}
            ]
            assert artifact.payload["overall_importance"] == "high" and "query" not in str(
                artifact.payload
            )
            return artifact.payload

    return asyncio.run(scenario())


def test_nonzero_zero_occurrence_invokes_agent_with_exact_projection_and_persists(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _assert_nonzero_alert_persists(session_factory, occurrences=0)


def test_optional_failures_continue_and_persist_only_minimal_trace(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    def registry(records: tuple[object, ...], evidence: object) -> AlertOptionalToolRegistry:
        tools = AlertOptionalToolRegistry(records, evidence)

        def failed() -> object:
            raise RuntimeError("transient")

        def timed_out() -> object:
            raise TimeoutError("transient")

        tools._evaluators["recurrence_concentration_analysis"] = timed_out
        tools._evaluators["reference_pattern_analysis"] = failed
        return tools

    payload = _assert_nonzero_alert_persists(
        session_factory, occurrences=1, tool_registry_factory=registry
    )
    assert payload["optional_tool_execution"] == {
        "unsuccessful_calls": [
            {"tool": "recurrence_concentration_analysis", "status": "timeout"},
            {"tool": "reference_pattern_analysis", "status": "failed"},
        ]
    }
    assert "diagnostic" not in str(payload) and "ordinal" not in str(payload)


def test_representative_nonzero_alert_result_round_trips_strictly(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _assert_nonzero_alert_persists(session_factory, occurrences=3)


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


def test_invalid_current_subset_persists_correlated_partial(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            return AlertRecordsAvailable(
                source=scope.source,
                records=(
                    AlertProviderRecord(
                        id="usable", title="Usable", started_at=window.from_, source_status="open"
                    ),
                    {"title": "Missing ID", "started_at": "2026-09-01T00:00:00Z"},
                    {"id": "missing-title", "started_at": "2026-09-01T00:00:00Z"},
                    {"id": "bad-start", "title": "Bad start", "started_at": "invalid"},
                    {
                        "id": "bad-end",
                        "title": "Bad end",
                        "started_at": "2026-09-01T00:00:00Z",
                        "ended_at": "invalid",
                    },
                    {
                        "id": "reversed",
                        "title": "Reversed",
                        "started_at": "2026-09-01T00:30:00Z",
                        "ended_at": "2026-09-01T00:00:00Z",
                    },
                ),
            )

    class Agent:
        async def complete(self, request: object) -> AlertAgentCompletion:
            return AlertAgentCompletion(findings=(), overall_importance="low")

    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_run = await repository.create_lens_run(
                session, run, LensRunInput(lens_id="partial-alert", lens_type=LensType.ALERT)
            )
            await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
            context = AlertLensExecutionContext(
                identity=AlertIdentity(
                    observation_id=observation.id,
                    observation_run_id=run.id,
                    lens_id=lens_run.lens_id,
                    lens_run_id=lens_run.id,
                ),
                provider_scope=AlertProviderScope(source="fake-alert-provider", query="partial"),
                analysis_window=AlertAnalysisWindow(
                    **{
                        "from": datetime(2026, 9, 1, tzinfo=UTC),
                        "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                    }
                ),
                lens_name="Partial alerts",
                reference_periods=("1d",),
            )
            outcome = await AlertAnalysisPipeline(provider=Provider(), agent=Agent()).analyze(
                context
            )
            assert outcome.status is LensRunStatus.PARTIAL
            await persist_alert_terminal(session, lens_run, outcome, repository)
            run_id, lens_run_id = run.id, lens_run.id
            await session.commit()
        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            persisted = next(item for item in restored.lens_runs if item.id == lens_run_id)
            assert persisted.status == "partial"
            assert persisted.reason == {
                "code": "invalid_records",
                "component": "current_normalization",
            }
            assert persisted.analysis_result is not None
            assert persisted.analysis_result.status == "partial"
            assert persisted.analysis_result.payload["reason"] == persisted.reason
            assert persisted.analysis_result.payload["identity"]["lens_run_id"] == str(lens_run_id)

    asyncio.run(scenario())


def test_current_incompleteness_precedes_reference_and_persists_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        reference_requested = False

        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            if window.from_ == datetime(2026, 9, 1, tzinfo=UTC):
                return AlertRecordsAvailable(
                    source=scope.source,
                    records=(
                        _nonzero_alert_record(occurrences=1),
                        {"id": "invalid", "started_at": "invalid"},
                    ),
                )
            self.reference_requested = True
            raise RuntimeError("reference unavailable")

    class Agent:
        async def complete(self, request: object) -> AlertAgentCompletion:
            return AlertAgentCompletion(findings=(), overall_importance="low")

    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        provider = Provider()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_run = await repository.create_lens_run(
                session, run, LensRunInput(lens_id="precedence-alert", lens_type=LensType.ALERT)
            )
            await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
            context = AlertLensExecutionContext(
                identity=AlertIdentity(
                    observation_id=observation.id,
                    observation_run_id=run.id,
                    lens_id=lens_run.lens_id,
                    lens_run_id=lens_run.id,
                ),
                provider_scope=AlertProviderScope(source="fake-alert-provider", query="precedence"),
                analysis_window=AlertAnalysisWindow(
                    **{
                        "from": datetime(2026, 9, 1, tzinfo=UTC),
                        "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                    }
                ),
                lens_name="Precedence alerts",
                reference_periods=("1d",),
            )
            outcome = await AlertAnalysisPipeline(provider=provider, agent=Agent()).analyze(context)
            assert provider.reference_requested
            assert outcome.status is LensRunStatus.PARTIAL
            assert outcome.reason is not None and outcome.reason.model_dump() == {
                "code": "invalid_records",
                "component": "current_normalization",
            }
            assert "reference_unavailable" not in str(outcome.artifact.payload)
            await persist_alert_terminal(session, lens_run, outcome, repository)
            run_id, lens_run_id = run.id, lens_run.id
            await session.commit()

        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            persisted = next(item for item in restored.lens_runs if item.id == lens_run_id)
            assert persisted.status == "partial"
            assert persisted.reason == {
                "code": "invalid_records",
                "component": "current_normalization",
            }
            assert persisted.analysis_result is not None
            assert persisted.analysis_result.status == "partial"
            assert persisted.analysis_result.payload["reason"] == persisted.reason
            assert persisted.analysis_result.payload["identity"]["lens_run_id"] == str(lens_run_id)
            assert "reference_unavailable" not in str(persisted.analysis_result.payload)

    asyncio.run(scenario())


def test_all_references_unavailable_persists_usable_reference_partial(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            if window.from_ == datetime(2026, 9, 1, tzinfo=UTC):
                return AlertRecordsAvailable(
                    source=scope.source, records=(_nonzero_alert_record(occurrences=1),)
                )
            if window.from_ == datetime(2026, 8, 31, tzinfo=UTC):
                raise RuntimeError("reference error")
            if window.from_ == datetime(2026, 8, 25, tzinfo=UTC):
                raise TimeoutError("reference timeout")
            return AlertRecordsAvailable(
                source=scope.source, records=({"id": "malformed", "started_at": "bad"},)
            )

    class Agent:
        async def complete(self, request: object) -> AlertAgentCompletion:
            return AlertAgentCompletion(findings=(), overall_importance="low")

    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_run = await repository.create_lens_run(
                session, run, LensRunInput(lens_id="reference-partial", lens_type=LensType.ALERT)
            )
            await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
            context = AlertLensExecutionContext(
                identity=AlertIdentity(
                    observation_id=observation.id,
                    observation_run_id=run.id,
                    lens_id=lens_run.lens_id,
                    lens_run_id=lens_run.id,
                ),
                provider_scope=AlertProviderScope(source="fake-alert-provider", query="partial"),
                analysis_window=AlertAnalysisWindow(
                    **{
                        "from": datetime(2026, 9, 1, tzinfo=UTC),
                        "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                    }
                ),
                lens_name="Reference partial alerts",
                reference_periods=("1d", "7d", "14d"),
            )
            outcome = await AlertAnalysisPipeline(provider=Provider(), agent=Agent()).analyze(
                context
            )
            assert outcome.status is LensRunStatus.PARTIAL
            assert outcome.reason is not None and outcome.reason.model_dump() == {
                "code": "reference_unavailable",
                "component": "reference_periods",
            }
            assert outcome.artifact.payload["comparisons"] == []
            await persist_alert_terminal(session, lens_run, outcome, repository)
            run_id, lens_run_id = run.id, lens_run.id
            await session.commit()

        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            persisted = next(item for item in restored.lens_runs if item.id == lens_run_id)
            assert persisted.status == "partial"
            assert persisted.reason == {
                "code": "reference_unavailable",
                "component": "reference_periods",
            }
            assert persisted.analysis_result is not None
            assert persisted.analysis_result.status == "partial"
            assert persisted.analysis_result.payload["reason"] == persisted.reason
            assert persisted.analysis_result.payload["comparisons"] == []

    asyncio.run(scenario())


def test_successful_empty_reference_yields_zero_comparison_without_partial(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Provider:
        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            if window.from_ == datetime(2026, 9, 1, tzinfo=UTC):
                return AlertRecordsAvailable(
                    source=scope.source, records=(_nonzero_alert_record(occurrences=3),)
                )
            return AlertRecordsAvailable(source=scope.source)

    class Agent:
        async def complete(self, request: object) -> AlertAgentCompletion:
            return AlertAgentCompletion(findings=(), overall_importance="low")

    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            await repository.advance_observation_run(session, run, ObservationRunStatus.RUNNING)
            lens_run = await repository.create_lens_run(
                session, run, LensRunInput(lens_id="empty-reference", lens_type=LensType.ALERT)
            )
            await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
            context = AlertLensExecutionContext(
                identity=AlertIdentity(
                    observation_id=observation.id,
                    observation_run_id=run.id,
                    lens_id=lens_run.lens_id,
                    lens_run_id=lens_run.id,
                ),
                provider_scope=AlertProviderScope(source="fake-alert-provider", query="complete"),
                analysis_window=AlertAnalysisWindow(
                    **{
                        "from": datetime(2026, 9, 1, tzinfo=UTC),
                        "to": datetime(2026, 9, 1, 1, tzinfo=UTC),
                    }
                ),
                lens_name="Empty reference alerts",
                reference_periods=("1d",),
            )
            outcome = await AlertAnalysisPipeline(provider=Provider(), agent=Agent()).analyze(
                context
            )
            assert outcome.status is LensRunStatus.COMPLETED and outcome.reason is None
            assert outcome.artifact.payload["comparisons"] == [
                {
                    "offset": "1d",
                    "occurrence_comparison": {
                        "current": 3,
                        "reference": 0,
                        "delta": 3,
                        "direction": "increased",
                    },
                }
            ]
            await persist_alert_terminal(session, lens_run, outcome, repository)
            run_id, lens_run_id = run.id, lens_run.id
            await session.commit()

        async with session_factory() as session:
            restored = await repository.get_observation_run(session, run_id)
            assert restored is not None
            persisted = next(item for item in restored.lens_runs if item.id == lens_run_id)
            assert persisted.status == "completed" and persisted.reason is None
            assert persisted.analysis_result is not None
            assert persisted.analysis_result.status == "completed"
            assert "reason" not in persisted.analysis_result.payload
            assert persisted.analysis_result.payload["comparisons"] == [
                {
                    "offset": "1d",
                    "occurrence_comparison": {
                        "current": 3,
                        "reference": 0,
                        "delta": 3,
                        "direction": "increased",
                    },
                }
            ]

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


def test_lens_runs_allow_same_id_across_types_and_reject_same_type_duplicates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        repository = RuntimePersistenceRepository()
        lens_id = f"shared-lens-{uuid4()}"
        async with session_factory() as session:
            observation = await _seed_observation(session)
            observation_run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            metric_lens_run = await repository.create_lens_run(
                session,
                observation_run,
                LensRunInput(lens_id=lens_id, lens_type=LensType.METRIC),
            )
            alert_lens_run = await repository.create_lens_run(
                session,
                observation_run,
                LensRunInput(lens_id=lens_id, lens_type=LensType.ALERT),
            )
            await repository.advance_lens_run(session, metric_lens_run, LensRunStatus.RUNNING)
            await repository.advance_lens_run(session, metric_lens_run, LensRunStatus.COMPLETED)
            await repository.advance_lens_run(session, alert_lens_run, LensRunStatus.RUNNING)
            await repository.advance_lens_run(
                session,
                alert_lens_run,
                LensRunStatus.FAILED,
                reason=StructuredReason(code="data_source_unavailable"),
            )
            observation_run_id = observation_run.id
            await session.commit()

        async with session_factory() as session:
            restored = await repository.get_observation_run(session, observation_run_id)
            assert restored is not None
            restored_by_type = {lens_run.lens_type: lens_run for lens_run in restored.lens_runs}
            assert set(restored_by_type) == {LensType.METRIC.value, LensType.ALERT.value}
            assert restored_by_type[LensType.METRIC.value].status == LensRunStatus.COMPLETED.value
            assert restored_by_type[LensType.ALERT.value].status == LensRunStatus.FAILED.value
            assert restored_by_type[LensType.ALERT.value].reason == {
                "code": "data_source_unavailable",
                "component": None,
            }

            session.add(
                LensRunModel(
                    observation_run_id=observation_run_id,
                    lens_id=lens_id,
                    lens_type=LensType.METRIC.value,
                    status=LensRunStatus.PENDING.value,
                    provenance={},
                    execution_context={},
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        async with session_factory() as session:
            restored = await repository.get_observation_run(session, observation_run_id)
            assert restored is not None
            assert {(lens_run.lens_type, lens_run.lens_id) for lens_run in restored.lens_runs} == {
                (LensType.METRIC.value, lens_id),
                (LensType.ALERT.value, lens_id),
            }

    asyncio.run(scenario())


def test_final_migration_upgrades_and_guards_unsafe_downgrade(
    postgres_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", postgres_url)

    async def assert_constraint_and_alert_table(
        *, expected_constraint: tuple[str, list[str]], alert_table_exists: bool
    ) -> None:
        async with session_factory() as session:
            connection = await session.connection()
            constraints = await connection.run_sync(
                lambda connection: inspect(connection).get_unique_constraints("lens_runs")
            )
            table_names = await connection.run_sync(
                lambda connection: inspect(connection).get_table_names()
            )
        assert expected_constraint in [
            (constraint["name"], constraint["column_names"]) for constraint in constraints
        ]
        assert ("alert_lens_definitions" in table_names) is alert_table_exists

    async def create_unsafe_same_id_rows() -> tuple[UUID, UUID, UUID]:
        repository = RuntimePersistenceRepository()
        async with session_factory() as session:
            observation = await _seed_observation(session)
            observation_run = await repository.create_observation_run(
                session, ObservationRunInput(observation_id=observation.id)
            )
            for lens_type in (LensType.METRIC, LensType.ALERT):
                await repository.create_lens_run(
                    session,
                    observation_run,
                    LensRunInput(lens_id="unsafe-downgrade-id", lens_type=lens_type),
                )
            alert = AlertLensModel(
                observation_id=observation.id,
                lens_id="unsafe-alert-definition",
                lens_type="alert",
                name="Unsafe downgrade alert",
                source="jira_track_and_release",
                selector_query="project = UNSAFE",
                analysis_objectives=[],
                reference_periods=[],
                position=0,
            )
            session.add(alert)
            await session.commit()
            return observation.id, observation_run.id, alert.id

    async def remove_cross_type_duplicate_rows() -> None:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM lens_runs
                    WHERE (observation_run_id, lens_id) IN (
                        SELECT observation_run_id, lens_id
                        FROM lens_runs
                        GROUP BY observation_run_id, lens_id
                        HAVING COUNT(DISTINCT lens_type) > 1
                    )
                    """
                )
            )
            await session.commit()

    async def assert_unsafe_rows_preserved(
        observation_id: UUID, observation_run_id: UUID, alert_id: UUID
    ) -> None:
        async with session_factory() as session:
            alert = await session.get(AlertLensModel, alert_id)
            assert alert is not None and alert.observation_id == observation_id
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ObservationRunModel)
                    .where(ObservationRunModel.id == observation_run_id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    text(
                        "SELECT count(*) FROM lens_runs "
                        "WHERE observation_run_id = :observation_run_id"
                    ).bindparams(observation_run_id=observation_run_id)
                )
                == 2
            )

    asyncio.run(
        assert_constraint_and_alert_table(
            expected_constraint=(
                "uq_lens_runs_observation_run_id_lens_type_lens_id",
                ["observation_run_id", "lens_type", "lens_id"],
            ),
            alert_table_exists=True,
        )
    )
    unsafe_identity = asyncio.run(create_unsafe_same_id_rows())
    with pytest.raises(RuntimeError, match="Cannot downgrade"):
        command.downgrade(config, "20260823_01")
    asyncio.run(assert_unsafe_rows_preserved(*unsafe_identity))
    asyncio.run(
        assert_constraint_and_alert_table(
            expected_constraint=(
                "uq_lens_runs_observation_run_id_lens_type_lens_id",
                ["observation_run_id", "lens_type", "lens_id"],
            ),
            alert_table_exists=True,
        )
    )

    asyncio.run(remove_cross_type_duplicate_rows())
    command.downgrade(config, "20260823_01")
    asyncio.run(
        assert_constraint_and_alert_table(
            expected_constraint=(
                "lens_runs_observation_run_id_lens_id_key",
                ["observation_run_id", "lens_id"],
            ),
            alert_table_exists=False,
        )
    )
    command.upgrade(config, "head")
    asyncio.run(
        assert_constraint_and_alert_table(
            expected_constraint=(
                "uq_lens_runs_observation_run_id_lens_type_lens_id",
                ["observation_run_id", "lens_type", "lens_id"],
            ),
            alert_table_exists=True,
        )
    )
