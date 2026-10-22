"""Tests for platform_api.middleware.request_log.

A user-facing 500 on ``/api/v3/web-music/generate`` (2026-10-21) left no log
line whatsoever: the middleware only emitted an INFO access record, and every
5xx produced without an exception reaching the global handler vanished. These
tests pin the behaviour that a 5xx is always logged at ERROR, with enough
context to identify the route.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from platform_api.logging_setup import configure_api_logging
from platform_api.middleware.request_log import RequestLogMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestLogMiddleware)

    @app.get("/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/explodes")
    async def explodes() -> JSONResponse:
        return JSONResponse(
            status_code=500, content={"error": {"code": "INTERNAL_SERVER_ERROR"}}
        )

    @app.get("/raises")
    async def raises() -> None:
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_5xx_response_is_logged_at_error(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="platform_api.middleware.request_log"):
        response = _client().post("/explodes?retry=2")

    assert response.status_code == 500
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("API 5xx response" in m for m in messages), messages
    line = next(m for m in messages if "API 5xx response" in m)
    assert "POST" in line
    assert "/explodes?retry=2" in line
    assert "500" in line


def test_successful_request_is_not_logged_as_an_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="platform_api.middleware.request_log"):
        response = _client().get("/ok")

    assert response.status_code == 200
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_unhandled_exception_is_logged_with_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="platform_api.middleware.request_log"):
        response = _client().get("/raises")

    assert response.status_code == 500
    record = next(
        (r for r in caplog.records if "unhandled exception" in r.getMessage()), None
    )
    assert record is not None
    assert record.exc_info is not None, "expected a traceback on the 5xx log record"
    assert "boom" in str(record.exc_info[1])


def test_configure_api_logging_repairs_a_disabled_logger() -> None:
    access = logging.getLogger("platform_api.access")
    original_level, original_disabled = access.level, access.disabled
    try:
        access.disabled = True
        access.setLevel(logging.WARNING)
        assert not access.isEnabledFor(logging.INFO)

        configure_api_logging()

        assert access.disabled is False
        assert access.isEnabledFor(logging.INFO)
        assert logging.getLogger().level == logging.INFO
    finally:
        access.disabled = original_disabled
        access.setLevel(original_level)
