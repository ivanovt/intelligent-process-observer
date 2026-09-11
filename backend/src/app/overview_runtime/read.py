"""Read-only service for resilient Overview runtime projections."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.overview_runtime.contracts import OverviewRuntimeResponse
from app.overview_runtime.projection import project_overview_runtime_response


class OverviewRuntimeReadService:
    """Serve a resilient presentation read model without mutating runtime state."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        runtime_repository: RuntimePersistenceRepository,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_repository = runtime_repository

    async def get_runtime(self) -> OverviewRuntimeResponse:
        """Return every newest-first durable run as available or limited data."""

        async with self._session_factory() as session:
            records = await self._runtime_repository.list_observation_run_summaries(session)
            return project_overview_runtime_response(records)
