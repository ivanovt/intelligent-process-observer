"""Strict, framework-neutral contracts for curated knowledge management."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, model_validator

KNOWLEDGE_EMBEDDING_DIMENSIONS = 1_536


class StrictKnowledgeManagementModel(BaseModel):
    """Base model for immutable curated-knowledge management values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class KnowledgeDocumentType(StrEnum):
    """Supported operator-declared categories for a retained source document."""

    OFFICIAL_DOCUMENT = "official_document"
    RUNBOOK = "runbook"
    MAINTENANCE_GUIDE = "maintenance_guide"
    INCIDENT = "incident"
    OPERATOR_JOURNAL = "operator_journal"


class KnowledgeAuthority(StrEnum):
    """Operator-declared authority of a retained source document."""

    OFFICIAL = "official"
    INTERNAL_APPROVED = "internal_approved"
    OPERATOR_AUTHORED = "operator_authored"


class KnowledgeVersionLifecycle(StrEnum):
    """Review lifecycle of an immutable knowledge document version."""

    IMPORTED = "imported"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class KnowledgeExtractionState(StrEnum):
    """Derived extraction state of a retained document version."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


def _require_non_whitespace(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must contain non-whitespace content")


class KnowledgeServiceTag(StrictKnowledgeManagementModel):
    """One version-local applicability tag for a canonical service."""

    service_id: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    supported_versions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_values(self) -> KnowledgeServiceTag:
        """Reject blank or duplicate tag values before they reach persistence."""
        _require_non_whitespace(self.service_id, "service_id")
        for alias in self.aliases:
            _require_non_whitespace(alias, "aliases")
        for version in self.supported_versions:
            _require_non_whitespace(version, "supported_versions")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("aliases must be unique")
        if len(self.supported_versions) != len(set(self.supported_versions)):
            raise ValueError("supported_versions must be unique")
        return self


class KnowledgeServiceScope(StrictKnowledgeManagementModel):
    """One canonical service and its own optional applicability version."""

    service_id: str = Field(min_length=1)
    service_version: str | None = None

    @model_validator(mode="after")
    def validate_values(self) -> KnowledgeServiceScope:
        """Reject blank service identities and blank supplied version labels."""
        _require_non_whitespace(self.service_id, "service_id")
        if self.service_version is not None:
            _require_non_whitespace(self.service_version, "service_version")
        return self


class KnowledgeScope(StrictKnowledgeManagementModel):
    """Ordered retriever-only service entries for one Observation definition."""

    services: tuple[KnowledgeServiceScope, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_values(self) -> KnowledgeScope:
        """Require each canonical service identity at most once."""
        service_ids = tuple(service.service_id for service in self.services)
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("service IDs must be unique")
        return self


def parse_knowledge_scope(value: object) -> KnowledgeScope:
    """Normalize canonical or legacy scope data into strict per-service entries."""
    if isinstance(value, KnowledgeScope):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("knowledge scope must be an object")
    fields = dict(value)
    if "services" in fields:
        if "service_ids" in fields or "service_version" in fields:
            raise ValueError("knowledge scope cannot mix legacy and per-service fields")
        services = fields["services"]
        if isinstance(services, (str, bytes)) or not isinstance(services, (list, tuple)):
            raise ValueError("knowledge scope services must be a collection")
        fields["services"] = tuple(services)
        return KnowledgeScope.model_validate(fields)
    if set(fields) - {"service_ids", "service_version"} or "service_ids" not in fields:
        raise ValueError("knowledge scope has unknown or missing fields")
    service_ids = fields["service_ids"]
    if isinstance(service_ids, (str, bytes)) or not isinstance(service_ids, (list, tuple)):
        raise ValueError("legacy service IDs must be a collection")
    if any(not isinstance(service_id, str) for service_id in service_ids):
        raise ValueError("legacy service IDs must be text")
    service_version = fields.get("service_version")
    if service_version is not None and not isinstance(service_version, str):
        raise ValueError("legacy service version must be text")
    return KnowledgeScope.model_validate(
        {
            "services": tuple(
                {"service_id": service_id, "service_version": service_version}
                for service_id in service_ids
            )
        }
    )


class KnowledgeDocumentVersionCreate(StrictKnowledgeManagementModel):
    """Immutable source identity and submitted metadata for one new document version."""

    title: str = Field(min_length=1)
    document_type: KnowledgeDocumentType
    authority: KnowledgeAuthority
    owner: str = Field(min_length=1)
    source_reference: str | None = None
    source_media_type: str = Field(min_length=1)
    source_bytes: bytes = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    service_tags: tuple[KnowledgeServiceTag, ...] = ()

    @model_validator(mode="after")
    def validate_values(self) -> KnowledgeDocumentVersionCreate:
        """Reject blank metadata and duplicate canonical service tags."""
        for field_name, value in (
            ("title", self.title),
            ("owner", self.owner),
            ("source_media_type", self.source_media_type),
            ("content_hash", self.content_hash),
        ):
            _require_non_whitespace(value, field_name)
        if self.source_reference is not None:
            _require_non_whitespace(self.source_reference, "source_reference")
        service_ids = tuple(tag.service_id for tag in self.service_tags)
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("service_tags must use unique service IDs")
        return self


class KnowledgeChunkCreate(StrictKnowledgeManagementModel):
    """Immutable extracted passage and location metadata prepared for one version."""

    ordinal: int = Field(gt=0)
    text: str = Field(min_length=1)
    embedding: tuple[StrictFloat, ...] = Field(
        min_length=KNOWLEDGE_EMBEDDING_DIMENSIONS,
        max_length=KNOWLEDGE_EMBEDDING_DIMENSIONS,
    )
    page_number: int | None = Field(default=None, gt=0)
    page_ordinal: int | None = Field(default=None, gt=0)
    heading_path: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def validate_location(self) -> KnowledgeChunkCreate:
        """Validate one complete, indexed chunk and its source location."""
        _require_non_whitespace(self.text, "text")
        if any(not isfinite(value) for value in self.embedding):
            raise ValueError("embedding must contain only finite values")
        if (self.page_number is None) != (self.page_ordinal is None):
            raise ValueError("page_number and page_ordinal must be provided together")
        if self.heading_path is not None and any(not part.strip() for part in self.heading_path):
            raise ValueError("heading_path must contain only non-whitespace values")
        return self


class ApprovedServiceCatalogEntry(StrictKnowledgeManagementModel):
    """Derived approved-service catalog entry used by retrieval and suggestion only."""

    service_id: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_values(self) -> ApprovedServiceCatalogEntry:
        """Reject invalid catalog values before callers consume the projection."""
        _require_non_whitespace(self.service_id, "service_id")
        for alias in self.aliases:
            _require_non_whitespace(alias, "aliases")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("aliases must be unique")
        return self
