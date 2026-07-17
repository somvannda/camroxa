"""Per-account local workspace context exposed on the active session."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.lib.app_paths import (
    get_image_workspace_prefs_path,
    get_music_workspace_prefs_path,
    get_profile_media_cache_dir,
    get_user_data_dir,
    get_user_video_templates_path,
    get_video_draft_store_dir,
    get_video_presets_dir,
    get_video_workspace_prefs_path,
    get_workflow_workspace_prefs_path,
)


def _user_workspace_root(user_id: str) -> Path:
    return get_user_data_dir() / "users" / user_id


@dataclass(frozen=True, slots=True)
class LocalWorkspaceContext:
    """Resolved on-disk locations for the currently active account."""

    user_id: str

    @property
    def root(self) -> Path:
        return _user_workspace_root(self.user_id)

    @property
    def music_prefs_path(self) -> Path:
        return get_music_workspace_prefs_path(self.user_id)

    @property
    def video_prefs_path(self) -> Path:
        return get_video_workspace_prefs_path(self.user_id)

    @property
    def video_templates_path(self) -> Path:
        return get_user_video_templates_path(self.user_id)

    @property
    def video_drafts_dir(self) -> Path:
        return get_video_draft_store_dir(self.user_id)

    @property
    def video_presets_dir(self) -> Path:
        return get_video_presets_dir(self.user_id)

    @property
    def image_prefs_path(self) -> Path:
        return get_image_workspace_prefs_path(self.user_id)

    @property
    def workflow_prefs_path(self) -> Path:
        return get_workflow_workspace_prefs_path(self.user_id)

    @property
    def profile_media_dir(self) -> Path:
        return get_profile_media_cache_dir(self.user_id)
