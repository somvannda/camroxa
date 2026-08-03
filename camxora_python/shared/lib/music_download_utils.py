"""Shared helpers for Suno MP3 download queue presentation."""

from __future__ import annotations

from shared.lib.device_workspace_paths import (
    remap_suno_download_paths,
    resolve_local_suno_output_dir,
)
from shared.models.platform import PendingMusicDownloadItem, PendingMusicDownloadTarget


def pending_download_is_actionable(item: PendingMusicDownloadItem) -> bool:
    for target in (item.primary, item.secondary):
        if target.downloaded:
            continue
        if str(target.download_url or "").strip() and str(target.target_path or "").strip():
            return True
    return False


def filter_actionable_pending_downloads(
    items: list[PendingMusicDownloadItem],
) -> list[PendingMusicDownloadItem]:
    return [item for item in items if pending_download_is_actionable(item)]


def remap_pending_download_target(
    target: PendingMusicDownloadTarget,
    *,
    local_suno_base: str | None = None,
) -> PendingMusicDownloadTarget:
    """Rebase one pending channel target onto this machine's Suno root."""
    base = str(local_suno_base or "").strip() or resolve_local_suno_output_dir()
    output_dir = str(target.output_dir or "").strip()
    target_path = str(target.target_path or "").strip()
    if not output_dir or not base:
        return target
    new_out, new_path = remap_suno_download_paths(output_dir, target_path, base)
    if new_out == output_dir and new_path == target_path:
        return target
    return target.model_copy(update={"output_dir": new_out, "target_path": new_path or target_path})