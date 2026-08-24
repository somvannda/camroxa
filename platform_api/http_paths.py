"""Canonical API version prefixes and legacy path rewrites.

The platform API version lives at the root:

- ``/api/v1`` — existing studio, auth, streaming, and web-music generate APIs
- ``/api/v2`` — web-music subscriptions, credits, and top-ups

Do not nest versions (``/api/v1/v2/...``). That happened when v2 routers
were included under ``api_v1_prefix``.
"""

from __future__ import annotations

API_V1_PREFIX = "/api/v1"
API_V2_PREFIX = "/api/v2"
LEGACY_NESTED_V2_PREFIX = "/api/v1/v2"


def rewrite_legacy_nested_v2_path(path: str) -> str:
    """Rewrite ``/api/v1/v2/...`` to ``/api/v2/...``."""
    if path == LEGACY_NESTED_V2_PREFIX:
        return API_V2_PREFIX
    nested = f"{LEGACY_NESTED_V2_PREFIX}/"
    if path.startswith(nested):
        return f"{API_V2_PREFIX}/{path[len(nested):]}"
    return path


def strip_api_version_prefix(path: str) -> str:
    """Strip ``/api/v1``, ``/api/v2``, and the legacy nested prefix from a path."""
    normalized = path.lower().strip("/")
    for prefix in ("api/v1/v2/", "api/v1/", "api/v2/"):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    if normalized in {"api/v1", "api/v2", "api/v1/v2"}:
        return ""
    return normalized
