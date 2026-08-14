"""First-run defaults for local media folders and FFmpeg path.

Users can still change any path in Settings. Empty values are filled once and
directories are created automatically.

Media folder roots are stored per-machine in
``device_workspace_paths`` (under the local user workspace) and overlaid onto
cloud settings before heal/defaults run. Absolute media roots are never
pushed into account ``user_settings`` — the API plans portable run keys.
Foreign / unusable cloud leftovers self-heal to this machine's defaults in
the local store only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shared.lib.app_paths import get_user_data_dir
from shared.lib.disk_space import has_sufficient_free_space
from shared.lib.export_codec import DEFAULT_EXPORT_SPEED_MODE
from shared.lib.ffmpeg_paths import get_bundled_ffmpeg_path, resolve_ffmpeg_path
from shared.lib.path_locality import is_foreign_windows_profile_path


_PATH_KEYS = (
    "ffmpegPath",
    "downloadsDir",
    "sunoOutputDir",
    "mergedDir",
    "imageBackgroundSamplesDir",
    "imageThumbnailSamplesDir",
    "imageOutputDir",
)

_known_uncreatable_paths: set[str] = set()
_logged_foreign_paths: set[str] = set()


def default_media_root() -> Path:
    return get_user_data_dir() / "Media"


def default_workspace_paths() -> dict[str, str]:
    root = default_media_root()
    return {
        "downloadsDir": str(root / "Downloads"),
        "sunoOutputDir": str(root / "Suno"),
        "mergedDir": str(root / "Merged"),
        "imageBackgroundSamplesDir": str(root / "Samples" / "Background"),
        "imageThumbnailSamplesDir": str(root / "Samples" / "Thumbnail"),
        "imageOutputDir": str(root / "Images"),
    }


def workspace_paths_equivalent(left: str, right: str) -> bool:
    """True when two folder strings name the same location (Windows-insensitive)."""
    a = str(left or "").strip()
    b = str(right or "").strip()
    if not a or not b:
        return False
    try:
        a = os.path.normpath(a)
        b = os.path.normpath(b)
    except (OSError, ValueError):
        pass
    return a.rstrip("\\/").casefold() == b.rstrip("\\/").casefold()


def is_usable_workspace_path(path: str) -> bool:
    """True when ``path`` is safe to mkdir / use as a workspace folder here.

    Rejects empty values and paths under a *different* Windows user profile
    (account-synced leftovers from another machine) without touching the
    filesystem — those always fail with Access Denied and used to spam the
    log on every settings/startup pass.
    """
    normalized = str(path or "").strip()
    if not normalized:
        return False
    if is_foreign_windows_profile_path(normalized):
        return False
    return True


def _log_foreign_path_once(path: str) -> None:
    if path in _logged_foreign_paths:
        return
    _logged_foreign_paths.add(path)
    from shared.services.app_logger import log_warn

    log_warn(
        f"Ignoring workspace path from another Windows user profile "
        f"(will use this machine's default instead): {path}",
        category="workspace",
    )


def ensure_directory(path: str) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return ""
    if is_foreign_windows_profile_path(normalized):
        # Never attempt mkdir under someone else's profile — Windows denies
        # creating anything under C:\\Users\\<other>, and pathlib walks the
        # whole parent chain producing a multi-level PermissionError cascade.
        _known_uncreatable_paths.add(normalized)
        _log_foreign_path_once(normalized)
        return normalized
    if normalized in _known_uncreatable_paths:
        # Already proven uncreatable this session — skip the syscall
        # entirely. apply_workspace_path_defaults() re-derives settings on
        # every Settings-page keystroke (dirty-check diffing), so retrying a
        # real mkdir(parents=True) against a permanently broken path (e.g. a
        # missing Windows profile folder) on every keystroke turned a fast
        # crash into a silent, repeating multi-level failure cascade that
        # froze the UI thread. Caching the negative result makes repeat
        # calls near-free.
        return normalized
    try:
        Path(normalized).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Best-effort only. Seen in the wild when %LOCALAPPDATA% points at a
        # Windows user profile folder that doesn't actually exist yet (or the
        # process can't create new folders directly under C:\Users\ — that
        # requires elevated rights). Every settings/workspace touch used to
        # re-raise this and crash the caller; log once per path and keep
        # going so the rest of the app stays usable even if this folder
        # never gets created (callers that write into it will surface their
        # own, more specific error at that point).
        _known_uncreatable_paths.add(normalized)
        from shared.services.app_logger import log_error

        log_error(f"Could not create directory: {normalized}", category="workspace", exc=exc)
    return normalized


def _keep_saved_device_path(
    key: str,
    existing: str,
    stored_paths: dict[str, str],
    default_path: str,
) -> bool:
    """True when ``existing`` is this PC's saved preference, not a cloud leftover.

    Startup used to replace a Preferences folder with AppData ``Media\\Suno``
    whenever mkdir failed, the drive was missing, or free space was under
    200 MB — then persist that default and wipe the user's choice. Keep the
    saved path instead; warn so the operator can free space / reconnect D:.
    """
    saved = str(stored_paths.get(key) or "").strip()
    if not saved or not existing:
        return False
    if not workspace_paths_equivalent(saved, existing):
        return False
    if workspace_paths_equivalent(saved, default_path):
        return False
    if is_foreign_windows_profile_path(saved):
        return False
    return True


def apply_workspace_path_defaults(settings: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, object]]:
    """Fill empty path settings and create folders.

    Returns (merged_settings, patch_for_api) where patch only contains newly
    applied keys so callers can persist without overwriting user choices.
    """
    from shared.lib.device_workspace_paths import load_device_workspace_paths, overlay_device_paths

    # This machine's stored roots win over account-cloud leftovers.
    current = overlay_device_paths(settings)
    stored_paths = load_device_workspace_paths()
    defaults = default_workspace_paths()
    patch: dict[str, object] = {}

    for key, default_path in defaults.items():
        existing = str(current.get(key) or "").strip()
        if existing and is_usable_workspace_path(existing):
            ensure_directory(existing)
            if Path(existing).is_dir():
                if has_sufficient_free_space(existing):
                    continue
                # A synced path can be a perfectly valid, creatable folder
                # and still be useless — e.g. an account-level path that
                # happened to point at a near-full USB/recovery drive on
                # *this* machine (seen in the wild as "E:\Suno" landing on
                # a Rufus boot stick with a few KB free). mkdir()/is_dir()
                # both succeed there, but every download/export into it
                # silently produces 0-byte files. Self-heal the same as an
                # uncreatable cross-machine path — unless this folder is the
                # user's saved Preferences path on this PC.
                from shared.services.app_logger import log_warn

                if _keep_saved_device_path(key, existing, stored_paths, default_path):
                    log_warn(
                        f"Workspace path has too little free space; keeping saved folder: {existing}",
                        category="workspace",
                    )
                    continue
                log_warn(
                    f"Workspace path has too little free space, switching to local default: {existing}",
                    category="workspace",
                )
            elif _keep_saved_device_path(key, existing, stored_paths, default_path):
                from shared.services.app_logger import log_warn

                log_warn(
                    f"Workspace path is not usable right now; keeping saved folder: {existing}",
                    category="workspace",
                )
                continue
            # Path was creatable in principle but isn't a usable directory
            # here (missing parents, permission, etc.) — fall through and
            # self-heal to this machine's own default.
        elif existing:
            # Account-synced leftover from another Windows profile / machine.
            # Do not call ensure_directory — that would mkdir-walk into
            # Access Denied and spam the log. Heal quietly below.
            _log_foreign_path_once(existing)
        # Empty, foreign, uncreatable, or low-disk: use this machine's default.
        ensure_directory(default_path)
        current[key] = default_path
        patch[key] = default_path

    existing_ffmpeg = str(current.get("ffmpegPath") or "").strip()
    resolved = resolve_ffmpeg_path(existing_ffmpeg)
    if Path(resolved).is_file() and resolved != existing_ffmpeg:
        current["ffmpegPath"] = resolved
        patch["ffmpegPath"] = resolved
    elif not existing_ffmpeg:
        bundled = get_bundled_ffmpeg_path()
        if bundled:
            current["ffmpegPath"] = bundled
            patch["ffmpegPath"] = bundled

    # New installs / unset Speed → Fast. Leave Balanced (etc.) alone if already set.
    existing_speed = str(current.get("videoExportSpeedMode") or "").strip()
    if not existing_speed:
        current["videoExportSpeedMode"] = DEFAULT_EXPORT_SPEED_MODE
        patch["videoExportSpeedMode"] = DEFAULT_EXPORT_SPEED_MODE

    return current, patch


def path_keys() -> tuple[str, ...]:
    return _PATH_KEYS
