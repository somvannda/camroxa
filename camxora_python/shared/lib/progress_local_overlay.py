"""Apply desktop filesystem truth to API progress rows.

When the local run folder is scannable, Music ``saved`` / Progress % use landed
role MP3 files — not API ``downloaded_ok`` / ``downloaded_alt`` flags (those can
flip before files exist, or stay true after files are deleted).

Missing/moved run folders must not rewind a finished terminal pipeline
(Done / YouTube / Completed / pipeline_complete).
"""

from __future__ import annotations

from pathlib import Path

from shared.lib.channel_asset_paths import (
    compute_long_ready,
    compute_reel_ready,
    count_channel_mp3_files,
    resolve_local_channel_asset_paths,
)
from shared.lib.progress_presentation import format_images_compact, format_music_compact
from shared.lib.video_runtime_inspection import STATUS_IN_PROGRESS, STATUS_PENDING, row_skip_disk_scan
from shared.models.platform import ProgressRow, ProgressRowMeta
from shared.services.file_service import sanitize_local_path

_TERMINAL_STAGES = frozenset({"youtube", "done", "completed", "error"})
_POST_MUSIC_STAGES = frozenset(
    {"image", "converter", "export", "merger", "merge", "youtube", "done", "completed", "error"}
)
_ARCHIVED_NOTE = (
    "Local run folder is missing or incomplete (moved/archived). "
    "Pipeline status is unchanged — files will not be regenerated automatically."
)


def _stage_key(stage: str) -> str:
    return str(stage or "").strip().lower()


def _api_music_complete(meta: ProgressRowMeta) -> bool:
    expected = max(1, int(meta.expected or 0))
    return (
        int(meta.saved or 0) >= expected
        and int(meta.download_ready or 0) >= expected
        and int(meta.download_pending or 0) <= 0
    )


def _run_dir_missing(run_dir: str) -> bool:
    if not run_dir:
        return True
    try:
        return not Path(run_dir).is_dir()
    except OSError:
        return True


def _image_status_label(*, ready: int, total: int, api_status: str, files_present: bool) -> str:
    if total <= 0:
        return str(api_status or "PENDING").upper()
    if ready >= total and not files_present:
        api = str(api_status or "").strip().upper()
        if api in {"READY", "SUCCESS", "DONE", "COMPLETE", "ARCHIVED"}:
            return "READY"
        return "ARCHIVED"
    if ready >= total:
        return "READY"
    return str(api_status or "PENDING").upper()


def _apply_local_music_truth(
    row: ProgressRow,
    *,
    local_saved: int,
    folder_scannable: bool,
    preserve_music: bool,
) -> ProgressRow:
    """When the run folder can be scanned, ``saved`` is always disk MP3 count."""
    meta = row.meta
    expected = max(1, int(meta.expected or 0))
    # Retries can leave extra role MP3s on disk; never let the Music counter
    # exceed the batch's song count (e.g. 16/15).
    local_saved = min(max(0, int(local_saved or 0)), expected)

    if preserve_music or not folder_scannable:
        return row

    download_ready = max(0, int(meta.download_ready or 0))
    download_pending = max(0, download_ready - local_saved)
    meta = meta.model_copy(
        update={
            "saved": local_saved,
            "download_pending": download_pending,
        }
    )
    music = f"{local_saved}/{expected}"
    if download_pending > 0:
        music = f"{music} ↓"
    elif local_saved >= expected:
        music = f"{music} ✓"
    return row.model_copy(update={"meta": meta, "music": music})


def _with_archived_note(row: ProgressRow) -> ProgressRow:
    notes = str(row.notes or "").strip()
    if _ARCHIVED_NOTE in notes:
        return row
    archived = f"{notes} {_ARCHIVED_NOTE}".strip() if notes else _ARCHIVED_NOTE
    return row.model_copy(update={"notes": archived})


def _apply_local_stage_truth(
    row: ProgressRow,
    *,
    assets_ready: bool,
    music_ready: bool,
    preserve_stage: bool,
) -> ProgressRow:
    stage = str(row.stage or "").strip()
    status = str(row.status or "").strip()
    notes = str(row.notes or "").strip()
    stage_key = _stage_key(stage)

    if stage_key in _TERMINAL_STAGES:
        return row

    if preserve_stage:
        if not music_ready or not assets_ready:
            return _with_archived_note(row)
        # Locals present again — keep stage, allow normal promotion below.

    if not music_ready:
        return row.model_copy(
            update={
                "stage": "Music",
                "status": "Downloading" if row.meta.download_pending > 0 else "Preparing",
                "notes": "Waiting for desktop MP3 downloads before downstream video work can begin.",
            }
        )

    if stage_key in {"converter", "export", "merger", "merge"} and not assets_ready:
        return row.model_copy(
            update={
                "stage": "Image",
                "status": STATUS_IN_PROGRESS,
                "notes": "Background image is not present locally yet (needed before video export).",
                "converter": "Not started · waiting for background image",
                "merge": "—",
            }
        )

    converter_lower = str(row.converter or "").strip().lower()
    waiting_for_assets = "waiting for image assets" in converter_lower
    if assets_ready and (stage_key == "image" or waiting_for_assets):
        if stage_key in _TERMINAL_STAGES:
            return row
        return row.model_copy(
            update={
                "stage": "Export",
                "status": STATUS_PENDING
                if status in {"", "Rendering", STATUS_IN_PROGRESS, "Queued", "Waiting"}
                else status,
                "notes": notes or "Background is ready locally; waiting for video export.",
                "converter": "Pending · no exports yet",
            }
        )

    if stage_key == "converter":
        normalized_status = (
            STATUS_PENDING
            if status in {"", "Rendering", STATUS_IN_PROGRESS, "Queued", "Waiting"}
            else status
        )
        return row.model_copy(update={"stage": "Export", "status": normalized_status})
    if stage_key == "merger":
        return row.model_copy(update={"stage": "Merge"})

    return row


def apply_local_progress_overlays(rows: list[ProgressRow]) -> list[ProgressRow]:
    from shared.lib.device_workspace_paths import local_run_dir_for_disk

    patched: list[ProgressRow] = []
    for row in rows:
        # API may still advertise another PC's absolute AppData/drive path.
        # Desktop owns the drop root: always resolve under this machine's Suno folder.
        raw_run_dir = sanitize_local_path(str(row.meta.run_dir or "").strip())
        run_dir = local_run_dir_for_disk(raw_run_dir) if raw_run_dir else ""
        folder_missing = _run_dir_missing(run_dir)
        idle_row = row_skip_disk_scan(row)
        folder_scannable = bool(run_dir) and not folder_missing and not idle_row
        pipeline_complete = bool(getattr(row.meta, "pipeline_complete", False))
        stage_key = _stage_key(row.stage)
        api_music_done = _api_music_complete(row.meta)
        expected = max(1, int(row.meta.expected or 0))

        # Only skip rewriting Music counters when we cannot scan (archived folder)
        # or the row is terminal / explicitly pipeline-complete.
        # Do NOT preserve based on API downloaded_* alone — those can be premature.
        preserve_music = pipeline_complete or stage_key in _TERMINAL_STAGES or folder_missing

        assets = (
            resolve_local_channel_asset_paths(run_dir, channel_role=row.meta.role)
            if folder_scannable
            else {
                "background_16x9_path": None,
                "background_9x16_path": None,
                "thumbnail_16x9_path": None,
                "thumbnail_9x16_path": None,
            }
        )
        local_long_ready = compute_long_ready(assets)
        local_reel_ready = compute_reel_ready(assets)
        long_ready = local_long_ready or bool(row.meta.long_ready)
        reel_ready = local_reel_ready or bool(row.meta.reel_ready)
        assets_ready = long_ready or reel_ready
        local_saved = count_channel_mp3_files(run_dir, row.meta.role) if folder_scannable else 0
        local_music_complete = (not folder_scannable) or local_saved >= expected

        # Keep post-music stages only when local MP3s are actually present (or folder gone).
        preserve_stage = (
            pipeline_complete
            or stage_key in _TERMINAL_STAGES
            or (folder_missing and api_music_done)
            or (
                stage_key in _POST_MUSIC_STAGES
                and local_music_complete
                and (bool(row.meta.long_ready) or bool(row.meta.reel_ready) or pipeline_complete)
            )
        )

        bg_status = _image_status_label(
            ready=row.meta.bg_ready,
            total=row.meta.bg_total,
            api_status=row.meta.bg_status,
            files_present=bool(assets.get("background_16x9_path") or assets.get("background_9x16_path")),
        )
        th_status = _image_status_label(
            ready=row.meta.th_ready,
            total=row.meta.th_total,
            api_status=row.meta.th_status,
            files_present=bool(assets.get("thumbnail_16x9_path") or assets.get("thumbnail_9x16_path")),
        )

        meta = row.meta.model_copy(
            update={
                "run_dir": run_dir or row.meta.run_dir,
                "background_16x9_path": assets["background_16x9_path"] or row.meta.background_16x9_path,
                "background_9x16_path": assets["background_9x16_path"] or row.meta.background_9x16_path,
                "thumbnail_16x9_path": assets["thumbnail_16x9_path"] or row.meta.thumbnail_16x9_path,
                "thumbnail_9x16_path": assets["thumbnail_9x16_path"] or row.meta.thumbnail_9x16_path,
                "long_ready": long_ready,
                "reel_ready": reel_ready,
                "bg_status": bg_status,
                "th_status": th_status,
            }
        )
        updated = row.model_copy(
            update={
                "meta": meta,
                "image": format_images_compact(meta),
            }
        )
        updated = _apply_local_music_truth(
            updated,
            local_saved=local_saved,
            folder_scannable=folder_scannable,
            preserve_music=preserve_music,
        )
        # Disk is authority when the folder exists; API flags only when it does not.
        if folder_scannable:
            music_ready = local_saved >= expected
        else:
            music_ready = _api_music_complete(updated.meta)
        updated = _apply_local_stage_truth(
            updated,
            assets_ready=assets_ready,
            music_ready=music_ready,
            preserve_stage=preserve_stage,
        )
        updated = updated.model_copy(update={"music": format_music_compact(updated)})
        patched.append(updated)
    return patched
