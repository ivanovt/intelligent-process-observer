"""PostgreSQL end-to-end coverage for the curated knowledge retrieval boundary."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator, Sequence
from hashlib import sha256
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import Settings, get_settings
from app.infrastructure.execution import composition as execution_composition
from app.infrastructure.execution.composition import build_production_execution_composition
from app.infrastructure.knowledge.retrieval import (
    CuratedKnowledgeReferenceResolver,
    CuratedKnowledgeRetriever,
)
from app.infrastructure.persistence.models import (
    KnowledgeDocumentModel,
    ObservationModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.repository import (
    KnowledgeRepository,
    RuntimePersistenceRepository,
)
from app.infrastructure.persistence.runtime_contracts import (
    ObservationAnalysisIdentity,
    ObservationAnalysisResultInput,
)
from app.knowledge.contracts import (
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
    """Replace external OpenRouter calls with deterministic vectors at the adapter boundary."""

    secret = "provider-secret-must-not-escape"

    @property
    def is_available(self) -> bool:
        """Expose the production-composition availability contract without a provider call."""
        return True

    async def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Return one valid deterministic document vector for every source passage."""
        return tuple(_EMBEDDING for _ in texts)

    async def embed_query(self, text: str) -> tuple[float, ...]:
        """Return an unrelated vector only for the no-match query."""
        return _UNRELATED_EMBEDDING if text == "unrelated vocabulary" else _EMBEDDING


class FailingQueryEmbedder:
    """Simulate a redacted transient query-embedding failure without provider I/O."""

    async def embed_query(self, _text: str) -> tuple[float, ...]:
        """Raise the boundary failure consumed by the retrieval executor."""
        raise RuntimeError("provider detail must not escape")


class TimedOutQueryEmbedder:
    """Simulate a bounded query-embedding timeout without provider I/O."""

    async def embed_query(self, _text: str) -> tuple[float, ...]:
        """Raise the normalized timeout consumed by the retrieval executor."""
        raise TimeoutError


def _candidate(
    source: bytes, title: str, *, service_id: str = "cooling-loop"
) -> KnowledgeDocumentVersionCreate:
    """Build one upload-admitted Markdown source with a scoped applicability tag."""
    return KnowledgeDocumentVersionCreate(
        title=title,
        document_type=KnowledgeDocumentType.RUNBOOK,
        authority=KnowledgeAuthority.INTERNAL_APPROVED,
        owner="operations",
        source_media_type="text/markdown",
        source_bytes=source,
        content_hash=sha256(source).hexdigest(),
        service_tags=(KnowledgeServiceTag(service_id=service_id, aliases=("chiller",)),),
    )


def _request(query: str = "cooling pressure guidance") -> KnowledgeRetrievalRequest:
    """Build one finding-grounded retrieval request for the frozen run scope."""
    return KnowledgeRetrievalRequest(query=query, finding_ids=("finding-1",))


def test_curated_knowledge_lifecycle_retrieval_and_historical_provenance(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise upload through persisted cited hypothesis and exact historical source inspection."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        runtime_repository = RuntimePersistenceRepository()
        embeddings = StubEmbeddingAdapter()
        monkeypatch.setattr(
            execution_composition, "OpenRouterEmbeddingAdapter", lambda _settings: embeddings
        )
        ingestion = KnowledgeIngestionService(
            session_factory,
            repository,
            max_upload_bytes=10_000,
            max_extraction_characters=10_000,
        )
        publication = KnowledgePublicationService(
            session_factory,
            repository,
            embeddings,
            max_extraction_characters=10_000,
        )
        first_source = b"# Cooling\nCooling pressure guidance requires a valve inspection."
        second_source = b"# Cooling\nReplacement guidance uses the updated valve procedure."
        document_id = None
        document_ids = []
        observation_id = None
        run_id = None
        try:
            document_id, first_version = await ingestion.create_document(
                _candidate(first_source, "Cooling runbook v1")
            )
            document_ids.append(document_id)
            await publication.approve(document_id, first_version)
            excluded_document_id, excluded_version = await ingestion.create_document(
                _candidate(
                    b"# Cooling\nCooling pressure guidance for another service.",
                    "Other service runbook",
                    service_id="other-service",
                )
            )
            document_ids.append(excluded_document_id)
            await publication.approve(excluded_document_id, excluded_version)

            production = build_production_execution_composition(
                settings=Settings(openrouter_api_key="test-only-composition-key"),
                session_factory=session_factory,
            )
            assert production.orchestrator._knowledge_retriever_factory is not None  # noqa: SLF001
            scoped_retriever = production.orchestrator._knowledge_retriever_factory(  # noqa: SLF001
                KnowledgeScope(service_ids=("cooling-loop",))
            )
            assert isinstance(scoped_retriever, CuratedKnowledgeRetriever)
            retrieval = BoundedRetrievalExecutor(frozenset({"finding-1"}), scoped_retriever)
            outcome = await retrieval.execute(_request())
            assert isinstance(outcome, RetrievalSuccess)
            assert len(outcome.items) == 1
            item = outcome.items[0]
            assert item.statement == "Cooling pressure guidance requires a valve inspection."
            reference = item.references[0]
            assert reference.source_id == f"knowledge-document:{document_id}:v1"

            async with session_factory.begin() as session:
                observation = ObservationModel(
                    name="Cooling health",
                    description="Scope-only retrieval test.",
                    objective="Observe pressure deviations.",
                    knowledge_scope={"service_ids": ["cooling-loop"], "service_version": None},
                )
                session.add(observation)
                await session.flush()
                observation_id = observation.id
                run = ObservationRunModel(
                    observation_id=observation.id,
                    status="completed",
                    provenance={},
                    execution_context={"knowledge_scope": {"service_ids": ["cooling-loop"]}},
                )
                session.add(run)
                await session.flush()
                run_id = run.id
                payload = {
                    "schema_version": "1.0",
                    "identity": {
                        "observation_id": str(observation.id),
                        "observation_run_id": str(run.id),
                    },
                    "findings": [
                        {
                            "id": "finding-1",
                            "statement": "Observed pressure deviation.",
                            "evidence_refs": [{"source_type": "metric_result", "source_id": "m1"}],
                        }
                    ],
                    "hypotheses": [
                        {
                            "id": "hypothesis-1",
                            "statement": "The cited guidance may explain the deviation.",
                            "supported_by": ["finding-1"],
                            "knowledge_refs": [reference.model_dump(mode="json")],
                        }
                    ],
                    "limitations": [],
                }
                persisted = await runtime_repository.persist_observation_analysis_result(
                    session,
                    run,
                    ObservationAnalysisResultInput(
                        schema_version="1.0",
                        identity=ObservationAnalysisIdentity(
                            observation_id=observation.id, observation_run_id=run.id
                        ),
                        payload=payload,
                    ),
                )
                public_projection = str(persisted.payload)
                assert "recommendation" not in public_projection.lower()
                assert "root cause" not in public_projection.lower()
                assert embeddings.secret not in public_projection
                assert "source_bytes" not in public_projection

            second_version = await ingestion.add_version(
                document_id, _candidate(second_source, "Cooling runbook v2")
            )
            await publication.approve(document_id, second_version)

            async with session_factory() as session:
                historical = await CuratedKnowledgeReferenceResolver().resolve(session, reference)
                retained = await repository.get_version(session, document_id, first_version)
                assert historical is not None
                assert historical.version == first_version
                assert historical.text == "Cooling pressure guidance requires a valve inspection."
                assert retained is not None and retained.source_bytes == first_source
                assert retained.lifecycle == "deprecated"

            empty = await BoundedRetrievalExecutor(
                frozenset({"finding-1"}), scoped_retriever
            ).execute(_request("unrelated vocabulary"))
            unavailable = await BoundedRetrievalExecutor(
                frozenset({"finding-1"}), EmptyKnowledgeRetriever()
            ).execute(_request())
            failed = await BoundedRetrievalExecutor(
                frozenset({"finding-1"}),
                CuratedKnowledgeRetriever(
                    session_factory,
                    FailingQueryEmbedder(),
                    scope=KnowledgeScope(service_ids=("cooling-loop",)),
                ),
            ).execute(_request())
            timed_out = await BoundedRetrievalExecutor(
                frozenset({"finding-1"}),
                CuratedKnowledgeRetriever(
                    session_factory,
                    TimedOutQueryEmbedder(),
                    scope=KnowledgeScope(service_ids=("cooling-loop",)),
                ),
            ).execute(_request())
            assert isinstance(empty, RetrievalSuccess) and empty.items == ()
            assert isinstance(unavailable, RetrievalSuccess) and unavailable.items == ()
            assert (
                isinstance(failed, RetrievalFailure)
                and failed.diagnostic_code == "retriever_failed"
            )
            assert isinstance(timed_out, RetrievalTimeout)
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
                if document_ids:
                    await session.execute(
                        delete(KnowledgeDocumentModel).where(
                            KnowledgeDocumentModel.id.in_(document_ids)
                        )
                    )

    asyncio.run(scenario())
