"""Apply desktop filesystem truth to API progress rows."""

from __future__ import annotations

from shared.lib.channel_asset_paths import (
    compute_long_ready,
    compute_reel_ready,
    count_channel_mp3_files,
    resolve_local_channel_asset_paths,
)
from shared.lib.progress_presentation import format_images_compact, format_music_compact
from shared.lib.video_runtime_inspection import STATUS_IN_PROGRESS, STATUS_PENDING
from shared.models.platform import ProgressRow
from shared.services.file_service import sanitize_local_path


def _image_status_label(*, ready: int, total: int, api_status: str, files_present: bool) -> str:
    if total <= 0:
        return str(api_status or "PENDING").upper()
    if ready >= total and not files_present:
        return "SYNC"
    if ready >= total:
        return "READY"
    return str(api_status or "PENDING").upper()


def _music_downloads_ready(row: ProgressRow) -> bool:
    meta = row.meta
    expected = max(1, int(meta.expected or 0))
    return (
        int(meta.saved or 0) >= expected
        and int(meta.download_ready or 0) >= expected
        and int(meta.download_pending or 0) <= 0
    )


def _apply_local_music_truth(row: ProgressRow, *, local_saved: int) -> ProgressRow:
    meta = row.meta
    expected = max(1, int(meta.expected or 0))
    api_saved = max(0, int(meta.saved or 0))
    local_saved = max(0, int(local_saved or 0))
    if local_saved >= api_saved:
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


def _apply_local_stage_truth(row: ProgressRow, *, assets_ready: bool, music_ready: bool) -> ProgressRow:
    stage = str(row.stage or "").strip()
    status = str(row.status or "").strip()
    notes = str(row.notes or "").strip()
    stage_key = stage.lower()

    if stage_key in {"youtube", "done", "error"}:
        return row

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
                "notes": "Background/thumbnail files are not present locally yet.",
                "converter": "Not started · waiting for image assets",
                "merge": "—",
            }
        )

    converter_lower = str(row.converter or "").strip().lower()
    waiting_for_assets = "waiting for image assets" in converter_lower
    if assets_ready and (stage_key == "image" or waiting_for_assets):
        if stage_key in {"youtube", "done"}:
            return row
        return row.model_copy(
            update={
                "stage": "Export",
                "status": STATUS_PENDING if status in {"", "Rendering", STATUS_IN_PROGRESS} else status,
                "notes": notes or "Image assets are ready locally; waiting for video export.",
                "converter": "Pending · no exports yet",
            }
        )

    if stage_key == "converter":
        return row.model_copy(update={"stage": "Export"})
    if stage_key == "merger":
        return row.model_copy(update={"stage": "Merge"})

    return row


def apply_local_progress_overlays(rows: list[ProgressRow]) -> list[ProgressRow]:
    patched: list[ProgressRow] = []
    for row in rows:
        run_dir = sanitize_local_path(str(row.meta.run_dir or "").strip())
        assets = resolve_local_channel_asset_paths(run_dir, channel_role=row.meta.role) if run_dir else {
            "background_16x9_path": None,
            "background_9x16_path": None,
            "thumbnail_16x9_path": None,
            "thumbnail_9x16_path": None,
        }
        long_ready = compute_long_ready(assets)
        reel_ready = compute_reel_ready(assets)
        assets_ready = long_ready or reel_ready
        local_saved = count_channel_mp3_files(run_dir, row.meta.role) if run_dir else 0

        bg_files_present = bool(assets.get("background_16x9_path") or assets.get("background_9x16_path"))
        th_files_present = bool(assets.get("thumbnail_16x9_path") or assets.get("thumbnail_9x16_path"))
        bg_status = _image_status_label(
            ready=row.meta.bg_ready,
            total=row.meta.bg_total,
            api_status=row.meta.bg_status,
            files_present=bg_files_present,
        )
        th_status = _image_status_label(
            ready=row.meta.th_ready,
            total=row.meta.th_total,
            api_status=row.meta.th_status,
            files_present=th_files_present,
        )

        meta = row.meta.model_copy(
            update={
                "run_dir": run_dir or row.meta.run_dir,
                "background_16x9_path": assets["background_16x9_path"],
                "background_9x16_path": assets["background_9x16_path"],
                "thumbnail_16x9_path": assets["thumbnail_16x9_path"],
                "thumbnail_9x16_path": assets["thumbnail_9x16_path"],
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
        updated = _apply_local_music_truth(updated, local_saved=local_saved)
        expected = max(1, int(updated.meta.expected or 0))
        music_ready = _music_downloads_ready(updated) and (
            not run_dir or local_saved >= expected
        )
        updated = _apply_local_stage_truth(updated, assets_ready=assets_ready, music_ready=music_ready)
        updated = updated.model_copy(update={"music": format_music_compact(updated)})
        patched.append(updated)
    return patched
