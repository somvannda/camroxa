"""Per-account local workspace paths on this machine.

Desktop workspace prefs (music dates, video template selection, drafts, etc.)
are stored under ``%LOCALAPPDATA%/Camxora/users/{userId}/`` so switching
accounts on the same PC does not reuse another user's local layout.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from shared.lib.app_paths import get_user_data_dir
from shared.models.local_workspace import LocalWorkspaceContext
from shared.services.secure_storage import LAST_USER_ID_KEY, SecureStorage

_active_user_id: str | None = None
_active_context: LocalWorkspaceContext | None = None

_LEGACY_FILES = (
    "camxora-music-workspace.json",
    "camxora-video-workspace.json",
    "video-templates.json",
)
_LEGACY_DIRS = (
    "video-drafts",
    "video-presets",
    "profile-media",
)


def _normalize_user_id(user_id: str) -> str:
    cleaned = str(user_id or "").strip()
    if not cleaned:
        raise ValueError("user_id is required for local workspace scope")
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", cleaned)
    return safe or cleaned


def get_active_user_id() -> str | None:
    return _active_user_id


def get_active_workspace_context() -> LocalWorkspaceContext | None:
    return _active_context


def set_active_user_id(user_id: str | None) -> None:
    global _active_user_id, _active_context
    if user_id is None:
        _active_user_id = None
        _active_context = None
        return
    normalized = _normalize_user_id(user_id)
    _active_user_id = normalized
    _active_context = LocalWorkspaceContext(user_id=normalized)


def get_user_workspace_dir(user_id: str | None = None) -> Path:
    """Return the on-disk workspace root for a user (or the active session user)."""
    uid = user_id or _active_user_id
    if uid is None:
        return get_user_data_dir()
    return get_user_data_dir() / "users" / _normalize_user_id(uid)


def _legacy_has_data(root: Path) -> bool:
    for name in _LEGACY_FILES:
        if (root / name).is_file():
            return True
    for name in _LEGACY_DIRS:
        path = root / name
        if path.is_dir() and any(path.iterdir()):
            return True
    return False


def _scoped_has_data(scoped: Path) -> bool:
    if not scoped.is_dir():
        return False
    for name in _LEGACY_FILES:
        if (scoped / name).is_file():
            return True
    for name in _LEGACY_DIRS:
        path = scoped / name
        if path.is_dir() and any(path.iterdir()):
            return True
    return any(scoped.iterdir())


def _move_legacy_to_user_dir(scoped: Path) -> None:
    root = get_user_data_dir()
    scoped.mkdir(parents=True, exist_ok=True)
    for name in _LEGACY_FILES:
        source = root / name
        if source.is_file():
            target = scoped / name
            if not target.exists():
                shutil.move(str(source), str(target))
    for name in _LEGACY_DIRS:
        source = root / name
        if not source.is_dir():
            continue
        target = scoped / name
        if target.exists():
            continue
        shutil.move(str(source), str(target))


def _migrate_legacy_workspace_if_needed(user_id: str) -> None:
    """One-time upgrade: move pre-scoping global files into the first user's folder."""
    scoped = get_user_workspace_dir(user_id)
    if _scoped_has_data(scoped):
        return
    root = get_user_data_dir()
    if not _legacy_has_data(root):
        return
    users_root = root / "users"
    if users_root.is_dir():
        for child in users_root.iterdir():
            if child.is_dir() and child.name != scoped.name and _scoped_has_data(child):
                return
    _move_legacy_to_user_dir(scoped)


def activate_local_user_scope(user_id: str, storage: SecureStorage | None = None) -> None:
    """Point all local workspace stores at this account's directory."""
    normalized = _normalize_user_id(user_id)
    _migrate_legacy_workspace_if_needed(normalized)
    set_active_user_id(normalized)
    if storage is not None:
        storage.set(LAST_USER_ID_KEY, normalized)


def deactivate_local_user_scope() -> None:
    """Clear in-memory scope on logout (per-user files remain on disk)."""
    set_active_user_id(None)
    from shared.services.video_workspace_service import get_video_workspace_service

    get_video_workspace_service().set_workspace_state(None)


def forget_local_user_data(user_id: str, storage: SecureStorage | None = None) -> None:
    """Delete all on-disk workspace files for one account on this machine."""
    from shared.services.account_token_store import remove_saved_account

    scoped = get_user_workspace_dir(user_id)
    if scoped.is_dir():
        shutil.rmtree(scoped, ignore_errors=True)
    if storage is not None:
        remove_saved_account(storage, user_id)
