from __future__ import annotations

import asyncio
import inspect
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.infrastructure.persistence.models import ObservationModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunInput,
    LensRunStatus,
    LensType,
    ObservationRunInput,
    ObservationRunStatus,
    StructuredReason,
)
from app.metrics.contracts import (
    FIXED_ALLOWED_TOOLS,
    CompletedInsufficientMetricResult,
    CurrentMetricAcquisitionFailedError,
    CurrentMetricSeriesMalformedError,
    FailedMetricResult,
    MandatoryMetricAnalysisFailedError,
    MetricAgentCompletion,
    MetricAnalysisWindow,
    MetricCurrentAcquisitionFailed,
    MetricCurrentSeriesMalformed,
    MetricEvidence,
    MetricHistoryCandidate,
    MetricHistoryCandidates,
    MetricHistoryEmpty,
    MetricHistoryPolicy,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
    MetricProviderScope,
    MetricReferenceUnavailable,
    MetricSample,
    MetricSemantics,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAcquisitionTimeout,
    MetricSeriesAvailable,
    MetricSeriesUnavailable,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
    PreparedInsufficientSeries,
)
from app.metrics.pipeline import MetricAnalysisPipeline
from app.metrics.preprocessing import prepare_series
from app.metrics.references import compare_reference, reference_window
from app.metrics.result_builder import MetricResultBuilder
from app.metrics.semantics import semanticize_mandatory

WINDOW_START = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run(coroutine):
    return asyncio.run(coroutine)


def context(*, reference_periods: tuple[str, ...] = ()) -> MetricLensExecutionContext:
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
        reference_periods=reference_periods,
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


class SequencedProvider:
    def __init__(self, outcomes) -> None:
        self.requests: list[tuple[MetricProviderScope, MetricAnalysisWindow]] = []
        self.outcomes = list(outcomes)

    async def acquire(self, scope, window):
        self.requests.append((scope, window))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def available_for_window(
    window: MetricAnalysisWindow, values: tuple[float, ...]
) -> MetricSeriesAvailable:
    timestamps = (window.from_, window.from_ + timedelta(seconds=60), window.to)
    return MetricSeriesAvailable(
        source="prometheus",
        samples=tuple(
            MetricSample(timestamp=timestamp, value=value)
            for timestamp, value in zip(timestamps, values, strict=True)
        ),
    )


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

    async def load(self, session, execution_context):
        self.calls.append((session, execution_context))
        return MetricHistoryEmpty()


class CandidateHistoryReader:
    def __init__(self, candidates: tuple[MetricHistoryCandidate, ...]) -> None:
        self.calls = []
        self.candidates = candidates

    async def load(self, session, execution_context):
        self.calls.append((session, execution_context))
        return MetricHistoryCandidates(candidates=self.candidates)


class RecordingRepository:
    def __init__(self, trace: list[str]) -> None:
        self.trace = trace
        self.persisted = []

    async def advance_lens_run(self, session, lens_run, target, *, reason=None):
        self.trace.append("repository_transition_flush")
        lens_run.status = target.value
        lens_run.reason = None if reason is None else reason.model_dump(mode="json")
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
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=provider,
            agent=agent,
            history_reader=repository,
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
        phase_trace: list[str] = []
        execution_context = context()
        provider = FakeProvider(available)
        agent = FakeAgent(agent_failure)
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=provider,
            agent=agent,
            history_reader=repository,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            record_phase=phase_trace.append,
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
            phase_trace.append("caller_transaction_open")
            async with session.begin():
                await pipeline.persist_terminal(session, lens_run, analysis)
            phase_trace.append("caller_commit")

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
        if quality == "degraded":
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
        else:
            assert phase_trace == [
                "provider_acquisition",
                "current_preparation",
                "agent_execution",
                "caller_transaction_open",
                "lens_run_transition",
                "artifact_insertion_flush",
                "caller_commit",
            ]
        if quality == "insufficient":
            assert analysis.insufficient_agent_outcome is not None
            assert analysis.insufficient_agent_outcome.state == "operational_failure"

    run(scenario())


@pytest.mark.parametrize(
    ("failure", "error_type", "expected_error"),
    [
        (
            MetricCurrentAcquisitionFailed(diagnostic="provider endpoint unavailable"),
            CurrentMetricAcquisitionFailedError,
            {
                "code": "current_metric_acquisition_failed",
                "message": "Current metric data acquisition failed.",
            },
        ),
        (
            MetricCurrentSeriesMalformed(diagnostic="duplicate timestamp"),
            CurrentMetricSeriesMalformedError,
            {
                "code": "current_metric_series_malformed",
                "message": "Current metric series is malformed.",
            },
        ),
        (
            MetricMandatoryAnalysisFailure(diagnostic="overflow in statistics"),
            MandatoryMetricAnalysisFailedError,
            {
                "code": "mandatory_metric_analysis_failed",
                "message": "Mandatory metric analysis failed.",
            },
        ),
    ],
)
def test_failed_builder_uses_only_fixed_public_error_and_minimal_payload(
    failure, error_type, expected_error
) -> None:
    execution_context = context()
    result, envelope = MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)).failed(
        execution_context, failure
    )

    assert isinstance(result.status.error, error_type)
    assert result.model_dump(mode="json", by_alias=True) == {
        "schema_version": "1.0",
        "lens_type": "metric",
        "identity": execution_context.identity.model_dump(mode="json"),
        "status": {"state": "failed", "error": expected_error},
        "analysis_window": execution_context.analysis_window.model_dump(mode="json", by_alias=True),
        "provenance": {"source": "prometheus", "generated_at": "2026-08-27T12:05:00Z"},
    }
    assert envelope.status is LensRunStatus.FAILED
    with pytest.raises(ValidationError):
        FailedMetricResult.model_validate(result.model_dump() | {"evidence": {}})
    with pytest.raises(ValidationError):
        FailedMetricResult.model_validate(
            result.model_dump()
            | {"status": {"state": "failed", "error": expected_error | {"x": "y"}}}
        )


class FailingSufficientBuilder(MetricResultBuilder):
    def completed_sufficient(self, context, prepared, semantics):
        raise ValueError("result validation unexpectedly failed")


@pytest.mark.parametrize(
    ("provider", "result_builder", "expected_error", "expected_agent_calls", "phase_prefix"),
    [
        (
            FakeProvider(MetricSeriesUnavailable(diagnostic="prometheus unavailable")),
            MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            "current_metric_acquisition_failed",
            0,
            ["provider_acquisition"],
        ),
        (
            FakeProvider(MetricSeriesAcquisitionFailure(diagnostic="provider rejected query")),
            MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            "current_metric_acquisition_failed",
            0,
            ["provider_acquisition"],
        ),
        (
            FakeProvider(MetricSeriesAcquisitionTimeout(diagnostic="provider timed out")),
            MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            "current_metric_acquisition_failed",
            0,
            ["provider_acquisition"],
        ),
        (
            FakeProvider(
                MetricSeriesAvailable(
                    source="prometheus",
                    samples=(
                        MetricSample(timestamp=WINDOW_START, value=10.0),
                        MetricSample(timestamp=WINDOW_START, value=20.0),
                    ),
                )
            ),
            MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            "current_metric_series_malformed",
            0,
            ["provider_acquisition", "current_preparation"],
        ),
        (
            FakeProvider(
                MetricSeriesAvailable(
                    source="prometheus",
                    samples=(
                        MetricSample(timestamp=WINDOW_START - timedelta(seconds=1), value=10.0),
                        MetricSample(timestamp=WINDOW_START, value=20.0),
                        MetricSample(timestamp=WINDOW_START + timedelta(seconds=60), value=30.0),
                    ),
                )
            ),
            MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            "current_metric_series_malformed",
            0,
            ["provider_acquisition", "current_preparation"],
        ),
        (
            FakeProvider(),
            FailingSufficientBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            "mandatory_metric_analysis_failed",
            1,
            [
                "provider_acquisition",
                "current_preparation",
                "mandatory_semanticization",
                "agent_execution",
            ],
        ),
    ],
)
def test_current_technical_failures_are_decided_before_terminal_persistence(
    provider,
    result_builder,
    expected_error,
    expected_agent_calls,
    phase_prefix,
) -> None:
    phase_trace: list[str] = []
    agent = FakeAgent()
    history = FakeHistoryReader()
    repository = RecordingRepository(phase_trace)
    pipeline = MetricAnalysisPipeline(
        provider=provider,
        agent=agent,
        history_reader=history,
        repository=repository,
        result_builder=result_builder,
        record_phase=phase_trace.append,
    )

    analysis = run(pipeline.analyze(context()))
    phase_trace.append("caller_transaction_open")
    lens_run = SimpleNamespace(status="running", reason=None)
    artifact = run(pipeline.persist_terminal(object(), lens_run, analysis))
    phase_trace.append("caller_commit")

    assert analysis.failure is not None
    assert analysis.terminal_result.payload["status"] == {
        "state": "failed",
        "error": {
            "code": expected_error,
            "message": {
                "current_metric_acquisition_failed": "Current metric data acquisition failed.",
                "current_metric_series_malformed": "Current metric series is malformed.",
                "mandatory_metric_analysis_failed": "Mandatory metric analysis failed.",
            }[expected_error],
        },
    }
    assert len(agent.requests) == expected_agent_calls
    assert history.calls == []
    assert lens_run.status == "failed"
    assert lens_run.reason == {"code": expected_error, "component": None}
    assert artifact.status == "failed"
    assert phase_trace == phase_prefix + [
        "caller_transaction_open",
        "lens_run_transition",
        "repository_transition_flush",
        "artifact_insertion_flush",
        "repository_artifact_flush",
        "caller_commit",
    ]


@pytest.mark.parametrize(
    ("stage", "expected_agent_calls"),
    [("statistics", 0), ("semanticization", 0), ("result_validation", 1)],
)
def test_unexpected_mandatory_stage_failures_produce_minimal_failed_result(
    monkeypatch, stage: str, expected_agent_calls: int
) -> None:
    import app.metrics.pipeline as pipeline_module

    if stage == "statistics":
        monkeypatch.setattr(
            pipeline_module,
            "prepare_series",
            lambda samples, window: (_ for _ in ()).throw(ArithmeticError("statistics overflow")),
        )
        result_builder = MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5))
    elif stage == "semanticization":
        monkeypatch.setattr(
            pipeline_module,
            "semanticize_mandatory",
            lambda prepared, window: (_ for _ in ()).throw(ValueError("semanticization failure")),
        )
        result_builder = MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5))
    else:
        result_builder = FailingSufficientBuilder(lambda: WINDOW_START + timedelta(minutes=5))
    agent = FakeAgent()
    history = FakeHistoryReader()
    pipeline = MetricAnalysisPipeline(
        provider=FakeProvider(),
        agent=agent,
        history_reader=history,
        repository=RecordingRepository([]),
        result_builder=result_builder,
    )

    analysis = run(pipeline.analyze(context()))

    assert isinstance(analysis.failure, MetricMandatoryAnalysisFailure)
    assert analysis.terminal_result.payload["status"] == {
        "state": "failed",
        "error": {
            "code": "mandatory_metric_analysis_failed",
            "message": "Mandatory metric analysis failed.",
        },
    }
    assert len(agent.requests) == expected_agent_calls
    assert history.calls == []


@pytest.mark.parametrize(
    ("case", "expected_error", "expected_agent_calls"),
    [
        ("acquisition", "current_metric_acquisition_failed", 0),
        ("malformed", "current_metric_series_malformed", 0),
        ("mandatory", "mandatory_metric_analysis_failed", 1),
    ],
)
def test_failed_metric_outcomes_round_trip_through_runtime_aggregate(
    session_factory: async_sessionmaker[AsyncSession],
    case: str,
    expected_error: str,
    expected_agent_calls: int,
) -> None:
    async def scenario() -> None:
        phase_trace: list[str] = []
        execution_context = context()
        if case == "acquisition":
            provider = FakeProvider(MetricSeriesUnavailable(diagnostic="provider unavailable"))
            result_builder = MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5))
        elif case == "malformed":
            provider = FakeProvider(
                MetricSeriesAvailable(
                    source="prometheus",
                    samples=(
                        MetricSample(timestamp=WINDOW_START, value=10.0),
                        MetricSample(timestamp=WINDOW_START, value=20.0),
                    ),
                )
            )
            result_builder = MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5))
        else:
            provider = FakeProvider()
            result_builder = FailingSufficientBuilder(lambda: WINDOW_START + timedelta(minutes=5))
        agent = FakeAgent()
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=provider,
            agent=agent,
            history_reader=repository,
            repository=repository,
            result_builder=result_builder,
            record_phase=phase_trace.append,
        )

        async with session_factory() as session:
            async with session.begin():
                observation = ObservationModel(
                    id=execution_context.identity.observation_id,
                    name=f"Metric failed result {case} {uuid4()}",
                    objective="Verify failed Metric persistence.",
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
            assert analysis.failure is not None
            phase_trace.append("caller_transaction_open")
            async with session.begin():
                await pipeline.persist_terminal(session, lens_run, analysis)
            phase_trace.append("caller_commit")

        async with session_factory() as session:
            restored = await repository.get_observation_run(
                session, execution_context.identity.observation_run_id
            )
            assert restored is not None
            restored_lens_run = restored.lens_runs[0]
            assert restored_lens_run.status == "failed"
            assert restored_lens_run.reason == {"code": expected_error, "component": None}
            assert restored_lens_run.analysis_result is not None
            assert restored_lens_run.analysis_result.status == "failed"
            assert restored_lens_run.analysis_result.payload == analysis.terminal_result.payload

        assert len(agent.requests) == expected_agent_calls
        expected_pre_transaction_phases = {
            "acquisition": ["provider_acquisition"],
            "malformed": ["provider_acquisition", "current_preparation"],
            "mandatory": [
                "provider_acquisition",
                "current_preparation",
                "mandatory_semanticization",
                "agent_execution",
            ],
        }[case]
        assert phase_trace == expected_pre_transaction_phases + [
            "caller_transaction_open",
            "lens_run_transition",
            "artifact_insertion_flush",
            "caller_commit",
        ]

    run(scenario())


def test_reference_windows_and_comparison_relations_are_current_relative() -> None:
    execution_context = context(reference_periods=("1h",))
    reference_analysis_window = reference_window(execution_context.analysis_window, "1h")
    assert reference_analysis_window.model_dump(by_alias=True) == {
        "from": WINDOW_START - timedelta(hours=1),
        "to": WINDOW_START + timedelta(seconds=180) - timedelta(hours=1),
    }

    current = prepare_series(good_available().samples, execution_context.analysis_window)
    current_semantics = semanticize_mandatory(current, execution_context.analysis_window)
    reference = prepare_series(
        available_for_window(reference_analysis_window, (40.0, 30.0, 20.0)).samples,
        reference_analysis_window,
    )
    reference_semantics = semanticize_mandatory(reference, reference_analysis_window)
    comparison, evidence = compare_reference(
        offset="1h",
        window=reference_analysis_window,
        current=current,
        current_semantics=current_semantics,
        reference=reference,
        reference_semantics=reference_semantics,
    )

    assert comparison.model_dump(by_alias=True) == {
        "offset": "1h",
        "analysis_window": reference_analysis_window.model_dump(by_alias=True),
        "level": {"relation": "lower"},
        "trend": {
            "direction": "decreasing",
            "rate": "fast",
            "direction_relation": "different",
            "rate_relation": "same",
        },
        "variability": {"state": "moderate", "relation": "lower"},
    }
    assert evidence.offset == comparison.offset
    assert evidence.analysis_window == comparison.analysis_window
    assert evidence.relative_level_change == pytest.approx(-0.25)


def test_extreme_finite_reference_means_do_not_create_a_false_partial_result() -> None:
    execution_context = context(reference_periods=("1h",))
    reference_analysis_window = reference_window(execution_context.analysis_window, "1h")
    largest_finite = math.nextafter(math.inf, 0.0)
    provider = SequencedProvider(
        (
            available_for_window(
                execution_context.analysis_window,
                (largest_finite, largest_finite, largest_finite),
            ),
            available_for_window(
                reference_analysis_window,
                (-largest_finite, -largest_finite, -largest_finite),
            ),
        )
    )
    repository = RecordingRepository([])
    pipeline = MetricAnalysisPipeline(
        provider=provider,
        agent=FakeAgent(),
        history_reader=FakeHistoryReader(),
        repository=repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
    )

    analysis = run(pipeline.analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)
    artifact = run(pipeline.persist_terminal(object(), lens_run, analysis))

    assert analysis.reference_diagnostics == ()
    assert artifact.status == "completed"
    assert lens_run.status == "completed"
    assert lens_run.reason is None
    reference_evidence = repository.persisted[0].payload["evidence"]["reference_periods"][0]
    assert reference_evidence["relative_level_change"] == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("reference_outcome", "category"),
    [
        (MetricSeriesUnavailable(diagnostic="upstream unavailable"), "acquisition"),
        (
            MetricSeriesAvailable(
                source="prometheus",
                samples=(
                    MetricSample(timestamp=WINDOW_START - timedelta(hours=1), value=10.0),
                    MetricSample(timestamp=WINDOW_START - timedelta(hours=1), value=20.0),
                ),
            ),
            "malformed",
        ),
        (
            MetricSeriesAvailable(
                source="prometheus",
                samples=(
                    MetricSample(
                        timestamp=WINDOW_START - timedelta(hours=1, seconds=1), value=10.0
                    ),
                    MetricSample(timestamp=WINDOW_START - timedelta(hours=1), value=20.0),
                    MetricSample(
                        timestamp=WINDOW_START - timedelta(hours=1) + timedelta(seconds=60),
                        value=30.0,
                    ),
                ),
            ),
            "malformed",
        ),
        (None, "insufficient"),
    ],
)
def test_each_unavailable_reference_yields_only_reference_partial(
    reference_outcome, category: str
) -> None:
    execution_context = context(reference_periods=("1h",))
    reference_analysis_window = reference_window(execution_context.analysis_window, "1h")
    if reference_outcome is None:
        reference_outcome = available_for_window(
            reference_analysis_window, (float("nan"), 10.0, 20.0)
        )
    provider = SequencedProvider((good_available(), reference_outcome))
    repository = RecordingRepository([])
    pipeline = MetricAnalysisPipeline(
        provider=provider,
        agent=FakeAgent(),
        history_reader=FakeHistoryReader(),
        repository=repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
    )

    analysis = run(pipeline.analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)
    artifact = run(pipeline.persist_terminal(object(), lens_run, analysis))

    assert [request[1] for request in provider.requests] == [
        execution_context.analysis_window,
        reference_analysis_window,
    ]
    assert analysis.reference_diagnostics == (
        MetricReferenceUnavailable(
            offset="1h", category=category, diagnostic=analysis.reference_diagnostics[0].diagnostic
        ),
    )
    assert artifact.status == "partial"
    assert lens_run.status == "partial"
    assert lens_run.reason == {
        "code": "reference_unavailable",
        "component": "reference_periods",
    }
    payload = repository.persisted[0].payload
    assert payload["reason"] == lens_run.reason
    assert "reference_periods" not in payload
    assert "reference_periods" not in payload["evidence"]


def test_reference_successes_preserve_configured_order_around_a_failed_offset() -> None:
    execution_context = context(reference_periods=("1h", "1d", "1w"))
    first_window = reference_window(execution_context.analysis_window, "1h")
    third_window = reference_window(execution_context.analysis_window, "1w")
    provider = SequencedProvider(
        (
            good_available(),
            available_for_window(first_window, (10.0, 20.0, 40.0)),
            MetricSeriesAcquisitionTimeout(diagnostic="timeout"),
            available_for_window(third_window, (40.0, 30.0, 20.0)),
        )
    )
    phase_trace: list[str] = []
    repository = RecordingRepository(phase_trace)
    pipeline = MetricAnalysisPipeline(
        provider=provider,
        agent=FakeAgent(),
        history_reader=FakeHistoryReader(),
        repository=repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
        record_phase=phase_trace.append,
    )

    analysis = run(pipeline.analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)
    run(pipeline.persist_terminal(object(), lens_run, analysis))

    assert [window for _, window in provider.requests] == [
        execution_context.analysis_window,
        first_window,
        reference_window(execution_context.analysis_window, "1d"),
        third_window,
    ]
    assert [(item.offset, item.category) for item in analysis.reference_diagnostics] == [
        ("1d", "acquisition")
    ]
    payload = repository.persisted[0].payload
    assert [item["offset"] for item in payload["reference_periods"]] == ["1h", "1w"]
    assert [item["offset"] for item in payload["evidence"]["reference_periods"]] == ["1h", "1w"]
    assert payload["status"] == {"state": "partial"}
    assert payload["reason"] == {"code": "reference_unavailable", "component": "reference_periods"}
    assert (
        phase_trace.index("mandatory_semanticization")
        < phase_trace.index("reference_acquisition")
        < phase_trace.index("agent_execution")
        < phase_trace.index("reference_comparison")
    )


def test_reference_partial_round_trips_through_runtime_aggregate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        phase_trace: list[str] = []
        execution_context = context(reference_periods=("1h", "1d"))
        first_window = reference_window(execution_context.analysis_window, "1h")
        provider = SequencedProvider(
            (
                good_available(),
                available_for_window(first_window, (10.0, 20.0, 40.0)),
                MetricSeriesUnavailable(diagnostic="reference unavailable"),
            )
        )
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=provider,
            agent=FakeAgent(),
            history_reader=repository,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            record_phase=phase_trace.append,
        )

        async with session_factory() as session:
            async with session.begin():
                observation = ObservationModel(
                    id=execution_context.identity.observation_id,
                    name=f"Metric reference partial {uuid4()}",
                    objective="Verify reference partial persistence.",
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
            restored_lens_run = restored.lens_runs[0]
            assert restored_lens_run.status == "partial"
            assert restored_lens_run.reason == {
                "code": "reference_unavailable",
                "component": "reference_periods",
            }
            assert restored_lens_run.analysis_result is not None
            assert restored_lens_run.analysis_result.status == "partial"
            assert restored_lens_run.analysis_result.payload == analysis.terminal_result.payload

        assert phase_trace == [
            "provider_acquisition",
            "current_preparation",
            "mandatory_semanticization",
            "reference_acquisition",
            "reference_preparation",
            "reference_semanticization",
            "reference_acquisition",
            "agent_execution",
            "reference_comparison",
            "caller_transaction_open",
            "history_read",
            "lens_run_transition",
            "artifact_insertion_flush",
            "caller_commit",
        ]

    run(scenario())


def test_current_insufficiency_does_not_acquire_or_partial_configured_references() -> None:
    execution_context = context(reference_periods=("1h", "1d"))
    provider = SequencedProvider((available_from_values((float("nan"), 10.0, 20.0)),))
    repository = RecordingRepository([])
    pipeline = MetricAnalysisPipeline(
        provider=provider,
        agent=FakeAgent(),
        history_reader=FakeHistoryReader(),
        repository=repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
    )

    analysis = run(pipeline.analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)
    run(pipeline.persist_terminal(object(), lens_run, analysis))

    assert [window for _, window in provider.requests] == [execution_context.analysis_window]
    assert analysis.reference_diagnostics == ()
    assert lens_run.status == "completed"
    assert repository.persisted[0].payload["data_quality"] == "insufficient"
    assert "reason" not in repository.persisted[0].payload


@pytest.mark.parametrize("history_failure", [False, True])
def test_fake_reader_history_outcomes_round_trip_through_runtime_aggregate(
    session_factory: async_sessionmaker[AsyncSession],
    history_failure: bool,
    monkeypatch,
) -> None:
    async def scenario() -> None:
        phase_trace: list[str] = []
        execution_context = context()
        candidate_id = uuid4()
        history = CandidateHistoryReader(
            (
                MetricHistoryCandidate(
                    lens_run_id=candidate_id,
                    analysis_window=MetricAnalysisWindow(
                        **{
                            "from": WINDOW_START - timedelta(minutes=1),
                            "to": WINDOW_START + timedelta(minutes=2),
                        }
                    ),
                    status="completed",
                    data_quality="good",
                    mean=10.0,
                ),
            )
        )
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=FakeProvider(),
            agent=FakeAgent(),
            history_reader=history,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            record_phase=phase_trace.append,
        )

        async with session_factory() as session:
            async with session.begin():
                observation = ObservationModel(
                    id=execution_context.identity.observation_id,
                    name=f"Metric History result {uuid4()}",
                    objective="Verify fake-reader Metric History persistence.",
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
            restored_lens_run = restored.lens_runs[0]
            assert restored_lens_run.analysis_result is not None
            payload = restored_lens_run.analysis_result.payload
            if history_failure:
                assert restored_lens_run.status == "partial"
                assert restored_lens_run.reason == {
                    "code": "history_analysis_failed",
                    "component": "history",
                }
                assert "history" not in payload
                assert "history" not in payload["evidence"]
            else:
                assert restored_lens_run.status == "completed"
                assert payload["history"]["run_ids"] == [str(candidate_id)]
                assert payload["evidence"]["history"]["increasing_transitions"] == 1
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

    if history_failure:
        import app.metrics.pipeline as pipeline_module

        monkeypatch.setattr(
            pipeline_module,
            "analyze_history",
            lambda *_: (_ for _ in ()).throw(RuntimeError("unexpected History failure")),
        )
    run(scenario())


def test_postgresql_history_reader_filters_orders_and_bounds_event_time_candidates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The real reader is bounded by event time, not insertion chronology."""

    async def persist_candidate(
        session: AsyncSession,
        repository: RuntimePersistenceRepository,
        execution_context: MetricLensExecutionContext,
        *,
        lens_run_id,
        window: MetricAnalysisWindow,
        mean: float | None,
        status: LensRunStatus,
        data_quality: str | None,
        observation_id: UUID | None = None,
        lens_id: str | None = None,
    ) -> None:
        candidate_observation_id = observation_id or execution_context.identity.observation_id
        candidate_lens_id = lens_id or execution_context.identity.lens_id
        observation_run = await repository.create_observation_run(
            session, ObservationRunInput(observation_id=candidate_observation_id)
        )
        await repository.advance_observation_run(
            session, observation_run, ObservationRunStatus.RUNNING
        )
        lens_run = await repository.create_lens_run(
            session,
            observation_run,
            LensRunInput(
                id=lens_run_id,
                lens_id=candidate_lens_id,
                lens_type=LensType.METRIC,
            ),
        )
        await repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING)
        result_identity = LensResultIdentity.model_validate(
            execution_context.identity.model_dump()
            | {
                "observation_id": candidate_observation_id,
                "observation_run_id": observation_run.id,
                "lens_id": candidate_lens_id,
                "lens_run_id": lens_run_id,
            }
        )
        reason = (
            StructuredReason(code="history_analysis_failed", component="history")
            if status is LensRunStatus.PARTIAL
            else (
                StructuredReason(code="current_metric_acquisition_failed")
                if status is LensRunStatus.FAILED
                else None
            )
        )
        await repository.advance_lens_run(session, lens_run, status, reason=reason)
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "lens_type": "metric",
            "identity": {
                **result_identity.model_dump(mode="json", exclude_none=True),
            },
            "status": {"state": status.value},
            "analysis_window": window.model_dump(mode="json", by_alias=True),
            "provenance": {
                "source": "prometheus",
                "generated_at": "2026-08-27T12:05:00Z",
            },
        }
        if status is LensRunStatus.FAILED:
            payload["status"] = {
                "state": "failed",
                "error": {
                    "code": "current_metric_acquisition_failed",
                    "message": "Current metric data acquisition failed.",
                },
            }
        elif data_quality == "insufficient":
            payload["data_quality"] = "insufficient"
        else:
            assert mean is not None and data_quality is not None
            payload |= {
                "data_quality": data_quality,
                "current_state": {
                    "trend": {"direction": "stable", "rate": "not_classified"},
                    "variability": {"state": "low"},
                },
                "evidence": {
                    "current": {"mean": mean, "std": 0.0, "min": mean, "max": mean, "slope": 0.0}
                },
            }
            if status is LensRunStatus.PARTIAL:
                payload["reason"] = {"code": "history_analysis_failed", "component": "history"}
        await repository.persist_lens_analysis_result(
            session,
            lens_run,
            LensAnalysisResultInput(
                result_type=LensType.METRIC,
                status=status,
                schema_version="1.0",
                identity=result_identity,
                provenance=payload["provenance"],
                payload=payload,
            ),
        )

    async def scenario() -> None:
        execution_context = context().model_copy(
            update={"history_policy": MetricHistoryPolicy(lookback_runs=3)}
        )
        repository = RuntimePersistenceRepository()
        earliest = uuid4()
        tied_first = uuid4()
        tied_second = uuid4()
        newest = uuid4()
        other_observation_id = uuid4()
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    ObservationModel(
                        id=execution_context.identity.observation_id,
                        name=f"PostgreSQL Metric History {uuid4()}",
                        objective="Verify History reader selection.",
                        schema_version=1,
                    )
                )
                session.add(
                    ObservationModel(
                        id=other_observation_id,
                        name=f"Other PostgreSQL Metric History {uuid4()}",
                        objective="Prove History aggregate scope filtering.",
                        schema_version=1,
                    )
                )
                await session.flush()
                # Persisted deliberately newest-first: event time must still control selection.
                for lens_run_id, start, end, mean, status, quality in (
                    (newest, -1, 2, 40.0, LensRunStatus.PARTIAL, "degraded"),
                    (tied_second, -13, -5, 30.0, LensRunStatus.COMPLETED, "good"),
                    (tied_first, -13, -5, 20.0, LensRunStatus.COMPLETED, "good"),
                    (earliest, -20, -10, 10.0, LensRunStatus.COMPLETED, "good"),
                    (uuid4(), -4, 3, 50.0, LensRunStatus.COMPLETED, "good"),
                    (uuid4(), -4, -2, None, LensRunStatus.COMPLETED, "insufficient"),
                    (uuid4(), -4, -2, None, LensRunStatus.FAILED, None),
                ):
                    await persist_candidate(
                        session,
                        repository,
                        execution_context,
                        lens_run_id=lens_run_id,
                        window=MetricAnalysisWindow(
                            **{
                                "from": execution_context.analysis_window.from_
                                + timedelta(minutes=start),
                                "to": execution_context.analysis_window.from_
                                + timedelta(minutes=end),
                            }
                        ),
                        mean=mean,
                        status=status,
                        data_quality=quality,
                    )
                # These are newer, eligible-looking artifacts, but they belong to
                # different aggregates and must not enter this History projection.
                await persist_candidate(
                    session,
                    repository,
                    execution_context,
                    lens_run_id=uuid4(),
                    window=MetricAnalysisWindow(
                        **{
                            "from": execution_context.analysis_window.from_ - timedelta(minutes=3),
                            "to": execution_context.analysis_window.from_ - timedelta(minutes=1),
                        }
                    ),
                    mean=60.0,
                    status=LensRunStatus.COMPLETED,
                    data_quality="good",
                    observation_id=other_observation_id,
                )
                await persist_candidate(
                    session,
                    repository,
                    execution_context,
                    lens_run_id=uuid4(),
                    window=MetricAnalysisWindow(
                        **{
                            "from": execution_context.analysis_window.from_ - timedelta(minutes=3),
                            "to": execution_context.analysis_window.from_ - timedelta(minutes=1),
                        }
                    ),
                    mean=70.0,
                    status=LensRunStatus.COMPLETED,
                    data_quality="good",
                    lens_id="different-metric-lens",
                )

            async with session.begin():
                history = await repository.load(session, execution_context)

        assert isinstance(history, MetricHistoryCandidates)
        expected_tied = sorted((tied_first, tied_second), key=str)
        assert [candidate.lens_run_id for candidate in history.candidates] == [
            *expected_tied,
            newest,
        ]
        assert [candidate.mean for candidate in history.candidates] == [
            20.0 if expected_tied[0] == tied_first else 30.0,
            30.0 if expected_tied[1] == tied_second else 20.0,
            40.0,
        ]

    run(scenario())


def test_postgresql_history_reader_failure_propagates_without_terminal_artifact(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    """A real session History-query error aborts before any terminal write."""

    async def scenario() -> None:
        phase_trace: list[str] = []
        execution_context = context()
        repository = RuntimePersistenceRepository()
        pipeline = MetricAnalysisPipeline(
            provider=FakeProvider(),
            agent=FakeAgent(),
            history_reader=repository,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            record_phase=phase_trace.append,
        )

        async with session_factory() as session:
            async with session.begin():
                observation = ObservationModel(
                    id=execution_context.identity.observation_id,
                    name=f"Metric History query failure {uuid4()}",
                    objective="Verify History infrastructure failure propagation.",
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

            async def fail_history_query(*_args, **_kwargs) -> None:
                raise RuntimeError("forced History query failure")

            monkeypatch.setattr(session, "execute", fail_history_query)
            phase_trace.append("caller_transaction_open")
            with pytest.raises(RuntimeError, match="forced History query failure"):
                async with session.begin():
                    await pipeline.persist_terminal(session, lens_run, analysis)
            phase_trace.append("caller_rollback")

        async with session_factory() as session:
            restored = await repository.get_observation_run(
                session, execution_context.identity.observation_run_id
            )
            assert restored is not None
            restored_lens_run = restored.lens_runs[0]
            assert restored_lens_run.status == "running"
            assert restored_lens_run.analysis_result is None

        assert phase_trace == [
            "provider_acquisition",
            "current_preparation",
            "mandatory_semanticization",
            "agent_execution",
            "caller_transaction_open",
            "history_read",
            "caller_rollback",
        ]

    run(scenario())


@pytest.mark.parametrize("failure_stage", ["flush", "commit"])
def test_postgresql_terminal_persistence_failures_rollback_lens_run_and_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    failure_stage: str,
    monkeypatch,
) -> None:
    """Caller-owned transaction failures leave no terminal state or Metric artifact."""

    async def scenario() -> None:
        execution_context = context()
        repository = RuntimePersistenceRepository()
        phase_trace: list[str] = []
        pipeline = MetricAnalysisPipeline(
            provider=FakeProvider(),
            agent=FakeAgent(),
            history_reader=repository,
            repository=repository,
            result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
            record_phase=phase_trace.append,
        )
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    ObservationModel(
                        id=execution_context.identity.observation_id,
                        name=f"Metric persistence rollback {uuid4()}",
                        objective="Verify terminal persistence rollback.",
                        schema_version=1,
                    )
                )
                await session.flush()
                observation_run = await repository.create_observation_run(
                    session,
                    ObservationRunInput(
                        id=execution_context.identity.observation_run_id,
                        observation_id=execution_context.identity.observation_id,
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
            if failure_stage == "flush":
                original_flush = session.flush
                flush_count = 0

                async def fail_artifact_flush(*args, **kwargs):
                    nonlocal flush_count
                    flush_count += 1
                    if flush_count == 2:
                        raise RuntimeError("forced artifact flush failure")
                    return await original_flush(*args, **kwargs)

                monkeypatch.setattr(session, "flush", fail_artifact_flush)
            else:
                from sqlalchemy import event

                def fail_commit(_session) -> None:
                    raise RuntimeError("forced transaction commit failure")

                event.listen(session.sync_session, "before_commit", fail_commit)

            phase_trace.append("caller_transaction_open")
            with pytest.raises(RuntimeError, match="forced .* failure"):
                async with session.begin():
                    await pipeline.persist_terminal(session, lens_run, analysis)
            phase_trace.append("caller_rollback")
            if failure_stage == "commit":
                event.remove(session.sync_session, "before_commit", fail_commit)

        async with session_factory() as session:
            restored = await repository.get_observation_run(
                session, execution_context.identity.observation_run_id
            )
            assert restored is not None
            assert restored.lens_runs[0].status == "running"
            assert restored.lens_runs[0].analysis_result is None

        assert phase_trace == [
            "provider_acquisition",
            "current_preparation",
            "mandatory_semanticization",
            "agent_execution",
            "caller_transaction_open",
            "history_read",
            "lens_run_transition",
            "artifact_insertion_flush",
            "caller_rollback",
        ]

    run(scenario())
