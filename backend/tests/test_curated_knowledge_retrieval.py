"""Focused behavior tests for curated PostgreSQL retrieval infrastructure."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

import app.infrastructure.knowledge.retrieval as retrieval_module
from app.infrastructure.knowledge.retrieval import (
    _MAX_SERIALIZED_BYTES,
    CuratedKnowledgeReferenceResolver,
    _Candidate,
    _eligible_chunks,
    _serialize_admitted_candidates,
    _serialized_batch_bytes,
    build_curated_knowledge_reference,
    parse_curated_knowledge_reference,
)
from app.knowledge.contracts import (
    KnowledgeRetrievalRequest,
    RetrievalSuccess,
    RetrievalTimeout,
    RetrievedKnowledgeItem,
)
from app.knowledge.executor import BoundedRetrievalExecutor
from app.knowledge.management_contracts import KnowledgeScope, KnowledgeServiceScope

_DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")


def candidate(
    ordinal: int,
    *,
    text: str = "approved source passage",
    lexical_rank: float | None = 0.1,
    semantic_distance: float | None = 0.2,
    lexical_position: int | None = 1,
    semantic_position: int | None = 1,
) -> _Candidate:
    """Build one metadata-eligible candidate with deterministic source provenance."""
    return _Candidate(
        chunk_id=UUID(f"00000000-0000-0000-0000-{ordinal:012d}"),
        document_id=_DOCUMENT_ID,
        version=3,
        ordinal=ordinal,
        text=text,
        page_number=None,
        page_ordinal=None,
        lexical_rank=lexical_rank,
        semantic_distance=semantic_distance,
        lexical_position=lexical_position,
        semantic_position=semantic_position,
    )


def test_curated_reference_uses_immutable_version_and_source_specific_locators() -> None:
    """PDF locations stay page-local while Markdown uses its document-local ordinal."""
    pdf = build_curated_knowledge_reference(
        _DOCUMENT_ID,
        3,
        ordinal=47,
        page_number=12,
        page_ordinal=3,
    )
    markdown = build_curated_knowledge_reference(
        _DOCUMENT_ID,
        3,
        ordinal=7,
        page_number=None,
        page_ordinal=None,
    )

    assert pdf.model_dump() == {
        "source_id": "knowledge-document:12345678-1234-5678-1234-567812345678:v3",
        "reference": "pdf:page:12:chunk:3",
    }
    assert markdown.reference == "md:chunk:7"
    assert parse_curated_knowledge_reference(pdf).page_number == 12  # type: ignore[union-attr]
    assert parse_curated_knowledge_reference(markdown).ordinal == 7  # type: ignore[union-attr]


def test_curated_reference_parser_rejects_noncanonical_or_other_opaque_references() -> None:
    """Only the adapter-owned grammar is recognized by historical resolution."""
    other = build_curated_knowledge_reference(
        _DOCUMENT_ID,
        3,
        ordinal=1,
        page_number=None,
        page_ordinal=None,
    ).model_copy(
        update={"source_id": "knowledge-document:12345678-1234-5678-1234-567812345678:v03"}
    )
    assert parse_curated_knowledge_reference(other) is None


def test_historical_resolver_uses_pdf_page_local_locator_without_version_substitution() -> None:
    """A PDF locator resolves the retained page-local chunk of its cited older version."""

    class Result:
        def one_or_none(self) -> tuple[object, object]:
            return (
                SimpleNamespace(
                    ordinal=47,
                    text="heading-free page passage",
                    page_number=12,
                    page_ordinal=3,
                    heading_path=None,
                ),
                SimpleNamespace(document_id=_DOCUMENT_ID, version=3),
            )

    class Session:
        async def execute(self, statement: object) -> Result:
            self.statement = statement
            return Result()

    reference = build_curated_knowledge_reference(
        _DOCUMENT_ID,
        3,
        ordinal=47,
        page_number=12,
        page_ordinal=3,
    )
    session = Session()
    resolved = asyncio.run(CuratedKnowledgeReferenceResolver().resolve(session, reference))

    assert resolved is not None
    assert resolved.version == 3
    assert resolved.ordinal == 47
    assert resolved.page_number == 12 and resolved.page_ordinal == 3
    assert resolved.text == "heading-free page passage"
    compiled = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "knowledge_document_versions.version" in compiled
    assert "knowledge_chunks.page_ordinal" in compiled


def test_eligibility_sql_filters_approval_and_global_or_matching_versioned_service_first() -> None:
    """Both lexical and vector searches inherit the same metadata-first candidate CTE."""
    global_sql = str(_eligible_chunks(None).compile(dialect=postgresql.dialect()))
    scoped_sql = str(
        _eligible_chunks(
            KnowledgeScope(
                services=(KnowledgeServiceScope(service_id="cooling-loop", service_version="2.x"),)
            )
        ).compile(dialect=postgresql.dialect())
    )

    assert "knowledge_document_versions.lifecycle" in global_sql
    assert "NOT (EXISTS" in global_sql
    assert "knowledge_document_service_tags.service_id =" in scoped_sql
    assert "jsonb_array_length" in scoped_sql
    assert " @> " in scoped_sql


def test_unrelated_candidates_do_not_pass_rank_fusion_admission() -> None:
    """A nearest but semantically distant or lexically weak passage is an empty result."""
    items = _serialize_admitted_candidates(
        (
            candidate(
                1,
                lexical_rank=0.05,
                semantic_distance=0.36,
                lexical_position=1,
                semantic_position=1,
            ),
            candidate(
                2,
                lexical_rank=0.0,
                semantic_distance=0.8,
                lexical_position=2,
                semantic_position=2,
            ),
        )
    )
    assert items == ()


def test_rank_fusion_limits_to_four_whole_passages_without_truncation() -> None:
    """The ranked fifth passage is omitted intact once the server-owned count limit is reached."""
    items = _serialize_admitted_candidates(
        tuple(
            candidate(
                ordinal,
                text=f"complete passage {ordinal}",
                lexical_position=ordinal,
                semantic_position=ordinal,
            )
            for ordinal in range(1, 6)
        )
    )
    assert [item.statement for item in items] == [
        "complete passage 1",
        "complete passage 2",
        "complete passage 3",
        "complete passage 4",
    ]
    assert all("complete passage" in item.statement for item in items)


def test_serialized_batch_accepts_exact_boundary_and_omits_next_whole_passage() -> None:
    """The UTF-8 limit measures the complete model-visible success payload exactly."""
    seed = candidate(1, text="")
    seed_item = RetrievedKnowledgeItem(
        statement="x",
        references=(
            build_curated_knowledge_reference(
                seed.document_id,
                seed.version,
                ordinal=seed.ordinal,
                page_number=None,
                page_ordinal=None,
            ),
        ),
    )
    overhead = _serialized_batch_bytes((seed_item,)) - 1
    exact_text = "x" * (_MAX_SERIALIZED_BYTES - overhead)
    exact = candidate(1, text=exact_text)
    oversized = candidate(2, text="remaining complete passage")

    items = _serialize_admitted_candidates((exact, oversized))
    assert items == (
        RetrievedKnowledgeItem(
            statement=exact_text,
            references=(
                build_curated_knowledge_reference(
                    _DOCUMENT_ID,
                    3,
                    ordinal=1,
                    page_number=None,
                    page_ordinal=None,
                ),
            ),
        ),
    )
    assert _serialized_batch_bytes(items) == _MAX_SERIALIZED_BYTES
    assert (
        len(RetrievalSuccess(items=items).model_dump_json().encode("utf-8"))
        == _MAX_SERIALIZED_BYTES
    )
    assert oversized.text not in [item.statement for item in items]


def test_whole_retrieval_deadline_maps_to_existing_typed_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixed deadline includes query embedding before any database work can begin."""

    class SlowEmbedder:
        async def embed_query(self, _text: str) -> tuple[float, ...]:
            await asyncio.sleep(0.05)
            return ()

    monkeypatch.setattr(retrieval_module, "_RETRIEVAL_DEADLINE_SECONDS", 0.01)
    retriever = retrieval_module.CuratedKnowledgeRetriever(
        session_factory=None,  # type: ignore[arg-type]
        embedder=SlowEmbedder(),
        scope=None,
    )
    executor = BoundedRetrievalExecutor(frozenset(("finding-1",)), retriever)

    outcome = asyncio.run(
        executor.execute(
            KnowledgeRetrievalRequest(query="grounded query", finding_ids=("finding-1",))
        )
    )

    assert isinstance(outcome, RetrievalTimeout)
    assert executor.ledger[0].outcome == "timed_out"
