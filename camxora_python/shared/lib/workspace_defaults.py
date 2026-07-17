"""First-run defaults for local media folders and FFmpeg path.

Users can still change any path in Settings. Empty values are filled once and
directories are created automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.lib.app_paths import get_user_data_dir
from shared.lib.ffmpeg_paths import get_bundled_ffmpeg_path, resolve_ffmpeg_path


_PATH_KEYS = (
    "ffmpegPath",
    "downloadsDir",
    "sunoOutputDir",
    "mergedDir",
    "imageBackgroundSamplesDir",
    "imageThumbnailSamplesDir",
    "imageOutputDir",
)


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


def ensure_directory(path: str) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return ""
    Path(normalized).mkdir(parents=True, exist_ok=True)
    return normalized


def apply_workspace_path_defaults(settings: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, object]]:
    """Fill empty path settings and create folders.

    Returns (merged_settings, patch_for_api) where patch only contains newly
    applied keys so callers can persist without overwriting user choices.
    """
    current = dict(settings or {})
    defaults = default_workspace_paths()
    patch: dict[str, object] = {}

    for key, default_path in defaults.items():
        existing = str(current.get(key) or "").strip()
        if existing:
            ensure_directory(existing)
            continue
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

    return current, patch


def path_keys() -> tuple[str, ...]:
    return _PATH_KEYS
