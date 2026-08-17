"""Detect and filter missing role-scoped MP3s for Progress recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.lib.channel_asset_paths import count_channel_mp3_files
from shared.lib.device_workspace_paths import local_run_dir_for_disk
from shared.lib.suno_mp3_download import file_looks_like_mpeg_audio
from shared.models.platform import ProgressRow
from shared.services.file_service import sanitize_local_path


def resolve_row_local_run_dir(row: ProgressRow, *, local_suno_base: str | None = None) -> str:
    """Local absolute run folder for this Progress row (app-owned drop path)."""
    raw = sanitize_local_path(str(row.meta.run_dir or "").strip())
    if not raw:
        return ""
    return local_run_dir_for_disk(raw, local_suno_base=local_suno_base)


def count_missing_role_mp3s_from_meta(row: ProgressRow) -> int:
    """UI-safe missing count from overlay counters — no disk I/O."""
    meta = row.meta
    expected = max(0, int(meta.expected or 0))
    url_ready = max(0, int(meta.download_ready or 0))
    saved = max(0, int(meta.saved or 0))
    ceiling = max(expected, url_ready)
    if ceiling <= 0:
        return 0
    missing = max(0, ceiling - saved)
    if missing <= 0:
        return 0
    if url_ready <= 0 and saved <= 0:
        return 0
    return missing


def count_missing_role_mp3s(row: ProgressRow, *, local_suno_base: str | None = None) -> int:
    """How many role MP3s are still missing on disk for this Progress row.

    Disk count is authority. Compare against the larger of:
    - ``download_ready`` (Suno Alt/OK URLs known to the API), and
    - ``expected`` (album song count)

    so a 9/10 disk gap still surfaces the menu when API URL counts lag (or one
    track is only on Backblaze). The download worker no-ops when the plan has
    nothing fetchable; Retry Failed Suno covers true generation gaps.
    """
    meta = row.meta
    expected = max(0, int(meta.expected or 0))
    url_ready = max(0, int(meta.download_ready or 0))
    ceiling = max(expected, url_ready)
    if ceiling <= 0:
        return 0

    run_dir = resolve_row_local_run_dir(row, local_suno_base=local_suno_base)
    if not run_dir:
        return ceiling
    try:
        if not Path(run_dir).is_dir():
            return ceiling
    except OSError:
        return ceiling

    local_count = count_channel_mp3_files(run_dir, meta.role)
    missing = max(0, ceiling - local_count)
    if missing <= 0:
        return 0
    # Avoid advertising downloads before any audio exists for the batch/role.
    if url_ready <= 0 and local_count <= 0:
        return 0
    return missing


def target_path_is_present(target_path: str) -> bool:
    text = sanitize_local_path(str(target_path or "").strip())
    if not text:
        return False
    try:
        return file_looks_like_mpeg_audio(text)
    except OSError:
        return False


def filter_missing_redownload_items(items: list[Any]) -> list[Any]:
    """Keep plan items whose local ``target_path`` is missing or empty."""
    missing: list[Any] = []
    for item in items:
        target = str(getattr(item, "target_path", "") or "").strip()
        if target_path_is_present(target):
            continue
        missing.append(item)
    return missing
