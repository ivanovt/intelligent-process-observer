"""Focused validation tests for framework-neutral curated knowledge contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.knowledge.management_contracts import (
    KNOWLEDGE_EMBEDDING_DIMENSIONS,
    KnowledgeAuthority,
    KnowledgeChunkCreate,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeScope,
    KnowledgeServiceScope,
    KnowledgeServiceTag,
    parse_knowledge_scope,
)

_EMBEDDING = (0.0,) * KNOWLEDGE_EMBEDDING_DIMENSIONS


def valid_version(**overrides: object) -> KnowledgeDocumentVersionCreate:
    """Create a valid immutable source-version input for focused contract tests."""
    values: dict[str, object] = {
        "title": "Cooling runbook",
        "document_type": KnowledgeDocumentType.RUNBOOK,
        "authority": KnowledgeAuthority.INTERNAL_APPROVED,
        "owner": "operations",
        "source_media_type": "text/markdown",
        "source_bytes": b"# Cooling",
        "content_hash": "a" * 64,
        "service_tags": (
            KnowledgeServiceTag(
                service_id="mprm-server",
                aliases=("mprm",),
                supported_versions=("2.x",),
            ),
        ),
    }
    values.update(overrides)
    return KnowledgeDocumentVersionCreate(**values)


def test_scope_is_strict_immutable_and_validates_service_ids() -> None:
    """Knowledge scope must remain explicit, typed, and retriever-only."""
    scope = KnowledgeScope(
        services=(KnowledgeServiceScope(service_id="mprm-server", service_version="2.x"),)
    )
    assert scope.model_dump() == {
        "services": ({"service_id": "mprm-server", "service_version": "2.x"},),
    }
    with pytest.raises(ValidationError):
        KnowledgeScope(services=())
    with pytest.raises(ValidationError, match="service IDs must be unique"):
        KnowledgeScope(services=(KnowledgeServiceScope(service_id="mprm-server"),) * 2)
    with pytest.raises(ValidationError, match="non-whitespace"):
        KnowledgeServiceScope(service_id="mprm-server", service_version=" ")
    with pytest.raises(ValidationError):
        KnowledgeScope(services=(KnowledgeServiceScope(service_id="mprm-server"),), unknown="x")
    with pytest.raises(ValidationError):
        scope.services = (KnowledgeServiceScope(service_id="other-service"),)  # type: ignore[misc]


def test_scope_normalizes_legacy_shared_versions_without_guessing() -> None:
    """Every legacy service retains the old shared filter when read canonically."""
    scope = parse_knowledge_scope(
        {"service_ids": ["mprm-server", "gateway"], "service_version": "1.0"}
    )
    assert scope.model_dump(mode="json") == {
        "services": [
            {"service_id": "mprm-server", "service_version": "1.0"},
            {"service_id": "gateway", "service_version": "1.0"},
        ]
    }
    assert parse_knowledge_scope({"service_ids": ["gateway"]}).services[0].service_version is None
    with pytest.raises(ValueError, match="mix"):
        parse_knowledge_scope({"services": [], "service_ids": ["gateway"]})


def test_document_version_rejects_invalid_metadata_and_duplicate_service_tags() -> None:
    """Source metadata must be complete before a repository can retain a version."""
    version = valid_version()
    assert version.service_tags[0].service_id == "mprm-server"
    with pytest.raises(ValidationError, match="title must contain non-whitespace"):
        valid_version(title=" ")
    with pytest.raises(ValidationError, match="service_tags must use unique service IDs"):
        valid_version(
            service_tags=(
                KnowledgeServiceTag(service_id="mprm-server"),
                KnowledgeServiceTag(service_id="mprm-server"),
            )
        )
    with pytest.raises(ValidationError, match="aliases must be unique"):
        KnowledgeServiceTag(service_id="mprm-server", aliases=("mprm", "mprm"))
    with pytest.raises(ValidationError, match="supported_versions"):
        KnowledgeServiceTag(service_id="mprm-server", supported_versions=(" ",))


def test_chunk_location_contract_preserves_pdf_or_markdown_locators() -> None:
    """Chunk location metadata must not leave a half-formed PDF locator."""
    assert KnowledgeChunkCreate(
        ordinal=1,
        text="PDF passage",
        embedding=_EMBEDDING,
        page_number=2,
        page_ordinal=1,
    )
    assert KnowledgeChunkCreate(
        ordinal=2,
        text="Markdown passage",
        embedding=_EMBEDDING,
        heading_path=("Operations",),
    )
    with pytest.raises(ValidationError, match="provided together"):
        KnowledgeChunkCreate(ordinal=1, text="invalid", embedding=_EMBEDDING, page_number=2)
    with pytest.raises(ValidationError, match="heading_path"):
        KnowledgeChunkCreate(ordinal=1, text="invalid", embedding=_EMBEDDING, heading_path=(" ",))


def test_chunk_rejects_missing_malformed_or_non_finite_embedding() -> None:
    """A publishable chunk always carries one finite fixed-dimension embedding."""
    with pytest.raises(ValidationError):
        KnowledgeChunkCreate(ordinal=1, text="passage")
    with pytest.raises(ValidationError):
        KnowledgeChunkCreate(ordinal=1, text="passage", embedding=_EMBEDDING[:-1])
    with pytest.raises(ValidationError, match="finite"):
        KnowledgeChunkCreate(
            ordinal=1,
            text="passage",
            embedding=(float("nan"),) + _EMBEDDING[1:],
        )
    with pytest.raises(ValidationError, match="non-whitespace"):
        KnowledgeChunkCreate(ordinal=1, text=" ", embedding=_EMBEDDING)
