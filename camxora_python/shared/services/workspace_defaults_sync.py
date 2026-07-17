"""Persist first-run media/FFmpeg defaults into platform settings when empty."""

from __future__ import annotations

from typing import Any

from shared.lib.workspace_defaults import apply_workspace_path_defaults
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache


def ensure_workspace_defaults(
    *,
    settings_raw: dict[str, Any] | None,
    api: PlatformApi | None = None,
    cache: WorkspaceCache | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Fill empty path settings, create folders, optionally PATCH the server."""
    merged, patch = apply_workspace_path_defaults(settings_raw)
    if cache is not None and patch:
        connections, _ = cache.snapshot_settings_extras()
        cache.apply_settings_workspace(settings_raw=merged, youtube_connections=connections)
    if persist and patch and api is not None:
        try:
            api.patch_settings(patch)
        except Exception:
            pass
    return merged
