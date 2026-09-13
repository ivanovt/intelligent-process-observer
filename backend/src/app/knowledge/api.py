"""HTTP boundary for transient catalog-backed knowledge scope suggestions."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import get_settings
from app.infrastructure.openrouter.composition import build_knowledge_scope_suggestion_agent
from app.infrastructure.persistence.repository import KnowledgeRepository
from app.knowledge.scope_suggestion import (
    KnowledgeScopeSuggestionDraft,
    KnowledgeScopeSuggestionResponse,
    KnowledgeScopeSuggestionService,
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one read-only-capable request session without committing it."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_scope_suggestion_service() -> KnowledgeScopeSuggestionService:
    """Build the transient service with lazy model composition after catalog loading."""
    return KnowledgeScopeSuggestionService(
        KnowledgeRepository(),
        lambda: build_knowledge_scope_suggestion_agent(get_settings()),
    )


@router.post("/scope-suggestion", response_model=KnowledgeScopeSuggestionResponse)
async def suggest_knowledge_scope(
    draft: KnowledgeScopeSuggestionDraft,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: KnowledgeScopeSuggestionService = Depends(get_scope_suggestion_service),  # noqa: B008
) -> KnowledgeScopeSuggestionResponse:
    """Return an advisory catalog-backed scope suggestion without persisting the draft."""
    return await service.suggest(session, draft)
