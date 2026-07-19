"""Read-only music history endpoint for authenticated users."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.batch_service import BatchService
from platform_api.models.schemas import (
    MusicHistoryBatchResponse,
    MusicHistoryListResponse,
    MusicHistorySongResponse,
)
from platform_api.services.run_directory_planner import resolve_history_output_dirs

router = APIRouter(prefix="/music", tags=["music"])


async def _get_batch_service() -> BatchService:
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )


BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return row[key] if key in row else None


def _is_schema_drift_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "does not exist" in message
        and (
            "planned_from_date" in message
            or "planned_to_date" in message
            or "output_dir_ok" in message
            or "output_dir_alt" in message
            or "ok_run_dir" in message
            or "alt_run_dir" in message
            or "folder_name" in message
            or "youtube_upload_jobs" in message
            or "error_message" in message
        )
    )


@router.get("/history", response_model=MusicHistoryListResponse)
async def list_music_history(
    batch_service: BatchServiceDep,
    ctx: AuthContext = Depends(get_current_user),
    limit: int = Query(default=8, ge=1, le=25),
) -> MusicHistoryListResponse:
    """Return recent batch/song history for the authenticated user."""
    user_id = UUID(ctx.user_id)
    pool = get_db_pool()

    # Reconcile in-flight Suno tasks so history reflects provider success even when
    # webhooks were rejected or delayed (client refresh should not depend on MP3 sync).
    try:
        await batch_service.reconcile_pending_suno_tasks(
            user_id=ctx.user_id,
            limit=max(limit, 25),
        )
    except Exception:
        pass

    try:
        batch_rows = await pool.fetch(
            """
            SELECT
                b.id,
                b.status,
                b.song_count,
                b.planned_from_date,
                b.planned_to_date,
                b.created_at,
                b.updated_at,
                b.ok_profile_id,
                b.alt_profile_id,
                b.ok_run_dir,
                b.alt_run_dir,
                b.ok_album,
                b.alt_album,
                okp.name AS ok_profile_name,
                okp.folder_name AS ok_profile_folder,
                altp.name AS alt_profile_name,
                altp.folder_name AS alt_profile_folder
            FROM batches b
            LEFT JOIN channel_profiles okp ON okp.id = b.ok_profile_id
            LEFT JOIN channel_profiles altp ON altp.id = b.alt_profile_id
            WHERE b.user_id = $1
            ORDER BY b.created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    except Exception as error:
        if not _is_schema_drift_error(error):
            raise
        batch_rows = await pool.fetch(
            """
            SELECT
                b.id,
                b.status,
                b.song_count,
                DATE(b.created_at) AS planned_from_date,
                DATE(b.created_at) AS planned_to_date,
                b.created_at,
                b.updated_at,
                b.ok_profile_id,
                b.alt_profile_id,
                NULL::text AS ok_run_dir,
                NULL::text AS alt_run_dir,
                okp.name AS ok_profile_name,
                NULL::text AS ok_profile_folder,
                altp.name AS alt_profile_name,
                NULL::text AS alt_profile_folder
            FROM batches b
            LEFT JOIN channel_profiles okp ON okp.id = b.ok_profile_id
            LEFT JOIN channel_profiles altp ON altp.id = b.alt_profile_id
            WHERE b.user_id = $1
            ORDER BY b.created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )

    if not batch_rows:
        now = _utc_now()
        return MusicHistoryListResponse(
            batches=[],
            summary="No music history found yet.",
            updated_at=now,
        )

    batch_ids = [row["id"] for row in batch_rows]

    try:
        song_rows = await pool.fetch(
            """
            SELECT
                s.id AS song_id,
                s.batch_id,
                s.batch_index,
                s.title,
                s.album,
                s.lyrics,
                s.description_id,
                d.name AS description_name,
                s.structure_id,
                CASE
                    WHEN b.structure_mode = 'ai_free' THEN 'AI Structure'
                    ELSE ms.name
                END AS structure_name,
                st.output_dir_ok,
                st.output_dir_alt,
                s.status,
                s.created_at,
                s.updated_at,
                st.status AS suno_status,
                st.error_message AS suno_error_message,
                COALESCE(st.downloaded_ok, false) AS downloaded_ok,
                COALESCE(st.downloaded_alt, false) AS downloaded_alt,
                y.status AS youtube_status
            FROM songs s
            LEFT JOIN batches b ON b.id = s.batch_id
            LEFT JOIN music_descriptions d ON d.id = s.description_id
            LEFT JOIN music_structures ms ON ms.id = s.structure_id
            LEFT JOIN LATERAL (
                SELECT status, output_dir_ok, output_dir_alt, downloaded_ok, downloaded_alt, error_message
                FROM suno_tasks st
                WHERE st.song_id = s.id
                ORDER BY st.updated_at DESC, st.created_at DESC
                LIMIT 1
            ) st ON TRUE
            LEFT JOIN LATERAL (
                SELECT status
                FROM youtube_upload_jobs y
                WHERE y.song_id = s.id
                ORDER BY y.updated_at DESC, y.created_at DESC
                LIMIT 1
            ) y ON TRUE
            WHERE s.user_id = $1
              AND s.batch_id = ANY($2::uuid[])
            ORDER BY s.batch_id DESC, s.batch_index ASC
            """,
            user_id,
            batch_ids,
        )
    except Exception as error:
        if not _is_schema_drift_error(error):
            raise
        song_rows = await pool.fetch(
            """
            SELECT
                s.id AS song_id,
                s.batch_id,
                s.batch_index,
                s.title,
                s.album,
                s.lyrics,
                s.description_id,
                d.name AS description_name,
                s.structure_id,
                CASE
                    WHEN b.structure_mode = 'ai_free' THEN 'AI Structure'
                    ELSE ms.name
                END AS structure_name,
                NULL::text AS output_dir_ok,
                NULL::text AS output_dir_alt,
                s.status,
                s.created_at,
                s.updated_at,
                st.status AS suno_status,
                st.error_message AS suno_error_message,
                COALESCE(st.downloaded_ok, false) AS downloaded_ok,
                COALESCE(st.downloaded_alt, false) AS downloaded_alt,
                NULL::text AS youtube_status
            FROM songs s
            LEFT JOIN batches b ON b.id = s.batch_id
            LEFT JOIN music_descriptions d ON d.id = s.description_id
            LEFT JOIN music_structures ms ON ms.id = s.structure_id
            LEFT JOIN LATERAL (
                SELECT status, downloaded_ok, downloaded_alt, error_message
                FROM suno_tasks st
                WHERE st.song_id = s.id
                ORDER BY st.updated_at DESC, st.created_at DESC
                LIMIT 1
            ) st ON TRUE
            WHERE s.user_id = $1
              AND s.batch_id = ANY($2::uuid[])
            ORDER BY s.batch_id DESC, s.batch_index ASC
            """,
            user_id,
            batch_ids,
        )

    image_rows = await pool.fetch(
        """
        SELECT
            song_id,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE status = 'success')::int AS completed
        FROM image_jobs
        WHERE user_id = $1
          AND batch_id = ANY($2::uuid[])
          AND song_id IS NOT NULL
        GROUP BY song_id
        """,
        user_id,
        batch_ids,
    )
    image_counts = {
        str(row["song_id"]): {
            "total": int(row["total"] or 0),
            "completed": int(row["completed"] or 0),
        }
        for row in image_rows
    }

    songs_by_batch: dict[str, list[MusicHistorySongResponse]] = defaultdict(list)
    batch_meta_by_id: dict[str, dict[str, Any]] = {
        str(row["id"]): {
            "ok_run_dir": str(row.get("ok_run_dir") or "").strip() or None,
            "alt_run_dir": str(row.get("alt_run_dir") or "").strip() or None,
            "alt_profile_folder": str(row.get("alt_profile_folder") or "").strip() or None,
            "alt_profile_name": str(row.get("alt_profile_name") or "").strip() or None,
        }
        for row in batch_rows
    }
    for row in song_rows:
        song_id = str(row["song_id"])
        image_meta = image_counts.get(song_id, {})
        batch_meta = batch_meta_by_id.get(str(row["batch_id"]), {})
        output_dir_ok, output_dir_alt = resolve_history_output_dirs(
            song_output_dir_ok=str(_row_value(row, "output_dir_ok")) if _row_value(row, "output_dir_ok") else None,
            song_output_dir_alt=str(_row_value(row, "output_dir_alt")) if _row_value(row, "output_dir_alt") else None,
            batch_ok_run_dir=batch_meta.get("ok_run_dir"),
            batch_alt_run_dir=batch_meta.get("alt_run_dir"),
            alt_profile_folder=batch_meta.get("alt_profile_folder"),
            alt_profile_name=batch_meta.get("alt_profile_name"),
        )
        songs_by_batch[str(row["batch_id"])].append(
            MusicHistorySongResponse(
                song_id=song_id,
                batch_index=int(row["batch_index"] or 0),
                title=row["title"],
                album=row["album"],
                lyrics=_row_value(row, "lyrics"),
                description_id=str(_row_value(row, "description_id")) if _row_value(row, "description_id") else None,
                description_name=str(_row_value(row, "description_name")) if _row_value(row, "description_name") else None,
                structure_id=str(_row_value(row, "structure_id")) if _row_value(row, "structure_id") else None,
                structure_name=str(_row_value(row, "structure_name")) if _row_value(row, "structure_name") else None,
                output_dir_ok=output_dir_ok,
                output_dir_alt=output_dir_alt,
                status=str(row["status"] or "pending"),
                suno_status=str(row["suno_status"]) if row["suno_status"] else None,
                suno_error_message=str(_row_value(row, "suno_error_message")).strip()
                if _row_value(row, "suno_error_message")
                else None,
                youtube_status=str(row["youtube_status"]) if row["youtube_status"] else None,
                downloaded_ok=bool(row["downloaded_ok"]),
                downloaded_alt=bool(row["downloaded_alt"]),
                image_jobs_completed=int(image_meta.get("completed", 0)),
                image_jobs_total=int(image_meta.get("total", 0)),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )

    batches: list[MusicHistoryBatchResponse] = []
    total_songs = 0
    for row in batch_rows:
        batch_id = str(row["id"])
        songs = songs_by_batch.get(batch_id, [])
        total_songs += len(songs)
        from_date = row["planned_from_date"] or row["created_at"].date()
        to_date = row["planned_to_date"] or from_date
        planned_days = max((to_date - from_date).days + 1, 1)

        batches.append(
            MusicHistoryBatchResponse(
                batch_id=batch_id,
                status=str(row["status"] or "pending"),
                song_count=int(row["song_count"] or len(songs)),
                from_date=from_date,
                to_date=to_date,
                planned_days=planned_days,
                ok_profile_id=str(row["ok_profile_id"]) if row["ok_profile_id"] else None,
                ok_profile_name=str(row["ok_profile_name"]) if row["ok_profile_name"] else None,
                alt_profile_id=str(row["alt_profile_id"]) if row["alt_profile_id"] else None,
                alt_profile_name=str(row["alt_profile_name"]) if row["alt_profile_name"] else None,
                ok_album=str(row["ok_album"]).strip() if _row_value(row, "ok_album") else None,
                alt_album=str(row["alt_album"]).strip() if _row_value(row, "alt_album") else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                songs=songs,
            )
        )

    now = _utc_now()
    return MusicHistoryListResponse(
        batches=batches,
        summary=f"{len(batches)} recent batches · {total_songs} songs loaded",
        updated_at=now,
    )
