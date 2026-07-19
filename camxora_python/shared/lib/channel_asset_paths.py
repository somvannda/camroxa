"""Local run-folder asset resolution for desktop progress overlays."""

from __future__ import annotations

from pathlib import Path

from shared.services.file_service import sanitize_local_path

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_ASSET_PATH_KEYS = (
    "background_16x9_path",
    "background_9x16_path",
    "thumbnail_16x9_path",
    "thumbnail_9x16_path",
)


def _resolve_named_asset(run_dir: str, stem: str) -> str | None:
    base = Path(sanitize_local_path(run_dir)).expanduser()
    if not base.exists() or not base.is_dir():
        return None

    for suffix in IMAGE_EXTENSIONS:
        candidate = base / f"{stem}{suffix}"
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def _role_stem_suffix(channel_role: str | None) -> str | None:
    normalized = str(channel_role or "").strip().upper()
    if normalized in {"OK", "PRIMARY"}:
        return "ok"
    if normalized in {"ALT", "SECONDARY"}:
        return "alt"
    return None


def resolve_local_channel_asset_paths(
    run_dir: str,
    *,
    channel_role: str | None = None,
) -> dict[str, str | None]:
    normalized = sanitize_local_path(str(run_dir or "").strip())
    if not normalized:
        return {key: None for key in _ASSET_PATH_KEYS}

    role_key = _role_stem_suffix(channel_role)

    def resolve_stem(stem: str) -> str | None:
        if role_key:
            resolved = _resolve_named_asset(normalized, f"{stem}-{role_key}")
            if resolved:
                return resolved
        return _resolve_named_asset(normalized, stem)

    return {
        "background_16x9_path": resolve_stem("background-16x9"),
        "background_9x16_path": resolve_stem("background-9x16"),
        "thumbnail_16x9_path": resolve_stem("thumbnail-16x9"),
        "thumbnail_9x16_path": resolve_stem("thumbnail-9x16"),
    }


def compute_long_ready(asset_paths: dict[str, str | None]) -> bool:
    return bool(asset_paths.get("background_16x9_path") and asset_paths.get("thumbnail_16x9_path"))


def compute_reel_ready(asset_paths: dict[str, str | None]) -> bool:
    return bool(asset_paths.get("background_9x16_path") and asset_paths.get("thumbnail_9x16_path"))


def count_channel_mp3_files(run_dir: str, role: str) -> int:
    directory = Path(sanitize_local_path(str(run_dir or "").strip())).expanduser()
    if not directory.is_dir():
        return 0

    suffix = "_OK.mp3" if str(role or "").strip().upper() == "OK" else "_Alt.mp3"
    count = 0
    try:
        for child in directory.iterdir():
            if child.is_file() and child.name.lower().endswith(suffix.lower()):
                count += 1
    except OSError:
        return 0
    return count
