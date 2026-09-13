"""Focused validation tests for framework-neutral curated knowledge contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.knowledge.management_contracts import (
    KnowledgeAuthority,
    KnowledgeChunkCreate,
    KnowledgeDocumentType,
    KnowledgeDocumentVersionCreate,
    KnowledgeScope,
    KnowledgeServiceTag,
)


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
    scope = KnowledgeScope(service_ids=("mprm-server",), service_version="2.x")
    assert scope.model_dump() == {
        "service_ids": ("mprm-server",),
        "service_version": "2.x",
    }
    with pytest.raises(ValidationError):
        KnowledgeScope(service_ids=())
    with pytest.raises(ValidationError, match="service_ids must be unique"):
        KnowledgeScope(service_ids=("mprm-server", "mprm-server"))
    with pytest.raises(ValidationError, match="non-whitespace"):
        KnowledgeScope(service_ids=("mprm-server",), service_version=" ")
    with pytest.raises(ValidationError):
        KnowledgeScope(service_ids=("mprm-server",), unknown="forbidden")
    with pytest.raises(ValidationError):
        scope.service_ids = ("other-service",)  # type: ignore[misc]


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
    assert KnowledgeChunkCreate(ordinal=1, text="PDF passage", page_number=2, page_ordinal=1)
    assert KnowledgeChunkCreate(ordinal=2, text="Markdown passage", heading_path=("Operations",))
    with pytest.raises(ValidationError, match="provided together"):
        KnowledgeChunkCreate(ordinal=1, text="invalid", page_number=2)
    with pytest.raises(ValidationError, match="heading_path"):
        KnowledgeChunkCreate(ordinal=1, text="invalid", heading_path=(" ",))
