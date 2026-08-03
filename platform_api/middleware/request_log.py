"""Readable HTTP request logging for the API terminal."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_PROGRESS_PATH_SUFFIXES = ("/progress",)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log each API request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
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
        line = f"→ {request.method} {path} {response.status_code} {elapsed_ms:.0f}ms"
        from platform_api.terminal_log import emit

        emit("access", "%s", line)
        return response
