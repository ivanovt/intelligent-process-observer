"""HTTP boundary for managed Observation run launch and read operations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.execution import (
    AnalysisWindow,
    LaunchAccepted,
    LaunchConflict,
    LaunchUnavailable,
    ObservationExecutionRequest,
    ObservationRunManager,
    RejectedObservationExecutionOutcome,
)
from app.observation_runs.contracts import (
    ObservationRunDetail,
    ObservationRunLaunchRequest,
    ObservationRunSummary,
)
from app.observation_runs.projection import RuntimeProjectionInvalid
from app.observation_runs.read import ObservationRunReadService
from app.observations.errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["observation-runs"])


async def get_run_manager(request: Request) -> ObservationRunManager:
    """Return the single lifespan-owned manager for detached run execution."""

    return request.app.state.observation_run_manager


async def get_run_read_service(request: Request) -> ObservationRunReadService:
    """Return the lifespan-owned read-only public run projection service."""

    return request.app.state.observation_run_read_service


@router.post(
    "/observation-runs",
    response_model=ObservationRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
async def launch_observation_run(
    payload: ObservationRunLaunchRequest,
    manager: ObservationRunManager = Depends(get_run_manager),  # noqa: B008
) -> ObservationRunSummary:
    """Initialize one run and return its detached immutable running acceptance snapshot."""

    outcome = await manager.launch(
        ObservationExecutionRequest(
            observation_id=payload.observation_id,
            analysis_window=AnalysisWindow(
                from_=payload.analysis_window.from_, to=payload.analysis_window.to
            ),
        )
    )
    if isinstance(outcome, LaunchAccepted):
        return _acceptance_summary(outcome)
    if isinstance(outcome, LaunchConflict):
        raise _conflict_error(outcome.observation_run_id)
    if isinstance(outcome, LaunchUnavailable):
        raise ApiError(503, outcome.code, "Observation run launch is temporarily unavailable")
    if isinstance(outcome, RejectedObservationExecutionOutcome):
        raise _preparation_error(outcome)
    raise ApiError(503, "execution_recovery_pending", "Observation run launch is unavailable")


@router.get("/observation-runs", response_model=list[ObservationRunSummary])
async def list_observation_runs(
    read_service: ObservationRunReadService = Depends(get_run_read_service),  # noqa: B008
) -> list[ObservationRunSummary]:
    """Return the complete durable history without changing execution state."""

    return await _read_safely(read_service.list_summaries)


@router.get("/observation-runs/{observation_run_id}", response_model=ObservationRunDetail)
async def get_observation_run(
    observation_run_id: UUID,
    read_service: ObservationRunReadService = Depends(get_run_read_service),  # noqa: B008
) -> ObservationRunDetail:
    """Return one coherent durable run projection without changing execution state."""

    detail = await _read_safely(lambda: read_service.get_detail(observation_run_id))
    if detail is None:
        raise ApiError(404, "observation_run_not_found", "Observation run was not found")
    return detail


def _acceptance_summary(outcome: LaunchAccepted) -> ObservationRunSummary:
    """Convert only the already captured initialization handoff without persistence I/O."""

    summary = outcome.summary
    return ObservationRunSummary.model_validate(
        {
            "id": summary.observation_run_id,
            "observation": {"id": summary.observation_id, "name": summary.observation_name},
            "analysis_window": {
                "from": summary.analysis_window.from_,
                "to": summary.analysis_window.to,
            },
            "status": summary.status,
            "reason": summary.reason,
            "analytical_state": summary.analytical_state,
            "created_at": summary.created_at,
            "started_at": summary.started_at,
            "finished_at": summary.finished_at,
            "duration_seconds": summary.duration_seconds,
            "href": summary.href,
        }
    )


def _conflict_error(observation_run_id: UUID) -> ApiError:
    """Build the stable existing-run conflict payload without inspecting mutable state."""

    return ApiError(
        409,
        "observation_run_active",
        "Observation already has an active run",
        details={
            "observation_run_id": str(observation_run_id),
            "href": f"/api/v1/observation-runs/{observation_run_id}",
        },
    )


def _preparation_error(outcome: RejectedObservationExecutionOutcome) -> ApiError:
    """Map closed framework-neutral preparation rejections to safe HTTP outcomes."""

    code = outcome.reason.code
    if code == "observation_not_found":
        return ApiError(404, code, "Observation definition was not found")
    return ApiError(422, code, "Observation definition cannot be executed")


async def _read_safely(
    operation: Callable[[], Awaitable[object]],
) -> object:
    """Keep corrupt artifacts and unavailable persistence behind safe public errors."""

    try:
        return await operation()
    except RuntimeProjectionInvalid as error:
        raise ApiError(
            500, "runtime_projection_invalid", "Run projection is unavailable"
        ) from error
    except ApiError:
        raise
    except Exception as error:
        raise ApiError(
            503, "runtime_read_unavailable", "Run data is temporarily unavailable"
        ) from error
