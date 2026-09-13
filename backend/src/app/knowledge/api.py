"""HTTP boundary for curated knowledge administration and scope suggestions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import get_settings
from app.infrastructure.openrouter.composition import build_knowledge_scope_suggestion_agent
from app.infrastructure.openrouter.embeddings import (
    OpenRouterEmbeddingAdapter,
    OpenRouterEmbeddingError,
)
from app.infrastructure.persistence.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentVersionModel,
)
from app.infrastructure.persistence.repository import (
    KnowledgeLifecycleConflict,
    KnowledgeRepository,
)
from app.knowledge.ingestion import (
    ExtractionAlreadyRunning,
    KnowledgeIngestionService,
    KnowledgeUploadRejected,
    make_upload_candidate,
)
from app.knowledge.management_contracts import (
    KnowledgeAuthority,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeServiceTag,
)
from app.knowledge.publication import KnowledgePublicationRejected, KnowledgePublicationService
from app.knowledge.scope_suggestion import (
    KnowledgeScopeSuggestionDraft,
    KnowledgeScopeSuggestionResponse,
    KnowledgeScopeSuggestionService,
)
from app.observations.errors import ApiError

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeUploadMetadata(BaseModel):
    """Strict multipart metadata submitted before immutable source bytes are retained."""

    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1)
    document_type: KnowledgeDocumentType
    authority: KnowledgeAuthority
    owner: str = Field(min_length=1)
    source_reference: str | None = None
    service_tags: tuple[KnowledgeServiceTag, ...] = ()


class KnowledgeServiceTagResponse(BaseModel):
    """Public immutable applicability metadata for one source version."""

    service_id: str
    aliases: tuple[str, ...]
    supported_versions: tuple[str, ...]


class KnowledgeVersionResponse(BaseModel):
    """Public immutable source-version and derived-state projection."""

    version: int
    title: str
    document_type: KnowledgeDocumentType
    authority: KnowledgeAuthority
    owner: str
    source_reference: str | None
    media_type: str
    content_hash: str
    extraction_state: str
    lifecycle_state: str
    service_tags: tuple[KnowledgeServiceTagResponse, ...]


class KnowledgeDocumentResponse(BaseModel):
    """Document identity with current display metadata and optional immutable history."""

    id: UUID
    title: str
    document_type: KnowledgeDocumentType
    authority: KnowledgeAuthority
    service_tags: tuple[KnowledgeServiceTagResponse, ...]
    active_version: int | None
    versions: tuple[KnowledgeVersionResponse, ...] | None = None


class KnowledgeChunkResponse(BaseModel):
    """Inert exact historical chunk projection for a recognized citation locator."""

    ordinal: int
    location: str
    text: str


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one request session for local read projections without committing it."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_scope_suggestion_service() -> KnowledgeScopeSuggestionService:
    """Build the transient service with lazy model composition after catalog loading."""
    return KnowledgeScopeSuggestionService(
        KnowledgeRepository(), lambda: build_knowledge_scope_suggestion_agent(get_settings())
    )


async def get_ingestion_service(request: Request) -> KnowledgeIngestionService:
    """Build durable upload/extraction orchestration from lifespan-owned persistence."""
    settings = get_settings()
    return KnowledgeIngestionService(
        request.app.state.session_factory,
        KnowledgeRepository(),
        max_upload_bytes=settings.knowledge_upload_max_bytes,
        max_extraction_characters=settings.knowledge_extraction_max_characters,
    )


async def get_publication_service(request: Request) -> KnowledgePublicationService:
    """Build explicit publication orchestration with the server-only embedding adapter."""
    settings = get_settings()
    return KnowledgePublicationService(
        request.app.state.session_factory,
        KnowledgeRepository(),
        OpenRouterEmbeddingAdapter(settings),
        max_extraction_characters=settings.knowledge_extraction_max_characters,
    )


@router.post("/scope-suggestion", response_model=KnowledgeScopeSuggestionResponse)
async def suggest_knowledge_scope(
    draft: KnowledgeScopeSuggestionDraft,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: KnowledgeScopeSuggestionService = Depends(get_scope_suggestion_service),  # noqa: B008
) -> KnowledgeScopeSuggestionResponse:
    """Return an advisory catalog-backed scope suggestion without persisting the draft."""
    return await service.suggest(session, draft)


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
async def list_documents(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[KnowledgeDocumentResponse]:
    """List local manually retained knowledge documents without changing lifecycle state."""
    documents = await KnowledgeRepository().list_documents(session)
    return [_document_response(document, include_versions=False) for document in documents]


@router.post("/documents", response_model=KnowledgeDocumentResponse)
async def upload_document(
    request: Request,
    service: KnowledgeIngestionService = Depends(get_ingestion_service),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeDocumentResponse:
    """Retain one validated source before its initial extraction attempt begins."""
    document_id, _ = await _upload(request, service, None)
    return await _read_document_response(session, document_id)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentResponse)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeDocumentResponse:
    """Return one document and every immutable retained version in its history."""
    return await _read_document_response(session, document_id)


@router.post("/documents/{document_id}/versions", response_model=KnowledgeDocumentResponse)
async def upload_version(
    document_id: UUID,
    request: Request,
    service: KnowledgeIngestionService = Depends(get_ingestion_service),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeDocumentResponse:
    """Retain one later immutable source version before extracting it once."""
    await _upload(request, service, document_id)
    return await _read_document_response(session, document_id)


@router.post(
    "/documents/{document_id}/versions/{version}/retry-extraction",
    response_model=KnowledgeDocumentResponse,
)
async def retry_extraction(
    document_id: UUID,
    version: Annotated[int, Path(gt=0)],
    service: KnowledgeIngestionService = Depends(get_ingestion_service),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeDocumentResponse:
    """Run one explicit re-extraction of the exact retained immutable source version."""
    try:
        await service.extract(document_id, version)
    except ExtractionAlreadyRunning as error:
        raise ApiError(
            409, "knowledge_extraction_running", "Extraction is already running"
        ) from error
    except LookupError as error:
        raise ApiError(
            404, "knowledge_version_not_found", "Knowledge version was not found"
        ) from error
    except ValueError as error:
        raise ApiError(
            422, "knowledge_extraction_rejected", "Extraction cannot be retried"
        ) from error
    return await _read_document_response(session, document_id)


@router.post(
    "/documents/{document_id}/versions/{version}/approve", response_model=KnowledgeDocumentResponse
)
async def approve_version(
    document_id: UUID,
    version: Annotated[int, Path(gt=0)],
    service: KnowledgePublicationService = Depends(get_publication_service),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeDocumentResponse:
    """Index and atomically publish one ready immutable version after explicit approval."""
    try:
        await service.approve(document_id, version)
    except KnowledgeLifecycleConflict as error:
        raise ApiError(
            409, "knowledge_lifecycle_conflict", "Knowledge lifecycle action is stale"
        ) from error
    except LookupError as error:
        raise ApiError(
            404, "knowledge_version_not_found", "Knowledge version was not found"
        ) from error
    except KnowledgePublicationRejected as error:
        raise ApiError(
            422, "knowledge_publication_rejected", "Knowledge version cannot be approved"
        ) from error
    except (OpenRouterEmbeddingError, TimeoutError) as error:
        raise ApiError(
            503, "knowledge_index_unavailable", "Knowledge indexing is unavailable"
        ) from error
    return await _read_document_response(session, document_id)


@router.post(
    "/documents/{document_id}/versions/{version}/deprecate",
    response_model=KnowledgeDocumentResponse,
)
async def deprecate_version(
    document_id: UUID,
    version: Annotated[int, Path(gt=0)],
    service: KnowledgePublicationService = Depends(get_publication_service),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeDocumentResponse:
    """Remove exactly one approved version from future retrieval eligibility."""
    try:
        await service.deprecate(document_id, version)
    except KnowledgeLifecycleConflict as error:
        raise ApiError(
            409, "knowledge_lifecycle_conflict", "Knowledge lifecycle action is stale"
        ) from error
    except LookupError as error:
        raise ApiError(
            404, "knowledge_version_not_found", "Knowledge version was not found"
        ) from error
    except KnowledgePublicationRejected as error:
        raise ApiError(
            422, "knowledge_publication_rejected", "Knowledge version cannot be deprecated"
        ) from error
    return await _read_document_response(session, document_id)


@router.get("/documents/{document_id}/versions/{version}/source")
async def download_source(
    document_id: UUID,
    version: Annotated[int, Path(gt=0)],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Return only the exact retained source bytes as a safe inert browser attachment."""
    source = await KnowledgeRepository().get_version(session, document_id, version)
    if source is None:
        raise ApiError(404, "knowledge_version_not_found", "Knowledge version was not found")
    extension = ".pdf" if source.source_media_type == "application/pdf" else ".md"
    filename = f"knowledge-document-{document_id}-v{version}{extension}"
    return Response(
        content=source.source_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/documents/{document_id}/versions/{version}/chunks/{ordinal}",
    response_model=KnowledgeChunkResponse,
)
async def get_chunk(
    document_id: UUID,
    version: Annotated[int, Path(gt=0)],
    ordinal: Annotated[int, Path(gt=0)],
    page: Annotated[int | None, Query(gt=0)] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeChunkResponse:
    """Resolve one exact PDF page-local or Markdown document-local historical chunk."""
    chunk = await KnowledgeRepository().get_chunk(
        session, document_id, version, ordinal, page_number=page
    )
    if chunk is None:
        raise ApiError(404, "knowledge_chunk_not_found", "Knowledge chunk was not found")
    return _chunk_response(chunk)


async def _upload(
    request: Request, service: KnowledgeIngestionService, document_id: UUID | None
) -> tuple[UUID, int]:
    """Parse strict multipart input without introducing an unapproved multipart dependency."""
    try:
        metadata_text, filename, declared_type, source_bytes = await _multipart_upload(
            request, max_upload_bytes=service.max_upload_bytes
        )
        metadata = KnowledgeUploadMetadata.model_validate_json(metadata_text)
        candidate = make_upload_candidate(
            KnowledgeDocumentVersionCreate(
                title=metadata.title,
                document_type=metadata.document_type,
                authority=metadata.authority,
                owner=metadata.owner,
                source_reference=metadata.source_reference,
                source_media_type="text/markdown",
                source_bytes=b"placeholder",
                content_hash="placeholder",
                service_tags=metadata.service_tags,
            ),
            filename=filename,
            declared_media_type=declared_type,
            source_bytes=source_bytes,
        )
        if document_id is None:
            return await service.create_document(candidate)
        version = await service.add_version(document_id, candidate)
        return document_id, version
    except (KnowledgeUploadRejected, ValueError) as error:
        raise ApiError(422, "knowledge_upload_rejected", "Knowledge upload is invalid") from error
    except IntegrityError as error:
        raise ApiError(
            409, "knowledge_duplicate_source", "This source version is already retained"
        ) from error
    except LookupError as error:
        raise ApiError(
            404, "knowledge_document_not_found", "Knowledge document was not found"
        ) from error
    except ExtractionAlreadyRunning as error:
        raise ApiError(
            409, "knowledge_extraction_running", "Extraction is already running"
        ) from error


async def _multipart_upload(
    request: Request, *, max_upload_bytes: int
) -> tuple[str, str | None, str | None, bytes]:
    """Decode the two accepted multipart fields with bounded, dependency-free parsing."""
    content_type = request.headers.get("content-type", "")
    marker = "boundary="
    if not content_type.startswith("multipart/form-data") or marker not in content_type:
        raise KnowledgeUploadRejected("knowledge upload must use multipart form data")
    boundary = content_type.split(marker, 1)[1].strip().strip('"').encode("ascii", "strict")
    payload = await _bounded_body(request, max_upload_bytes=max_upload_bytes)
    fields = _parse_multipart(payload, boundary)
    metadata = fields.get("metadata")
    file = fields.get("file")
    if metadata is None or file is None:
        raise KnowledgeUploadRejected("knowledge upload requires metadata and file fields")
    if len(file[1]) > max_upload_bytes:
        raise KnowledgeUploadRejected("uploaded source exceeds the server limit")
    try:
        metadata_text = metadata[1].decode("utf-8")
    except UnicodeDecodeError as error:
        raise KnowledgeUploadRejected("knowledge metadata is not valid UTF-8") from error
    disposition = file[0].get("content-disposition", "")
    return (
        metadata_text,
        _disposition_value(disposition, "filename"),
        file[0].get("content-type"),
        file[1],
    )


async def _bounded_body(request: Request, *, max_upload_bytes: int) -> bytes:
    """Read multipart framing incrementally while bounding total allocation before parsing."""
    maximum_body_bytes = max_upload_bytes + 65_536
    body = bytearray()
    async for fragment in request.stream():
        if len(body) + len(fragment) > maximum_body_bytes:
            raise KnowledgeUploadRejected("knowledge upload exceeds the server limit")
        body.extend(fragment)
    return bytes(body)


def _parse_multipart(payload: bytes, boundary: bytes) -> dict[str, tuple[dict[str, str], bytes]]:
    """Parse fixed-form MIME parts only at complete delimiter lines, preserving source bytes."""
    opening = b"--" + boundary + b"\r\n"
    if not payload.startswith(opening):
        raise KnowledgeUploadRejected("knowledge upload has invalid multipart framing")
    fields: dict[str, tuple[dict[str, str], bytes]] = {}
    cursor = len(opening)
    while True:
        headers_end = payload.find(b"\r\n\r\n", cursor)
        if headers_end < 0:
            raise KnowledgeUploadRejected("knowledge upload has invalid multipart headers")
        headers = _multipart_headers(payload[cursor:headers_end])
        content_start = headers_end + 4
        boundary_start, terminal = _next_multipart_boundary(payload, boundary, content_start)
        if boundary_start is None:
            raise KnowledgeUploadRejected("knowledge upload has incomplete multipart framing")
        name = _disposition_value(headers.get("content-disposition", ""), "name")
        if name is not None:
            if name in fields:
                raise KnowledgeUploadRejected("knowledge upload has duplicate multipart fields")
            fields[name] = (headers, payload[content_start:boundary_start])
        if terminal:
            return fields
        cursor = boundary_start + len(boundary) + 6


def _next_multipart_boundary(
    payload: bytes, boundary: bytes, start: int
) -> tuple[int | None, bool]:
    """Find a MIME delimiter line without mistaking arbitrary PDF bytes for a boundary."""
    marker = b"\r\n--" + boundary
    candidate = payload.find(marker, start)
    while candidate >= 0:
        suffix_start = candidate + len(marker)
        suffix = payload[suffix_start : suffix_start + 2]
        if suffix == b"--":
            if payload[suffix_start + 2 :] in (b"", b"\r\n"):
                return candidate, True
        elif suffix == b"\r\n":
            return candidate, False
        candidate = payload.find(marker, candidate + 1)
    return None, False


def _multipart_headers(raw_headers: bytes) -> dict[str, str]:
    """Decode simple MIME part headers required by the fixed local upload form."""
    headers: dict[str, str] = {}
    for line in raw_headers.decode("latin-1").split("\r\n"):
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    return headers


def _disposition_value(disposition: str, key: str) -> str | None:
    """Read one fixed-form disposition parameter without interpreting its contents."""
    for parameter in disposition.split(";")[1:]:
        name, separator, value = parameter.strip().partition("=")
        if separator and name.lower() == key:
            return value.strip().strip('"')
    return None


async def _read_document_response(
    session: AsyncSession, document_id: UUID
) -> KnowledgeDocumentResponse:
    document = await KnowledgeRepository().get_document(session, document_id)
    if document is None:
        raise ApiError(404, "knowledge_document_not_found", "Knowledge document was not found")
    return _document_response(document, include_versions=True)


def _document_response(
    document: KnowledgeDocumentModel, *, include_versions: bool
) -> KnowledgeDocumentResponse:
    versions = sorted(document.versions, key=lambda item: item.version)
    current = versions[-1]
    active = next((item.version for item in versions if item.lifecycle == "approved"), None)
    return KnowledgeDocumentResponse(
        id=document.id,
        title=current.title,
        document_type=KnowledgeDocumentType(current.document_type),
        authority=KnowledgeAuthority(current.authority),
        service_tags=_service_tags(current),
        active_version=active,
        versions=tuple(_version_response(item) for item in versions) if include_versions else None,
    )


def _version_response(version: KnowledgeDocumentVersionModel) -> KnowledgeVersionResponse:
    return KnowledgeVersionResponse(
        version=version.version,
        title=version.title,
        document_type=KnowledgeDocumentType(version.document_type),
        authority=KnowledgeAuthority(version.authority),
        owner=version.owner,
        source_reference=version.source_reference,
        media_type=version.source_media_type,
        content_hash=version.content_hash,
        extraction_state=version.extraction_state,
        lifecycle_state=version.lifecycle,
        service_tags=_service_tags(version),
    )


def _service_tags(
    version: KnowledgeDocumentVersionModel,
) -> tuple[KnowledgeServiceTagResponse, ...]:
    return tuple(
        KnowledgeServiceTagResponse(
            service_id=tag.service_id,
            aliases=tuple(tag.aliases),
            supported_versions=tuple(tag.supported_versions),
        )
        for tag in version.service_tags
    )


def _chunk_response(chunk: KnowledgeChunkModel) -> KnowledgeChunkResponse:
    if chunk.page_number is not None:
        location = f"PDF page {chunk.page_number}, chunk {chunk.page_ordinal}"
    elif chunk.heading_path:
        location = f"Markdown {' > '.join(chunk.heading_path)}, chunk {chunk.ordinal}"
    else:
        location = f"Markdown chunk {chunk.ordinal}"
    return KnowledgeChunkResponse(
        ordinal=chunk.page_ordinal or chunk.ordinal, location=location, text=chunk.text
    )
