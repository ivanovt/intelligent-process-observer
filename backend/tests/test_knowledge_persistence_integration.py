"""PostgreSQL integration coverage for curated knowledge persistence invariants."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings
from app.infrastructure.persistence.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentVersionModel,
    ObservationModel,
)
from app.infrastructure.persistence.repository import (
    KnowledgeLifecycleConflict,
    KnowledgeRepository,
)
from app.knowledge.extraction import KnowledgeExtractionError, extract_source
from app.knowledge.ingestion import KnowledgeIngestionService
from app.knowledge.management_contracts import (
    KNOWLEDGE_EMBEDDING_DIMENSIONS,
    KnowledgeAuthority,
    KnowledgeChunkCreate,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeServiceTag,
)
from app.knowledge.publication import KnowledgePublicationService

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_REVISION = "20260913_01"
_PRE_KNOWLEDGE_REVISION = "20260909_01"
_EMBEDDING = (0.0,) * KNOWLEDGE_EMBEDDING_DIMENSIONS


@pytest.fixture(scope="module")
def postgres_url() -> Generator[str]:
    """Provide an explicitly configured PostgreSQL database at the migration head."""
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
    """Create short-lived async sessions for isolated repository transactions."""
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def source_version(content_hash: str) -> KnowledgeDocumentVersionCreate:
    """Build a valid retained Markdown version with one service applicability tag."""
    return KnowledgeDocumentVersionCreate(
        title="Cooling loop runbook",
        document_type=KnowledgeDocumentType.RUNBOOK,
        authority=KnowledgeAuthority.INTERNAL_APPROVED,
        owner="operations",
        source_media_type="text/markdown",
        source_bytes=b"# Cooling loop",
        content_hash=content_hash,
        service_tags=(KnowledgeServiceTag(service_id="cooling-loop", aliases=("cooling",)),),
    )


def indexed_chunk(ordinal: int = 1) -> KnowledgeChunkCreate:
    """Build one complete indexed chunk suitable for atomic publication."""
    return KnowledgeChunkCreate(
        ordinal=ordinal,
        text="Cooling loop pressure should remain stable.",
        embedding=_EMBEDDING,
        heading_path=("Operations",),
    )


async def alembic_revision(session_factory: async_sessionmaker[AsyncSession]) -> str:
    """Read the database's current Alembic revision without changing it."""
    async with session_factory() as session:
        return (await session.scalar(text("SELECT version_num FROM alembic_version"))) or ""


async def knowledge_table_exists(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    """Report whether the migration's root table is present in PostgreSQL."""
    async with session_factory() as session:
        statement = text("SELECT to_regclass('knowledge_documents') IS NOT NULL")
        return bool(await session.scalar(statement))


def test_version_lifecycle_uniqueness_and_deprecation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Enforce source-hash uniqueness and publish exactly one approved version per document."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        async with session_factory() as session:
            document = await repository.create_document(session, source_version("1" * 64))
            first = document.versions[0]
            first.extraction_state = "ready"
            await repository.replace_chunks(session, first.id, (indexed_chunk(),))
            await repository.approve_version(session, document.id, 1)

            async with session.begin_nested():
                with pytest.raises(IntegrityError):
                    await repository.add_version(session, document.id, source_version("1" * 64))

            second = await repository.add_version(session, document.id, source_version("2" * 64))
            second.extraction_state = "ready"
            await repository.replace_chunks(session, second.id, (indexed_chunk(),))
            approved = await repository.approve_version(session, document.id, 2)
            assert approved.lifecycle == "approved"
            assert first.lifecycle == "deprecated"
            catalog = await repository.approved_service_catalog(session)
            assert tuple(item.model_dump() for item in catalog) == (
                {"service_id": "cooling-loop", "aliases": ("cooling",)},
            )

            deprecated = await repository.deprecate_version(session, document.id, 2)
            assert deprecated.lifecycle == "deprecated"
            assert await repository.approved_service_catalog(session) == ()
            await session.rollback()

    asyncio.run(scenario())


def test_approval_rejects_empty_or_unindexed_chunks_without_displacing_prior_publication(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Reject incomplete ready candidates and retain the approved predecessor."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        async with session_factory() as session:
            document = await repository.create_document(session, source_version("3" * 64))
            first = document.versions[0]
            first.extraction_state = "ready"
            await repository.replace_chunks(session, first.id, (indexed_chunk(),))
            await repository.approve_version(session, document.id, 1)

            empty_candidate = await repository.add_version(
                session, document.id, source_version("4" * 64)
            )
            empty_candidate.extraction_state = "ready"
            unindexed_candidate = await repository.add_version(
                session, document.id, source_version("5" * 64)
            )
            unindexed_candidate.extraction_state = "ready"
            session.add(
                KnowledgeChunkModel(
                    document_version_id=unindexed_candidate.id,
                    ordinal=1,
                    heading_path=["Operations"],
                    text="Derived text without a durable embedding.",
                    embedding=None,
                )
            )
            await session.commit()
            document_id = document.id

        async with session_factory() as session:
            with pytest.raises(ValueError, match="at least one indexed chunk"):
                await repository.approve_version(session, document_id, 2)
            await session.rollback()
            with pytest.raises(ValueError, match="finite 1536-dimensional embeddings"):
                await repository.approve_version(session, document_id, 3)
            await session.rollback()

        async with session_factory() as session:
            versions = list(
                await session.scalars(
                    select(KnowledgeDocumentVersionModel)
                    .where(KnowledgeDocumentVersionModel.document_id == document_id)
                    .order_by(KnowledgeDocumentVersionModel.version)
                )
            )
            assert [version.lifecycle for version in versions] == [
                "approved",
                "imported",
                "imported",
            ]
            await session.execute(
                delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == document_id)
            )
            await session.commit()

    asyncio.run(scenario())


def test_extraction_attempt_fence_retains_source_and_ignores_a_late_completion(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A retry retains the immutable source and only its current attempt may publish extraction."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        async with session_factory() as session:
            document = await repository.create_document(session, source_version("7" * 64))
            version = document.versions[0]
            retained_source = version.source_bytes
            interrupted_attempt = await repository.begin_extraction_attempt(session, document.id, 1)
            retry_attempt = await repository.begin_extraction_attempt(session, document.id, 1)

            assert version.source_bytes == retained_source
            assert version.extraction_state == "pending"
            assert not await repository.complete_extraction_attempt(
                session,
                document.id,
                1,
                interrupted_attempt,
                extracted_text="late interrupted output",
                succeeded=True,
            )
            assert await repository.complete_extraction_attempt(
                session,
                document.id,
                1,
                retry_attempt,
                extracted_text="retry output",
                succeeded=True,
            )
            await session.refresh(version)
            assert version.source_bytes == retained_source
            assert version.extraction_state == "ready"
            assert version.extracted_text == "retry output"
            await session.rollback()

    asyncio.run(scenario())


def test_committed_image_only_pdf_is_retained_when_initial_extraction_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The initial extraction failure cannot roll back the already committed immutable source."""

    def image_only_pdf_extractor(*_args, **_kwargs):
        raise KnowledgeExtractionError("PDF source contains no extractable text")

    async def scenario() -> None:
        repository = KnowledgeRepository()
        service = KnowledgeIngestionService(
            session_factory,
            repository,
            max_upload_bytes=10_000,
            max_extraction_characters=10_000,
            extractor=image_only_pdf_extractor,
        )
        candidate = source_version("d" * 64).model_copy(
            update={
                "source_media_type": "application/pdf",
                "source_bytes": b"%PDF-1.7\nimage-only fixture",
            }
        )
        document_id, version_number = await service.create_document(candidate)
        try:
            async with session_factory() as session:
                version = await repository.get_version(session, document_id, version_number)
                assert version is not None
                assert version.source_bytes == candidate.source_bytes
                assert version.content_hash == candidate.content_hash
                assert version.lifecycle == "imported"
                assert version.extraction_state == "failed"
                assert version.extracted_text is None
        finally:
            async with session_factory.begin() as session:
                await session.execute(
                    delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == document_id)
                )

    asyncio.run(scenario())


def test_postgresql_extraction_lock_excludes_overlapping_retry_and_releases_after_interrupt(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """One lock holder excludes an overlap, then another session can retry after release."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        engine = session_factory.kw.get("bind")
        assert isinstance(engine, AsyncEngine)
        version_id = uuid4()
        async with engine.connect() as first_connection, engine.connect() as second_connection:
            async with (
                AsyncSession(bind=first_connection) as first,
                AsyncSession(bind=second_connection) as second,
            ):
                async with first.begin():
                    assert await repository.try_acquire_extraction_lock(first, version_id)
                async with second.begin():
                    assert not await repository.try_acquire_extraction_lock(second, version_id)
                await repository.release_extraction_lock(first, version_id)
                await first.commit()
                async with second.begin():
                    assert await repository.try_acquire_extraction_lock(second, version_id)
                await repository.release_extraction_lock(second, version_id)
                await second.commit()

    asyncio.run(scenario())


def test_stale_lifecycle_preflight_preserves_authoritative_approval_and_candidate_chunks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Stale approval/deprecation snapshots fail before candidate chunks are published."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        async with session_factory() as session:
            document = await repository.create_document(session, source_version("8" * 64))
            first = document.versions[0]
            first.extraction_state = "ready"
            await repository.replace_chunks(session, first.id, (indexed_chunk(),))
            await repository.approve_version(session, document.id, 1)
            approved_snapshot = first.id

            replacement = await repository.add_version(
                session, document.id, source_version("9" * 64)
            )
            replacement.extraction_state = "ready"
            await repository.replace_chunks(session, replacement.id, (indexed_chunk(),))
            await repository.approve_version(
                session,
                document.id,
                2,
                expected_approved_version_id=approved_snapshot,
            )

            stale_candidate = await repository.add_version(
                session, document.id, source_version("a" * 64)
            )
            stale_candidate.extraction_state = "ready"
            with pytest.raises(KnowledgeLifecycleConflict, match="publication became stale"):
                await repository.ensure_publication_current(
                    session,
                    document.id,
                    3,
                    expected_approved_version_id=approved_snapshot,
                )
            assert replacement.lifecycle == "approved"
            assert stale_candidate.lifecycle == "imported"
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeChunkModel)
                    .where(KnowledgeChunkModel.document_version_id == stale_candidate.id)
                )
                == 0
            )

            current_snapshot = replacement.id
            await repository.deprecate_version(
                session,
                document.id,
                2,
                expected_approved_version_id=current_snapshot,
            )
            with pytest.raises(KnowledgeLifecycleConflict, match="publication became stale"):
                await repository.ensure_publication_current(
                    session,
                    document.id,
                    3,
                    expected_approved_version_id=current_snapshot,
                )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeChunkModel)
                    .where(KnowledgeChunkModel.document_version_id == stale_candidate.id)
                )
                == 0
            )
            await session.rollback()

    asyncio.run(scenario())


def test_approved_catalog_unions_aliases_and_removes_only_deprecated_unique_tags(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The derived catalog keeps overlapping aliases visible and drops only absent approved tags."""

    async def scenario() -> None:
        repository = KnowledgeRepository()
        async with session_factory() as session:
            first = await repository.create_document(
                session,
                source_version("b" * 64).model_copy(
                    update={
                        "service_tags": (
                            KnowledgeServiceTag(
                                service_id="cooling-loop", aliases=("cooling", "chiller")
                            ),
                            KnowledgeServiceTag(service_id="legacy-gateway", aliases=("shared",)),
                        )
                    }
                ),
            )
            second = await repository.create_document(
                session,
                source_version("c" * 64).model_copy(
                    update={
                        "service_tags": (
                            KnowledgeServiceTag(
                                service_id="cooling-loop", aliases=("plant", "chiller")
                            ),
                            KnowledgeServiceTag(service_id="heating-loop", aliases=("shared",)),
                        )
                    }
                ),
            )
            for document in (first, second):
                version = document.versions[0]
                version.extraction_state = "ready"
                await repository.replace_chunks(session, version.id, (indexed_chunk(),))
                await repository.approve_version(session, document.id, 1)

            catalog = await repository.approved_service_catalog(session)
            assert tuple(entry.model_dump() for entry in catalog) == (
                {"service_id": "cooling-loop", "aliases": ("chiller", "cooling", "plant")},
                {"service_id": "heating-loop", "aliases": ("shared",)},
                {"service_id": "legacy-gateway", "aliases": ("shared",)},
            )

            await repository.deprecate_version(session, first.id, 1)
            assert tuple(
                entry.model_dump() for entry in await repository.approved_service_catalog(session)
            ) == (
                {"service_id": "cooling-loop", "aliases": ("chiller", "plant")},
                {"service_id": "heating-loop", "aliases": ("shared",)},
            )
            await session.rollback()

    asyncio.run(scenario())


def test_two_session_lifecycle_races_reject_stale_publication_before_chunk_replacement(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A real PostgreSQL lifecycle race leaves one authoritative state and no stale chunks."""

    class BlockingEmbedder:
        """Pause one approval after snapshot capture and before publication begins."""

        def __init__(self, started: asyncio.Event, release: asyncio.Event) -> None:
            self._started = started
            self._release = release

        async def embed_documents(self, texts):
            """Signal pre-publication readiness, then return complete deterministic vectors."""
            self._started.set()
            await self._release.wait()
            return tuple(_EMBEDDING for _ in texts)

    async def ready_version(repository, session, document_id, content_hash: str):
        candidate = source_version(content_hash).model_copy(
            update={"source_bytes": f"# Version {content_hash[0]}\nRetained text".encode()}
        )
        version = await repository.add_version(session, document_id, candidate)
        extracted = extract_source(
            version.source_bytes,
            version.source_media_type,
            max_characters=10_000,
        )
        version.extraction_state = "ready"
        version.extracted_text = extracted.text
        return version

    async def prepare_document(repository, session, content_hash: str):
        document = await repository.create_document(session, source_version(content_hash))
        first = document.versions[0]
        extracted = extract_source(
            first.source_bytes,
            first.source_media_type,
            max_characters=10_000,
        )
        first.extraction_state = "ready"
        first.extracted_text = extracted.text
        await repository.replace_chunks(session, first.id, (indexed_chunk(),))
        await repository.approve_version(session, document.id, 1)
        return document, first

    async def chunk_count(session, document_version_id) -> int:
        return (
            await session.scalar(
                select(func.count())
                .select_from(KnowledgeChunkModel)
                .where(KnowledgeChunkModel.document_version_id == document_version_id)
            )
            or 0
        )

    async def scenario() -> None:
        repository = KnowledgeRepository()
        created_document_ids = []
        try:
            async with session_factory() as session:
                approval_document, approved = await prepare_document(repository, session, "e" * 64)
                created_document_ids.append(approval_document.id)
                second = await ready_version(repository, session, approval_document.id, "f" * 64)
                third = await ready_version(repository, session, approval_document.id, "0" * 64)
                await session.commit()

                second_started, third_started, release = (
                    asyncio.Event(),
                    asyncio.Event(),
                    asyncio.Event(),
                )
                second_service = KnowledgePublicationService(
                    session_factory,
                    repository,
                    BlockingEmbedder(second_started, release),
                    max_extraction_characters=10_000,
                )
                third_service = KnowledgePublicationService(
                    session_factory,
                    repository,
                    BlockingEmbedder(third_started, release),
                    max_extraction_characters=10_000,
                )
                second_task = asyncio.create_task(second_service.approve(approval_document.id, 2))
                third_task = asyncio.create_task(third_service.approve(approval_document.id, 3))
                await asyncio.gather(second_started.wait(), third_started.wait())
                release.set()
                outcomes = await asyncio.gather(second_task, third_task, return_exceptions=True)

                assert (
                    sum(isinstance(outcome, KnowledgeLifecycleConflict) for outcome in outcomes)
                    == 1
                )
                assert sum(outcome is None for outcome in outcomes) == 1
                await session.refresh(approved)
                await session.refresh(second)
                await session.refresh(third)
                approved_candidate = second if second.lifecycle == "approved" else third
                stale_candidate = third if approved_candidate is second else second
                assert approved.lifecycle == "deprecated"
                assert approved_candidate.lifecycle == "approved"
                assert stale_candidate.lifecycle == "imported"
                assert await chunk_count(session, stale_candidate.id) == 0

                deprecation_document, deprecated = await prepare_document(
                    repository, session, "1" * 64
                )
                created_document_ids.append(deprecation_document.id)
                replacement = await ready_version(
                    repository, session, deprecation_document.id, "2" * 64
                )
                await session.commit()
                approval_started, deprecation_release = asyncio.Event(), asyncio.Event()
                replacement_service = KnowledgePublicationService(
                    session_factory,
                    repository,
                    BlockingEmbedder(approval_started, deprecation_release),
                    max_extraction_characters=10_000,
                )
                approval_task = asyncio.create_task(
                    replacement_service.approve(deprecation_document.id, 2)
                )
                await approval_started.wait()
                await replacement_service.deprecate(deprecation_document.id, 1)
                deprecation_release.set()
                assert isinstance(
                    (await asyncio.gather(approval_task, return_exceptions=True))[0],
                    KnowledgeLifecycleConflict,
                )
                await session.refresh(deprecated)
                await session.refresh(replacement)
                assert deprecated.lifecycle == "deprecated"
                assert replacement.lifecycle == "imported"
                assert await chunk_count(session, replacement.id) == 0
        finally:
            if created_document_ids:
                async with session_factory.begin() as cleanup_session:
                    await cleanup_session.execute(
                        delete(KnowledgeDocumentModel).where(
                            KnowledgeDocumentModel.id.in_(created_document_ids)
                        )
                    )

    asyncio.run(scenario())


def test_knowledge_migration_downgrades_only_when_corpus_and_scope_are_empty(
    postgres_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Keep schema and revision intact when downgrade would discard retained data or scope."""
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", postgres_url)

    async def create_retained_document() -> object:
        repository = KnowledgeRepository()
        async with session_factory() as session:
            document = await repository.create_document(session, source_version("6" * 64))
            await session.commit()
            return document.id

    async def delete_document(document_id: object) -> None:
        async with session_factory() as session:
            await session.execute(
                delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == document_id)
            )
            await session.commit()

    async def create_scoped_observation() -> object:
        async with session_factory() as session:
            scoped_observation = ObservationModel(
                name="Migration guard observation",
                description=None,
                objective="Verify retained scope blocks downgrade.",
                knowledge_scope={"service_ids": ["cooling-loop"]},
            )
            session.add(scoped_observation)
            await session.commit()
            return scoped_observation.id

    async def delete_observation(observation_id: object) -> None:
        async with session_factory() as session:
            await session.execute(
                delete(ObservationModel).where(ObservationModel.id == observation_id)
            )
            await session.commit()

    assert asyncio.run(alembic_revision(session_factory)) == _MIGRATION_REVISION
    command.downgrade(config, _PRE_KNOWLEDGE_REVISION)
    assert asyncio.run(alembic_revision(session_factory)) == _PRE_KNOWLEDGE_REVISION
    assert not asyncio.run(knowledge_table_exists(session_factory))
    command.upgrade(config, "head")
    assert asyncio.run(alembic_revision(session_factory)) == _MIGRATION_REVISION
    assert asyncio.run(knowledge_table_exists(session_factory))

    document_id = asyncio.run(create_retained_document())
    with pytest.raises(RuntimeError, match="knowledge records"):
        command.downgrade(config, _PRE_KNOWLEDGE_REVISION)
    assert asyncio.run(alembic_revision(session_factory)) == _MIGRATION_REVISION
    asyncio.run(delete_document(document_id))

    observation_id = asyncio.run(create_scoped_observation())
    with pytest.raises(RuntimeError, match="knowledge scopes"):
        command.downgrade(config, _PRE_KNOWLEDGE_REVISION)
    assert asyncio.run(alembic_revision(session_factory)) == _MIGRATION_REVISION
    asyncio.run(delete_observation(observation_id))
