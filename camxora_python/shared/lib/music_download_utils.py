"""Shared helpers for Suno MP3 download queue presentation."""

from __future__ import annotations

from shared.models.platform import PendingMusicDownloadItem


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
