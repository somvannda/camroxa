"""Mark a Progress channel row as desktop-pipeline complete on the API."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_latched_session_keys: set[tuple[str, str, str]] = set()


def _row_identity(row: Any) -> tuple[str, str, str]:
    meta = getattr(row, "meta", None)
    batch = str(getattr(meta, "batch_id", "") or "").strip()
    profile = str(getattr(meta, "profile_id", "") or "").strip()
    role = str(getattr(meta, "role", "") or "OK").strip().upper() or "OK"
    return batch, profile, role


def inspection_has_conclusive_merge(row: Any, inspection: Any | None) -> bool:
    """True when a local MERGED long file exists and reel is done or not in the run."""
    if inspection is None:
        return False
    merged_long = tuple(getattr(inspection, "merged_long_paths", ()) or ())
    if not merged_long:
        return False
    merged_reel = tuple(getattr(inspection, "merged_reel_paths", ()) or ())
    if merged_reel:
        return True
    from shared.lib.video_runtime_inspection import run_includes_reel

    return not run_includes_reel(row)


def should_persist_pipeline_complete(row: Any, inspection: Any | None = None) -> bool:
    """True when desktop should latch pipeline_complete on the API."""
    meta = getattr(row, "meta", None)
    if bool(getattr(meta, "pipeline_complete", False)):
        return False
    from shared.lib.video_runtime_inspection import row_is_idle_progress_row

    if row_is_idle_progress_row(row):
        return True
    return inspection_has_conclusive_merge(row, inspection)


def build_pipeline_complete_sync_items(
    rows: list[Any],
    inspections: dict[str, Any] | None = None,
) -> list[Any]:
    """Latch-only sync payloads for rows that just became conclusively complete."""
    from shared.lib.video_runtime_inspection import progress_runtime_key
    from shared.models.platform import ProgressLocalSyncItem

    resolved = inspections or {}
    items: list[Any] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        identity = _row_identity(row)
        batch, profile, role = identity
        if not batch or not profile or identity in seen or identity in _latched_session_keys:
            continue
        key = progress_runtime_key(
            str(getattr(row.meta, "batch_id", "") or ""),
            str(getattr(row.meta, "profile_id", "") or ""),
            str(getattr(row.meta, "role", "") or ""),
        )
        inspection = resolved.get(key)
        if not should_persist_pipeline_complete(row, inspection):
            continue
        seen.add(identity)
        run_dir = str(getattr(row.meta, "run_dir", "") or "").strip() or None
        items.append(
            ProgressLocalSyncItem(
                batch_id=batch,
                profile_id=profile,
                role=role,
                run_dir=run_dir,
                pipeline_complete=True,
            )
        )
    return items


def persist_discovered_pipeline_complete(
    api: Any,
    rows: list[Any],
    inspections: dict[str, Any] | None = None,
) -> int:
    """Push newly discovered complete latches. Failures do not raise."""
    items = build_pipeline_complete_sync_items(rows, inspections)
    if not items:
        return 0
    try:
        api.sync_local_progress(items)
    except Exception:
        logger.warning("Failed to persist discovered pipeline_complete latches", exc_info=True)
        return 0
    for item in items:
        _latched_session_keys.add(
            (
                str(item.batch_id or "").strip(),
                str(item.profile_id or "").strip(),
                str(item.role or "OK").strip().upper() or "OK",
            )
        )
    return len(items)


def clear_pipeline_complete_latch_session() -> None:
    _latched_session_keys.clear()


def mark_desktop_pipeline_complete(
    api: Any,
    *,
    batch_id: str,
    profile_id: str,
    role: str,
    run_dir: str | None = None,
) -> None:
    """Persist conclusive Completed status so moved/archived folders do not reopen work."""
    batch = str(batch_id or "").strip()
    profile = str(profile_id or "").strip()
    channel_role = str(role or "OK").strip().upper() or "OK"
    if not batch or not profile:
        return
    try:
        from shared.models.platform import ProgressLocalSyncItem

        api.sync_local_progress(
            [
                ProgressLocalSyncItem(
                    batch_id=batch,
                    profile_id=profile,
                    role=channel_role,
                    run_dir=str(run_dir or "").strip() or None,
                    pipeline_complete=True,
                )
            ]
        )
        _latched_session_keys.add((batch, profile, channel_role))
    except Exception:
        logger.warning(
            "Failed to mark desktop pipeline complete for batch=%s profile=%s role=%s",
            batch,
            profile,
            channel_role,
            exc_info=True,
        )
