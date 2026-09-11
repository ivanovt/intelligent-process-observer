"""HTTP boundary for the resilient read-only Overview runtime feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.observation_runs.api import _read_safely
from app.overview_runtime.contracts import OverviewRuntimeResponse
from app.overview_runtime.read import OverviewRuntimeReadService

router = APIRouter(prefix="/api/v1", tags=["overview-runtime"])


async def get_overview_runtime_read_service(request: Request) -> OverviewRuntimeReadService:
    """Return the lifespan-owned resilient Overview runtime read service."""

    return request.app.state.overview_runtime_read_service


@router.get("/overview-runtime", response_model=OverviewRuntimeResponse)
async def get_overview_runtime(
    read_service: OverviewRuntimeReadService = Depends(get_overview_runtime_read_service),  # noqa: B008
) -> OverviewRuntimeResponse:
    """Return durable runtime information without changing execution or persistence state."""

    return await _read_safely(read_service.get_runtime)
