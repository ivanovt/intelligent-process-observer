"""PostgreSQL integration coverage for curated knowledge persistence invariants."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.infrastructure.persistence.repository import KnowledgeRepository
from app.knowledge.management_contracts import (
    KnowledgeAuthority,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeServiceTag,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
            await repository.approve_version(session, document.id, 1)

            async with session.begin_nested():
                with pytest.raises(IntegrityError):
                    await repository.add_version(session, document.id, source_version("1" * 64))

            second = await repository.add_version(session, document.id, source_version("2" * 64))
            second.extraction_state = "ready"
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
