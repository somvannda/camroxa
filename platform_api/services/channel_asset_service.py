"""Shared helpers for resolving and validating per-channel run-dir assets."""

from __future__ import annotations

from pathlib import Path

from platform_api.models.domain import BatchChannelAssets
from platform_api.models.enums import ChannelRole

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _resolve_named_asset(run_dir: str, stem: str) -> str | None:
    base = Path(str(run_dir or "").strip()).expanduser()
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
    normalized = str(run_dir or "").strip()
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
    return bool(asset_paths.get("background_16x9_path") and asset_paths.get("thumbnail_16x9_path"))


def compute_reel_ready(asset_paths: dict[str, str | None]) -> bool:
    return bool(asset_paths.get("background_9x16_path") and asset_paths.get("thumbnail_9x16_path"))


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
