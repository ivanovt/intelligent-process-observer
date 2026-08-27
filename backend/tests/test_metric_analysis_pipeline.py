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
    CompletedInsufficientMetricResult,
    MetricAgentCompletion,
    MetricAnalysisWindow,
    MetricEvidence,
    MetricHistoryEmpty,
    MetricHistoryPolicy,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSample,
    MetricSemantics,
    MetricSeriesAvailable,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
    PreparedInsufficientSeries,
)
from app.metrics.pipeline import MetricAnalysisPipeline
from app.metrics.preprocessing import prepare_series
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


def available_from_values(values: tuple[float, ...]) -> MetricSeriesAvailable:
    return MetricSeriesAvailable(
        source="prometheus",
        samples=tuple(
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=index * 60), value=value)
            for index, value in enumerate(values)
        ),
    )


def degraded_available() -> MetricSeriesAvailable:
    return MetricSeriesAvailable(
        source="prometheus",
        samples=(
            MetricSample(timestamp=WINDOW_START, value=10.0),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=30), value=float("nan")),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=60), value=20.0),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=90), value=float("inf")),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=150), value=float("-inf")),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=180), value=40.0),
        ),
    )


class FakeProvider:
    def __init__(self, available: MetricSeriesAvailable | None = None) -> None:
        self.requests: list[tuple[MetricProviderScope, MetricAnalysisWindow]] = []
        self.available = available or good_available()

    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAvailable:
        self.requests.append((scope, window))
        return self.available


class FakeAgent:
    def __init__(self, failure: Exception | None = None) -> None:
        self.requests = []
        self.failure = failure

    async def complete(self, request):
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
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
    prepared = prepare_series(good_available().samples, context().analysis_window)
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


@pytest.mark.parametrize(
    ("available", "quality"),
    [
        (good_available(), "good"),
        (degraded_available(), "degraded"),
        (available_from_values((float("nan"), 10.0, float("inf"), 20.0)), "insufficient"),
    ],
)
def test_preparation_filters_non_finite_samples_and_classifies_every_quality_boundary(
    available: MetricSeriesAvailable, quality: str
) -> None:
    prepared = prepare_series(available.samples, context().analysis_window)

    assert prepared.data_quality == quality
    assert all(math.isfinite(sample.value) for sample in prepared.samples)
    if quality == "insufficient":
        assert isinstance(prepared, PreparedInsufficientSeries)
        assert "evidence" not in prepared.model_dump()
    else:
        assert prepared.evidence.model_dump() == pytest.approx(
            {"mean": 70 / 3, "std": math.sqrt(1400 / 9), "min": 10.0, "max": 40.0, "slope": 1 / 6}
        )


def test_preparation_calculates_irregular_and_constant_series_with_finite_evidence() -> None:
    irregular_window = MetricAnalysisWindow(
        **{"from": WINDOW_START, "to": WINDOW_START + timedelta(seconds=93)}
    )
    irregular = prepare_series(
        (
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=93), value=13.0),
            MetricSample(timestamp=WINDOW_START, value=5.0),
            MetricSample(timestamp=WINDOW_START + timedelta(seconds=17), value=7.0),
        ),
        irregular_window,
    )
    constant = prepare_series(
        available_from_values((3.0, 3.0, 3.0)).samples, context().analysis_window
    )

    assert irregular.evidence.mean == pytest.approx(25 / 3)
    assert irregular.evidence.std == pytest.approx(math.sqrt(104 / 9))
    assert irregular.evidence.slope == pytest.approx(0.0838657061302161)
    assert all(math.isfinite(value) for value in irregular.evidence.model_dump().values())
    assert constant.evidence.model_dump() == {
        "mean": 3.0,
        "std": 0.0,
        "min": 3.0,
        "max": 3.0,
        "slope": 0.0,
    }


def _semantic_prepared(*, slope: float, residual_scale: float) -> PreparedGoodSeries:
    return PreparedGoodSeries(
        data_quality="good",
        samples=(),
        evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=slope),
        residuals=(-residual_scale, residual_scale),
    )


@pytest.mark.parametrize(
    ("value", "direction", "rate"),
    [
        (math.nextafter(0.05, 0.0), "stable", "not_classified"),
        (0.05, "increasing", "slow"),
        (math.nextafter(0.05, math.inf), "increasing", "slow"),
        (math.nextafter(0.15, 0.0), "increasing", "slow"),
        (0.15, "increasing", "moderate"),
        (math.nextafter(0.15, math.inf), "increasing", "moderate"),
        (math.nextafter(0.35, 0.0), "increasing", "moderate"),
        (0.35, "increasing", "fast"),
        (math.nextafter(0.35, math.inf), "increasing", "fast"),
        (math.nextafter(-0.05, 0.0), "stable", "not_classified"),
        (-0.05, "decreasing", "slow"),
        (math.nextafter(-0.05, -math.inf), "decreasing", "slow"),
        (math.nextafter(-0.15, 0.0), "decreasing", "slow"),
        (-0.15, "decreasing", "moderate"),
        (math.nextafter(-0.15, -math.inf), "decreasing", "moderate"),
        (math.nextafter(-0.35, 0.0), "decreasing", "moderate"),
        (-0.35, "decreasing", "fast"),
        (math.nextafter(-0.35, -math.inf), "decreasing", "fast"),
    ],
)
def test_semanticizes_every_adr_153_trend_boundary(value: float, direction: str, rate: str) -> None:
    one_second_window = MetricAnalysisWindow(
        **{"from": WINDOW_START, "to": WINDOW_START + timedelta(seconds=1)}
    )
    semantics = semanticize_mandatory(
        _semantic_prepared(slope=value, residual_scale=0.0), one_second_window
    )

    assert semantics.trend.model_dump() == {"direction": direction, "rate": rate}


@pytest.mark.parametrize(
    ("value", "state"),
    [
        (math.nextafter(0.05, 0.0), "low"),
        (0.05, "moderate"),
        (math.nextafter(0.05, math.inf), "moderate"),
        (math.nextafter(0.15, 0.0), "moderate"),
        (0.15, "high"),
        (math.nextafter(0.15, math.inf), "high"),
    ],
)
def test_semanticizes_every_adr_153_variability_boundary(value: float, state: str) -> None:
    one_second_window = MetricAnalysisWindow(
        **{"from": WINDOW_START, "to": WINDOW_START + timedelta(seconds=1)}
    )
    semantics = semanticize_mandatory(
        _semantic_prepared(slope=0.0, residual_scale=value), one_second_window
    )

    assert semantics.variability.state == state


def test_semanticizes_constant_scale_without_division_and_rejects_public_non_finite_values() -> (
    None
):
    one_second_window = MetricAnalysisWindow(
        **{"from": WINDOW_START, "to": WINDOW_START + timedelta(seconds=1)}
    )
    prepared = PreparedGoodSeries(
        data_quality="good",
        samples=(),
        evidence=MetricEvidence(mean=0.0, std=0.0, min=0.0, max=0.0, slope=0.0),
        residuals=(0.0, 0.0),
    )

    assert semanticize_mandatory(prepared, one_second_window) == MetricSemantics(
        trend=MetricTrend(direction="stable", rate="not_classified"),
        variability=MetricVariability(state="low"),
    )
    with pytest.raises(ValidationError):
        MetricEvidence(mean=float("nan"), std=0.0, min=0.0, max=0.0, slope=0.0)


def test_pipeline_projects_degraded_and_resilient_insufficient_agent_requests() -> None:
    degraded_context = context()
    degraded_provider = FakeProvider(degraded_available())
    degraded_agent = FakeAgent()
    degraded_pipeline = MetricAnalysisPipeline(
        provider=degraded_provider,
        agent=degraded_agent,
        history_reader=FakeHistoryReader(),
        repository=RecordingRepository([]),
    )
    degraded = run(degraded_pipeline.analyze(degraded_context))

    degraded_request = degraded_agent.requests[0]
    assert degraded_request.model_dump() == {
        "identity": degraded_context.identity.model_dump(),
        "analysis_window": degraded_context.analysis_window.model_dump(),
        "analysis_objectives": degraded_context.analysis_objectives,
        "data_quality": "degraded",
        "evidence": degraded.prepared.evidence.model_dump(),
        "semantics": degraded.semantics.model_dump(),
        "allowed_tools": tuple(tool.model_dump() for tool in FIXED_ALLOWED_TOOLS),
        "dataset_ref": degraded.dataset_ref,
    }
    assert degraded.dataset_ref is not None

    insufficient_context = context()
    insufficient_agent = FakeAgent(RuntimeError("adapter unavailable"))
    insufficient_history = FakeHistoryReader()
    insufficient_repository = RecordingRepository([])
    insufficient_pipeline = MetricAnalysisPipeline(
        provider=FakeProvider(available_from_values((float("nan"), 10.0, 20.0))),
        agent=insufficient_agent,
        history_reader=insufficient_history,
        repository=insufficient_repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
    )
    insufficient = run(insufficient_pipeline.analyze(insufficient_context))
    lens_run = SimpleNamespace(status="running")
    artifact = run(insufficient_pipeline.persist_terminal(object(), lens_run, insufficient))

    request = insufficient_agent.requests[0]
    assert request.model_dump() == {
        "identity": insufficient_context.identity.model_dump(),
        "analysis_window": insufficient_context.analysis_window.model_dump(),
        "data_quality": "insufficient",
    }
    assert insufficient.insufficient_agent_outcome is not None
    assert insufficient.insufficient_agent_outcome.state == "operational_failure"
    assert insufficient.dataset_ref is None
    assert insufficient.semantics is None
    assert insufficient_history.calls == []
    assert lens_run.status == "completed"
    assert artifact.status == "completed"
    assert insufficient_repository.persisted[0].payload == {
        "schema_version": "1.0",
        "lens_type": "metric",
        "identity": insufficient_context.identity.model_dump(mode="json"),
        "status": {"state": "completed"},
        "analysis_window": insufficient_context.analysis_window.model_dump(
            mode="json", by_alias=True
        ),
        "data_quality": "insufficient",
        "provenance": {"source": "prometheus", "generated_at": "2026-08-27T12:05:00Z"},
    }
    with pytest.raises(ValidationError):
        CompletedInsufficientMetricResult.model_validate(
            insufficient_repository.persisted[0].payload | {"evidence": {}}
        )


@pytest.mark.parametrize(
    ("available", "agent_failure", "quality"),
    [
        (degraded_available(), None, "degraded"),
        (
            available_from_values((float("nan"), 10.0, 20.0)),
            RuntimeError("unavailable"),
            "insufficient",
        ),
    ],
)
def test_degraded_and_insufficient_metric_outcomes_round_trip_through_runtime_aggregate(
    session_factory: async_sessionmaker[AsyncSession],
    available: MetricSeriesAvailable,
    agent_failure: Exception | None,
    quality: str,
) -> None:
    async def scenario() -> None:
        execution_context = context()
        provider = FakeProvider(available)
        agent = FakeAgent(agent_failure)
        history = FakeHistoryReader()
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=provider,
            agent=agent,
            history_reader=history,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
        )

        async with session_factory() as session:
            async with session.begin():
                observation = ObservationModel(
                    id=execution_context.identity.observation_id,
                    name=f"Metric {quality} result {uuid4()}",
                    objective="Verify Metric quality persistence.",
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
            async with session.begin():
                await pipeline.persist_terminal(session, lens_run, analysis)

        async with session_factory() as session:
            restored = await repository.get_observation_run(
                session, execution_context.identity.observation_run_id
            )
            assert restored is not None
            restored_lens_run = restored.lens_runs[0]
            assert restored_lens_run.status == "completed"
            assert restored_lens_run.analysis_result is not None
            payload = restored_lens_run.analysis_result.payload
            assert payload["data_quality"] == quality
            assert payload["status"] == {"state": "completed"}
            assert payload["identity"] == execution_context.identity.model_dump(mode="json")
            assert payload["analysis_window"] == execution_context.analysis_window.model_dump(
                mode="json", by_alias=True
            )
            assert payload["provenance"] == {
                "source": "prometheus",
                "generated_at": "2026-08-27T12:05:00Z",
            }
            if quality == "degraded":
                assert set(payload) == {
                    "schema_version",
                    "lens_type",
                    "identity",
                    "status",
                    "analysis_window",
                    "data_quality",
                    "current_state",
                    "evidence",
                    "provenance",
                }
            else:
                assert set(payload) == {
                    "schema_version",
                    "lens_type",
                    "identity",
                    "status",
                    "analysis_window",
                    "data_quality",
                    "provenance",
                }

        assert len(provider.requests) == 1
        assert len(agent.requests) == 1
        assert len(history.calls) == (1 if quality == "degraded" else 0)
        if quality == "insufficient":
            assert analysis.insufficient_agent_outcome is not None
            assert analysis.insufficient_agent_outcome.state == "operational_failure"

    run(scenario())
