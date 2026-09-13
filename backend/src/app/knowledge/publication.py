"""Explicit index preparation and atomic lifecycle publication for curated knowledge."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.repository import (
    KnowledgeLifecycleConflict,
    KnowledgeRepository,
)
from app.knowledge.extraction import KnowledgeExtractionError, extract_source
from app.knowledge.management_contracts import KnowledgeChunkCreate


class DocumentEmbedder(Protocol):
    """Embed derived, approved source passages for the curated index."""

    async def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Return one validated embedding for every supplied derived passage."""


class KnowledgePublicationRejected(ValueError):
    """Reject lifecycle publication without modifying a prior approved version."""


class KnowledgePublicationService:
    """Prepare chunks outside publication, then atomically index and publish one version."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repository: KnowledgeRepository,
        embedder: DocumentEmbedder,
        *,
        max_extraction_characters: int,
    ) -> None:
        """Bind the repository, server-only embedding adapter, and extraction bound."""
        self._session_factory = session_factory
        self._repository = repository
        self._embedder = embedder
        self._max_extraction_characters = max_extraction_characters

    async def approve(self, document_id: UUID, version_number: int) -> None:
        """Validate, index, and publish a ready imported version in one lifecycle transaction."""
        async with self._session_factory() as session:
            version = await self._repository.get_version(session, document_id, version_number)
            if version is None:
                raise LookupError(f"knowledge document version {version_number} does not exist")
            if version.lifecycle != "imported" or version.extraction_state != "ready":
                raise KnowledgePublicationRejected("only a ready imported version can be approved")
            expected_approved = await self._repository.approved_version_id(session, document_id)
            try:
                extracted = extract_source(
                    version.source_bytes,
                    version.source_media_type,
                    max_characters=self._max_extraction_characters,
                )
            except KnowledgeExtractionError as error:
                raise KnowledgePublicationRejected("stored source cannot be revalidated") from error
            if extracted.text != version.extracted_text:
                raise KnowledgePublicationRejected(
                    "stored extraction no longer matches its retained source"
                )
            vectors = await self._embedder.embed_documents(
                tuple(passage.text for passage in extracted.passages)
            )
        if len(vectors) != len(extracted.passages):
            raise KnowledgePublicationRejected("embedding service returned an incomplete index")
        chunks = tuple(
            KnowledgeChunkCreate(
                ordinal=ordinal,
                text=passage.text,
                embedding=vector,
                page_number=passage.page_number,
                page_ordinal=passage.page_ordinal,
                heading_path=passage.heading_path,
            )
            for ordinal, (passage, vector) in enumerate(
                zip(extracted.passages, vectors, strict=True), start=1
            )
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    version = await self._repository.ensure_publication_current(
                        session,
                        document_id,
                        version_number,
                        expected_approved_version_id=expected_approved,
                    )
                    await self._repository.replace_chunks(session, version.id, chunks)
                    await self._repository.approve_version(
                        session,
                        document_id,
                        version_number,
                        expected_approved_version_id=expected_approved,
                    )
        except KnowledgeLifecycleConflict:
            raise

    async def deprecate(self, document_id: UUID, version_number: int) -> None:
        """Remove one approved version from eligibility while retaining all source history."""
        async with self._session_factory() as session:
            version = await self._repository.get_version(session, document_id, version_number)
            if version is None:
                raise LookupError(f"knowledge document version {version_number} does not exist")
            expected_approved = await self._repository.approved_version_id(session, document_id)
        if expected_approved != version.id:
            raise KnowledgePublicationRejected(
                "only the current approved version can be deprecated"
            )
        await self._deprecate_transaction(document_id, version_number, expected_approved)

    async def _deprecate_transaction(
        self, document_id: UUID, version_number: int, expected_approved: UUID
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await self._repository.deprecate_version(
                    session,
                    document_id,
                    version_number,
                    expected_approved_version_id=expected_approved,
                )
