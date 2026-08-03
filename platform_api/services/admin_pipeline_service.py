"""Admin multi-user pipeline board (P1 — read-only watch).

Reuses progress stage derivation without per-user FS run-dir inspection.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from platform_api.dependencies import get_db_pool
from platform_api.routers.progress import _build_row
from platform_api.services.channel_asset_service import (
    compute_long_ready,
    compute_reel_ready,
    normalize_client_path,
)
from platform_api.services.run_directory_planner import resolve_channel_run_dir

logger = logging.getLogger(__name__)

_ASSET_PATH_KEYS = (
    "background_16x9_path",
    "background_9x16_path",
    "thumbnail_16x9_path",
    "thumbnail_9x16_path",
)


def _trust_persisted_asset_paths(persisted: dict[str, Any] | None) -> dict[str, str | None]:
    """Admin board runs on the API host and cannot see desktop E:\\ run folders.

    Trust DB-persisted paths as-is (do not require Path.is_file on this machine).
    """
    persisted_assets = persisted or {}
    merged: dict[str, str | None] = {}
    for key in _ASSET_PATH_KEYS:
        raw = str(persisted_assets.get(key) or "").strip() or None
        merged[key] = normalize_client_path(raw) if raw else None
    return merged


def _mark_ready_from_image_jobs(
    channel_assets: dict[tuple[str, str, str], dict[str, Any]],
    image_groups: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    """If BG/TH image jobs succeeded, treat export readiness as true even without FS paths."""
    for key, asset in channel_assets.items():
        image_group = image_groups.get(key, {})
        bg = image_group.get("background", {})
        th = image_group.get("thumbnail", {})
        bg_ready = int(bg.get("ready", 0) or 0)
        bg_total = int(bg.get("total", 0) or 0)
        th_ready = int(th.get("ready", 0) or 0)
        th_total = int(th.get("total", 0) or 0)
        if bg_total > 0 and bg_ready >= bg_total and not asset.get("background_16x9_path"):
            asset["background_16x9_path"] = "server://image-job-ready/background-16x9"
        if th_total > 0 and th_ready >= th_total and not asset.get("thumbnail_16x9_path"):
            asset["thumbnail_16x9_path"] = "server://image-job-ready/thumbnail-16x9"
        asset["long_ready"] = compute_long_ready(asset) or (bg_total > 0 and bg_ready >= bg_total)
        asset["reel_ready"] = compute_reel_ready(asset)


def _aggregate_streaming_groups(stream_rows: list[Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Aggregate stream_upload_jobs into (batch_id, role) progress chips."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in stream_rows:
        batch_id = str(row["batch_id"] or "")
        kind = str(row["kind"] or "").lower()
        role = "ALT" if kind.endswith("_alt") else "OK"
        key = (batch_id, role)
        group = groups.setdefault(
            key,
            {
                "total": 0,
                "success": 0,
                "pending": 0,
                "failed": 0,
                "error": None,
                "updated_at": None,
                "latest_status": "",
            },
        )
        status = str(row["status"] or "").lower()
        group["total"] += 1
        if status in {"success", "completed", "done"}:
            group["success"] += 1
        elif status in {"pending", "queued", "running", "processing", "uploading"}:
            group["pending"] += 1
        else:
            group["failed"] += 1
            err = str(row["error"] or "").strip()
            if err:
                group["error"] = err
        updated = row["updated_at"]
        if group["updated_at"] is None or (updated and updated >= group["updated_at"]):
            group["updated_at"] = updated
            group["latest_status"] = status.upper()
    return groups


def _format_streaming_chip(group: dict[str, Any] | None) -> str:
    if not group or int(group.get("total", 0) or 0) <= 0:
        return "—"
    success = int(group.get("success", 0) or 0)
    pending = int(group.get("pending", 0) or 0)
    failed = int(group.get("failed", 0) or 0)
    total = int(group.get("total", 0) or 0)
    if failed > 0:
        return f"Failed {failed}/{total}"
    if pending > 0:
        return f"Uploading {success}/{total}"
    if success >= total:
        return f"Done {success}/{total}"
    return f"{success}/{total}"


def _promote_admin_stage(
    *,
    stage: str,
    status: str,
    notes: str,
    stream_group: dict[str, Any] | None,
    music_done: bool,
    image_done: bool,
) -> tuple[str, str, str]:
    """Adjust desktop-centric stages for the admin board (no local MP4 inspection)."""
    stream_total = int((stream_group or {}).get("total", 0) or 0)
    stream_success = int((stream_group or {}).get("success", 0) or 0)
    stream_pending = int((stream_group or {}).get("pending", 0) or 0)
    stream_failed = int((stream_group or {}).get("failed", 0) or 0)
    stage_l = stage.strip().lower()

    if stream_total > 0 and stream_failed > 0 and stream_pending <= 0:
        return "Error", "Failed", "Streaming upload failed."
    if stream_total > 0 and stream_pending > 0:
        return "Streaming", "Uploading", "Streaming upload is in progress."
    if (
        music_done
        and image_done
        and stream_total > 0
        and stream_success >= stream_total
        and stage_l in {"image", "converter", "export", "merge", "merger", "streaming", "done", "completed"}
    ):
        return "Done", "Done", "Music, images, and streaming uploads are complete."
    if music_done and image_done and stage_l in {"image"}:
        return (
            "Converter",
            "Queued",
            "Images ready — waiting for desktop export/merge (not visible from API host).",
        )
    return stage, status, notes


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _age_seconds(updated_at: datetime | None, now: datetime) -> int | None:
    if updated_at is None:
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return max(0, int((now - updated_at.astimezone(timezone.utc)).total_seconds()))


async def list_admin_pipeline_board(
    *,
    limit: int = 50,
    active_only: bool = True,
    stage: str | None = None,
    user_id: UUID | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """Return cross-user progress rows for the admin Pipeline Ops board."""
    pool = get_db_pool()
    now = _utc_now()
    batch_fetch_limit = min(200, max(limit * 2, limit))

    where = ["1=1"]
    params: list[Any] = []
    if user_id is not None:
        params.append(user_id)
        where.append(f"b.user_id = ${len(params)}")
    if q:
        params.append(f"%{q.strip()}%")
        where.append(
            f"(u.email ILIKE ${len(params)} OR u.display_name ILIKE ${len(params)} "
            f"OR CAST(b.id AS text) ILIKE ${len(params)})"
        )
    params.append(batch_fetch_limit)

    batch_rows = await pool.fetch(
        f"""
        SELECT
            b.id,
            b.user_id,
            b.song_count,
            b.status,
            b.planned_from_date,
            b.planned_to_date,
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
            altp.folder_name AS alt_profile_folder,
            u.email AS user_email,
            u.display_name AS user_display_name
        FROM batches b
        INNER JOIN users u ON u.id = b.user_id
        LEFT JOIN channel_profiles okp ON okp.id = b.ok_profile_id
        LEFT JOIN channel_profiles altp ON altp.id = b.alt_profile_id
        WHERE {' AND '.join(where)}
        ORDER BY b.updated_at DESC NULLS LAST, b.created_at DESC
        LIMIT ${len(params)}
        """,
        *params,
    )

    if not batch_rows:
        return {
            "rows": [],
            "summary": "No pipelines found.",
            "updated_at": now,
            "counts": {
                "active": 0,
                "failed": 0,
                "stuck": 0,
                "total": 0,
            },
        }

    batch_ids = [row["id"] for row in batch_rows]

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
        WHERE batch_id = ANY($1::uuid[])
        GROUP BY batch_id
        """,
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
        WHERE batch_id = ANY($1::uuid[])
          AND COALESCE(TRIM(album), '') <> ''
        ORDER BY batch_id, batch_index ASC
        """,
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
        WHERE batch_id = ANY($1::uuid[])
        GROUP BY batch_id
        """,
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

    suno_error_rows = await pool.fetch(
        """
        SELECT DISTINCT ON (batch_id)
            batch_id,
            error_message
        FROM suno_tasks
        WHERE batch_id = ANY($1::uuid[])
          AND status = 'failed'
          AND COALESCE(TRIM(error_message), '') <> ''
        ORDER BY batch_id, updated_at DESC
        """,
        batch_ids,
    )
    suno_errors = {
        str(row["batch_id"]): str(row["error_message"] or "").strip()[:240]
        for row in suno_error_rows
    }

    image_rows = await pool.fetch(
        """
        SELECT
            batch_id,
            profile_id,
            channel_role,
            kind,
            status,
            error,
            created_at,
            updated_at
        FROM image_jobs
        WHERE batch_id = ANY($1::uuid[])
          AND profile_id IS NOT NULL
        """,
        batch_ids,
    )
    image_groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(dict)
    image_errors: dict[tuple[str, str, str], str] = {}
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
            err = str(row["error"] or "").strip()
            if err:
                image_errors[(batch_id, profile_id, role)] = err[:240]
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
            WHERE batch_id = ANY($1::uuid[])
            """,
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
        for role, profile_id in (("OK", batch["ok_profile_id"]), ("ALT", batch["alt_profile_id"])):
            if not profile_id:
                continue
            key = (str(batch["id"]), str(profile_id), role)
            run_dir = (
                resolve_channel_run_dir(
                    role=role,
                    ok_run_dir=str(batch.get("ok_run_dir") or ""),
                    alt_run_dir=str(batch.get("alt_run_dir") or ""),
                    alt_profile_folder=str(batch.get("alt_profile_folder") or ""),
                    alt_profile_name=str(batch.get("alt_profile_name") or ""),
                )
                or ""
            )
            persisted = dict(persisted_asset_groups.get(key, {}))
            # Do not scan desktop run dirs on the API host — paths like E:\ are not local.
            merged = _trust_persisted_asset_paths(persisted)
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

    _mark_ready_from_image_jobs(channel_assets, image_groups)

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
                y.error_message,
                y.created_at,
                y.updated_at
            FROM youtube_upload_jobs y
            LEFT JOIN songs s ON s.id = y.song_id
            WHERE COALESCE(y.batch_id, s.batch_id) = ANY($1::uuid[])
            """,
            batch_ids,
        )
        youtube_errors: dict[tuple[str, str, str], str] = {}
        for row in youtube_rows:
            batch_id = str(row["batch_id"])
            profile_id = str(row["profile_id"] or "").strip()
            role = str(row["role"] or "").strip().upper()
            exact_key = (batch_id, profile_id, role) if profile_id and role else None
            blank = {
                "success": 0,
                "pending": 0,
                "failed": 0,
                "latest_status": "",
                "youtube_url": None,
                "created_at": None,
                "updated_at": None,
            }
            group = (
                youtube_groups.setdefault(exact_key, dict(blank))
                if exact_key is not None
                else youtube_batch_groups.setdefault(batch_id, dict(blank))
            )
            batch_group = youtube_batch_groups.setdefault(batch_id, dict(blank))
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
                    target_group["youtube_url"] = (
                        f"https://www.youtube.com/watch?v={row['youtube_video_id']}"
                    )
                elif row["youtube_url"]:
                    target_group["youtube_url"] = str(row["youtube_url"])
                if target_group["created_at"] is None or row["created_at"] < target_group["created_at"]:
                    target_group["created_at"] = row["created_at"]
                if target_group["updated_at"] is None or row["updated_at"] >= target_group["updated_at"]:
                    target_group["updated_at"] = row["updated_at"]
                    target_group["latest_status"] = status.upper()
            if exact_key and status == "failed":
                err = str(row["error_message"] or "").strip()
                if err:
                    youtube_errors[exact_key] = err[:240]
    except Exception:
        logger.exception("admin pipeline board: youtube aggregate failed")
        youtube_groups = {}
        youtube_batch_groups = {}
        youtube_errors = {}

    streaming_groups: dict[tuple[str, str], dict[str, Any]] = {}
    streaming_errors: dict[tuple[str, str], str] = {}
    try:
        stream_rows = await pool.fetch(
            """
            SELECT
                batch_id,
                song_id,
                kind,
                status,
                error,
                updated_at
            FROM stream_upload_jobs
            WHERE batch_id = ANY($1::uuid[])
              AND kind IN ('mp3_ok', 'mp3_alt')
            """,
            batch_ids,
        )
        streaming_groups = _aggregate_streaming_groups(list(stream_rows))
        for key, group in streaming_groups.items():
            err = str(group.get("error") or "").strip()
            if err and int(group.get("failed", 0) or 0) > 0:
                streaming_errors[key] = err[:240]
    except Exception:
        logger.exception("admin pipeline board: streaming aggregate failed")
        streaming_groups = {}
        streaming_errors = {}

    stage_filter = str(stage or "").strip().lower() or None
    board_rows: list[dict[str, Any]] = []

    for batch in batch_rows:
        batch_payload = dict(batch)
        batch_key = str(batch["id"])
        fallback_album = album_map.get(batch_key)
        batch_payload["album"] = fallback_album
        if not batch_payload.get("ok_album"):
            batch_payload["ok_album"] = fallback_album
        song_stats = song_stats_map.get(batch_key, {})
        suno_stats = suno_stats_map.get(batch_key, {})

        for role, profile_id, profile_name in (
            ("OK", batch["ok_profile_id"], batch["ok_profile_name"] or "Primary Channel"),
            ("ALT", batch["alt_profile_id"], batch["alt_profile_name"] or "Secondary Channel"),
        ):
            if not profile_id:
                continue
            progress = _build_row(
                batch=batch_payload,
                role=role,
                profile_id=str(profile_id),
                profile_name=str(profile_name),
                song_stats=song_stats,
                suno_stats=suno_stats,
                image_groups=image_groups,
                channel_assets=channel_assets,
                youtube_groups=youtube_groups,
                youtube_batch_groups=youtube_batch_groups,
            )
            stream_key = (batch_key, role)
            stream_group = streaming_groups.get(stream_key)
            streaming_chip = _format_streaming_chip(stream_group)
            asset_key = (batch_key, str(profile_id), role)
            asset = channel_assets.get(asset_key, {})
            image_group = image_groups.get(asset_key, {})
            bg = image_group.get("background", {})
            bg_ready = int(bg.get("ready", 0) or 0)
            bg_total = int(bg.get("total", 0) or 0)
            music_done = int(suno_stats.get("downloaded_ok" if role == "OK" else "downloaded_alt", 0) or 0) >= max(
                1, int(batch.get("song_count", 0) or 0)
            )
            image_done = bool(asset.get("long_ready")) or (bg_total > 0 and bg_ready >= bg_total)
            stage_name, progress_status, progress_notes = _promote_admin_stage(
                stage=str(progress.stage or ""),
                status=str(progress.status or ""),
                notes=str(progress.notes or ""),
                stream_group=stream_group,
                music_done=music_done,
                image_done=image_done,
            )

            if active_only and stage_name.strip().lower() in {"done", "completed"}:
                continue
            if stage_filter and stage_name.strip().lower() != stage_filter:
                continue

            key = asset_key
            error_snippet = (
                image_errors.get(key)
                or youtube_errors.get(key)
                or streaming_errors.get(stream_key)
                or suno_errors.get(batch_key)
                or None
            )
            if str(progress_status).lower() == "failed" and not error_snippet:
                error_snippet = progress_notes

            updated_at = progress.meta.updated_at
            # Prefer converter/merge text that matches admin promotion.
            converter_text = progress.converter
            merge_text = progress.merge
            if stage_name.strip().lower() in {"done", "completed"}:
                converter_text = "Completed"
                merge_text = "Completed"
            elif stage_name.strip().lower() == "converter" and image_done:
                converter_text = "Assets ready · desktop export not visible on API"
                merge_text = "Waiting for desktop merge"

            board_rows.append(
                {
                    "user_id": str(batch["user_id"]),
                    "user_email": str(batch["user_email"] or ""),
                    "user_display_name": str(batch["user_display_name"] or ""),
                    "batch_id": batch_key,
                    "role": role,
                    "profile_id": str(profile_id),
                    "profile_name": str(profile_name),
                    "album": progress.album,
                    "run_date": progress.run_date,
                    "stage": stage_name,
                    "status": progress_status,
                    "music": progress.music,
                    "image": progress.image,
                    "converter": converter_text,
                    "merge": merge_text,
                    "youtube": progress.youtube,
                    "streaming": streaming_chip,
                    "notes": progress_notes,
                    "error_snippet": error_snippet,
                    "updated": progress.updated,
                    "updated_at": updated_at,
                    "age_seconds": _age_seconds(updated_at, now),
                    "draft_failed_count": int(song_stats.get("draft_failed", 0) or 0),
                    "suno_failed_count": int(song_stats.get("suno_failed", 0) or 0),
                    "meta": progress.meta.model_dump(mode="json"),
                }
            )

    # Failed / stuck first, then newest.
    def _sort_key(row: dict[str, Any]) -> tuple:
        status = str(row.get("status") or "").lower()
        stage = str(row.get("stage") or "").lower()
        failed = 0 if status == "failed" or stage == "error" else 1
        age = int(row.get("age_seconds") or 0)
        stuck = 0 if age >= 15 * 60 and failed == 1 and stage not in {"done", "completed"} else 1
        updated = row.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc)
        return (failed, stuck, -updated.timestamp() if hasattr(updated, "timestamp") else 0)

    board_rows.sort(key=_sort_key)
    board_rows = board_rows[:limit]

    failed = sum(
        1
        for row in board_rows
        if str(row.get("status") or "").lower() == "failed"
        or str(row.get("stage") or "").lower() == "error"
    )
    stuck = sum(
        1
        for row in board_rows
        if int(row.get("age_seconds") or 0) >= 15 * 60
        and str(row.get("stage") or "").lower() not in {"done", "completed", "error"}
    )
    active = sum(
        1
        for row in board_rows
        if str(row.get("stage") or "").lower() not in {"done", "completed"}
    )

    return {
        "rows": board_rows,
        "summary": f"{len(board_rows)} pipelines · refreshed at {now.strftime('%H:%M:%S UTC')}",
        "updated_at": now,
        "counts": {
            "active": active,
            "failed": failed,
            "stuck": stuck,
            "total": len(board_rows),
        },
    }


async def get_admin_pipeline_batch_detail(batch_id: UUID) -> dict[str, Any] | None:
    """Return drawer payload: songs, image jobs, youtube jobs for one batch."""
    pool = get_db_pool()
    batch = await pool.fetchrow(
        """
        SELECT
            b.id,
            b.user_id,
            b.status,
            b.song_count,
            b.created_at,
            b.updated_at,
            b.ok_profile_id,
            b.alt_profile_id,
            b.ok_album,
            b.alt_album,
            u.email AS user_email,
            u.display_name AS user_display_name
        FROM batches b
        INNER JOIN users u ON u.id = b.user_id
        WHERE b.id = $1
        """,
        batch_id,
    )
    if batch is None:
        return None

    songs = await pool.fetch(
        """
        SELECT
            s.id,
            s.batch_index,
            s.title,
            s.album,
            s.status,
            s.updated_at,
            st.status AS suno_status,
            st.error_message AS suno_error,
            st.updated_at AS suno_updated_at
        FROM songs s
        LEFT JOIN LATERAL (
            SELECT status, error_message, updated_at
            FROM suno_tasks t
            WHERE t.song_id = s.id
            ORDER BY t.updated_at DESC NULLS LAST
            LIMIT 1
        ) st ON true
        WHERE s.batch_id = $1
        ORDER BY s.batch_index ASC
        """,
        batch_id,
    )

    images = await pool.fetch(
        """
        SELECT
            id,
            profile_id,
            channel_role,
            kind,
            status,
            attempt_count,
            error,
            updated_at
        FROM image_jobs
        WHERE batch_id = $1
        ORDER BY channel_role ASC, kind ASC, created_at ASC
        """,
        batch_id,
    )

    youtube = await pool.fetch(
        """
        SELECT
            id,
            profile_id,
            role,
            status,
            youtube_video_id,
            youtube_url,
            error_message,
            updated_at
        FROM youtube_upload_jobs
        WHERE batch_id = $1
        ORDER BY role ASC, updated_at DESC
        """,
        batch_id,
    )

    streaming = await pool.fetch(
        """
        SELECT
            j.id,
            j.song_id,
            j.batch_id,
            j.album_id,
            j.kind,
            j.status,
            j.attempt_count,
            j.error,
            j.source_url,
            j.storage_key,
            j.created_at,
            j.updated_at,
            s.title AS song_title,
            s.album AS song_album,
            s.batch_index AS song_batch_index,
            a.album_name AS stream_album_name,
            a.channel_role AS stream_channel_role,
            a.publish_status AS stream_album_publish_status,
            t.publish_status AS stream_track_publish_status,
            t.variant AS stream_track_variant
        FROM stream_upload_jobs j
        LEFT JOIN songs s ON s.id = j.song_id
        LEFT JOIN stream_albums a ON a.id = j.album_id
        LEFT JOIN LATERAL (
            SELECT st.publish_status, st.variant
            FROM stream_tracks st
            WHERE st.song_id = j.song_id
              AND st.user_id = j.user_id
              AND (
                    (j.kind = 'mp3_ok' AND st.variant = 'ok')
                 OR (j.kind = 'mp3_alt' AND st.variant = 'alt')
              )
            ORDER BY st.updated_at DESC NULLS LAST
            LIMIT 1
        ) t ON TRUE
        WHERE j.batch_id = $1
        ORDER BY
            CASE j.kind
                WHEN 'mp3_ok' THEN 1
                WHEN 'mp3_alt' THEN 2
                WHEN 'cover' THEN 3
                ELSE 4
            END,
            s.batch_index ASC NULLS LAST,
            j.updated_at DESC
        """,
        batch_id,
    )

    return {
        "batch_id": str(batch["id"]),
        "user_id": str(batch["user_id"]),
        "user_email": str(batch["user_email"] or ""),
        "user_display_name": str(batch["user_display_name"] or ""),
        "status": str(batch["status"] or ""),
        "song_count": int(batch["song_count"] or 0),
        "ok_profile_id": str(batch["ok_profile_id"]) if batch["ok_profile_id"] else None,
        "alt_profile_id": str(batch["alt_profile_id"]) if batch["alt_profile_id"] else None,
        "ok_album": batch["ok_album"],
        "alt_album": batch["alt_album"],
        "created_at": batch["created_at"],
        "updated_at": batch["updated_at"],
        "songs": [
            {
                "id": str(row["id"]),
                "batch_index": int(row["batch_index"] or 0),
                "title": row["title"],
                "album": row["album"],
                "status": row["status"],
                "updated_at": row["updated_at"],
                "suno_status": row["suno_status"],
                "suno_error": row["suno_error"],
                "suno_updated_at": row["suno_updated_at"],
            }
            for row in songs
        ],
        "image_jobs": [
            {
                "id": str(row["id"]),
                "profile_id": str(row["profile_id"]) if row["profile_id"] else None,
                "channel_role": row["channel_role"],
                "kind": row["kind"],
                "status": row["status"],
                "attempt_count": int(row["attempt_count"] or 0),
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            for row in images
        ],
        "youtube_jobs": [
            {
                "id": str(row["id"]),
                "profile_id": str(row["profile_id"]) if row["profile_id"] else None,
                "role": row["role"],
                "status": row["status"],
                "youtube_video_id": row["youtube_video_id"],
                "youtube_url": row["youtube_url"],
                "error_message": row["error_message"],
                "updated_at": row["updated_at"],
            }
            for row in youtube
        ],
        "streaming_jobs": [
            {
                "id": str(row["id"]),
                "song_id": str(row["song_id"]) if row["song_id"] else None,
                "batch_id": str(row["batch_id"]) if row.get("batch_id") else None,
                "album_id": str(row["album_id"]) if row.get("album_id") else None,
                "kind": row["kind"],
                "status": row["status"],
                "attempt_count": int(row["attempt_count"] or 0),
                "error": row["error"],
                "source_url": row.get("source_url"),
                "storage_key": row["storage_key"],
                "song_title": row.get("song_title"),
                "song_album": row.get("song_album"),
                "song_batch_index": (
                    int(row["song_batch_index"])
                    if row.get("song_batch_index") is not None
                    else None
                ),
                "stream_album_name": row.get("stream_album_name"),
                "stream_channel_role": row.get("stream_channel_role"),
                "stream_album_publish_status": row.get("stream_album_publish_status"),
                "stream_track_publish_status": row.get("stream_track_publish_status"),
                "stream_track_variant": row.get("stream_track_variant"),
                "created_at": row.get("created_at"),
                "updated_at": row["updated_at"],
            }
            for row in streaming
        ],
    }
