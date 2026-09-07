# ruff: noqa: E501
"""PostgreSQL end-to-end coverage for the Observation execution composition."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.execution import (
    AnalysisWindow,
    ExecutionPolicy,
    ObservationExecutionOrchestrator,
    ObservationExecutionRequest,
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
from app.infrastructure.persistence.runtime_contracts import LensRunStatus, StructuredReason
from app.metrics.contracts import (
    MetricEvidence,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.result_builder import MetricResultBuilder
from app.reasoning.contracts import ObservationAnalysisResult, ReasoningSuccess
from app.relationships.contracts import UnknownRelationshipEvaluation
from app.reporting.contracts import ObservationReport, ReportFailure, ReportSuccess

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """Provide the opt-in migrated PostgreSQL database used by integration tests."""
    url = os.environ.get("IPO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set IPO_TEST_DATABASE_URL to run PostgreSQL integration tests")
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    yield url
    if old is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old
    get_settings.cache_clear()


@pytest.fixture
def sessions(postgres_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Create real async SQLAlchemy sessions without resetting shared test data."""
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


class MetricFixtureAdapter:
    """Persist deterministic Metric outcomes through the real runtime repository."""

    def __init__(self, factory, modes: dict[str, str]) -> None:
        self.factory, self.modes = factory, modes

    async def execute(self, assignment, policy):
        mode = self.modes.get(assignment.lens.lens_id, "completed")
        context = MetricLensExecutionContext(
            identity=MetricIdentity(
                observation_id=assignment.observation_id,
                observation_run_id=assignment.observation_run_id,
                lens_id=assignment.lens.lens_id,
                lens_run_id=assignment.lens_run_id,
                metric_ref=assignment.lens.metric_id,
                unit=assignment.lens.unit,
            ),
            provider_scope=MetricProviderScope(
                adapter_type=assignment.lens.adapter_type,
                source_id=assignment.lens.source_id,
                query=assignment.lens.query,
            ),
            analysis_window={
                "from": assignment.analysis_window.from_,
                "to": assignment.analysis_window.to,
            },
            analysis_objectives=assignment.lens.analysis_objectives,
            reference_periods=(),
        )
        builder = MetricResultBuilder(clock=lambda: assignment.analysis_window.to)
        if mode == "failed":
            from app.metrics.contracts import MetricMandatoryAnalysisFailure

            _, envelope = builder.failed(
                context, MetricMandatoryAnalysisFailure(diagnostic="fixture")
            )
            status, reason = (
                LensRunStatus.FAILED,
                StructuredReason(code="analysis_failed", component="metric"),
            )
        elif mode == "insufficient":
            _, envelope = builder.completed_insufficient(context)
            status, reason = LensRunStatus.COMPLETED, None
        else:
            _, envelope = builder.completed_sufficient(
                context,
                PreparedGoodSeries(
                    data_quality="good",
                    samples=(),
                    evidence=MetricEvidence(mean=1, std=0, min=1, max=1, slope=0),
                    residuals=(),
                ),
                MetricSemantics(
                    trend=MetricTrend(direction="stable", rate="not_classified"),
                    variability=MetricVariability(state="low"),
                ),
            )
            status, reason = (
                LensRunStatus.PARTIAL if mode == "partial" else LensRunStatus.COMPLETED,
                None,
            )
            if mode == "partial":
                envelope = envelope.model_copy(update={"status": LensRunStatus.PARTIAL})
        async with self.factory.begin() as session:
            run = await session.get(
                __import__(
                    "app.infrastructure.persistence.models", fromlist=["LensRunModel"]
                ).LensRunModel,
                assignment.lens_run_id,
            )
            repo = RuntimePersistenceRepository()
            await repo.advance_lens_run(session, run, status, reason=reason)
            await repo.persist_lens_analysis_result(session, run, envelope)
        from app.execution.contracts import CollectedLensOutcome

        return CollectedLensOutcome(
            assignment=assignment,
            status=status.value,
            artifact=__import__(
                "app.execution.contracts", fromlist=["CollectedLensArtifact"]
            ).CollectedLensArtifact.from_persistence_envelope(envelope),
            reason=reason
            and __import__("app.execution.contracts", fromlist=["ExecutionReason"]).ExecutionReason(
                reason.code, reason.component
            ),
        )


class AlertFixtureAdapter:
    """Persist a deterministic failed Alert outcome, preserving missing-artifact semantics."""

    def __init__(self, factory) -> None:
        self.factory = factory

    async def execute(self, assignment, policy):
        from app.execution.contracts import CollectedLensOutcome, ExecutionReason
        from app.infrastructure.persistence.models import LensRunModel

        async with self.factory.begin() as session:
            run = await session.get(LensRunModel, assignment.lens_run_id)
            await RuntimePersistenceRepository().advance_lens_run(
                session,
                run,
                LensRunStatus.FAILED,
                reason=StructuredReason(code="analysis_failed", component="alert"),
            )
        return CollectedLensOutcome(
            assignment=assignment,
            status="failed",
            reason=ExecutionReason("analysis_failed", "alert"),
        )


class RelationshipFixture:
    """Return one exact unknown evaluation per configured Relationship."""

    def evaluate(self, definitions, results):
        return tuple(
            UnknownRelationshipEvaluation(
                relationship_id=d.relationship_id,
                name=d.name,
                description=d.description,
                conditions=(),
                expectations=(),
            )
            for d in definitions
        )


class ReasoningFixture:
    """Return a correlated, empty-but-valid Observation analysis."""

    async def execute(self, value):
        return ReasoningSuccess(
            result=ObservationAnalysisResult(
                identity=value.context.identity,
                overall_state="uncertain",
                findings=(),
                hypotheses=(),
                limitations=(),
            )
        )


class ReportFixture:
    """Return either a correlated Markdown report or a typed failure."""

    def __init__(self, failed=False):
        self.failed = failed

    async def execute(self, value):
        if self.failed:
            return ReportFailure(code="report_model_failed", component="report_generation")
        return ReportSuccess(
            report=ObservationReport(
                observation_id=value.context.identity.observation_id,
                observation_run_id=value.context.identity.observation_run_id,
                generated_at=datetime(2026, 9, 7, tzinfo=UTC),
                content="# fixture",
            )
        )


async def _seed(factory, *, alerts=False, relationships=False) -> UUID:
    oid = uuid4()
    async with factory.begin() as session:
        observation = ObservationModel(
            id=oid, name=f"e2e-{oid}", objective="fixture", schema_version=7
        )
        observation.lenses = [
            MetricLensModel(
                lens_id="metric-a",
                name="metric-a",
                adapter_type="prometheus",
                source_id="fixture",
                metric_id="metric-a",
                query="up",
                unit="count",
                analysis_objectives=[],
                reference_periods=[],
                position=0,
            ),
            MetricLensModel(
                lens_id="metric-b",
                name="metric-b",
                adapter_type="prometheus",
                source_id="fixture",
                metric_id="metric-b",
                query="up",
                unit="count",
                analysis_objectives=[],
                reference_periods=[],
                position=1,
            ),
        ]
        if alerts:
            observation.alert_lenses = [
                AlertLensModel(
                    lens_id="metric-a",
                    lens_type="alert",
                    name="alert",
                    source="jira_track_and_release",
                    selector_query="x",
                    analysis_objectives=[],
                    reference_periods=[],
                    position=0,
                )
            ]
        if relationships:
            observation.relationships = [
                ObservationRelationshipModel(
                    relationship_id="rel-a",
                    name="rel-a",
                    description=None,
                    participants=["metric-a", "metric-b"],
                    conditions={},
                    expected={"metric-a": {"trend": {"direction": "stable"}}},
                    position=0,
                )
            ]
        session.add(observation)
    return oid


def _request(oid):
    end = datetime(2026, 9, 7, 12, tzinfo=UTC)
    return ObservationExecutionRequest(oid, AnalysisWindow(end - timedelta(minutes=5), end))


def _orchestrator(factory, modes, *, report_failed=False):
    repo = RuntimePersistenceRepository()
    return ObservationExecutionOrchestrator(
        session_factory=factory,
        definition_loader=ObservationRepository(),
        runtime_repository=repo,
        metric_adapter=MetricFixtureAdapter(factory, modes),
        alert_adapter=AlertFixtureAdapter(factory),
        relationship_evaluator=RelationshipFixture(),
        reasoning_executor=ReasoningFixture(),
        report_executor=ReportFixture(report_failed),
    )


def test_postgresql_success_persists_exact_aggregate_and_report(sessions):
    async def scenario():
        oid = await _seed(sessions, relationships=True)
        out = await _orchestrator(sessions, {}).execute(_request(oid), ExecutionPolicy(2, 5))
        async with sessions() as s:
            run = await RuntimePersistenceRepository().get_observation_run(
                s, out.observation_run_id
            )
            assert run.status == "completed" and len(run.lens_runs) == 2
            assert len(run.relationship_evaluations) == 1
            assert run.observation_analysis_result is not None
            assert run.observation_analysis_result.report is not None

    asyncio.run(scenario())


def test_postgresql_mixed_degradation_preserves_metric_and_alert_distinctions(sessions):
    async def scenario():
        oid = await _seed(sessions, alerts=True, relationships=True)
        out = await _orchestrator(sessions, {"metric-a": "partial", "metric-b": "failed"}).execute(
            _request(oid), ExecutionPolicy(2, 5)
        )
        async with sessions() as s:
            run = await RuntimePersistenceRepository().get_observation_run(
                s, out.observation_run_id
            )
            assert run.status == "completed"
            assert [
                (x.lens_type, x.status, x.analysis_result is not None) for x in run.lens_runs
            ] == [
                ("metric", "partial", True),
                ("metric", "failed", True),
                ("alert", "failed", False),
            ]
            assert (
                run.observation_analysis_result is not None
                and len(run.relationship_evaluations) == 1
            )

    asyncio.run(scenario())


def test_postgresql_report_failure_preserves_analysis_but_not_report(sessions):
    async def scenario():
        oid = await _seed(sessions)
        out = await _orchestrator(sessions, {}, report_failed=True).execute(
            _request(oid), ExecutionPolicy(2, 5)
        )
        async with sessions() as s:
            run = await RuntimePersistenceRepository().get_observation_run(
                s, out.observation_run_id
            )
            assert run.status == "failed" and run.observation_analysis_result is not None
            assert run.observation_analysis_result.report is None

    asyncio.run(scenario())
