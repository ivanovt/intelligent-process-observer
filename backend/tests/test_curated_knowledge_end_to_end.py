"""PostgreSQL end-to-end coverage for scoped curated knowledge in one Observation run."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.infrastructure.knowledge.retrieval as retrieval_module
from app.core.settings import Settings, get_settings
from app.execution import AnalysisWindow, ExecutionPolicy, ObservationExecutionRequest
from app.execution.contracts import CollectedLensArtifact, CollectedLensOutcome
from app.execution.orchestrator import ObservationExecutionOrchestrator
from app.infrastructure.execution.composition import build_production_execution_composition
from app.infrastructure.knowledge.retrieval import (
    CuratedKnowledgeReferenceResolver,
    CuratedKnowledgeRetriever,
)
from app.infrastructure.persistence.models import (
    KnowledgeDocumentModel,
    LensRunModel,
    ObservationModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.repository import (
    KnowledgeRepository,
    ObservationRepository,
    RuntimePersistenceRepository,
)
from app.infrastructure.persistence.runtime_contracts import LensRunStatus
from app.knowledge.contracts import (
    KnowledgeReference,
    KnowledgeRetrievalRequest,
    RetrievalFailure,
    RetrievalSuccess,
    RetrievalTimeout,
)
from app.knowledge.empty import EmptyKnowledgeRetriever
from app.knowledge.executor import BoundedRetrievalExecutor
from app.knowledge.ingestion import KnowledgeIngestionService
from app.knowledge.management_contracts import (
    KnowledgeAuthority,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeScope,
    KnowledgeServiceTag,
)
from app.knowledge.publication import KnowledgePublicationService
from app.metrics.contracts import (
    MetricEvidence,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSample,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.result_builder import MetricResultBuilder
from app.observations.contracts import ObservationCreate
from app.reasoning.contracts import (
    FindingCompletion,
    FindingDraft,
    Hypothesis,
    HypothesisCompletion,
    OverallStateCompletion,
)
from app.reasoning.executor import ObservationReasoningExecutor
from app.relationships.evaluator import RelationshipEvaluator
from app.reporting.contracts import ObservationReport, ReportSuccess

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_EMBEDDING = (1.0, *([0.0] * 1_535))
_UNRELATED_EMBEDDING = (0.0, 1.0, *([0.0] * 1_534))


@pytest.fixture(scope="module")
def postgres_url() -> Generator[str]:
    """Provide the explicitly configured PostgreSQL database at migration head."""
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
def session_factory(postgres_url: str) -> Generator[async_sessionmaker[AsyncSession]]:
    """Create short-lived sessions against the isolated PostgreSQL integration database."""
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


class StubEmbeddingAdapter:
    """Return deterministic valid embeddings without an external provider call."""

    secret = "provider-secret-must-not-escape"

    def __init__(self) -> None:
        self.query_calls: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Return one vector for every approved source passage."""
        return tuple(_EMBEDDING for _ in texts)

    async def embed_query(self, text: str) -> tuple[float, ...]:
        """Record and embed the bounded finding-grounded query."""
        self.query_calls.append(text)
        return _UNRELATED_EMBEDDING if text == "unrelated vocabulary" else _EMBEDDING


class MetricFixtureAdapter:
    """Persist one valid completed Metric artifact through the runtime repository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self, assignment, _policy: ExecutionPolicy) -> CollectedLensOutcome:
        """Create the minimum sufficient Metric result for Observation reasoning."""
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
        result, envelope = builder.completed_sufficient(
            context,
            PreparedGoodSeries(
                data_quality="good",
                samples=(MetricSample(timestamp=assignment.analysis_window.to, value=1.0),),
                evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
                residuals=(0.0,),
            ),
            MetricSemantics(
                trend=MetricTrend(direction="stable", rate="not_classified"),
                variability=MetricVariability(state="low"),
            ),
        )
        async with self._session_factory.begin() as session:
            lens_run = await session.get(LensRunModel, assignment.lens_run_id)
            assert lens_run is not None
            repository = RuntimePersistenceRepository()
            await repository.advance_lens_run(session, lens_run, LensRunStatus.COMPLETED)
            await repository.persist_lens_analysis_result(session, lens_run, envelope)
        return CollectedLensOutcome(
            assignment=assignment,
            status="completed",
            artifact=CollectedLensArtifact.from_persistence_envelope(
                envelope.model_copy(update={"payload": result.model_dump(by_alias=True)})
            ),
        )


class CitedReasoningAgent:
    """Form one evidence-grounded finding and a retrieval-grounded cited hypothesis."""

    def __init__(self) -> None:
        self.finding_request = None
        self.overall_request = None

    async def form_findings(self, request):
        """Freeze one finding from the real Metric evidence catalog."""
        self.finding_request = request
        metric = next(
            item for item in request.catalog if item.reference.source_type == "metric_result"
        )
        return FindingCompletion(
            findings=(
                FindingDraft(
                    id="finding-1",
                    statement="Observed metric evidence needs an explanation.",
                    evidence_ids=(metric.id,),
                ),
            )
        )

    async def form_hypotheses(self, _request, retrieval):
        """Use exactly the supplied run-scoped retriever before citing a hypothesis."""
        outcome = await retrieval.execute(
            KnowledgeRetrievalRequest(query="cooling pressure guidance", finding_ids=("finding-1",))
        )
        assert isinstance(outcome, RetrievalSuccess)
        assert len(outcome.items) == 1
        return HypothesisCompletion(
            hypotheses=(
                Hypothesis(
                    id="hypothesis-1",
                    statement="Approved guidance may explain the observed metric evidence.",
                    supported_by=("finding-1",),
                    knowledge_refs=outcome.items[0].references,
                ),
            )
        )

    async def determine_overall_state(self, request):
        """Return a separate evidence-only overall state."""
        self.overall_request = request
        return OverallStateCompletion(overall_state="significant_findings_present")


class ReportFixture:
    """Return a minimal correlated report after successful Observation reasoning."""

    async def execute(self, request):
        """Produce a valid report without introducing another model boundary."""
        return ReportSuccess(
            report=ObservationReport(
                observation_id=request.context.identity.observation_id,
                observation_run_id=request.context.identity.observation_run_id,
                generated_at=datetime(2026, 9, 13, tzinfo=UTC),
                content="# Curated knowledge test report",
            )
        )


class _BrokenSearchSession:
    """Fail the database-search boundary only after the query is embedded."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> bool:
        return False

    async def execute(self, _statement):
        raise RuntimeError("database detail must not escape")


class _SlowSearchSession(_BrokenSearchSession):
    """Delay search long enough to exhaust the whole retrieval deadline."""

    async def execute(self, _statement):
        await asyncio.sleep(0.05)
        raise AssertionError("deadline should expire before search returns")


def _candidate(source: bytes, title: str) -> KnowledgeDocumentVersionCreate:
    """Build one scoped, upload-admitted Markdown source."""
    return KnowledgeDocumentVersionCreate(
        title=title,
        document_type=KnowledgeDocumentType.RUNBOOK,
        authority=KnowledgeAuthority.INTERNAL_APPROVED,
        owner="operations",
        source_media_type="text/markdown",
        source_bytes=source,
        content_hash=sha256(source).hexdigest(),
        service_tags=(KnowledgeServiceTag(service_id="cooling-loop"),),
    )


def _definition(scope: KnowledgeScope) -> ObservationCreate:
    """Build one complete aggregate definition with a single Metric Lens."""
    return ObservationCreate.model_validate(
        {
            "name": "Cooling health",
            "objective": "Explain cooling pressure evidence.",
            "lenses": [
                {
                    "id": "pressure",
                    "name": "Cooling pressure",
                    "type": "metric",
                    "metric_id": "cooling.pressure",
                    "adapter_type": "prometheus",
                    "source_id": "fixture",
                    "query": "cooling_pressure",
                    "unit": "bar",
                    "analysis_objectives": ["spike"],
                    "reference_periods": [],
                }
            ],
            "relationships": [],
            "knowledge_scope": scope.model_dump(mode="json"),
        }
    )


def test_scoped_run_retrieval_persists_cited_hypothesis_and_freezes_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Run an initialized definition after replacement and preserve its original scope."""

    async def scenario() -> None:
        knowledge_repository = KnowledgeRepository()
        observation_repository = ObservationRepository()
        runtime_repository = RuntimePersistenceRepository()
        embeddings = StubEmbeddingAdapter()
        ingestion = KnowledgeIngestionService(
            session_factory,
            knowledge_repository,
            max_upload_bytes=10_000,
            max_extraction_characters=10_000,
        )
        publication = KnowledgePublicationService(
            session_factory,
            knowledge_repository,
            embeddings,
            max_extraction_characters=10_000,
        )
        source = b"# Cooling\nCooling pressure guidance requires a valve inspection."
        document_id = observation_id = run_id = None
        try:
            document_id, version = await ingestion.create_document(
                _candidate(source, "Cooling runbook")
            )
            await publication.approve(document_id, version)
            original_scope = KnowledgeScope(service_ids=("cooling-loop",), service_version="2.x")
            replacement_scope = KnowledgeScope(service_ids=("other-service",))
            async with session_factory.begin() as session:
                definition = await observation_repository.create(
                    session, _definition(original_scope)
                )
                observation_id = definition.id

            scopes: list[KnowledgeScope | None] = []

            def retriever_factory(scope: KnowledgeScope | None) -> CuratedKnowledgeRetriever:
                scopes.append(scope)
                return CuratedKnowledgeRetriever(session_factory, embeddings, scope=scope)

            agent = CitedReasoningAgent()
            orchestrator = ObservationExecutionOrchestrator(
                session_factory=session_factory,
                definition_loader=observation_repository,
                runtime_repository=runtime_repository,
                metric_adapter=MetricFixtureAdapter(session_factory),
                alert_adapter=object(),
                relationship_evaluator=RelationshipEvaluator(),
                reasoning_executor=ObservationReasoningExecutor(agent, EmptyKnowledgeRetriever()),
                report_executor=ReportFixture(),
                knowledge_retriever_factory=retriever_factory,
            )
            end = datetime(2026, 9, 13, 12, tzinfo=UTC)
            start = end - timedelta(minutes=5)
            policy = ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=5)
            initialized = await orchestrator.initialize(
                ObservationExecutionRequest(observation_id, AnalysisWindow(start, end)), policy
            )
            assert not hasattr(initialized, "reason")
            run_id = initialized.observation_run_id
            assert initialized.snapshot.knowledge_scope == original_scope
            async with session_factory.begin() as session:
                assert (
                    await observation_repository.replace(
                        session, observation_id, _definition(replacement_scope)
                    )
                    is not None
                )

            outcome = await orchestrator.continue_execution(initialized, policy)

            assert outcome.status == "completed"
            assert scopes == [original_scope]
            assert agent.finding_request is not None and agent.overall_request is not None
            assert "knowledge_scope" not in agent.finding_request.model_dump()
            assert "knowledge_scope" not in agent.overall_request.model_dump()
            next_version = await ingestion.add_version(
                document_id,
                _candidate(
                    b"# Cooling\nReplacement guidance uses an updated valve procedure.",
                    "Cooling runbook revision",
                ),
            )
            await publication.approve(document_id, next_version)
            async with session_factory() as session:
                run = await runtime_repository.get_observation_run(session, run_id)
                assert run.execution_context == {
                    "definition_schema_version": 1,
                    "analysis_window": {"from": start.isoformat(), "to": end.isoformat()},
                }
                assert run.observation_analysis_result is not None
                reference = run.observation_analysis_result.payload["hypotheses"][0][
                    "knowledge_refs"
                ][0]
                assert reference["source_id"] == f"knowledge-document:{document_id}:v1"
                historical = await CuratedKnowledgeReferenceResolver().resolve(
                    session, KnowledgeReference.model_validate(reference)
                )
                assert historical is not None
                assert historical.version == version
                assert historical.text == source.decode().split("\n", 1)[1]
                retained = await knowledge_repository.get_version(session, document_id, version)
                assert retained is not None
                assert retained.source_bytes == source
                assert retained.lifecycle == "deprecated"
                public_payload = str(run.observation_analysis_result.payload).lower()
                for forbidden in (
                    "knowledge_scope",
                    "recommendation",
                    "causal",
                    "source_bytes",
                    embeddings.secret,
                    "provider-secret",
                    "database detail",
                ):
                    assert forbidden not in public_payload
                replaced = await observation_repository.get(session, observation_id)
                assert replaced is not None
                assert replaced.knowledge_scope == {
                    "service_ids": ["other-service"],
                    "service_version": None,
                }
            unrelated = await BoundedRetrievalExecutor(
                frozenset(("finding-1",)),
                CuratedKnowledgeRetriever(session_factory, embeddings, scope=original_scope),
            ).execute(
                KnowledgeRetrievalRequest(query="unrelated vocabulary", finding_ids=("finding-1",))
            )
            unavailable_composition = build_production_execution_composition(
                settings=Settings(openrouter_api_key=None, agent_trace_enabled=False),
                session_factory=session_factory,
            )
            unavailable = await BoundedRetrievalExecutor(
                frozenset(("finding-1",)),
                unavailable_composition.knowledge_retriever_factory(original_scope),
            ).execute(
                KnowledgeRetrievalRequest(
                    query="cooling pressure guidance", finding_ids=("finding-1",)
                )
            )
            assert isinstance(unrelated, RetrievalSuccess) and unrelated.items == ()
            assert isinstance(unavailable, RetrievalSuccess) and unavailable.items == ()
        finally:
            async with session_factory.begin() as session:
                if run_id is not None:
                    await session.execute(
                        delete(ObservationRunModel).where(ObservationRunModel.id == run_id)
                    )
                if observation_id is not None:
                    await session.execute(
                        delete(ObservationModel).where(ObservationModel.id == observation_id)
                    )
                if document_id is not None:
                    await session.execute(
                        delete(KnowledgeDocumentModel).where(
                            KnowledgeDocumentModel.id == document_id
                        )
                    )

    asyncio.run(scenario())


def test_database_search_failure_and_post_embedding_timeout_stay_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Search failures never become empty success after query embedding completed."""

    async def scenario() -> None:
        embeddings = StubEmbeddingAdapter()
        scope = KnowledgeScope(service_ids=("cooling-loop",))
        failed = await BoundedRetrievalExecutor(
            frozenset(("finding-1",)),
            CuratedKnowledgeRetriever(  # type: ignore[arg-type]
                lambda: _BrokenSearchSession(), embeddings, scope=scope
            ),
        ).execute(
            KnowledgeRetrievalRequest(query="cooling pressure guidance", finding_ids=("finding-1",))
        )
        monkeypatch.setattr(retrieval_module, "_RETRIEVAL_DEADLINE_SECONDS", 0.01)
        timed_out = await BoundedRetrievalExecutor(
            frozenset(("finding-1",)),
            CuratedKnowledgeRetriever(  # type: ignore[arg-type]
                lambda: _SlowSearchSession(), embeddings, scope=scope
            ),
        ).execute(
            KnowledgeRetrievalRequest(query="cooling pressure guidance", finding_ids=("finding-1",))
        )

        assert isinstance(failed, RetrievalFailure)
        assert failed.diagnostic_code == "retriever_failed"
        assert isinstance(timed_out, RetrievalTimeout)
        assert len(embeddings.query_calls) == 2

    asyncio.run(scenario())
