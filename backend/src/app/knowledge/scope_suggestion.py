"""Framework-neutral contracts and service for advisory knowledge scope suggestions."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.management_contracts import ApprovedServiceCatalogEntry


class StrictKnowledgeScopeSuggestionModel(BaseModel):
    """Immutable scope-suggestion value that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class KnowledgeScopeSuggestionLens(StrictKnowledgeScopeSuggestionModel):
    """Minimal Lens semantic text admitted to one suggestion request."""

    name: str = Field(min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def validate_text(self) -> KnowledgeScopeSuggestionLens:
        """Require non-whitespace Lens text when supplied."""
        _require_non_whitespace(self.name, "name")
        if self.description is not None:
            _require_non_whitespace(self.description, "description")
        return self


class KnowledgeScopeSuggestionDraft(StrictKnowledgeScopeSuggestionModel):
    """Transient Observation semantic projection for a scope suggestion."""

    name: str = Field(min_length=1)
    description: str | None = None
    objective: str = Field(min_length=1)
    lenses: list[KnowledgeScopeSuggestionLens]

    @model_validator(mode="after")
    def validate_text(self) -> KnowledgeScopeSuggestionDraft:
        """Require non-whitespace Observation semantic text when supplied."""
        _require_non_whitespace(self.name, "name")
        _require_non_whitespace(self.objective, "objective")
        if self.description is not None:
            _require_non_whitespace(self.description, "description")
        return self


class KnowledgeScopeSuggestionModelRequest(StrictKnowledgeScopeSuggestionModel):
    """Complete corpus-blind model input for one advisory suggestion."""

    draft: KnowledgeScopeSuggestionDraft
    catalog: tuple[ApprovedServiceCatalogEntry, ...] = Field(min_length=1)


class KnowledgeScopeSuggestionResponse(StrictKnowledgeScopeSuggestionModel):
    """Diagnostic-free catalog-backed service IDs suggested for a draft."""

    service_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_service_ids(self) -> KnowledgeScopeSuggestionResponse:
        """Require unique non-whitespace service IDs in the public response."""
        if len(self.service_ids) != len(set(self.service_ids)):
            raise ValueError("service_ids must be unique")
        for service_id in self.service_ids:
            _require_non_whitespace(service_id, "service_ids")
        return self


class ApprovedServiceCatalogProvider(Protocol):
    """Load the current approved service projection without exposing corpus content."""

    async def approved_service_catalog(
        self, session: AsyncSession
    ) -> tuple[ApprovedServiceCatalogEntry, ...]:
        """Return the current approved service IDs and aliases."""


class KnowledgeScopeSuggestionAgent(Protocol):
    """Produce one typed, catalog-constrained advisory scope suggestion."""

    async def suggest(
        self, request: KnowledgeScopeSuggestionModelRequest
    ) -> KnowledgeScopeSuggestionResponse:
        """Return only canonical IDs selected from the supplied catalog."""


class KnowledgeScopeSuggestionService:
    """Coordinate a transient, catalog-only LLM scope-suggestion request."""

    def __init__(
        self,
        catalog_provider: ApprovedServiceCatalogProvider,
        agent_factory: Callable[[], KnowledgeScopeSuggestionAgent],
    ) -> None:
        """Bind the service to catalog loading and lazy server-owned model composition."""
        self._catalog_provider = catalog_provider
        self._agent_factory = agent_factory

    async def suggest(
        self, session: AsyncSession, draft: KnowledgeScopeSuggestionDraft
    ) -> KnowledgeScopeSuggestionResponse:
        """Return a safe empty response for unavailable or invalid suggestion work."""
        try:
            catalog = await self._catalog_provider.approved_service_catalog(session)
            if not catalog:
                return KnowledgeScopeSuggestionResponse()
            result = await self._agent_factory().suggest(
                KnowledgeScopeSuggestionModelRequest(draft=draft, catalog=catalog)
            )
            return _catalog_backed_response(result, catalog)
        except asyncio.CancelledError:
            raise
        except Exception:
            return KnowledgeScopeSuggestionResponse()


def _catalog_backed_response(
    response: KnowledgeScopeSuggestionResponse,
    catalog: tuple[ApprovedServiceCatalogEntry, ...],
) -> KnowledgeScopeSuggestionResponse:
    """Reject a completion that is not a unique subset of the supplied catalog."""
    if not isinstance(response, KnowledgeScopeSuggestionResponse):
        raise TypeError("scope suggestion agent returned an invalid response")
    catalog_ids = {entry.service_id for entry in catalog}
    if not set(response.service_ids).issubset(catalog_ids):
        raise ValueError("scope suggestion includes an ID outside the catalog")
    return response


def _require_non_whitespace(value: str, field_name: str) -> None:
    """Reject a string that has no semantic text content."""
    if not value.strip():
        raise ValueError(f"{field_name} must contain non-whitespace content")
