"""Dashboard stats endpoint providing aggregated user metrics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.schemas import (
    DashboardStatsResponse,
    DailyUsage,
    PublicStatsResponse,
    RecentActivity,
)
from platform_api.dependencies import get_db_pool
from platform_api.services.credit_units import units_to_credits

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


@router.get("/stats/public", response_model=PublicStatsResponse)
async def get_public_stats() -> PublicStatsResponse:
    now = datetime.now(timezone.utc)

    users_total = await get_db_pool().fetchval(
        "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND status = 'active'"
    )
    profiles_total = await get_db_pool().fetchval("SELECT COUNT(*) FROM channel_profiles")
    batches_total = await get_db_pool().fetchval("SELECT COUNT(*) FROM batches")
    songs_total = await get_db_pool().fetchval("SELECT COUNT(*) FROM songs")
    images_total = await get_db_pool().fetchval("SELECT COUNT(*) FROM image_jobs")

    videos_total = 0
    youtube_uploads_total = 0
    studio_exports_total = 0
    manual_exports_total = 0
    try:
        youtube_uploads_total = int(
            await get_db_pool().fetchval(
                "SELECT COUNT(*) FROM youtube_upload_jobs WHERE status = 'success'"
            )
            or 0
        )
        videos_total = int(
            await get_db_pool().fetchval("SELECT COUNT(*) FROM youtube_upload_jobs") or 0
        )
    except Exception:
        youtube_uploads_total = 0
        videos_total = 0
    try:
        studio_exports_total = int(
            await get_db_pool().fetchval(
                """
                SELECT COALESCE(SUM(daily_count), 0)
                FROM usage_tracking
                WHERE operation_type = 'video'
                """
            )
            or 0
        )
        manual_exports_total = int(
            await get_db_pool().fetchval(
                """
                SELECT COALESCE(SUM(daily_count), 0)
                FROM usage_tracking
                WHERE operation_type = 'video_manual'
                """
            )
            or 0
        )
    except Exception:
        studio_exports_total = 0
        manual_exports_total = 0

    return PublicStatsResponse(
        updated_at=now,
        users_total=int(users_total) if users_total else 0,
        profiles_total=int(profiles_total) if profiles_total else 0,
        batches_total=int(batches_total) if batches_total else 0,
        songs_total=int(songs_total) if songs_total else 0,
        images_total=int(images_total) if images_total else 0,
        videos_total=videos_total,
        studio_exports_total=studio_exports_total,
        manual_exports_total=manual_exports_total,
        youtube_uploads_total=youtube_uploads_total,
    )


@router.get("/stats/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(ctx: AuthContext = Depends(get_current_user)) -> DashboardStatsResponse:
    """Return aggregated dashboard statistics for the authenticated user.

    Combines data from credit_wallets, credit_transactions, songs, image_jobs,
    youtube_upload_jobs, and licenses/plan_usage tables.
    """
    user_id = ctx.user_id

    now = datetime.now(timezone.utc)
    # Inclusive 7-day window ending today (UTC): today-6 .. today.
    # Using days=7 previously ended at yesterday and hid same-day Manual exports.
    today = now.date()
    seven_days_ago = today - timedelta(days=6)

    # --- Credits ---
    wallet_row = await get_db_pool().fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1", user_id
    )
    credits_remaining_units = int(wallet_row["balance"]) if wallet_row else 0

    # Net wallet spend: debits minus refunds. Gross debits overstate what the
    # user actually consumed because failed/deferred operations are refunded
    # (direction='refund'; legacy web-music refunds land as direction='credit'
    # with reason 'refunded_%'). Keeping this gross made "Credits spent" and the
    # derived "Credits total" (spent + remaining) overstate both figures.
    spent_row = await get_db_pool().fetchrow(
        """
        SELECT GREATEST(
            0,
            COALESCE(SUM(amount) FILTER (WHERE direction = 'debit'), 0)
            - COALESCE(SUM(amount) FILTER (WHERE direction = 'refund'), 0)
            - COALESCE(SUM(amount) FILTER (
                  WHERE direction = 'credit' AND reason LIKE 'refunded_%'
              ), 0)
        ) AS net_spent_units
        FROM credit_transactions
        WHERE user_id = $1
        """,
        user_id,
    )
    credits_spent_units = int(spent_row["net_spent_units"] or 0) if spent_row else 0
    credits_remaining = units_to_credits(credits_remaining_units)
    credits_spent = units_to_credits(credits_spent_units)
    # remaining + net spend = credits granted to the wallet (refunds excluded).
    credits_total = credits_spent + credits_remaining

    # --- Songs ---
    songs_count = await get_db_pool().fetchval(
        "SELECT COUNT(*) FROM songs WHERE user_id = $1", user_id
    )
    songs_generated = int(songs_count) if songs_count else 0

    # --- Images ---
    images_count = await get_db_pool().fetchval(
        "SELECT COUNT(*) FROM image_jobs WHERE user_id = $1", user_id
    )
    images_generated = int(images_count) if images_count else 0

    # --- Videos: studio exports, manual exports, YouTube uploads ---
    studio_exports = 0
    manual_exports = 0
    youtube_uploads = 0
    youtube_map: dict[str, int] = {}
    studio_map: dict[str, int] = {}
    manual_map: dict[str, int] = {}
    try:
        studio_exports = int(
            await get_db_pool().fetchval(
                """
                SELECT COALESCE(SUM(daily_count), 0)
                FROM usage_tracking
                WHERE user_id = $1 AND operation_type = 'video'
                """,
                user_id,
            )
            or 0
        )
        manual_exports = int(
            await get_db_pool().fetchval(
                """
                SELECT COALESCE(SUM(daily_count), 0)
                FROM usage_tracking
                WHERE user_id = $1 AND operation_type = 'video_manual'
                """,
                user_id,
            )
            or 0
        )
        studio_rows = await get_db_pool().fetch(
            """
            SELECT usage_date AS d, COALESCE(SUM(daily_count), 0) AS cnt
            FROM usage_tracking
            WHERE user_id = $1
              AND operation_type = 'video'
              AND usage_date >= $2
            GROUP BY usage_date
            ORDER BY usage_date
            """,
            user_id,
            seven_days_ago,
        )
        studio_map = {str(r["d"]): int(r["cnt"]) for r in studio_rows}
        manual_rows = await get_db_pool().fetch(
            """
            SELECT usage_date AS d, COALESCE(SUM(daily_count), 0) AS cnt
            FROM usage_tracking
            WHERE user_id = $1
              AND operation_type = 'video_manual'
              AND usage_date >= $2
            GROUP BY usage_date
            ORDER BY usage_date
            """,
            user_id,
            seven_days_ago,
        )
        manual_map = {str(r["d"]): int(r["cnt"]) for r in manual_rows}
    except Exception:
        studio_exports = 0
        manual_exports = 0

    try:
        youtube_uploads = int(
            await get_db_pool().fetchval(
                """
                SELECT COUNT(*) FROM youtube_upload_jobs
                WHERE user_id = $1 AND status = 'success'
                """,
                user_id,
            )
            or 0
        )
        video_rows = await get_db_pool().fetch(
            """
            SELECT DATE(created_at) as d, COUNT(*) as cnt
            FROM youtube_upload_jobs
            WHERE user_id = $1 AND created_at >= $2 AND status = 'success'
            GROUP BY d ORDER BY d
            """,
            user_id,
            seven_days_ago,
        )
        youtube_map = {str(r["d"]): int(r["cnt"]) for r in video_rows}
    except Exception:
        youtube_uploads = 0

    videos_generated = studio_exports + manual_exports
    videos_uploaded = youtube_uploads

    # --- Plans/quotas retired: credits-only tiers ---
    # The dashboard no longer reports plan quota meters. Tier + wallet replace
    # them; keeping the fields at None hides the meters in every client.
    songs_quota = None
    songs_remaining = None
    images_quota = None
    images_remaining = None
    drafts_quota = None
    drafts_remaining = None

    # --- Usage by day (last 7 days) ---
    song_rows = await get_db_pool().fetch(
        """SELECT DATE(created_at) as d, COUNT(*) as cnt
           FROM songs WHERE user_id = $1 AND created_at >= $2
           GROUP BY d ORDER BY d""",
        user_id, seven_days_ago,
    )
    image_rows = await get_db_pool().fetch(
        """SELECT DATE(created_at) as d, COUNT(*) as cnt
           FROM image_jobs WHERE user_id = $1 AND created_at >= $2
           GROUP BY d ORDER BY d""",
        user_id, seven_days_ago,
    )

    song_map = {str(r["d"]): int(r["cnt"]) for r in song_rows}
    image_map = {str(r["d"]): int(r["cnt"]) for r in image_rows}

    usage_by_day = []
    for i in range(7):
        day = (seven_days_ago + timedelta(days=i)).isoformat()
        studio = studio_map.get(day, 0)
        manual = manual_map.get(day, 0)
        youtube = youtube_map.get(day, 0)
        usage_by_day.append(DailyUsage(
            date=day,
            songs=song_map.get(day, 0),
            images=image_map.get(day, 0),
            videos=studio + manual,
            studio_exports=studio,
            manual_exports=manual,
            youtube_uploads=youtube,
        ))

    # --- Recent activity (last 20 events) ---
    recent: list[RecentActivity] = []

    song_events = await get_db_pool().fetch(
        """SELECT created_at as ts, title, status, 'song' as kind
           FROM songs WHERE user_id = $1
           ORDER BY created_at DESC LIMIT 10""",
        user_id,
    )
    for r in song_events:
        recent.append(RecentActivity(
            timestamp=r["ts"],
            kind="Song",
            detail=str(r["title"] or "Untitled"),
            status=str(r["status"]),
        ))

    image_events = await get_db_pool().fetch(
        """SELECT created_at as ts, kind, status, 'image' as kind2
           FROM image_jobs WHERE user_id = $1
           ORDER BY created_at DESC LIMIT 10""",
        user_id,
    )
    for r in image_events:
        recent.append(RecentActivity(
            timestamp=r["ts"],
            kind="Image",
            detail=str(r["kind"]),
            status=str(r["status"]),
        ))

    video_events_rows = []
    try:
        video_events_rows = await get_db_pool().fetch(
            """SELECT created_at as ts, status, 'video' as kind
               FROM youtube_upload_jobs WHERE user_id = $1
               ORDER BY created_at DESC LIMIT 10""",
            user_id,
        )
    except Exception:
        pass
    for r in video_events_rows:
        recent.append(RecentActivity(
            timestamp=r["ts"],
            kind="YouTube",
            detail="YouTube Upload",
            status=str(r["status"]),
        ))

    recent.sort(key=lambda x: x.timestamp, reverse=True)
    recent = recent[:20]

    avg_studio_export_ms = None
    avg_manual_export_ms = None
    last_export_at = None
    try:
        perf_rows = await get_db_pool().fetch(
            """
            SELECT operation_type,
                   AVG(duration_ms)::bigint AS avg_ms,
                   MAX(created_at) AS last_at
            FROM video_export_telemetry
            WHERE user_id = $1
              AND created_at >= $2
              AND duration_ms IS NOT NULL
              AND duration_ms > 0
              AND operation_type IN ('video', 'video_manual')
            GROUP BY operation_type
            """,
            user_id,
            seven_days_ago,
        )
        for row in perf_rows:
            op = str(row["operation_type"] or "")
            avg_ms = int(row["avg_ms"] or 0) if row["avg_ms"] is not None else None
            last_at = row["last_at"]
            if last_at is not None and (last_export_at is None or last_at > last_export_at):
                last_export_at = last_at
            if op == "video":
                avg_studio_export_ms = avg_ms
            elif op == "video_manual":
                avg_manual_export_ms = avg_ms
    except Exception:
        pass

    return DashboardStatsResponse(
        credits_spent=credits_spent,
        credits_remaining=credits_remaining,
        credits_total=credits_total,
        songs_generated=songs_generated,
        songs_remaining=songs_remaining,
        songs_quota=songs_quota,
        images_remaining=images_remaining,
        images_quota=images_quota,
        drafts_remaining=drafts_remaining,
        drafts_quota=drafts_quota,
        images_generated=images_generated,
        studio_exports=studio_exports,
        manual_exports=manual_exports,
        youtube_uploads=youtube_uploads,
        videos_generated=videos_generated,
        videos_uploaded=videos_uploaded,
        avg_studio_export_ms=avg_studio_export_ms,
        avg_manual_export_ms=avg_manual_export_ms,
        last_export_at=last_export_at,
        usage_by_day=usage_by_day,
        recent_activity=recent,
    )
