"""Progress/workflow aggregate endpoint for authenticated users."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.schemas import ProgressListResponse, ProgressRow, ProgressRowMeta
from platform_api.services.batch_service import BatchService
from platform_api.services.channel_asset_service import (
    compute_long_ready,
    compute_reel_ready,
    merge_channel_asset_paths,
)
from platform_api.services.run_directory_planner import resolve_channel_run_dir
from platform_api.services.video_run_inspection import (
    build_video_run_presentation,
    inspect_video_run_directory,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["progress"])


async def _get_batch_service() -> BatchService:
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )


BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(timezone.utc).strftime("%H:%M:%S UTC")


def _coerce_date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    return None


def _batch_run_from_date(batch: dict[str, Any]) -> date:
    planned = _coerce_date_value(batch.get("planned_from_date"))
    if planned is not None:
        return planned
    created = batch.get("created_at")
    if isinstance(created, datetime):
        return created.astimezone(timezone.utc).date()
    return _utc_now().date()


def _batch_run_to_date(batch: dict[str, Any]) -> date:
    planned = _coerce_date_value(batch.get("planned_to_date"))
    if planned is not None:
        return planned
    return _batch_run_from_date(batch)


def _format_batch_run_date(batch: dict[str, Any]) -> str:
    run_from = _batch_run_from_date(batch)
    run_to = _batch_run_to_date(batch)
    if run_from == run_to:
        return run_from.strftime("%Y-%m-%d")
    return f"{run_from.strftime('%Y-%m-%d')} → {run_to.strftime('%Y-%m-%d')}"


def _batch_run_end_expr(*, use_planned_dates: bool) -> str:
    if use_planned_dates:
        return (
            "COALESCE(b.planned_to_date, b.planned_from_date, "
            "(b.created_at AT TIME ZONE 'UTC')::date)"
        )
    return "(b.created_at AT TIME ZONE 'UTC')::date"


def _batch_run_start_expr(*, use_planned_dates: bool) -> str:
    if use_planned_dates:
        return "COALESCE(b.planned_from_date, (b.created_at AT TIME ZONE 'UTC')::date)"
    return "(b.created_at AT TIME ZONE 'UTC')::date"


def _is_schema_drift_error(error: Exception) -> bool:
    message = str(error).lower()
    return "does not exist" in message and (
        "planned_from_date" in message or "planned_to_date" in message
    )


def _coerce_uuid_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return [str(value)]


def _is_terminal_progress_stage(stage: str) -> bool:
    normalized = str(stage or "").strip().lower()
    return normalized in {"youtube", "done", "completed", "error"}


def _normalize_image_state(group: dict[str, Any]) -> str:
    total = int(group.get("total", 0) or 0)
    ready = int(group.get("ready", 0) or 0)
    failed = int(group.get("failed", 0) or 0)
    latest = str(group.get("latest_status", "") or "").upper()

    if total > 0 and ready >= total:
        return "READY"
    if failed > 0:
        return "FAILED"
    if latest in {"PENDING", "RUNNING", "PROCESSING"}:
        return "PENDING"
    return "PENDING"


def _batch_album_for_role(batch: dict[str, Any], role: str) -> str | None:
    role_key = str(role or "").strip().upper()
    if role_key == "ALT":
        # Never fall back to Primary album — empty Secondary must stay empty/distinct.
        album = batch.get("alt_album")
    else:
        album = batch.get("ok_album") or batch.get("album")
    text = str(album or "").strip()
    return text or None


def _build_row(
    *,
    batch: dict[str, Any],
    role: str,
    profile_id: str,
    profile_name: str,
    song_stats: dict[str, Any],
    suno_stats: dict[str, Any],
    image_groups: dict[tuple[str, str, str], dict[str, Any]],
    channel_assets: dict[tuple[str, str, str], dict[str, Any]],
    youtube_groups: dict[tuple[str, str, str], dict[str, Any]],
    youtube_batch_groups: dict[str, dict[str, Any]],
) -> ProgressRow:
    batch_id = str(batch["id"])
    key = (batch_id, profile_id, role)
    image_group = image_groups.get(key, {})
    bg_group = image_group.get("background", {})
    th_group = image_group.get("thumbnail", {})
    bg_ready = int(bg_group.get("ready", 0) or 0)
    bg_total = int(bg_group.get("total", 0) or 0)
    th_ready = int(th_group.get("ready", 0) or 0)
    th_total = int(th_group.get("total", 0) or 0)
    bg_status = _normalize_image_state(bg_group)
    th_status = _normalize_image_state(th_group)
    asset_group = channel_assets.get(key, {})
    background_16x9_path = asset_group.get("background_16x9_path")
    background_9x16_path = asset_group.get("background_9x16_path")
    thumbnail_16x9_path = asset_group.get("thumbnail_16x9_path")
    thumbnail_9x16_path = asset_group.get("thumbnail_9x16_path")
    long_ready = bool(asset_group.get("long_ready", False))
    reel_ready = bool(asset_group.get("reel_ready", False))
    source_mode = asset_group.get("source_mode")
    resolved_run_dir = resolve_channel_run_dir(
        role=role,
        ok_run_dir=str(batch.get("ok_run_dir") or ""),
        alt_run_dir=str(batch.get("alt_run_dir") or ""),
        alt_profile_folder=str(batch.get("alt_profile_folder") or ""),
        alt_profile_name=str(batch.get("alt_profile_name") or ""),
    )
    persisted_run_dir = str(asset_group.get("run_dir") or "").strip() or None
    row_run_dir = persisted_run_dir or resolved_run_dir

    expected = int(batch.get("song_count", 0) or 0)
    saved = int(suno_stats.get("downloaded_ok" if role == "OK" else "downloaded_alt", 0) or 0)
    download_ready = int(suno_stats.get("ready_ok" if role == "OK" else "ready_alt", 0) or 0)
    download_pending = max(0, download_ready - saved)
    song_failed = int(song_stats.get("draft_failed", 0) or 0) + int(song_stats.get("suno_failed", 0) or 0)
    music_pending = int(suno_stats.get("pending", 0) or 0)
    youtube = youtube_groups.get(key, youtube_batch_groups.get(batch_id, {}))
    youtube_success = int(youtube.get("success", 0) or 0)
    youtube_pending = int(youtube.get("pending", 0) or 0)
    youtube_failed = int(youtube.get("failed", 0) or 0)
    youtube_status = str(youtube.get("latest_status", "") or "").upper()
    youtube_url = youtube.get("youtube_url")

    # Export can start once the background is ready. Thumbnail is for YouTube upload
    # and may still be rendering while the row is already in Converter/Export.
    image_complete = (
        (bg_total <= 0 or bg_ready >= bg_total)
        and (bg_total > 0 or long_ready or reel_ready)
        and (long_ready or reel_ready)
    )

    stage = "Music"
    status = "Waiting"
    notes = "Waiting for music generation."
    pipeline_complete = bool(asset_group.get("pipeline_complete"))

    if str(batch.get("status", "")).lower() == "failed" or song_failed > 0 or bg_status == "FAILED" or th_status == "FAILED":
        stage = "Error"
        status = "Failed"
        notes = "One or more generation steps failed. Right-click this row for recovery actions."
    elif youtube_success > 0 or youtube_url:
        stage = "Done"
        status = "Done"
        notes = "Completed"
    elif pipeline_complete:
        stage = "Completed"
        status = "Completed"
        notes = (
            "Desktop pipeline completed. Local run-folder files may have been moved or archived."
        )
    elif youtube_pending > 0 or youtube_status in {"PENDING", "RUNNING", "PROCESSING"}:
        stage = "YouTube"
        if youtube_status == "PENDING":
            status = "Queued"
            notes = "YouTube upload is queued and waiting for the upload worker."
        else:
            status = "Uploading"
            notes = "YouTube upload is in progress."
    elif youtube_status == "BLOCKED":
        stage = "YouTube"
        status = "Blocked"
        notes = "YouTube upload is blocked until this profile is connected and credentials are valid."
    elif youtube_failed > 0 or youtube_status == "FAILED":
        stage = "Error"
        status = "Failed"
        notes = "YouTube upload failed. Retry tooling is not exposed in the API yet."
    elif saved < max(1, expected):
        stage = "Music"
        if download_pending > 0:
            status = "Downloading"
            notes = "Suno finished and the desktop app is downloading channel MP3 files."
        elif download_ready > saved:
            status = "Preparing"
            notes = "Suno audio is available and waiting for desktop download."
        elif music_pending > 0:
            status = "Generating"
            notes = "Music generation is still in progress."
        else:
            status = "Waiting"
            notes = "Waiting for music generation."
    elif not image_complete:
        stage = "Image"
        status = "Rendering" if (bg_total > 0 or th_total > 0) else "Queued"
        notes = "Background generation is still in progress (needed before video export)."
    else:
        stage = "Converter"
        status = "Queued"
        notes = "Waiting for desktop video export and merge."

    assets_ready = image_complete and any(
        [
            background_16x9_path,
            background_9x16_path,
            thumbnail_16x9_path,
            thumbnail_9x16_path,
        ]
    )
    if stage == "Completed":
        converter_text = "Completed"
        merge_text = "Completed"
    elif image_complete and not _is_terminal_progress_stage(stage):
        inspection = inspect_video_run_directory(row_run_dir) if row_run_dir else None
        video_presentation = build_video_run_presentation(
            inspection=inspection,
            expected=expected,
            assets_ready=assets_ready,
        )
        converter_text = video_presentation.converter
        merge_text = video_presentation.merge
        if video_presentation.stage and stage.lower() == "converter":
            stage = video_presentation.stage
            status = video_presentation.status or status
            notes = video_presentation.notes or notes
    elif assets_ready:
        converter_text = (
            f"Long {'Ready' if long_ready else 'Missing'} · "
            f"Reel {'Ready' if reel_ready else 'Missing'}"
        )
        merge_text = "Waiting for branch exports"
    else:
        converter_text = "Waiting for image assets"
        merge_text = "—"
    youtube_text = (
        "Ready"
        if youtube_success > 0
        else (
            "Blocked"
            if youtube_status == "BLOCKED"
            else (
                "Queued"
                if youtube_status == "PENDING"
                else (
                    "Uploading"
                    if (youtube_pending > 0 or youtube_status in {"RUNNING", "PROCESSING"})
                    else ("Failed" if youtube_failed > 0 or youtube_status == "FAILED" else "—")
                )
            )
        )
    )

    latest_image_started = min(
        [value for value in [bg_group.get("first_created_at"), th_group.get("first_created_at")] if value is not None],
        default=None,
    )
    latest_image_updated = max(
        [value for value in [bg_group.get("latest_updated_at"), th_group.get("latest_updated_at")] if value is not None],
        default=None,
    )
    activity_candidates = [
        value
        for value in [
            song_stats.get("music_updated_at"),
            suno_stats.get("music_updated_at"),
            latest_image_updated,
            youtube.get("updated_at"),
        ]
        if value is not None
    ]
    # Exclude batch.updated_at for terminal stages so desktop sync heartbeats
    # do not keep moving the Update column after the pipeline finished.
    if stage == "Done" and youtube.get("updated_at") is not None:
        updated_at = youtube.get("updated_at")
    elif stage in {"Done", "Completed", "Error"}:
        if stage == "Completed" and asset_group.get("pipeline_completed_at") is not None:
            updated_at = asset_group.get("pipeline_completed_at")
        else:
            updated_at = max(
                activity_candidates,
                default=batch.get("updated_at") or _utc_now(),
            )
    else:
        updated_at = max(
            [value for value in [*activity_candidates, batch.get("updated_at")] if value is not None],
            default=batch.get("updated_at") or _utc_now(),
        )

    return ProgressRow(
        batch=batch_id[-24:] if len(batch_id) > 24 else batch_id,
        run_date=_format_batch_run_date(batch),
        channel=profile_name,
        album=_batch_album_for_role(batch, role),
        status=status,
        music=f"{saved}/{max(1, expected)}",
        image=f"BG {bg_ready}/{max(bg_total, 1)} {bg_status} · TH {th_ready}/{max(th_total, 1)} {th_status}",
        converter=converter_text,
        merge=merge_text,
        youtube=youtube_text,
        stage=stage,
        notes=notes,
        updated=_iso_time(updated_at),
        meta=ProgressRowMeta(
            batch_id=batch_id,
            profile_id=profile_id,
            role=role,
            run_dir=row_run_dir,
            source_mode=str(source_mode) if source_mode else None,
            background_16x9_path=str(background_16x9_path) if background_16x9_path else None,
            background_9x16_path=str(background_9x16_path) if background_9x16_path else None,
            thumbnail_16x9_path=str(thumbnail_16x9_path) if thumbnail_16x9_path else None,
            thumbnail_9x16_path=str(thumbnail_9x16_path) if thumbnail_9x16_path else None,
            long_ready=long_ready,
            reel_ready=reel_ready,
            pipeline_complete=pipeline_complete,
            expected=expected,
            saved=saved,
            download_ready=download_ready,
            download_pending=download_pending,
            bg_ready=bg_ready,
            bg_total=bg_total,
            th_ready=th_ready,
            th_total=th_total,
            bg_status=bg_status,
            th_status=th_status,
            youtube_status=youtube_status,
            youtube_url=str(youtube_url) if youtube_url else None,
            youtube_success=youtube_success,
            youtube_pending=youtube_pending,
            youtube_failed=youtube_failed,
            music_started_at=song_stats.get("music_started_at"),
            music_updated_at=suno_stats.get("music_updated_at") or song_stats.get("music_updated_at"),
            image_started_at=latest_image_started,
            image_updated_at=latest_image_updated,
            youtube_created_at=youtube.get("created_at"),
            youtube_updated_at=youtube.get("updated_at"),
            updated_at=updated_at,
            draft_failed_song_ids=_coerce_uuid_list(song_stats.get("draft_failed_song_ids")),
            suno_failed_song_ids=_coerce_uuid_list(song_stats.get("suno_failed_song_ids")),
        ),
    )


@router.get("/progress", response_model=ProgressListResponse)
async def list_progress_rows(
    ctx: AuthContext = Depends(get_current_user),
    limit: int = Query(default=25, ge=1, le=100),
    active_only: bool = Query(default=False),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> ProgressListResponse:
    """Return aggregated progress rows for the authenticated user."""
    user_id = UUID(ctx.user_id)
    pool = get_db_pool()

    if from_date and to_date and from_date > to_date:
        from_date, to_date = to_date, from_date

    # Over-fetch batches so OK+ALT expansion can still fill the requested row limit.
    batch_fetch_limit = min(100, max(limit * 2, limit))

    async def _fetch_batches(*, planned_dates: bool) -> list[Any]:
        end_expr = _batch_run_end_expr(use_planned_dates=planned_dates)
        start_expr = _batch_run_start_expr(use_planned_dates=planned_dates)
        local_where = ["b.user_id = $1"]
        local_params: list[Any] = [user_id]
        if from_date:
            local_params.append(from_date)
            local_where.append(f"{end_expr} >= ${len(local_params)}")
        if to_date:
            local_params.append(to_date)
            local_where.append(f"{start_expr} <= ${len(local_params)}")
        local_params.append(batch_fetch_limit)
        planned_select = (
            "b.planned_from_date,\n                b.planned_to_date,"
            if planned_dates
            else "NULL::date AS planned_from_date,\n                NULL::date AS planned_to_date,"
        )
        order_by = (
            "COALESCE(b.planned_from_date, (b.created_at AT TIME ZONE 'UTC')::date) DESC, b.created_at DESC"
            if planned_dates
            else "(b.created_at AT TIME ZONE 'UTC')::date DESC, b.created_at DESC"
        )
        return await pool.fetch(
            f"""
        SELECT
            b.id,
            b.song_count,
            b.status,
            {planned_select}
            b.created_at,
            b.updated_at,
            b.ok_run_dir,
            b.alt_run_dir,
            b.ok_album,
            b.alt_album,
            b.ok_profile_id,
            b.alt_profile_id,
            okp.name AS ok_profile_name,
            okp.folder_name AS ok_profile_folder,
            altp.name AS alt_profile_name,
            altp.folder_name AS alt_profile_folder
        FROM batches b
        LEFT JOIN channel_profiles okp ON okp.id = b.ok_profile_id
        LEFT JOIN channel_profiles altp ON altp.id = b.alt_profile_id
        WHERE {' AND '.join(local_where)}
        ORDER BY {order_by}
        LIMIT ${len(local_params)}
        """,
            *local_params,
        )

    try:
        batch_rows = await _fetch_batches(planned_dates=True)
    except Exception as error:
        if not _is_schema_drift_error(error):
            raise
        batch_rows = await _fetch_batches(planned_dates=False)

    if not batch_rows:
        now = _utc_now()
        return ProgressListResponse(rows=[], summary="No runs found for the selected range.", updated_at=now)

    batch_ids = [row["id"] for row in batch_rows]

    # Only heal missing image-job rows — do not re-run ensure on every poll.
    # Previously this looped ensure_batch_image_jobs for every returned batch and
    # pegged uvicorn workers under desktop/coordinator polling.
    missing_image_job_batches = await pool.fetch(
        """
        SELECT b.id
        FROM UNNEST($1::uuid[]) AS b(id)
        WHERE NOT EXISTS (
            SELECT 1 FROM image_jobs ij WHERE ij.batch_id = b.id LIMIT 1
        )
        """,
        batch_ids,
    )
    if missing_image_job_batches:
        from platform_api.dependencies import get_batch_service

        batch_service = get_batch_service()
        for row in missing_image_job_batches:
            try:
                await batch_service.ensure_batch_image_jobs(
                    user_id=ctx.user_id,
                    batch_id=row["id"],
                )
            except Exception:
                logger.exception(
                    "Failed to ensure image jobs while loading progress for batch %s",
                    row["id"],
                )

    song_stats_rows = await pool.fetch(
        """
        SELECT
            batch_id,
            SUM(CASE WHEN status = 'draft_failed' THEN 1 ELSE 0 END)::int AS draft_failed,
            SUM(CASE WHEN status = 'suno_failed' THEN 1 ELSE 0 END)::int AS suno_failed,
            COALESCE(
                ARRAY_AGG(id) FILTER (WHERE status = 'draft_failed'),
                ARRAY[]::uuid[]
            ) AS draft_failed_song_ids,
            COALESCE(
                ARRAY_AGG(id) FILTER (WHERE status = 'suno_failed'),
                ARRAY[]::uuid[]
            ) AS suno_failed_song_ids,
            MIN(created_at) AS music_started_at,
            MAX(updated_at) AS music_updated_at
        FROM songs
        WHERE user_id = $1 AND batch_id = ANY($2::uuid[])
        GROUP BY batch_id
        """,
        user_id,
        batch_ids,
    )
    song_stats_map = {
        str(row["batch_id"]): {
            "draft_failed": int(row["draft_failed"] or 0),
            "suno_failed": int(row["suno_failed"] or 0),
            "draft_failed_song_ids": row["draft_failed_song_ids"],
            "suno_failed_song_ids": row["suno_failed_song_ids"],
            "music_started_at": row["music_started_at"],
            "music_updated_at": row["music_updated_at"],
        }
        for row in song_stats_rows
    }

    album_rows = await pool.fetch(
        """
        SELECT DISTINCT ON (batch_id)
            batch_id,
            album
        FROM songs
        WHERE user_id = $1
          AND batch_id = ANY($2::uuid[])
          AND COALESCE(TRIM(album), '') <> ''
        ORDER BY batch_id, batch_index ASC
        """,
        user_id,
        batch_ids,
    )
    album_map = {str(row["batch_id"]): str(row["album"]).strip() for row in album_rows}

    suno_stats_rows = await pool.fetch(
        """
        SELECT
            batch_id,
            COUNT(*)::int AS total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::int AS success,
            SUM(CASE WHEN status IN ('pending', 'running', 'processing') THEN 1 ELSE 0 END)::int AS pending,
            SUM(CASE WHEN audio_url_ok IS NOT NULL THEN 1 ELSE 0 END)::int AS ready_ok,
            SUM(CASE WHEN audio_url_alt IS NOT NULL THEN 1 ELSE 0 END)::int AS ready_alt,
            SUM(CASE WHEN downloaded_ok THEN 1 ELSE 0 END)::int AS downloaded_ok,
            SUM(CASE WHEN downloaded_alt THEN 1 ELSE 0 END)::int AS downloaded_alt,
            MAX(updated_at) AS music_updated_at
        FROM suno_tasks
        WHERE user_id = $1 AND batch_id = ANY($2::uuid[])
        GROUP BY batch_id
        """,
        user_id,
        batch_ids,
    )
    suno_stats_map = {
        str(row["batch_id"]): {
            "total": int(row["total"] or 0),
            "success": int(row["success"] or 0),
            "pending": int(row["pending"] or 0),
            "ready_ok": int(row["ready_ok"] or 0),
            "ready_alt": int(row["ready_alt"] or 0),
            "downloaded_ok": int(row["downloaded_ok"] or 0),
            "downloaded_alt": int(row["downloaded_alt"] or 0),
            "music_updated_at": row["music_updated_at"],
        }
        for row in suno_stats_rows
    }

    image_rows = await pool.fetch(
        """
        SELECT
            batch_id,
            profile_id,
            channel_role,
            kind,
            status,
            created_at,
            updated_at
        FROM image_jobs
        WHERE user_id = $1
          AND batch_id = ANY($2::uuid[])
          AND profile_id IS NOT NULL
        """,
        user_id,
        batch_ids,
    )
    image_groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(dict)
    for row in image_rows:
        batch_id = str(row["batch_id"])
        profile_id = str(row["profile_id"])
        role = str(row["channel_role"] or "").upper() or "OK"
        kind = str(row["kind"] or "").lower()
        group = image_groups[(batch_id, profile_id, role)].setdefault(
            kind,
            {
                "ready": 0,
                "failed": 0,
                "total": 0,
                "latest_status": "",
                "latest_updated_at": None,
                "first_created_at": None,
            },
        )
        group["total"] += 1
        status = str(row["status"] or "").lower()
        if status == "success":
            group["ready"] += 1
        if status == "failed":
            group["failed"] += 1
        if group["first_created_at"] is None or row["created_at"] < group["first_created_at"]:
            group["first_created_at"] = row["created_at"]
        if group["latest_updated_at"] is None or row["updated_at"] >= group["latest_updated_at"]:
            group["latest_updated_at"] = row["updated_at"]
            group["latest_status"] = status

    persisted_asset_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    try:
        asset_rows = await pool.fetch(
            """
            SELECT
                batch_id,
                profile_id,
                role,
                run_dir,
                source_mode,
                background_16x9_path,
                background_9x16_path,
                thumbnail_16x9_path,
                thumbnail_9x16_path,
                pipeline_complete,
                pipeline_completed_at
            FROM batch_channel_assets
            WHERE user_id = $1
              AND batch_id = ANY($2::uuid[])
            """,
            user_id,
            batch_ids,
        )
        persisted_asset_groups = {
            (
                str(row["batch_id"]),
                str(row["profile_id"]),
                str(row["role"] or "").upper() or "OK",
            ): {
                "run_dir": str(row["run_dir"] or "").strip() or None,
                "source_mode": str(row["source_mode"] or "").strip() or None,
                "background_16x9_path": row["background_16x9_path"],
                "background_9x16_path": row["background_9x16_path"],
                "thumbnail_16x9_path": row["thumbnail_16x9_path"],
                "thumbnail_9x16_path": row["thumbnail_9x16_path"],
                "pipeline_complete": bool(row.get("pipeline_complete", False)),
                "pipeline_completed_at": row.get("pipeline_completed_at"),
            }
            for row in asset_rows
        }
    except Exception:
        persisted_asset_groups = {}
    channel_assets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for batch in batch_rows:
        for role, profile_id in (
            ("OK", batch["ok_profile_id"]),
            ("ALT", batch["alt_profile_id"]),
        ):
            if not profile_id:
                continue
            key = (str(batch["id"]), str(profile_id), role)
            run_dir = resolve_channel_run_dir(
                role=role,
                ok_run_dir=str(batch.get("ok_run_dir") or ""),
                alt_run_dir=str(batch.get("alt_run_dir") or ""),
                alt_profile_folder=str(batch.get("alt_profile_folder") or ""),
                alt_profile_name=str(batch.get("alt_profile_name") or ""),
            ) or ""
            persisted = dict(persisted_asset_groups.get(key, {}))
            merged = merge_channel_asset_paths(run_dir, persisted)
            merged = {
                "run_dir": persisted.get("run_dir") or run_dir or None,
                "source_mode": persisted.get("source_mode"),
                **merged,
            }
            merged["long_ready"] = compute_long_ready(merged)
            merged["reel_ready"] = compute_reel_ready(merged)
            merged["pipeline_complete"] = bool(persisted.get("pipeline_complete", False))
            merged["pipeline_completed_at"] = persisted.get("pipeline_completed_at")
            channel_assets[key] = merged

    youtube_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    youtube_batch_groups: dict[str, dict[str, Any]] = {}
    try:
        youtube_rows = await pool.fetch(
            """
            SELECT
                COALESCE(y.batch_id, s.batch_id) AS batch_id,
                y.profile_id,
                y.role,
                y.status,
                y.youtube_video_id,
                y.youtube_url,
                y.created_at,
                y.updated_at
            FROM youtube_upload_jobs y
            LEFT JOIN songs s ON s.id = y.song_id
            WHERE y.user_id = $1
              AND COALESCE(y.batch_id, s.batch_id) = ANY($2::uuid[])
            """,
            user_id,
            batch_ids,
        )
        for row in youtube_rows:
            batch_id = str(row["batch_id"])
            profile_id = str(row["profile_id"] or "").strip()
            role = str(row["role"] or "").strip().upper()
            exact_key = (batch_id, profile_id, role) if profile_id and role else None
            group = (
                youtube_groups.setdefault(
                    exact_key,
                    {
                        "success": 0,
                        "pending": 0,
                        "failed": 0,
                        "latest_status": "",
                        "youtube_url": None,
                        "created_at": None,
                        "updated_at": None,
                    },
                )
                if exact_key is not None
                else youtube_batch_groups.setdefault(
                    batch_id,
                    {
                        "success": 0,
                        "pending": 0,
                        "failed": 0,
                        "latest_status": "",
                        "youtube_url": None,
                        "created_at": None,
                        "updated_at": None,
                    },
                )
            )
            if exact_key is not None:
                youtube_batch_groups.setdefault(
                    batch_id,
                    {
                        "success": 0,
                        "pending": 0,
                        "failed": 0,
                        "latest_status": "",
                        "youtube_url": None,
                        "created_at": None,
                        "updated_at": None,
                    },
                )
            batch_group = youtube_batch_groups.setdefault(
                batch_id,
                {
                    "success": 0,
                    "pending": 0,
                    "failed": 0,
                    "latest_status": "",
                    "youtube_url": None,
                    "created_at": None,
                    "updated_at": None,
                },
            )
            status = str(row["status"] or "").lower()
            target_groups = [group] if group is batch_group else [group, batch_group]
            for target_group in target_groups:
                if status == "success":
                    target_group["success"] += 1
                elif status in {"pending", "running", "processing"}:
                    target_group["pending"] += 1
                else:
                    target_group["failed"] += 1
                if row["youtube_video_id"]:
                    target_group["youtube_url"] = f"https://www.youtube.com/watch?v={row['youtube_video_id']}"
                elif row["youtube_url"]:
                    target_group["youtube_url"] = str(row["youtube_url"])
                if target_group["created_at"] is None or row["created_at"] < target_group["created_at"]:
                    target_group["created_at"] = row["created_at"]
                if target_group["updated_at"] is None or row["updated_at"] >= target_group["updated_at"]:
                    target_group["updated_at"] = row["updated_at"]
                    target_group["latest_status"] = status.upper()
    except Exception:
        youtube_groups = {}
        youtube_batch_groups = {}

    rows: list[ProgressRow] = []
    for batch in batch_rows:
        batch_payload = dict(batch)
        batch_key = str(batch["id"])
        fallback_album = album_map.get(batch_key)
        batch_payload["album"] = fallback_album
        if not batch_payload.get("ok_album"):
            batch_payload["ok_album"] = fallback_album
        # Do not copy Primary/song album onto alt_album — that caused Album 2 duplicates in UI.
        song_stats = song_stats_map.get(batch_key, {})
        suno_stats = suno_stats_map.get(batch_key, {})

        if batch["ok_profile_id"]:
            rows.append(
                _build_row(
                    batch=batch_payload,
                    role="OK",
                    profile_id=str(batch["ok_profile_id"]),
                    profile_name=str(batch["ok_profile_name"] or "Primary Channel"),
                    song_stats=song_stats,
                    suno_stats=suno_stats,
                    image_groups=image_groups,
                    channel_assets=channel_assets,
                    youtube_groups=youtube_groups,
                    youtube_batch_groups=youtube_batch_groups,
                )
            )

        if batch["alt_profile_id"]:
            rows.append(
                _build_row(
                    batch=batch_payload,
                    role="ALT",
                    profile_id=str(batch["alt_profile_id"]),
                    profile_name=str(batch["alt_profile_name"] or "Secondary Channel"),
                    song_stats=song_stats,
                    suno_stats=suno_stats,
                    image_groups=image_groups,
                    channel_assets=channel_assets,
                    youtube_groups=youtube_groups,
                    youtube_batch_groups=youtube_batch_groups,
                )
            )

    if active_only:
        rows = [
            row
            for row in rows
            if str(row.stage or "").strip().lower() not in {"done", "completed"}
        ]

    rows.sort(key=lambda row: (row.run_date, row.batch), reverse=True)
    # `limit` is a row count after OK/ALT expansion (and active_only), not batch count.
    rows = rows[:limit]
    now = _utc_now()
    summary = f"{len(rows)} rows loaded · refreshed at {_iso_time(now)}"
    return ProgressListResponse(rows=rows, summary=summary, updated_at=now)


class ProgressLocalSyncItemRequest(BaseModel):
    batch_id: str
    profile_id: str
    role: str = "OK"
    run_dir: str | None = None
    long_ready: bool | None = None
    reel_ready: bool | None = None
    local_mp3_count: int | None = None
    expected: int | None = None
    background_16x9_path: str | None = None
    background_9x16_path: str | None = None
    thumbnail_16x9_path: str | None = None
    thumbnail_9x16_path: str | None = None
    pipeline_complete: bool | None = None


class ProgressLocalSyncRequest(BaseModel):
    items: list[ProgressLocalSyncItemRequest] = Field(default_factory=list)


class ProgressLocalSyncResponse(BaseModel):
    updated: int = 0


@router.post("/progress/sync-local", response_model=ProgressLocalSyncResponse, status_code=200)
async def sync_local_progress(
    request: ProgressLocalSyncRequest,
    service: BatchServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> ProgressLocalSyncResponse:
    payload = [item.model_dump(exclude_none=True) for item in request.items]
    updated = await service.sync_local_progress_from_desktop(user_id=ctx.user_id, items=payload)
    return ProgressLocalSyncResponse(updated=updated)
