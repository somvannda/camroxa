"""Application filesystem paths — mirrors Electron main-process layout."""

from __future__ import annotations

import os
from pathlib import Path


def get_project_root() -> Path:
    """MusicGenerator repo root (parent of camxora_python).

    In frozen builds there is no repo tree — prefer get_package_root() for
    bundled assets instead of relying on this path.
    """
    from shared.lib.resource_paths import get_package_root
    from shared.lib.runtime_paths import is_frozen_runtime

    if is_frozen_runtime():
        return get_package_root()
    return Path(__file__).resolve().parents[3]


def get_python_app_dir() -> Path:
    return get_project_root() / "python_app"


def get_user_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return base / "Camxora"


def _workspace_root(user_id: str | None = None) -> Path:
    from shared.services.local_user_scope import get_user_workspace_dir

    return get_user_workspace_dir(user_id)


def get_video_templates_path() -> Path:
    """Legacy factory catalog path (no longer auto-loaded into the UI).

    Kept for packaging/tests that still reference the file on disk. The video
    workspace only reads per-user templates via ``get_user_video_templates_path``.
    """
    from shared.lib.resource_paths import get_package_root

    bundled = get_package_root() / "data" / "video_templates_local.json"
    if bundled.is_file():
        return bundled
    return get_python_app_dir() / "video_templates_local.json"


def get_user_video_templates_path(user_id: str | None = None) -> Path:
    """Per-account saved/edited video templates."""
    return _workspace_root(user_id) / "video-templates.json"


def get_music_workspace_prefs_path(user_id: str | None = None) -> Path:
    return _workspace_root(user_id) / "camxora-music-workspace.json"


def get_video_workspace_prefs_path(user_id: str | None = None) -> Path:
    return _workspace_root(user_id) / "camxora-video-workspace.json"


def get_video_draft_store_dir(user_id: str | None = None) -> Path:
    return _workspace_root(user_id) / "video-drafts"


def get_studio_projects_dir(user_id: str | None = None) -> Path:
    """Composition Studio projects (separate from Video templates)."""
    return _workspace_root(user_id) / "studio-projects"


def get_studio_prefs_path(user_id: str | None = None) -> Path:
    return _workspace_root(user_id) / "camxora-studio-workspace.json"


def get_effect_packs_dir() -> Path:
    """Shared effect-pack assets (large downloads) — machine-global."""
    return get_user_data_dir() / "effect-packs"


def get_video_presets_dir(user_id: str | None = None) -> Path:
    """Per-domain built-in preset overrides (user tweaks; survives restart)."""
    return _workspace_root(user_id) / "video-presets"


def get_image_workspace_prefs_path(user_id: str | None = None) -> Path:
    return _workspace_root(user_id) / "camxora-image-workspace.json"


def get_workflow_workspace_prefs_path(user_id: str | None = None) -> Path:
    return _workspace_root(user_id) / "camxora-workflow-workspace.json"


def get_client_logs_dir() -> Path:
    """Local app log files (ring-buffered UI + daily files)."""
    return get_user_data_dir() / "logs"


def get_profile_media_cache_dir(user_id: str | None = None) -> Path:
    """Cached channel logo/cover downloads from platform_api media endpoints."""
    return _workspace_root(user_id) / "profile-media"
