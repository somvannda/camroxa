"""Shared helpers for resolving and validating per-channel run-dir assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_api.models.domain import BatchChannelAssets
from platform_api.models.enums import ChannelRole
from platform_api.services.client_path_utils import denormalize_cross_platform_path

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_ASSET_PATH_KEYS = (
    "background_16x9_path",
    "background_9x16_path",
    "thumbnail_16x9_path",
    "thumbnail_9x16_path",
)


def normalize_client_path(path: str | None) -> str:
    return denormalize_cross_platform_path(str(path or "").strip())


def client_path_is_file(path: str | None) -> bool:
    normalized = normalize_client_path(path)
    if not normalized:
        return False
    candidate = Path(normalized).expanduser()
    return candidate.is_file()


def _resolve_named_asset(run_dir: str, stem: str) -> str | None:
    base = Path(normalize_client_path(run_dir)).expanduser()
    if not base.exists() or not base.is_dir():
        return None

    for suffix in IMAGE_EXTENSIONS:
        candidate = base / f"{stem}{suffix}"
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())
    return None


def _role_stem_suffix(channel_role: ChannelRole | None) -> str | None:
    if channel_role is None:
        return None
    return "ok" if channel_role == ChannelRole.OK else "alt"


def resolve_channel_asset_paths(
    run_dir: str,
    *,
    channel_role: ChannelRole | None = None,
    role_disambiguate: bool = False,
) -> dict[str, str | None]:
    normalized = normalize_client_path(run_dir)
    role_key = _role_stem_suffix(channel_role) if role_disambiguate else None

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
    """True when the long-video background exists (thumbnail is YouTube-only)."""
    return bool(asset_paths.get("background_16x9_path"))


def compute_reel_ready(asset_paths: dict[str, str | None]) -> bool:
    """True when the reel background exists (thumbnail is YouTube-only)."""
    return bool(asset_paths.get("background_9x16_path"))


def compute_youtube_long_ready(asset_paths: dict[str, str | None]) -> bool:
    """True when long upload assets are complete (background + thumbnail)."""
    return bool(asset_paths.get("background_16x9_path") and asset_paths.get("thumbnail_16x9_path"))


def compute_youtube_reel_ready(asset_paths: dict[str, str | None]) -> bool:
    """True when reel upload assets are complete (background + thumbnail)."""
    return bool(asset_paths.get("background_9x16_path") and asset_paths.get("thumbnail_9x16_path"))


def merge_channel_asset_paths(
    run_dir: str,
    persisted: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    """Prefer live run-dir scans; only keep persisted paths that still exist on disk."""
    live_assets = resolve_channel_asset_paths(run_dir)
    persisted_assets = persisted or {}
    merged: dict[str, str | None] = {}
    for key in _ASSET_PATH_KEYS:
        live_path = live_assets.get(key)
        if live_path:
            merged[key] = live_path
            continue
        persisted_path = normalize_client_path(str(persisted_assets.get(key) or "").strip() or None)
        merged[key] = persisted_path if persisted_path and client_path_is_file(persisted_path) else None
    return merged


def build_batch_channel_assets(
    *,
    batch_id,
    user_id,
    profile_id,
    role: ChannelRole,
    run_dir: str,
    source_mode: str,
    role_disambiguate: bool = False,
) -> BatchChannelAssets:
    asset_paths = resolve_channel_asset_paths(
        run_dir,
        channel_role=role,
        role_disambiguate=role_disambiguate,
    )
    return BatchChannelAssets(
        batch_id=batch_id,
        user_id=user_id,
        profile_id=profile_id,
        role=role,
        run_dir=str(run_dir or "").strip() or None,
        source_mode=str(source_mode or "").strip().lower() or "manual",
        background_16x9_path=asset_paths["background_16x9_path"],
        background_9x16_path=asset_paths["background_9x16_path"],
        thumbnail_16x9_path=asset_paths["thumbnail_16x9_path"],
        thumbnail_9x16_path=asset_paths["thumbnail_9x16_path"],
    )
