"""Rewrite the accidental ``/api/v1/v2`` nest onto canonical ``/api/v2``.

Old music-web clients called ``/api/v1/v2/subscriptions/...`` because the
v2 routers were mounted under the global v1 prefix. Keep those URLs working
while clients move to ``/api/v2``.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from platform_api.http_paths import rewrite_legacy_nested_v2_path


class LegacyNestedV2PathMiddleware:
    """Pure ASGI rewrite so routing, auth, and rate limits see ``/api/v2``."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"}:
            path = scope.get("path") or ""
            rewritten = rewrite_legacy_nested_v2_path(path)
            if rewritten != path:
                scope["path"] = rewritten
                raw = scope.get("raw_path")
                if isinstance(raw, (bytes, bytearray)):
                    scope["raw_path"] = rewritten.encode("utf-8")
        await self.app(scope, receive, send)
