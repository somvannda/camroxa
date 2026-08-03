"""Persist first-run media/FFmpeg defaults into platform settings when empty."""

from __future__ import annotations

from typing import Any

from shared.lib.device_workspace_paths import (
    device_path_patch_against_cloud,
    persist_device_paths_from_settings,
)
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
    """Fill empty path settings, create folders, optionally PATCH the server.

    Always writes resolved media folder roots into the per-device local store.
    When ``persist`` is true, also PATCHes any heal fixes plus any local-vs-cloud
    path diffs so the active machine owns account planning paths.
    """
    cloud = dict(settings_raw or {})
    merged, patch = apply_workspace_path_defaults(cloud)
    persist_device_paths_from_settings(merged)
    # Active desktop pushes its roots so Suno run-dir planning matches this PC.
    patch = {**patch, **device_path_patch_against_cloud(merged, cloud)}
    if cache is not None and (patch or merged != cloud):
        connections, _ = cache.snapshot_settings_extras()
        cache.apply_settings_workspace(settings_raw=merged, youtube_connections=connections)
    if persist and patch and api is not None:
        try:
            api.patch_settings(patch)
        except Exception:
            pass
    return merged
