"""Read-only coherent database access for public Observation run projections."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.observation_runs.contracts import ObservationRunDetail, ObservationRunSummary
from app.observation_runs.projection import (
    project_observation_run_detail,
    project_observation_run_summary,
)


class ObservationRunReadService:
    """Serve detached public run read models without mutating durable runtime state."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        runtime_repository: RuntimePersistenceRepository,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_repository = runtime_repository

    async def list_summaries(self) -> tuple[ObservationRunSummary, ...]:
        """Return complete newest-first history from the repository's single statement."""

        async with self._session_factory() as session:
            records = await self._runtime_repository.list_observation_run_summaries(session)
            return tuple(project_observation_run_summary(item) for item in records)

    async def get_detail(self, observation_run_id: UUID) -> ObservationRunDetail | None:
        """Return one eager run detail projection from one read-only MVCC snapshot."""

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                record = await self._runtime_repository.get_observation_run_detail(
                    session, observation_run_id
                )
                if record is None:
                    return None
                return project_observation_run_detail(record)
