"""Persist first-run media/FFmpeg defaults into platform settings when empty."""

from __future__ import annotations

from typing import Any

from shared.lib.device_workspace_paths import DEVICE_MEDIA_PATH_KEYS, persist_device_paths_from_settings
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
    """Fill empty path settings, create folders, optionally PATCH heal defaults.

    Always writes resolved media folder roots into the per-device local store.
    Absolute media roots are **not** pushed into account settings — the API plans
    portable ``channel\\date_album`` run keys; each desktop owns its own drop root.
    """
    cloud = dict(settings_raw or {})
    merged, patch = apply_workspace_path_defaults(cloud)
    persist_device_paths_from_settings(merged)
    if cache is not None and (patch or merged != cloud):
        connections, _ = cache.snapshot_settings_extras()
        cache.apply_settings_workspace(settings_raw=merged, youtube_connections=connections)
    cloud_patch = {key: value for key, value in patch.items() if key not in DEVICE_MEDIA_PATH_KEYS}
    if persist and cloud_patch and api is not None:
        try:
            api.patch_settings(cloud_patch)
        except Exception:
            pass
    return merged
