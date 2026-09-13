from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter
from app.core.settings import get_settings
from app.execution import ExecutionPolicy, ObservationRunManager
from app.infrastructure.execution import build_production_execution_composition
from app.infrastructure.jira import JiraAlertProviderResolver
from app.infrastructure.persistence.database import create_database_engine, create_session_factory
from app.infrastructure.persistence.repository import (
    RuntimeExecutionStateStore,
    RuntimePersistenceRepository,
)
from app.infrastructure.prometheus.adapter import HttpxPrometheusQueryAdapter
from app.infrastructure.prometheus.composition import PrometheusMetricSeriesProvider
from app.knowledge.api import router as knowledge_router
from app.observation_runs.api import router as observation_runs_router
from app.observation_runs.read import ObservationRunReadService
from app.observations.api import router
from app.observations.errors import ApiError
from app.observations.service import ObservationDefinitionService
from app.overview_runtime.api import router as overview_runtime_router
from app.overview_runtime.read import OverviewRuntimeReadService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    emitter = OperationalEventEmitter(configured_secrets=settings.configured_secret_values())
    app.state.operational_event_emitter = emitter
    engine = None
    try:
        engine = create_database_engine()
        app.state.session_factory = create_session_factory(engine)
        app.state.observation_service = ObservationDefinitionService()
        app.state.prometheus_adapter = HttpxPrometheusQueryAdapter()
        app.state.metric_series_provider = PrometheusMetricSeriesProvider(
            settings.prometheus_sources
        )
        app.state.jira_alert_provider_resolver = JiraAlertProviderResolver(
            settings.jira_alert_provider_raw
        )
        app.state.execution_composition = build_production_execution_composition(
            settings=settings, session_factory=app.state.session_factory, emitter=emitter
        )
        runtime_repository = RuntimePersistenceRepository()
        runtime_state_store = RuntimeExecutionStateStore(
            app.state.session_factory, runtime_repository
        )
        app.state.observation_run_read_service = ObservationRunReadService(
            app.state.session_factory, runtime_repository
        )
        app.state.overview_runtime_read_service = OverviewRuntimeReadService(
            app.state.session_factory, runtime_repository
        )
        app.state.observation_run_manager = ObservationRunManager(
            orchestrator=app.state.execution_composition.orchestrator,
            active_run_lookup=runtime_state_store,
            reconciler=runtime_state_store,
            policy=ExecutionPolicy(
                max_parallel_lens_runs=settings.max_parallel_lens_runs,
                lens_deadline_seconds=settings.lens_deadline_seconds,
            ),
            emitter=emitter,
        )
        await app.state.observation_run_manager.request_recovery()
        yield
    except BaseException as error:
        emitter.emit(
            DiagnosticEvent(
                event="application_startup_failed",
                category="startup_failed",
                component="lifespan",
            ),
            error=error,
        )
        raise
    finally:
        manager = getattr(app.state, "observation_run_manager", None)
        if manager is not None:
            await manager.shutdown()
        if engine is not None:
            await engine.dispose()


app = FastAPI(title="Intelligent Process Observer", lifespan=lifespan)
app.include_router(router)
app.include_router(knowledge_router)
app.include_router(observation_runs_router)
app.include_router(overview_runtime_router)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    if error.status_code >= 500:
        _event_emitter(_).emit(
            DiagnosticEvent(
                event="api_error_normalized",
                category=error.code,
                component="api",
                http_status=error.status_code,
            )
        )
    content: dict[str, str] = {"code": error.code, "message": error.message}
    if error.field is not None:
        content["field"] = error.field
    content.update(error.details)
    return JSONResponse(status_code=error.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    first_error = error.errors()[0]
    location = [str(part) for part in first_error["loc"] if part != "body"]
    content: dict[str, str] = {
        "code": "validation_error",
        "message": first_error["msg"],
    }
    if location:
        content["field"] = ".".join(location)
    return JSONResponse(status_code=status_code_for_validation(error), content=content)


@app.middleware("http")
async def log_unhandled_http_exception(request: Request, call_next) -> object:
    """Log unexpected HTTP failures, then preserve FastAPI's original error handling."""
    try:
        return await call_next(request)
    except Exception as error:
        _event_emitter(request).emit(
            DiagnosticEvent(
                event="http_unhandled_exception",
                category="internal_error",
                component="fastapi",
                http_status=500,
            ),
            error=error,
        )
        raise


def status_code_for_validation(error: RequestValidationError) -> int:
    return 422 if any(item["loc"][0] == "body" for item in error.errors()) else 400


def _event_emitter(request: Request) -> OperationalEventEmitter:
    """Return the lifespan-configured emitter or a safe default during isolated tests."""
    emitter = getattr(request.app.state, "operational_event_emitter", None)
    return emitter if isinstance(emitter, OperationalEventEmitter) else OperationalEventEmitter()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
