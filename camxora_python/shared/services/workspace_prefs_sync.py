"""Optional cloud sync for per-account desktop workspace prefs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from shared.lib.app_paths import (
    get_image_workspace_prefs_path,
    get_music_workspace_prefs_path,
    get_video_workspace_prefs_path,
    get_workflow_workspace_prefs_path,
)
from shared.services.local_user_scope import get_active_user_id

DESKTOP_WORKSPACE_PREFS_KEY = "desktopWorkspacePrefs"
SYNC_VERSION = 1

# Video workspace prefs carry local filesystem references (background/logo
# image, selected MP3, MP3 folder) but are synced account-wide via
# desktopWorkspacePrefs, so a snapshot pulled down after being written on a
# different machine can carry paths that don't exist here — same class of
# bug as the workspace_defaults folder-path fix. Same-machine round-trips are
# unaffected since the paths still resolve.
_VIDEO_FILE_PATH_KEYS = ("backgroundPath", "logoPath", "selectedMp3Path")
_VIDEO_DIR_PATH_KEYS = ("mp3Directory",)


def _sanitize_video_paths(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    for key in _VIDEO_FILE_PATH_KEYS:
        value = str(cleaned.get(key) or "").strip()
        if value and not Path(value).is_file():
            cleaned.pop(key, None)
    for key in _VIDEO_DIR_PATH_KEYS:
        value = str(cleaned.get(key) or "").strip()
        if value and not Path(value).is_dir():
            cleaned.pop(key, None)
    return cleaned


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def build_local_workspace_snapshot(user_id: str | None = None) -> dict[str, Any]:
    uid = user_id or get_active_user_id()
    if uid is None:
        return {}
    return {
        "version": SYNC_VERSION,
        "updatedAt": int(time.time() * 1000),
        "music": _read_json(get_music_workspace_prefs_path(uid)) or {},
        "video": _read_json(get_video_workspace_prefs_path(uid)) or {},
        "image": _read_json(get_image_workspace_prefs_path(uid)) or {},
        "workflow": _read_json(get_workflow_workspace_prefs_path(uid)) or {},
    }


def apply_workspace_snapshot(user_id: str, snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        return

    def _write(path: Path, payload: object, *, sanitize=None) -> None:
        if not isinstance(payload, dict) or not payload:
            return
        if sanitize is not None:
            payload = sanitize(payload)
            if not payload:
                return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _write(get_music_workspace_prefs_path(user_id), snapshot.get("music"))
    _write(get_video_workspace_prefs_path(user_id), snapshot.get("video"), sanitize=_sanitize_video_paths)
    _write(get_image_workspace_prefs_path(user_id), snapshot.get("image"))
    _write(get_workflow_workspace_prefs_path(user_id), snapshot.get("workflow"))


def extract_remote_snapshot(settings_raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not settings_raw:
        return None
    remote = settings_raw.get(DESKTOP_WORKSPACE_PREFS_KEY)
    if isinstance(remote, str):
        try:
            remote = json.loads(remote)
        except json.JSONDecodeError:
            return None
    return remote if isinstance(remote, dict) else None


def remote_is_newer(local_snapshot: dict[str, Any], remote_snapshot: dict[str, Any]) -> bool:
    local_ts = int(local_snapshot.get("updatedAt") or 0)
    remote_ts = int(remote_snapshot.get("updatedAt") or 0)
    return remote_ts > local_ts


def pull_workspace_prefs_from_settings(user_id: str, settings_raw: dict[str, Any] | None) -> bool:
    remote = extract_remote_snapshot(settings_raw)
    if remote is None:
        return False
    local = build_local_workspace_snapshot(user_id)
    if local and not remote_is_newer(local, remote):
        return False
    apply_workspace_snapshot(user_id, remote)
    return True


def build_settings_patch_from_local(user_id: str | None = None) -> dict[str, Any]:
    snapshot = build_local_workspace_snapshot(user_id)
    if not snapshot:
        return {}
    return {DESKTOP_WORKSPACE_PREFS_KEY: snapshot}


async def push_workspace_prefs_to_api(api: Any, user_id: str | None = None) -> None:
    patch = build_settings_patch_from_local(user_id)
    if not patch:
        return
    await api.patch_settings_async(patch) if hasattr(api, "patch_settings_async") else None
