"""Readable HTTP request logging for the API terminal."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_PROGRESS_PATH_SUFFIXES = ("/progress",)


def _client_host(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log each API request with method, path, status, and duration.

    Every 5xx also gets its own ERROR record. A 5xx can be produced without an
    exception ever reaching the global handler (a route returning an error
    response, or the audit middleware swallowing the failure), and those used
    to leave no trace at all in the journal — which is why a user-facing
    ``/web-music/generate`` failure on 2026-10-21 could not be diagnosed.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "API 5xx (unhandled exception): %s %s after %.0fms client=%s",
                request.method,
                request.url.path,
                (time.perf_counter() - start) * 1000.0,
                _client_host(request),
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        path = request.url.path
        if any(path.endswith(suffix) for suffix in _PROGRESS_PATH_SUFFIXES):
            try:
                from platform_api.services.request_latency import record_latency_ms

                record_latency_ms("/progress", elapsed_ms)
            except Exception:
                pass
        if request.url.query:
            path = f"{path}?{request.url.query}"
        if response.status_code >= 500:
            logger.error(
                "API 5xx response: %s %s -> %d in %.0fms client=%s",
                request.method,
                path,
                response.status_code,
                elapsed_ms,
                _client_host(request),
            )
        line = f"→ {request.method} {path} {response.status_code} {elapsed_ms:.0f}ms"
        from platform_api.terminal_log import emit

        emit("access", "%s", line)
        return response
