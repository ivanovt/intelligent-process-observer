"""PostgreSQL-backed retrieval and provenance for approved curated knowledge."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID

from sqlalchemy import Float, and_, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select

from app.infrastructure.persistence.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentServiceTagModel,
    KnowledgeDocumentVersionModel,
)
from app.knowledge.contracts import (
    KnowledgeReference,
    KnowledgeRetrievalRequest,
    RetrievalSuccess,
    RetrievedKnowledgeItem,
)
from app.knowledge.management_contracts import KnowledgeScope

_SOURCE_ID_PATTERN = re.compile(
    r"^knowledge-document:(?P<document_id>[0-9a-f]{8}"
    r"-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}):v(?P<version>[1-9][0-9]*)$"
)
_PDF_REFERENCE_PATTERN = re.compile(
    r"^pdf:page:(?P<page>[1-9][0-9]*):chunk:(?P<chunk>[1-9][0-9]*)$"
)
_MARKDOWN_REFERENCE_PATTERN = re.compile(r"^md:chunk:(?P<chunk>[1-9][0-9]*)$")

_LEXICAL_ADMISSION_MINIMUM = 0.05
_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE = 0.35
_CANDIDATE_LIMIT = 32
_RECIPROCAL_RANK_K = 60
_MAX_PASSAGES = 4
_MAX_SERIALIZED_BYTES = 8_192


class QueryEmbedder(Protocol):
    """Create one query embedding for the curated retrieval adapter."""

    async def embed_query(self, text: str) -> tuple[float, ...]:
        """Return a validated embedding for one non-blank retrieval query."""


@dataclass(frozen=True, slots=True)
class CuratedKnowledgeReference:
    """Parsed immutable identity and source location for a curated knowledge chunk."""

    document_id: UUID
    version: int
    ordinal: int
    page_number: int | None = None
    page_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedCuratedKnowledgeReference:
    """Historical chunk projection returned by exact curated-reference resolution."""

    document_id: UUID
    version: int
    ordinal: int
    text: str
    page_number: int | None
    page_ordinal: int | None
    heading_path: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class _Candidate:
    """One metadata-eligible source passage and its hybrid-search scores."""

    chunk_id: UUID
    document_id: UUID
    version: int
    ordinal: int
    text: str
    page_number: int | None
    page_ordinal: int | None
    lexical_rank: float | None = None
    semantic_distance: float | None = None
    lexical_position: int | None = None
    semantic_position: int | None = None


def build_curated_knowledge_reference(
    document_id: UUID,
    version: int,
    *,
    ordinal: int,
    page_number: int | None,
    page_ordinal: int | None,
) -> KnowledgeReference:
    """Build the fixed opaque reference for one immutable curated chunk."""
    if version <= 0 or ordinal <= 0:
        raise ValueError("curated document version and chunk ordinal must be positive")
    if (page_number is None) != (page_ordinal is None):
        raise ValueError("PDF page number and page-local ordinal must be provided together")
    source_id = f"knowledge-document:{document_id}:v{version}"
    if page_number is None:
        return KnowledgeReference(source_id=source_id, reference=f"md:chunk:{ordinal}")
    if page_number <= 0 or page_ordinal is None or page_ordinal <= 0:
        raise ValueError("PDF page number and page-local ordinal must be positive")
    return KnowledgeReference(
        source_id=source_id,
        reference=f"pdf:page:{page_number}:chunk:{page_ordinal}",
    )


def parse_curated_knowledge_reference(
    reference: KnowledgeReference,
) -> CuratedKnowledgeReference | None:
    """Parse the curated adapter's fixed grammar without claiming other opaque references."""
    source_match = _SOURCE_ID_PATTERN.fullmatch(reference.source_id)
    if source_match is None:
        return None
    document_id = UUID(source_match.group("document_id"))
    version = int(source_match.group("version"))
    pdf_match = _PDF_REFERENCE_PATTERN.fullmatch(reference.reference)
    if pdf_match is not None:
        return CuratedKnowledgeReference(
            document_id=document_id,
            version=version,
            ordinal=int(pdf_match.group("chunk")),
            page_number=int(pdf_match.group("page")),
            page_ordinal=int(pdf_match.group("chunk")),
        )
    markdown_match = _MARKDOWN_REFERENCE_PATTERN.fullmatch(reference.reference)
    if markdown_match is None:
        return None
    return CuratedKnowledgeReference(
        document_id=document_id,
        version=version,
        ordinal=int(markdown_match.group("chunk")),
    )


class CuratedKnowledgeReferenceResolver:
    """Resolve curated references to their exact retained historical chunk."""

    async def resolve(
        self,
        session: AsyncSession,
        reference: KnowledgeReference,
    ) -> ResolvedCuratedKnowledgeReference | None:
        """Return the exact retained chunk, including deprecated history, when it exists."""
        parsed = parse_curated_knowledge_reference(reference)
        if parsed is None:
            return None
        statement = (
            select(KnowledgeChunkModel, KnowledgeDocumentVersionModel)
            .join(
                KnowledgeDocumentVersionModel,
                KnowledgeDocumentVersionModel.id == KnowledgeChunkModel.document_version_id,
            )
            .where(
                KnowledgeDocumentVersionModel.document_id == parsed.document_id,
                KnowledgeDocumentVersionModel.version == parsed.version,
            )
        )
        if parsed.page_number is None:
            statement = statement.where(
                KnowledgeChunkModel.ordinal == parsed.ordinal,
                KnowledgeChunkModel.page_number.is_(None),
                KnowledgeChunkModel.page_ordinal.is_(None),
            )
        else:
            statement = statement.where(
                KnowledgeChunkModel.page_number == parsed.page_number,
                KnowledgeChunkModel.page_ordinal == parsed.page_ordinal,
            )
        row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        chunk, version = row
        return ResolvedCuratedKnowledgeReference(
            document_id=version.document_id,
            version=version.version,
            ordinal=chunk.ordinal,
            text=chunk.text,
            page_number=chunk.page_number,
            page_ordinal=chunk.page_ordinal,
            heading_path=tuple(chunk.heading_path) if chunk.heading_path is not None else None,
        )


class CuratedKnowledgeRetriever:
    """Retrieve metadata-eligible, admitted curated passages for one frozen scope."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedder: QueryEmbedder,
        *,
        scope: KnowledgeScope | None,
    ) -> None:
        """Bind server-owned storage, embedding, and frozen scope dependencies."""
        self._session_factory = session_factory
        self._embedder = embedder
        self._scope = scope

    async def retrieve(
        self, request: KnowledgeRetrievalRequest
    ) -> tuple[RetrievedKnowledgeItem, ...]:
        """Return only admitted whole source passages within fixed model-visible bounds."""
        embedding = await self._embedder.embed_query(request.query)
        async with self._session_factory() as session:
            candidates = await self._search_candidates(session, request.query, embedding)
        return _serialize_admitted_candidates(candidates)

    async def _search_candidates(
        self,
        session: AsyncSession,
        query: str,
        embedding: Sequence[float],
    ) -> tuple[_Candidate, ...]:
        eligible = _eligible_chunks(self._scope).cte("eligible_knowledge_chunks")
        tsquery = func.websearch_to_tsquery("simple", query)
        lexical_rank = cast(func.ts_rank_cd(eligible.c.search_vector, tsquery, 32), Float).label(
            "lexical_rank"
        )
        semantic_distance = cast(eligible.c.embedding.op("<=>")(list(embedding)), Float).label(
            "semantic_distance"
        )
        selected_columns = (
            eligible.c.chunk_id,
            eligible.c.document_id,
            eligible.c.version,
            eligible.c.ordinal,
            eligible.c.text,
            eligible.c.page_number,
            eligible.c.page_ordinal,
            lexical_rank,
            semantic_distance,
        )
        lexical_statement = (
            select(*selected_columns)
            .where(eligible.c.search_vector.op("@@")(tsquery))
            .order_by(
                lexical_rank.desc(),
                eligible.c.document_id,
                eligible.c.version,
                eligible.c.ordinal,
            )
            .limit(_CANDIDATE_LIMIT)
        )
        semantic_statement = (
            select(*selected_columns)
            .where(eligible.c.embedding.is_not(None))
            .order_by(
                semantic_distance,
                eligible.c.document_id,
                eligible.c.version,
                eligible.c.ordinal,
            )
            .limit(_CANDIDATE_LIMIT)
        )
        lexical_rows = (await session.execute(lexical_statement)).all()
        semantic_rows = (await session.execute(semantic_statement)).all()
        return _merge_ranked_candidates(lexical_rows, semantic_rows)


def _eligible_chunks(scope: KnowledgeScope | None) -> Select[tuple[object, ...]]:
    """Select only approved chunks allowed by immutable global/service/version metadata."""
    version = KnowledgeDocumentVersionModel
    chunk = KnowledgeChunkModel
    tag = KnowledgeDocumentServiceTagModel
    tag_exists = exists(select(tag.id).where(tag.document_version_id == version.id))
    global_document = ~tag_exists
    eligibility = global_document
    if scope is not None:
        matching_tag = and_(
            tag.document_version_id == version.id,
            tag.service_id.in_(scope.service_ids),
        )
        if scope.service_version is not None:
            version_labels = cast(tag.supported_versions, JSONB)
            matching_tag = and_(
                matching_tag,
                or_(
                    func.jsonb_array_length(version_labels) == 0,
                    version_labels.contains([scope.service_version]),
                ),
            )
        eligibility = or_(global_document, exists(select(tag.id).where(matching_tag)))
    return (
        select(
            chunk.id.label("chunk_id"),
            version.document_id.label("document_id"),
            version.version.label("version"),
            chunk.ordinal.label("ordinal"),
            chunk.text.label("text"),
            chunk.page_number.label("page_number"),
            chunk.page_ordinal.label("page_ordinal"),
            chunk.search_vector.label("search_vector"),
            chunk.embedding.label("embedding"),
        )
        .join(version, version.id == chunk.document_version_id)
        .where(version.lifecycle == "approved", eligibility)
    )


def _merge_ranked_candidates(
    lexical_rows: Sequence[object], semantic_rows: Sequence[object]
) -> tuple[_Candidate, ...]:
    """Merge independently ranked PostgreSQL candidate lists without changing their scores."""
    candidates: dict[UUID, _Candidate] = {}
    for position, row in enumerate(lexical_rows, start=1):
        candidate = _candidate_from_row(row, lexical_position=position)
        candidates[candidate.chunk_id] = candidate
    for position, row in enumerate(semantic_rows, start=1):
        candidate = _candidate_from_row(row, semantic_position=position)
        previous = candidates.get(candidate.chunk_id)
        candidates[candidate.chunk_id] = (
            candidate
            if previous is None
            else replace(
                previous,
                semantic_distance=candidate.semantic_distance,
                semantic_position=position,
            )
        )
    return tuple(candidates.values())


def _candidate_from_row(
    row: object,
    *,
    lexical_position: int | None = None,
    semantic_position: int | None = None,
) -> _Candidate:
    """Translate a typed SQL row to an internal candidate without exposing row objects."""
    mapping = row._mapping  # type: ignore[union-attr]
    return _Candidate(
        chunk_id=mapping["chunk_id"],
        document_id=mapping["document_id"],
        version=mapping["version"],
        ordinal=mapping["ordinal"],
        text=mapping["text"],
        page_number=mapping["page_number"],
        page_ordinal=mapping["page_ordinal"],
        lexical_rank=float(mapping["lexical_rank"]),
        semantic_distance=float(mapping["semantic_distance"]),
        lexical_position=lexical_position,
        semantic_position=semantic_position,
    )


def _serialize_admitted_candidates(
    candidates: Sequence[_Candidate],
) -> tuple[RetrievedKnowledgeItem, ...]:
    """Fuse admitted candidates then choose complete items that fit the fixed byte budget."""
    admitted = [candidate for candidate in candidates if _is_admitted(candidate)]
    ranked = sorted(admitted, key=_fusion_sort_key)
    selected: list[RetrievedKnowledgeItem] = []
    for candidate in ranked:
        if len(selected) == _MAX_PASSAGES:
            break
        item = RetrievedKnowledgeItem(
            statement=candidate.text,
            references=(
                build_curated_knowledge_reference(
                    candidate.document_id,
                    candidate.version,
                    ordinal=candidate.ordinal,
                    page_number=candidate.page_number,
                    page_ordinal=candidate.page_ordinal,
                ),
            ),
        )
        prospective = tuple((*selected, item))
        if _serialized_batch_bytes(prospective) <= _MAX_SERIALIZED_BYTES:
            selected.append(item)
    return tuple(selected)


def _is_admitted(candidate: _Candidate) -> bool:
    """Apply relevance thresholds before a candidate can participate in rank fusion."""
    return (
        candidate.lexical_rank is not None and candidate.lexical_rank > _LEXICAL_ADMISSION_MINIMUM
    ) or (
        candidate.semantic_distance is not None
        and candidate.semantic_distance <= _SEMANTIC_ADMISSION_MAXIMUM_DISTANCE
    )


def _fusion_sort_key(candidate: _Candidate) -> tuple[float, str, int, int]:
    """Return a deterministic descending reciprocal-rank-fusion ordering key."""
    score = 0.0
    if candidate.lexical_position is not None:
        score += 1 / (_RECIPROCAL_RANK_K + candidate.lexical_position)
    if candidate.semantic_position is not None:
        score += 1 / (_RECIPROCAL_RANK_K + candidate.semantic_position)
    return (-score, str(candidate.document_id), candidate.version, candidate.ordinal)


def _serialized_batch_bytes(items: Sequence[RetrievedKnowledgeItem]) -> int:
    """Measure the complete JSON retrieval batch exactly as model-visible UTF-8 content."""
    serialized = RetrievalSuccess(items=tuple(items)).model_dump_json()
    return len(serialized.encode("utf-8"))
