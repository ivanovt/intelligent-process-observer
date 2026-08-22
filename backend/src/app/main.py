from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.infrastructure.persistence.database import create_database_engine, create_session_factory
from app.infrastructure.prometheus.adapter import HttpxPrometheusQueryAdapter
from app.observations.api import router
from app.observations.errors import ApiError
from app.observations.service import ObservationDefinitionService


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_database_engine()
    app.state.session_factory = create_session_factory(engine)
    app.state.observation_service = ObservationDefinitionService()
    app.state.prometheus_adapter = HttpxPrometheusQueryAdapter()
    yield
    await engine.dispose()


app = FastAPI(title="Intelligent Process Observer", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    content: dict[str, str] = {"code": error.code, "message": error.message}
    if error.field is not None:
        content["field"] = error.field
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


def status_code_for_validation(error: RequestValidationError) -> int:
    return 422 if any(item["loc"][0] == "body" for item in error.errors()) else 400


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
