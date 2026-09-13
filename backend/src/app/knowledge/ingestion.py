"""Durable upload admission and fenced extraction for curated knowledge."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infrastructure.persistence.models import (
    KnowledgeDocumentVersionModel,
)
from app.infrastructure.persistence.repository import KnowledgeRepository
from app.knowledge.extraction import (
    ExtractedKnowledgeDocument,
    KnowledgeExtractionError,
    extract_source,
)
from app.knowledge.management_contracts import KnowledgeDocumentVersionCreate


class KnowledgeUploadRejected(ValueError):
    """Reject upload admission before any immutable source record is created."""


class ExtractionAlreadyRunning(RuntimeError):
    """Signal that a version's advisory extraction lock is held by another request."""


class KnowledgeIngestionService:
    """Retain source bytes before executing one explicit, UUID-fenced extraction attempt."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repository: KnowledgeRepository,
        *,
        max_upload_bytes: int,
        max_extraction_characters: int,
        extractor: Callable[..., ExtractedKnowledgeDocument] = extract_source,
    ) -> None:
        """Bind caller-owned persistence and server-owned source safety limits."""
        self._session_factory = session_factory
        self._repository = repository
        self._max_upload_bytes = max_upload_bytes
        self._max_extraction_characters = max_extraction_characters
        self._extractor = extractor

    @property
    def max_upload_bytes(self) -> int:
        """Return the server-owned immutable-source admission limit."""
        return self._max_upload_bytes

    async def create_document(
        self,
        candidate: KnowledgeDocumentVersionCreate,
    ) -> tuple[UUID, int]:
        """Commit a first immutable version before its single initial extraction attempt."""
        self._validate_admission(candidate)
        async with self._session_factory() as session:
            async with session.begin():
                document = await self._repository.create_document(session, candidate)
                document_id = document.id
                version_number = document.versions[0].version
        await self.extract(document_id, version_number)
        return document_id, version_number

    async def add_version(
        self, document_id: UUID, candidate: KnowledgeDocumentVersionCreate
    ) -> int:
        """Commit a later immutable source snapshot before extracting it once."""
        self._validate_admission(candidate)
        async with self._session_factory() as session:
            async with session.begin():
                version = await self._repository.add_version(session, document_id, candidate)
                version_number = version.version
        await self.extract(document_id, version_number)
        return version_number

    async def extract(self, document_id: UUID, version_number: int) -> None:
        """Run one operator-visible extraction attempt and fence its late completion."""
        engine = self._session_factory.kw.get("bind")
        if not isinstance(engine, AsyncEngine):
            raise RuntimeError("knowledge extraction requires an engine-bound session factory")
        # The explicitly held connection retains this session-level advisory lock across
        # the durable attempt claim, CPU extraction, and UUID-fenced completion.
        async with (
            engine.connect() as connection,
            AsyncSession(bind=connection, expire_on_commit=False) as lock_session,
        ):
            version: KnowledgeDocumentVersionModel | None = None
            version_id: UUID | None = None
            try:
                async with lock_session.begin():
                    version = await self._repository.get_version(
                        lock_session, document_id, version_number
                    )
                    if version is None:
                        raise LookupError(
                            f"knowledge document version {version_number} does not exist"
                        )
                    version_id = version.id
                    acquired = await self._repository.try_acquire_extraction_lock(
                        lock_session, version_id
                    )
                    if not acquired:
                        raise ExtractionAlreadyRunning("an extraction attempt is already running")
                    attempt_id = await self._repository.begin_extraction_attempt(
                        lock_session, document_id, version_number
                    )
                try:
                    result = self._extractor(
                        version.source_bytes,
                        version.source_media_type,
                        max_characters=self._max_extraction_characters,
                    )
                except (KnowledgeExtractionError, ValueError):
                    await self._complete(
                        document_id, version_number, attempt_id, None, succeeded=False
                    )
                else:
                    await self._complete(
                        document_id, version_number, attempt_id, result.text, succeeded=True
                    )
            finally:
                if version_id is not None:
                    await self._repository.release_extraction_lock(lock_session, version_id)

    async def _complete(
        self,
        document_id: UUID,
        version_number: int,
        attempt_id: UUID,
        extracted_text: str | None,
        *,
        succeeded: bool,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                return await self._repository.complete_extraction_attempt(
                    session,
                    document_id,
                    version_number,
                    attempt_id,
                    extracted_text=extracted_text,
                    succeeded=succeeded,
                )

    def _validate_admission(self, candidate: KnowledgeDocumentVersionCreate) -> None:
        if len(candidate.source_bytes) > self._max_upload_bytes:
            raise KnowledgeUploadRejected("uploaded source exceeds the server limit")
        _validate_content_type(candidate.source_bytes, candidate.source_media_type)


def make_upload_candidate(
    metadata: KnowledgeDocumentVersionCreate,
    *,
    filename: str | None,
    declared_media_type: str | None,
    source_bytes: bytes,
) -> KnowledgeDocumentVersionCreate:
    """Validate multipart file declarations and build immutable hash-bound source metadata."""
    media_type = _resolve_media_type(filename, declared_media_type, source_bytes)
    return metadata.model_copy(
        update={
            "source_media_type": media_type,
            "source_bytes": source_bytes,
            "content_hash": sha256(source_bytes).hexdigest(),
        }
    )


def _resolve_media_type(
    filename: str | None, declared_media_type: str | None, source: bytes
) -> str:
    suffix = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    suffix_type = {
        "pdf": "application/pdf",
        "md": "text/markdown",
        "markdown": "text/markdown",
    }.get(suffix)
    if suffix_type is None:
        raise KnowledgeUploadRejected("only PDF and Markdown filenames are supported")
    normalized_declared = (declared_media_type or "").split(";", 1)[0].strip().lower()
    if normalized_declared and normalized_declared not in (suffix_type, "application/octet-stream"):
        raise KnowledgeUploadRejected("declared media type does not match filename")
    _validate_content_type(source, suffix_type)
    return suffix_type


def _validate_content_type(source: bytes, media_type: str) -> None:
    if media_type == "application/pdf":
        if not source.startswith(b"%PDF-"):
            raise KnowledgeUploadRejected("uploaded PDF does not have a PDF signature")
        return
    if media_type == "text/markdown":
        try:
            source.decode("utf-8")
        except UnicodeDecodeError as error:
            raise KnowledgeUploadRejected("uploaded Markdown is not valid UTF-8") from error
        return
    raise KnowledgeUploadRejected("only PDF and Markdown sources are supported")
