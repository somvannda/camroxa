"""Canonical API version prefixes and legacy path rewrites.

The platform API version lives at the root:

- ``/api/v1`` — studio, auth, streaming, web-music generate (temporary dual-mount)
- ``/api/v2`` — web-music CutLuy subscriptions/credits/topups (temporary)
- ``/api/v3`` — canonical full surface (former v1 + v2 billing + wallet)

Do not nest versions (``/api/v1/v2/...``). That happened when v2 routers
were included under ``api_v1_prefix``.
"""

from __future__ import annotations

API_V1_PREFIX = "/api/v1"
API_V2_PREFIX = "/api/v2"
API_V3_PREFIX = "/api/v3"
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
    """Strip ``/api/v1``, ``/api/v2``, ``/api/v3``, and legacy nested prefix."""
    normalized = path.lower().strip("/")
    for prefix in ("api/v1/v2/", "api/v1/", "api/v2/", "api/v3/"):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    if normalized in {"api/v1", "api/v2", "api/v3", "api/v1/v2"}:
        return ""
    return normalized
