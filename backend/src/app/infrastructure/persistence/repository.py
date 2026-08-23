from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models import (
    MetricLensModel,
    ObservationModel,
    ObservationRelationshipModel,
)
from app.observations.contracts import ObservationCreate


class ObservationRepository:
    async def create(
        self, session: AsyncSession, definition: ObservationCreate
    ) -> ObservationModel:
        observation = ObservationModel(
            name=definition.name,
            description=definition.description,
            objective=definition.objective,
            lenses=[
                MetricLensModel(
                    lens_id=lens.id,
                    name=lens.name,
                    description=lens.description,
                    adapter_type=lens.adapter_type,
                    source_id=lens.source_id,
                    metric_id=lens.metric_id,
                    query=lens.query,
                    unit=lens.unit,
                    analysis_objectives=[objective.value for objective in lens.analysis_objectives],
                    reference_periods=lens.reference_periods,
                    position=index,
                )
                for index, lens in enumerate(definition.lenses)
            ],
            relationships=[
                ObservationRelationshipModel(
                    relationship_id=relationship.id,
                    name=relationship.name,
                    description=relationship.description,
                    participants=relationship.participants,
                    conditions={
                        key: value.model_dump(mode="json")
                        for key, value in relationship.conditions.items()
                    },
                    expected={
                        key: value.model_dump(mode="json")
                        for key, value in relationship.expected.items()
                    },
                    position=index,
                )
                for index, relationship in enumerate(definition.relationships)
            ],
        )
        session.add(observation)
        await session.flush()
        await session.refresh(observation, attribute_names=["lenses", "relationships"])
        return observation

    async def list(self, session: AsyncSession) -> list[ObservationModel]:
        result = await session.scalars(
            select(ObservationModel)
            .options(
                selectinload(ObservationModel.lenses),
                selectinload(ObservationModel.relationships),
            )
            .order_by(ObservationModel.creation_order)
        )
        return list(result.unique())

    async def get(self, session: AsyncSession, observation_id: UUID) -> ObservationModel | None:
        result = await session.scalars(
            select(ObservationModel)
            .where(ObservationModel.id == observation_id)
            .options(
                selectinload(ObservationModel.lenses),
                selectinload(ObservationModel.relationships),
            )
        )
        return result.unique().one_or_none()
