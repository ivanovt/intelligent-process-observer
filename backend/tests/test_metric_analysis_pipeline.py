from __future__ import annotations

import asyncio
import inspect
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.infrastructure.persistence.models import ObservationModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensRunInput,
    LensRunStatus,
    LensType,
    ObservationRunInput,
    ObservationRunStatus,
)
from app.metrics.contracts import (
    FIXED_ALLOWED_TOOLS,
    MetricAgentCompletion,
    MetricAnalysisWindow,
    MetricHistoryEmpty,
    MetricHistoryPolicy,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSample,
    MetricSeriesAvailable,
)
from app.metrics.pipeline import MetricAnalysisPipeline
from app.metrics.preprocessing import prepare_good_series
from app.metrics.result_builder import MetricResultBuilder
from app.metrics.semantics import semanticize_mandatory

WINDOW_START = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run(coroutine):
    return asyncio.run(coroutine)


def context() -> MetricLensExecutionContext:
    return MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=uuid4(),
            observation_run_id=uuid4(),
            lens_id="coolant-temperature",
            lens_run_id=uuid4(),
            metric_ref="coolant_temperature",
            unit="celsius",
        ),
        provider_scope=MetricProviderScope(
            adapter_type="prometheus",
            source_id="plant-prometheus",
            query="avg(coolant_temperature_celsius)",
        ),
        analysis_window=MetricAnalysisWindow(
            **{"from": WINDOW_START, "to": WINDOW_START + timedelta(seconds=180)}
        ),
        analysis_objectives=("spike", "drift"),
        reference_periods=(),
        history_policy=MetricHistoryPolicy(),
    )


def good_available() -> MetricSeriesAvailable:
    return MetricSeriesAvailable(
        source="prometheus",
        samples=(
            MetricSample(timestamp=WINDOW_START, value=10.0),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=60), value=20.0),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=180), value=40.0),
        ),
    )


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[tuple[MetricProviderScope, MetricAnalysisWindow]] = []

    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAvailable:
        self.requests.append((scope, window))
        return good_available()


class FakeAgent:
    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return MetricAgentCompletion()


class FakeHistoryReader:
    def __init__(self) -> None:
        self.calls = []

    async def load_empty(self, session, execution_context):
        self.calls.append((session, execution_context))
        return MetricHistoryEmpty()


class RecordingRepository:
    def __init__(self, trace: list[str]) -> None:
        self.trace = trace
        self.persisted = []

    async def advance_lens_run(self, session, lens_run, target):
        self.trace.append("repository_transition_flush")
        lens_run.status = target.value
        return lens_run

    async def persist_lens_analysis_result(self, session, lens_run, result):
        self.trace.append("repository_artifact_flush")
        self.persisted.append(result)
        return SimpleNamespace(payload=result.payload, status=result.status.value)


@pytest.fixture(scope="module")
def postgres_url() -> str:
    database_url = os.environ.get("IPO_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set IPO_TEST_DATABASE_URL to run PostgreSQL integration tests")
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
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


def test_context_is_frozen_utc_and_rejects_aliases_or_duplicate_offsets() -> None:
    execution_context = context()
    assert execution_context.analysis_window.from_.tzinfo is UTC
    with pytest.raises(ValidationError):
        execution_context.identity.lens_id = "other"
    with pytest.raises(ValidationError):
        MetricAnalysisWindow(start=WINDOW_START, end=WINDOW_START + timedelta(minutes=1))
    with pytest.raises(ValidationError):
        MetricIdentity(
            observation_id=str(uuid4()),
            observation_run_id=uuid4(),
            lens_id="coolant-temperature",
            lens_run_id=uuid4(),
            metric_ref="coolant_temperature",
            unit="celsius",
        )
    with pytest.raises(ValidationError, match="duplicates"):
        MetricLensExecutionContext(**(context().model_dump() | {"reference_periods": ("1h", "1h")}))


def test_preparation_statistics_and_semantics_are_exact_for_representative_good_series() -> None:
    prepared = prepare_good_series(good_available().samples, context().analysis_window)
    semantics = semanticize_mandatory(prepared, context().analysis_window)

    assert prepared.data_quality == "good"
    assert [sample.timestamp for sample in prepared.samples] == sorted(
        sample.timestamp for sample in prepared.samples
    )
    assert prepared.evidence.mean == pytest.approx(70 / 3)
    assert prepared.evidence.std == pytest.approx(math.sqrt(1400 / 9))
    assert prepared.evidence.min == 10
    assert prepared.evidence.max == 40
    assert prepared.evidence.slope == pytest.approx(1 / 6)
    assert semantics.model_dump() == {
        "trend": {"direction": "increasing", "rate": "fast"},
        "variability": {"state": "low"},
    }


def test_pipeline_projects_only_exact_good_agent_scope_and_two_phase_order() -> None:
    phase_trace: list[str] = []
    provider = FakeProvider()
    agent = FakeAgent()
    history = FakeHistoryReader()
    repository = RecordingRepository(phase_trace)
    pipeline = MetricAnalysisPipeline(
        provider=provider,
        agent=agent,
        history_reader=history,
        repository=repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
        record_phase=phase_trace.append,
    )
    execution_context = context()

    analysis = run(pipeline.analyze(execution_context))
    phase_trace.append("caller_transaction_open")
    lens_run = SimpleNamespace(status="running")
    artifact = run(pipeline.persist_terminal(object(), lens_run, analysis))
    phase_trace.append("caller_commit")

    assert provider.requests == [
        (execution_context.provider_scope, execution_context.analysis_window)
    ]
    assert len(agent.requests) == 1
    request = agent.requests[0]
    assert request.model_dump() == {
        "identity": execution_context.identity.model_dump(),
        "analysis_window": execution_context.analysis_window.model_dump(),
        "analysis_objectives": ("spike", "drift"),
        "data_quality": "good",
        "evidence": analysis.prepared.evidence.model_dump(),
        "semantics": analysis.semantics.model_dump(),
        "allowed_tools": tuple(tool.model_dump() for tool in FIXED_ALLOWED_TOOLS),
        "dataset_ref": analysis.dataset_ref,
    }
    assert "query" not in request.model_dump()
    assert "samples" not in request.model_dump()
    assert len(analysis.dataset_ref) == 32
    assert history.calls == [(ANY, execution_context)]
    assert artifact.status == "completed"
    assert lens_run.status == "completed"
    assert phase_trace == [
        "provider_acquisition",
        "current_preparation",
        "mandatory_semanticization",
        "agent_execution",
        "caller_transaction_open",
        "history_read",
        "lens_run_transition",
        "repository_transition_flush",
        "artifact_insertion_flush",
        "repository_artifact_flush",
        "caller_commit",
    ]
    payload = repository.persisted[0].payload
    assert payload == {
        "schema_version": "1.0",
        "lens_type": "metric",
        "identity": execution_context.identity.model_dump(mode="json"),
        "status": {"state": "completed"},
        "analysis_window": execution_context.analysis_window.model_dump(mode="json", by_alias=True),
        "data_quality": "good",
        "current_state": analysis.semantics.model_dump(),
        "evidence": {"current": analysis.prepared.evidence.model_dump()},
        "provenance": {
            "source": "prometheus",
            "generated_at": "2026-08-27T12:05:00Z",
        },
    }


def test_domain_modules_remain_transport_and_framework_free() -> None:
    import app.metrics.contracts as contracts
    import app.metrics.pipeline as pipeline
    import app.metrics.ports as ports
    import app.metrics.preprocessing as preprocessing
    import app.metrics.semantics as semantics

    source = "\n".join(
        inspect.getsource(module)
        for module in (contracts, ports, preprocessing, semantics, pipeline)
    )
    assert "pydantic_ai" not in source
    assert "app.infrastructure.prometheus" not in source
    assert "sqlalchemy" not in inspect.getsource(ports)


def test_completed_sufficient_metric_round_trips_through_runtime_aggregate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        phase_trace: list[str] = []
        provider = FakeProvider()
        agent = FakeAgent()
        history = FakeHistoryReader()
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=provider,
            agent=agent,
            history_reader=history,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            record_phase=phase_trace.append,
        )
        execution_context = context()

        async with session_factory() as session:
            async with session.begin():
                observation = ObservationModel(
                    id=execution_context.identity.observation_id,
                    name=f"Metric walking skeleton {uuid4()}",
                    objective="Verify completed Metric persistence.",
                    schema_version=1,
                )
                session.add(observation)
                await session.flush()
                observation_run = await repository.create_observation_run(
                    session,
                    ObservationRunInput(
                        id=execution_context.identity.observation_run_id,
                        observation_id=observation.id,
                    ),
                )
                await repository.advance_observation_run(
                    session, observation_run, ObservationRunStatus.RUNNING
                )
                lens_run = await repository.create_lens_run(
                    session,
                    observation_run,
                    LensRunInput(
                        id=execution_context.identity.lens_run_id,
                        lens_id=execution_context.identity.lens_id,
                        lens_type=LensType.METRIC,
                    ),
                )
                await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)

            analysis = await pipeline.analyze(execution_context)
            phase_trace.append("caller_transaction_open")
            async with session.begin():
                await pipeline.persist_terminal(session, lens_run, analysis)
            phase_trace.append("caller_commit")

        async with session_factory() as session:
            restored = await repository.get_observation_run(
                session, execution_context.identity.observation_run_id
            )
            assert restored is not None
            assert len(restored.lens_runs) == 1
            restored_lens_run = restored.lens_runs[0]
            assert restored_lens_run.status == "completed"
            assert restored_lens_run.analysis_result is not None
            assert restored_lens_run.analysis_result.payload == {
                "schema_version": "1.0",
                "lens_type": "metric",
                "identity": execution_context.identity.model_dump(mode="json"),
                "status": {"state": "completed"},
                "analysis_window": execution_context.analysis_window.model_dump(
                    mode="json", by_alias=True
                ),
                "data_quality": "good",
                "current_state": analysis.semantics.model_dump(),
                "evidence": {"current": analysis.prepared.evidence.model_dump()},
                "provenance": {
                    "source": "prometheus",
                    "generated_at": "2026-08-27T12:05:00Z",
                },
            }

        assert len(provider.requests) == 1
        assert len(agent.requests) == 1
        assert len(history.calls) == 1
        assert phase_trace == [
            "provider_acquisition",
            "current_preparation",
            "mandatory_semanticization",
            "agent_execution",
            "caller_transaction_open",
            "history_read",
            "lens_run_transition",
            "artifact_insertion_flush",
            "caller_commit",
        ]

    run(scenario())
