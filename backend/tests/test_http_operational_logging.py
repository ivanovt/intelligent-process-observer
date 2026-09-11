"""Tests for FastAPI's expected-rejection and unexpected-error diagnostic split."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.routing import Route

from app.core.diagnostics import OperationalEventEmitter
from app.core.settings import Settings
from app.main import (
    api_error_handler,
    app,
    lifespan,
    log_unhandled_http_exception,
    validation_error_handler,
)
from app.observations.errors import ApiError


def test_expected_api_rejection_is_not_logged_as_an_internal_error() -> None:
    """Known 4xx API errors remain ordinary contract responses."""
    messages, request = _configured_request()

    response = asyncio.run(api_error_handler(request, ApiError(409, "conflict", "Conflict")))

    assert response.status_code == 409
    assert messages == []


def test_safe_api_normalization_and_unhandled_error_are_operationally_visible() -> None:
    """Internal failures are correlated only through safe event metadata."""
    messages, request = _configured_request()

    normalized = asyncio.run(
        api_error_handler(request, ApiError(503, "runtime_read_unavailable", "Unavailable"))
    )

    async def fail(_: Request) -> object:
        raise RuntimeError("unexpected internal failure")

    with pytest.raises(RuntimeError, match="unexpected internal failure"):
        asyncio.run(log_unhandled_http_exception(request, fail))

    assert normalized.status_code == 503
    payloads = [json.loads(message) for message in messages]
    assert payloads[0]["event"] == "api_error_normalized"
    assert "traceback" not in payloads[0]
    assert payloads[1]["event"] == "http_unhandled_exception"
    assert payloads[1]["exception_type"] == "RuntimeError"
    assert "unexpected internal failure" not in payloads[1]["traceback"]


def test_unhandled_http_failure_uses_fastapis_existing_default_500_envelope(caplog) -> None:
    """Operational logging does not replace the framework's unhandled-error response."""
    import httpx

    async def endpoint(_: Request) -> object:
        raise RuntimeError("test unhandled endpoint")

    route = Route("/_test-unhandled-operational-error", endpoint=endpoint, methods=["GET"])
    app.router.routes.append(route)
    app.state.operational_event_emitter = OperationalEventEmitter()

    async def request_failure() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/_test-unhandled-operational-error")

    try:
        with caplog.at_level("ERROR", logger="app.operational"):
            response = asyncio.run(request_failure())
    finally:
        app.router.routes.remove(route)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "Internal Server Error"
    assert any("http_unhandled_exception" in record.message for record in caplog.records)


def test_validation_4xx_does_not_emit_an_internal_error_event() -> None:
    """FastAPI validation remains an expected client rejection."""
    messages, request = _configured_request()
    error = RequestValidationError(
        [{"type": "missing", "loc": ("body", "observation_id"), "msg": "Field required"}]
    )

    response = asyncio.run(validation_error_handler(request, error))

    assert response.status_code == 422
    assert messages == []


def test_startup_failure_is_logged_with_a_scrubbed_traceback(
    caplog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lifespan startup failures remain visible without leaking configured values."""
    import app.main as main_module

    secret = "startup-configured-secret"
    monkeypatch.setattr(main_module, "get_settings", lambda: Settings(openrouter_api_key=secret))

    def fail_engine_creation() -> object:
        raise RuntimeError(f"database startup failed: {secret}")

    monkeypatch.setattr(main_module, "create_database_engine", fail_engine_creation)

    async def start() -> None:
        async with lifespan(app):
            raise AssertionError("unreachable")

    with caplog.at_level("ERROR", logger="app.operational"), pytest.raises(RuntimeError):
        asyncio.run(start())

    payload = next(
        json.loads(record.message)
        for record in caplog.records
        if record.name == "app.operational" and "application_startup_failed" in record.message
    )
    assert payload["event"] == "application_startup_failed"
    assert secret not in json.dumps(payload)


def _configured_request() -> tuple[list[str], Request]:
    """Build one isolated request with a collecting lifespan-style emitter."""
    messages: list[str] = []
    logger = logging.getLogger("test.http.operational")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    app.state.operational_event_emitter = OperationalEventEmitter(logger=logger)
    return messages, Request({"type": "http", "app": app, "method": "GET", "headers": []})


class _CollectingHandler(logging.Handler):
    """Collect direct handler output without changing root logger configuration."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self._messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        """Capture one structured operational event."""
        self._messages.append(record.getMessage())
