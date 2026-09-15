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
    _RELAXED_LEXICAL_ADMISSION_MINIMUM,
    _RELAXED_MINIMUM_MATCHED_LEXEMES,
    _RELAXED_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE,
    CuratedKnowledgeReferenceResolver,
    _Candidate,
    _eligible_chunks,
    _is_relaxed_admitted,
    _merge_ranked_candidates,
    _normalized_query_lexemes,
    _relaxed_tsquery,
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
    matched_lexeme_count: int | None = None,
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
        matched_lexeme_count=matched_lexeme_count,
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


def test_relaxed_admission_requires_all_signals_at_their_exact_boundaries() -> None:
    """Fallback admission remains conjunctive and includes only its semantic equality boundary."""
    admitted = candidate(
        1,
        lexical_rank=_RELAXED_LEXICAL_ADMISSION_MINIMUM + 0.001,
        semantic_distance=_RELAXED_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE,
        matched_lexeme_count=_RELAXED_MINIMUM_MATCHED_LEXEMES,
    )
    assert _is_relaxed_admitted(admitted)
    assert not _is_relaxed_admitted(
        candidate(
            2,
            lexical_rank=_RELAXED_LEXICAL_ADMISSION_MINIMUM,
            semantic_distance=_RELAXED_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE,
            matched_lexeme_count=_RELAXED_MINIMUM_MATCHED_LEXEMES,
        )
    )
    assert not _is_relaxed_admitted(
        candidate(
            3,
            lexical_rank=_RELAXED_LEXICAL_ADMISSION_MINIMUM + 0.001,
            semantic_distance=_RELAXED_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE + 0.001,
            matched_lexeme_count=_RELAXED_MINIMUM_MATCHED_LEXEMES,
        )
    )
    assert not _is_relaxed_admitted(
        candidate(
            4,
            lexical_rank=_RELAXED_LEXICAL_ADMISSION_MINIMUM + 0.001,
            semantic_distance=_RELAXED_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE,
            matched_lexeme_count=_RELAXED_MINIMUM_MATCHED_LEXEMES - 1,
        )
    )


def test_strict_hybrid_candidate_count_is_the_deduplicated_branch_union() -> None:
    """Strict aggregate candidates retain both top-32 branches before admission or serialization."""
    lexical = [
        _row(1, lexical_rank=0.1, semantic_distance=0.4),
        _row(2, lexical_rank=0.1, semantic_distance=0.4),
    ]
    semantic = [
        _row(2, lexical_rank=0.1, semantic_distance=0.2),
        _row(3, lexical_rank=0.1, semantic_distance=0.2),
    ]

    overlapping = _merge_ranked_candidates(lexical, semantic)
    disjoint = _merge_ranked_candidates(
        lexical,
        [
            _row(3, lexical_rank=0.1, semantic_distance=0.2),
            _row(4, lexical_rank=0.1, semantic_distance=0.2),
        ],
    )

    assert [item.ordinal for item in overlapping] == [1, 2, 3]
    assert overlapping[1].semantic_position == 1
    assert len(disjoint) == 4


def test_relaxed_query_uses_database_normalization_and_deterministic_disjunction() -> None:
    """Punctuation and repeated terms are normalized by PostgreSQL before an OR query is built."""

    class Rows:
        def all(self) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(_mapping={"lexeme": "cooling"}),
                SimpleNamespace(_mapping={"lexeme": "pressure"}),
            ]

    class Session:
        async def execute(self, statement: object) -> Rows:
            self.statement = statement
            return Rows()

    session = Session()
    lexemes = asyncio.run(_normalized_query_lexemes(session, "Cooling, cooling! pressure?"))
    normalized_sql = str(session.statement.compile(dialect=postgresql.dialect()))
    compiled_tsquery = _relaxed_tsquery(lexemes).compile(dialect=postgresql.dialect())
    tsquery_sql = str(compiled_tsquery)

    assert lexemes == ("cooling", "pressure")
    assert "to_tsvector" in normalized_sql
    assert "tsvector_to_array" in normalized_sql
    assert "unnest" in normalized_sql
    assert "to_tsquery" in tsquery_sql
    assert "cooling | pressure" in compiled_tsquery.params.values()


def test_strict_admission_skips_relaxed_search_and_emits_strict_decision() -> None:
    """The existing strict path returns unchanged without evaluating fallback SQL."""

    class Rows:
        def __init__(self, rows: list[SimpleNamespace]) -> None:
            self._rows = rows

        def all(self) -> list[SimpleNamespace]:
            return self._rows

    class Session:
        def __init__(self) -> None:
            self.calls: list[object] = []
            self.results = [
                Rows([_row(1, lexical_rank=0.1, semantic_distance=0.4)]),
                Rows([]),
            ]

        async def execute(self, statement: object) -> Rows:
            self.calls.append(statement)
            return self.results.pop(0)

    class SessionFactory:
        def __init__(self, session: Session) -> None:
            self._session = session

        def __call__(self) -> SessionFactory:
            return self

        async def __aenter__(self) -> Session:
            return self._session

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Embedder:
        async def embed_query(self, _query: str) -> tuple[float, ...]:
            return (1.0,)

    class Emitter:
        def __init__(self) -> None:
            self.events: list[object] = []

        def emit(self, event: object) -> None:
            self.events.append(event)

    session = Session()
    emitter = Emitter()
    observation_run_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    retriever = retrieval_module.CuratedKnowledgeRetriever(
        SessionFactory(session),  # type: ignore[arg-type]
        Embedder(),
        scope=None,
        observation_run_id=observation_run_id,
        emitter=emitter,  # type: ignore[arg-type]
    )

    items = asyncio.run(retriever.retrieve(_request()))

    assert [item.statement for item in items] == ["passage 1"]
    assert len(session.calls) == 2
    event = emitter.events[0]
    assert event.category == "strict_admitted"
    assert event.observation_run_id == observation_run_id
    assert event.agent_role == "observation_reasoning"
    assert event.phase == "hypotheses"
    assert event.component == "curated_knowledge_retrieval"
    assert event.relaxed_candidate_count is None
    assert event.relaxed_admitted_count is None


def test_relaxed_admission_reuses_one_embedding_and_rejects_single_term_candidates() -> None:
    """A verbose strict miss recovers only a two-term, semantically close fallback candidate."""

    class Rows:
        def __init__(self, rows: list[SimpleNamespace]) -> None:
            self._rows = rows

        def all(self) -> list[SimpleNamespace]:
            return self._rows

    class Session:
        def __init__(self) -> None:
            self.statements: list[object] = []
            self.results = [
                Rows([]),
                Rows([_row(1, lexical_rank=0.0, semantic_distance=0.4)]),
                Rows(
                    [
                        SimpleNamespace(_mapping={"lexeme": "cooling"}),
                        SimpleNamespace(_mapping={"lexeme": "pressure"}),
                        SimpleNamespace(_mapping={"lexeme": "verbose"}),
                    ]
                ),
                Rows(
                    [
                        _row(
                            2,
                            lexical_rank=_RELAXED_LEXICAL_ADMISSION_MINIMUM + 0.001,
                            semantic_distance=_RELAXED_SEMANTIC_ADMISSION_MAXIMUM_DISTANCE,
                            matched_lexeme_count=2,
                        ),
                        _row(
                            3,
                            lexical_rank=_RELAXED_LEXICAL_ADMISSION_MINIMUM + 0.001,
                            semantic_distance=0.4,
                            matched_lexeme_count=1,
                        ),
                    ]
                ),
            ]

        async def execute(self, statement: object) -> Rows:
            self.statements.append(statement)
            return self.results.pop(0)

    class SessionFactory:
        def __init__(self, session: Session) -> None:
            self._session = session

        def __call__(self) -> SessionFactory:
            return self

        async def __aenter__(self) -> Session:
            return self._session

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Embedder:
        def __init__(self) -> None:
            self.calls = 0

        async def embed_query(self, _query: str) -> tuple[float, ...]:
            self.calls += 1
            return (1.0,)

    class Emitter:
        def __init__(self) -> None:
            self.events: list[object] = []

        def emit(self, event: object) -> None:
            self.events.append(event)

    session = Session()
    embedder = Embedder()
    emitter = Emitter()
    retriever = retrieval_module.CuratedKnowledgeRetriever(
        SessionFactory(session),  # type: ignore[arg-type]
        embedder,
        scope=None,
        emitter=emitter,  # type: ignore[arg-type]
    )

    items = asyncio.run(retriever.retrieve(_request()))

    assert [item.statement for item in items] == ["passage 2"]
    assert embedder.calls == 1
    event = emitter.events[0]
    assert event.category == "relaxed_admitted"
    assert event.strict_candidate_count == 1
    assert event.strict_admitted_count == 0
    assert event.relaxed_candidate_count == 2
    assert event.relaxed_admitted_count == 1
    relaxed_sql = str(session.statements[-1].compile(dialect=postgresql.dialect()))
    assert "CASE WHEN" in relaxed_sql
    assert "matched_lexeme_count" in relaxed_sql
    assert "embedding IS NOT NULL" in relaxed_sql
    assert "ORDER BY" in relaxed_sql


def test_no_match_reports_evaluated_relaxed_counts_without_fabricating_knowledge() -> None:
    """An insufficient normalized query is a successful empty retrieval and no-match decision."""

    class Rows:
        def __init__(self, rows: list[SimpleNamespace]) -> None:
            self._rows = rows

        def all(self) -> list[SimpleNamespace]:
            return self._rows

    class Session:
        def __init__(self) -> None:
            self.results = [
                Rows([]),
                Rows([_row(1, lexical_rank=0.0, semantic_distance=0.4)]),
                Rows([SimpleNamespace(_mapping={"lexeme": "cooling"})]),
            ]

        async def execute(self, _statement: object) -> Rows:
            return self.results.pop(0)

    class SessionFactory:
        def __init__(self, session: Session) -> None:
            self._session = session

        def __call__(self) -> SessionFactory:
            return self

        async def __aenter__(self) -> Session:
            return self._session

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Embedder:
        async def embed_query(self, _query: str) -> tuple[float, ...]:
            return (1.0,)

    class Emitter:
        def __init__(self) -> None:
            self.events: list[object] = []

        def emit(self, event: object) -> None:
            self.events.append(event)

    emitter = Emitter()
    retriever = retrieval_module.CuratedKnowledgeRetriever(
        SessionFactory(Session()),  # type: ignore[arg-type]
        Embedder(),
        scope=None,
        emitter=emitter,  # type: ignore[arg-type]
    )

    assert asyncio.run(retriever.retrieve(_request())) == ()
    event = emitter.events[0]
    assert event.category == "no_match"
    assert event.strict_candidate_count == 1
    assert event.strict_admitted_count == 0
    assert event.relaxed_candidate_count == 0
    assert event.relaxed_admitted_count == 0
    assert event.returned_passage_count == 0


def test_retrieval_outcome_is_unchanged_when_decision_emission_fails() -> None:
    """Operational event failures remain non-authoritative after a strict selection."""

    class Rows:
        def __init__(self, rows: list[SimpleNamespace]) -> None:
            self._rows = rows

        def all(self) -> list[SimpleNamespace]:
            return self._rows

    class Session:
        def __init__(self) -> None:
            self.results = [
                Rows([_row(1, lexical_rank=0.1, semantic_distance=0.4)]),
                Rows([]),
            ]

        async def execute(self, _statement: object) -> Rows:
            return self.results.pop(0)

    class SessionFactory:
        def __init__(self, session: Session) -> None:
            self._session = session

        def __call__(self) -> SessionFactory:
            return self

        async def __aenter__(self) -> Session:
            return self._session

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Embedder:
        async def embed_query(self, _query: str) -> tuple[float, ...]:
            return (1.0,)

    class FailingEmitter:
        def emit(self, _event: object) -> None:
            raise RuntimeError("diagnostic sink unavailable")

    retriever = retrieval_module.CuratedKnowledgeRetriever(
        SessionFactory(Session()),  # type: ignore[arg-type]
        Embedder(),
        scope=None,
        emitter=FailingEmitter(),  # type: ignore[arg-type]
    )

    assert [item.statement for item in asyncio.run(retriever.retrieve(_request()))] == ["passage 1"]


def _request() -> KnowledgeRetrievalRequest:
    """Create one valid findings-grounded retrieval request for infrastructure tests."""
    return KnowledgeRetrievalRequest(
        query="verbose cooling pressure condition", finding_ids=("finding-1",)
    )


def _row(
    ordinal: int,
    *,
    lexical_rank: float,
    semantic_distance: float,
    matched_lexeme_count: int | None = None,
) -> SimpleNamespace:
    """Build a lightweight SQL row compatible with the retriever's row mapper."""
    mapping: dict[str, object] = {
        "chunk_id": UUID(f"00000000-0000-0000-0000-{ordinal:012d}"),
        "document_id": _DOCUMENT_ID,
        "version": 3,
        "ordinal": ordinal,
        "text": f"passage {ordinal}",
        "page_number": None,
        "page_ordinal": None,
        "lexical_rank": lexical_rank,
        "semantic_distance": semantic_distance,
    }
    if matched_lexeme_count is not None:
        mapping["matched_lexeme_count"] = matched_lexeme_count
    return SimpleNamespace(_mapping=mapping)


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
