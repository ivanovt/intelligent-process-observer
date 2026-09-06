"""Framework-neutral boundary for external knowledge acquisition."""

from __future__ import annotations

from typing import Protocol

from app.knowledge.contracts import KnowledgeRetrievalRequest, RetrievedKnowledgeItem


class KnowledgeRetriever(Protocol):
    """Acquire zero or more validated knowledge items for one grounded request."""

    async def retrieve(
        self, request: KnowledgeRetrievalRequest
    ) -> tuple[RetrievedKnowledgeItem, ...]:
        """Return the validated retrieved batch without exposing provider details."""
