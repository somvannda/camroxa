"""Detect and filter missing role-scoped MP3s for Progress recovery."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class AutoMissingMp3Target:
    """One Progress row/channel whose role MP3s are missing on this device."""

    batch_id: str
    profile_id: str
    role: str
    run_dir: str
    missing_n: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.batch_id, self.profile_id, self.role)


def pick_auto_missing_mp3_target(
    rows: Sequence[ProgressRow],
    *,
    attempted_at: Mapping[tuple[str, str, str], float],
    now: float,
    cooldown_s: float,
    local_suno_base: str | None = None,
    missing_counter: Callable[[ProgressRow], int] | None = None,
) -> AutoMissingMp3Target | None:
    """First row whose role MP3s are missing on disk and not recently attempted.

    The account-wide pending-download sync is driven by *server* flags
    (``downloaded_ok`` / ``pipeline_complete``), so a track the server already
    recorded as downloaded — but whose file is missing on this PC (deleted,
    moved, or pulled on another device) — is invisible to it. This selects such
    a row so the client can re-fetch it through the same batch-redownload path
    the Progress right-click action uses.

    Pure and side-effect free: ``missing_counter`` is injectable for tests.
    """
    counter = missing_counter or (
        lambda row: count_missing_role_mp3s(row, local_suno_base=local_suno_base)
    )
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, ProgressRow):
            continue
        meta = row.meta
        batch_id = str(meta.batch_id or "").strip()
        profile_id = str(meta.profile_id or "").strip()
        role = str(meta.role or "").strip().upper() or "OK"
        if not batch_id or not profile_id:
            continue
        key = (batch_id, profile_id, role)
        if key in seen:
            continue
        seen.add(key)
        last = attempted_at.get(key)
        if last is not None and (now - float(last)) < float(cooldown_s):
            continue
        missing_n = int(counter(row) or 0)
        if missing_n <= 0:
            continue
        run_dir = resolve_row_local_run_dir(row, local_suno_base=local_suno_base)
        if not run_dir:
            continue
        return AutoMissingMp3Target(
            batch_id=batch_id,
            profile_id=profile_id,
            role=role,
            run_dir=run_dir,
            missing_n=missing_n,
        )
    return None
