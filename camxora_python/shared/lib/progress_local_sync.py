"""Detect when desktop local truth is ahead of API metadata and build sync payloads."""

from __future__ import annotations

from dataclasses import dataclass

from shared.lib.channel_asset_paths import (
    compute_long_ready,
    compute_reel_ready,
    count_channel_mp3_files,
    resolve_local_channel_asset_paths,
)
from shared.lib.mp3_naming import mp3_channel_label, mp3_naming_hint
from shared.models.platform import ProgressRow
from shared.services.file_service import sanitize_local_path


@dataclass(frozen=True, slots=True)
class LocalProgressSyncItem:
    batch_id: str
    profile_id: str
    role: str
    run_dir: str
    long_ready: bool
    reel_ready: bool
    local_mp3_count: int
    expected: int
    background_16x9_path: str | None = None
    background_9x16_path: str | None = None
    thumbnail_16x9_path: str | None = None
    thumbnail_9x16_path: str | None = None


def _needs_channel_asset_sync(row: ProgressRow, assets: dict[str, str | None]) -> bool:
    meta = row.meta
    long_ready = compute_long_ready(assets)
    reel_ready = compute_reel_ready(assets)
    if long_ready != bool(meta.long_ready):
        return True
    if reel_ready != bool(meta.reel_ready):
        return True
    for key in (
        "background_16x9_path",
        "background_9x16_path",
        "thumbnail_16x9_path",
        "thumbnail_9x16_path",
    ):
        local_path = str(assets.get(key) or "").strip()
        api_path = str(getattr(meta, key) or "").strip()
        if local_path and local_path != api_path:
            return True
    return False


def build_local_progress_sync_items(rows: list[ProgressRow]) -> list[LocalProgressSyncItem]:
    """Return rows whose local run-folder state should be pushed back to the API."""
    items: list[LocalProgressSyncItem] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        meta = row.meta
        batch_id = str(meta.batch_id or "").strip()
        profile_id = str(meta.profile_id or "").strip()
        role = str(meta.role or "").strip().upper() or "OK"
        run_dir = sanitize_local_path(str(meta.run_dir or "").strip())
        if not batch_id or not profile_id or not run_dir:
            continue
        key = (batch_id, profile_id, role)
        if key in seen:
            continue

        assets = resolve_local_channel_asset_paths(run_dir, channel_role=meta.role)
        long_ready = compute_long_ready(assets)
        reel_ready = compute_reel_ready(assets)
        local_mp3_count = count_channel_mp3_files(run_dir, meta.role)
        expected = max(1, int(meta.expected or 0))
        api_saved = max(0, int(meta.saved or 0))
        needs_assets = _needs_channel_asset_sync(row, assets)
        needs_music = local_mp3_count >= expected and local_mp3_count > api_saved
        if not needs_assets and not needs_music and not (long_ready or reel_ready):
            continue

        seen.add(key)
        items.append(
            LocalProgressSyncItem(
                batch_id=batch_id,
                profile_id=profile_id,
                role=role,
                run_dir=run_dir,
                long_ready=long_ready,
                reel_ready=reel_ready,
                local_mp3_count=local_mp3_count,
                expected=expected,
                background_16x9_path=assets.get("background_16x9_path"),
                background_9x16_path=assets.get("background_9x16_path"),
                thumbnail_16x9_path=assets.get("thumbnail_16x9_path"),
                thumbnail_9x16_path=assets.get("thumbnail_9x16_path"),
            )
        )
    return items


def local_mp3_files_ready(row: ProgressRow) -> bool:
    """True when the run folder contains enough role-scoped MP3 files."""
    meta = row.meta
    run_dir = sanitize_local_path(str(meta.run_dir or "").strip())
    if not run_dir:
        return False
    expected = max(1, int(meta.expected or 0))
    return count_channel_mp3_files(run_dir, meta.role) >= expected
