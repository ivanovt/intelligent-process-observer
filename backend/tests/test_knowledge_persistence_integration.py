"""PostgreSQL integration coverage for curated knowledge persistence invariants."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.infrastructure.persistence.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentVersionModel,
    ObservationModel,
)
from app.infrastructure.persistence.repository import KnowledgeRepository
from app.knowledge.management_contracts import (
    KNOWLEDGE_EMBEDDING_DIMENSIONS,
    KnowledgeAuthority,
    KnowledgeChunkCreate,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeServiceTag,
)

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
