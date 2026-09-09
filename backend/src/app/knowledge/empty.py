"""Production fallback knowledge retrieval implementation."""

from __future__ import annotations

from app.knowledge.contracts import KnowledgeRetrievalRequest, RetrievedKnowledgeItem


class EmptyKnowledgeRetriever:
    """Return no knowledge while no approved production knowledge backend exists."""

    async def retrieve(
        self, request: KnowledgeRetrievalRequest
    ) -> tuple[RetrievedKnowledgeItem, ...]:
        """Return one validated empty batch without external calls or fabricated items."""
        return ()
