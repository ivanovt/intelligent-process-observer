"""PostgreSQL integration coverage for curated retrieval eligibility and provenance."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.infrastructure.knowledge.retrieval import (
    CuratedKnowledgeReferenceResolver,
    CuratedKnowledgeRetriever,
    _eligible_chunks,
    _serialize_admitted_candidates,
    build_curated_knowledge_reference,
)
from app.infrastructure.persistence.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentServiceTagModel,
    KnowledgeDocumentVersionModel,
)
from app.knowledge.management_contracts import KnowledgeScope

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_EMBEDDING = [1.0, *([0.0] * 1_535)]
_UNRELATED_EMBEDDING = [0.0, 1.0, *([0.0] * 1_534)]


@pytest.fixture(scope="module")
def postgres_url() -> Generator[str]:
    """Provide the explicitly configured PostgreSQL database at the migration head."""
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
    """Create short-lived sessions against the configured PostgreSQL database."""
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def _version(
    document_id: UUID,
    number: int,
    lifecycle: str,
    *,
    source_name: str,
) -> KnowledgeDocumentVersionModel:
    """Build a retained version with a unique source identity for one isolated test transaction."""
    return KnowledgeDocumentVersionModel(
        id=uuid4(),
        document_id=document_id,
        version=number,
        title=source_name,
        document_type="runbook",
        authority="internal_approved",
        owner="operations",
        source_media_type="text/markdown",
        source_bytes=source_name.encode(),
        content_hash=f"{uuid4().hex}{uuid4().hex}",
        lifecycle=lifecycle,
        extraction_state="ready",
    )


def _chunk(
    version: KnowledgeDocumentVersionModel,
    ordinal: int,
    text: str,
    *,
    page_number: int | None = None,
    page_ordinal: int | None = None,
    heading_path: list[str] | None = None,
) -> KnowledgeChunkModel:
    """Build one searchable retained chunk with a valid pgvector embedding."""
    return KnowledgeChunkModel(
        document_version_id=version.id,
        ordinal=ordinal,
        text=text,
        embedding=_EMBEDDING,
        page_number=page_number,
        page_ordinal=page_ordinal,
        heading_path=heading_path,
    )


def _tag(
    version: KnowledgeDocumentVersionModel,
    service_id: str,
    supported_versions: list[str] | None = None,
) -> KnowledgeDocumentServiceTagModel:
    """Build one version-local service applicability tag."""
    return KnowledgeDocumentServiceTagModel(
        document_version_id=version.id,
        service_id=service_id,
        aliases=[],
        supported_versions=supported_versions or [],
    )


async def _eligible_texts(session: AsyncSession, scope: KnowledgeScope | None) -> set[str]:
    """Read PostgreSQL's actual metadata-first eligibility result for one scope."""
    eligible = _eligible_chunks(scope).cte("eligible")
    return set(await session.scalars(select(eligible.c.text)))


def test_postgresql_retrieval_eligibility_admits_only_approved_global_or_matching_tags(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Exercise global, scoped, versioned, excluded, and unrelated retrieval in PostgreSQL."""

    async def scenario() -> None:
        async with session_factory() as session:
            transaction = await session.begin()
            try:
                global_document = KnowledgeDocumentModel(id=uuid4())
                global_version = _version(
                    global_document.id, 1, "approved", source_name="global runbook"
                )
                versioned_document = KnowledgeDocumentModel(id=uuid4())
                versioned = _version(
                    versioned_document.id, 1, "approved", source_name="mprm v2 runbook"
                )
                unversioned_document = KnowledgeDocumentModel(id=uuid4())
                unversioned = _version(
                    unversioned_document.id, 1, "approved", source_name="mprm runbook"
                )
                other_document = KnowledgeDocumentModel(id=uuid4())
                other = _version(other_document.id, 1, "approved", source_name="other runbook")
                imported_document = KnowledgeDocumentModel(id=uuid4())
                imported = _version(
                    imported_document.id, 1, "imported", source_name="imported runbook"
                )
                deprecated_document = KnowledgeDocumentModel(id=uuid4())
                deprecated = _version(
                    deprecated_document.id, 1, "deprecated", source_name="old runbook"
                )
                session.add_all(
                    (
                        global_document,
                        versioned_document,
                        unversioned_document,
                        other_document,
                        imported_document,
                        deprecated_document,
                        global_version,
                        versioned,
                        unversioned,
                        other,
                        imported,
                        deprecated,
                        _chunk(global_version, 1, "global-token"),
                        _chunk(versioned, 1, "versioned-service-token"),
                        _chunk(unversioned, 1, "unversioned-service-token"),
                        _chunk(other, 1, "other-service-token"),
                        _chunk(imported, 1, "imported-token"),
                        _chunk(deprecated, 1, "deprecated-token"),
                        _tag(versioned, "mprm-server", ["2.x"]),
                        _tag(unversioned, "mprm-server"),
                        _tag(other, "another-service"),
                        _tag(imported, "mprm-server"),
                        _tag(deprecated, "mprm-server"),
                    )
                )
                await session.flush()

                assert await _eligible_texts(session, None) == {"global-token"}
                assert await _eligible_texts(
                    session, KnowledgeScope(service_ids=("mprm-server",))
                ) == {
                    "global-token",
                    "unversioned-service-token",
                    "versioned-service-token",
                }
                assert await _eligible_texts(
                    session, KnowledgeScope(service_ids=("mprm-server",), service_version="2.x")
                ) == {
                    "global-token",
                    "unversioned-service-token",
                    "versioned-service-token",
                }
                assert await _eligible_texts(
                    session, KnowledgeScope(service_ids=("mprm-server",), service_version="3.x")
                ) == {"global-token", "unversioned-service-token"}

                retriever = CuratedKnowledgeRetriever(
                    session_factory,
                    embedder=object(),
                    scope=None,  # type: ignore[arg-type]
                )
                candidates = await retriever._search_candidates(  # noqa: SLF001
                    session, "wholly-unrelated-query", _UNRELATED_EMBEDDING
                )
                assert _serialize_admitted_candidates(candidates) == ()
            finally:
                await transaction.rollback()

    asyncio.run(scenario())


def test_postgresql_historical_resolver_keeps_exact_pdf_and_markdown_chunks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Resolve deprecated PDF and duplicate-heading Markdown citations without substitution."""

    async def scenario() -> None:
        async with session_factory() as session:
            transaction = await session.begin()
            try:
                markdown_document = KnowledgeDocumentModel(id=uuid4())
                markdown_old = _version(
                    markdown_document.id, 1, "deprecated", source_name="old markdown"
                )
                markdown_current = _version(
                    markdown_document.id, 2, "approved", source_name="current markdown"
                )
                pdf_document = KnowledgeDocumentModel(id=uuid4())
                pdf_old = _version(pdf_document.id, 1, "deprecated", source_name="old pdf")
                pdf_current = _version(pdf_document.id, 2, "approved", source_name="current pdf")
                session.add_all(
                    (
                        markdown_document,
                        pdf_document,
                        markdown_old,
                        markdown_current,
                        pdf_old,
                        pdf_current,
                        _chunk(
                            markdown_old,
                            1,
                            "first repeated Markdown section",
                            heading_path=["Diagnostics", "Repeated"],
                        ),
                        _chunk(
                            markdown_old,
                            2,
                            "second repeated Markdown section",
                            heading_path=["Diagnostics", "Repeated"],
                        ),
                        _chunk(
                            markdown_current,
                            1,
                            "replacement Markdown section",
                            heading_path=["Diagnostics", "Repeated"],
                        ),
                        _chunk(
                            pdf_old,
                            47,
                            "heading-free historical PDF passage",
                            page_number=12,
                            page_ordinal=3,
                        ),
                        _chunk(
                            pdf_current,
                            47,
                            "replacement PDF passage",
                            page_number=12,
                            page_ordinal=3,
                        ),
                    )
                )
                await session.flush()

                resolver = CuratedKnowledgeReferenceResolver()
                markdown = await resolver.resolve(
                    session,
                    build_curated_knowledge_reference(
                        markdown_document.id,
                        1,
                        ordinal=2,
                        page_number=None,
                        page_ordinal=None,
                    ),
                )
                pdf = await resolver.resolve(
                    session,
                    build_curated_knowledge_reference(
                        pdf_document.id,
                        1,
                        ordinal=47,
                        page_number=12,
                        page_ordinal=3,
                    ),
                )

                assert markdown is not None
                assert markdown.version == 1
                assert markdown.text == "second repeated Markdown section"
                assert markdown.heading_path == ("Diagnostics", "Repeated")
                assert pdf is not None
                assert pdf.version == 1
                assert pdf.text == "heading-free historical PDF passage"
                assert pdf.page_number == 12 and pdf.page_ordinal == 3
            finally:
                await transaction.rollback()

    asyncio.run(scenario())
