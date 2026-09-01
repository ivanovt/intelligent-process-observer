"""Persistence composition for terminal Alert pipeline outcomes."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.contracts import AlertTerminalOutcome
from app.infrastructure.persistence.models import LensAnalysisResultModel, LensRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository


async def persist_alert_terminal(
    session: AsyncSession,
    lens_run: LensRunModel,
    outcome: AlertTerminalOutcome,
    repository: RuntimePersistenceRepository,
) -> LensAnalysisResultModel:
    """Transition and persist one usable Alert result, flushing but never committing."""

    await repository.advance_lens_run(session, lens_run, outcome.status, reason=outcome.reason)
    return await repository.persist_lens_analysis_result(session, lens_run, outcome.artifact)
