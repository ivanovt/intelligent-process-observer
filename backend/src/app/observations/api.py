from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.prometheus.contracts import PrometheusQueryAdapter
from app.observations.contracts import (
    AlertLensResponse,
    DefinitionCapabilities,
    MetricLensResponse,
    MetricPreflightRequest,
    MetricPreflightResponse,
    ObservationCreate,
    ObservationResponse,
    ObservationSummary,
    RelationshipResponse,
)
from app.observations.service import ObservationDefinitionService

router = APIRouter(prefix="/api/v1", tags=["observation-definitions"])


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_service(request: Request) -> ObservationDefinitionService:
    return request.app.state.observation_service


async def get_prometheus_adapter(request: Request) -> PrometheusQueryAdapter:
    return request.app.state.prometheus_adapter


@router.post(
    "/observations",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_observation(
    definition: ObservationCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> ObservationResponse:
    return await service.create(session, definition)


@router.get("/observations", response_model=list[ObservationSummary])
async def list_observations(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> list[ObservationSummary]:
    return await service.list(session)


@router.get("/observations/{observation_id}", response_model=ObservationResponse)
async def get_observation(
    observation_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> ObservationResponse:
    return await service.get(session, observation_id)


@router.get("/observations/{observation_id}/lenses/{lens_id}", response_model=MetricLensResponse)
async def get_lens(
    observation_id: UUID,
    lens_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> MetricLensResponse:
    return await service.get_lens(session, observation_id, lens_id)


@router.get(
    "/observations/{observation_id}/alert-lenses/{lens_id}", response_model=AlertLensResponse
)
async def get_alert_lens(
    observation_id: UUID,
    lens_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> AlertLensResponse:
    return await service.get_alert_lens(session, observation_id, lens_id)


@router.get(
    "/observations/{observation_id}/relationships/{relationship_id}",
    response_model=RelationshipResponse,
)
async def get_relationship(
    observation_id: UUID,
    relationship_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> RelationshipResponse:
    return await service.get_relationship(session, observation_id, relationship_id)


@router.get(
    "/observation-definition-capabilities",
    response_model=DefinitionCapabilities,
    response_model_exclude_none=True,
)
async def definition_capabilities(
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
) -> DefinitionCapabilities:
    return service.capabilities()


@router.post(
    "/observation-lens-validations/metric",
    response_model=MetricPreflightResponse,
)
async def preflight_metric_lens(
    candidate: MetricPreflightRequest,
    service: ObservationDefinitionService = Depends(get_service),  # noqa: B008
    adapter: PrometheusQueryAdapter = Depends(get_prometheus_adapter),  # noqa: B008
) -> MetricPreflightResponse:
    return await service.preflight_metric(candidate, adapter)
