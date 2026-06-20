"""Dashboard stats endpoint providing aggregated user metrics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.schemas import DashboardStatsResponse, DailyUsage, RecentActivity
from platform_api.dependencies import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


@router.get("/stats/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(ctx: AuthContext = Depends(get_current_user)) -> DashboardStatsResponse:
    """Return aggregated dashboard statistics for the authenticated user.

    Combines data from credit_wallets, credit_transactions, songs, image_jobs,
    youtube_upload_jobs, and licenses/plan_usage tables.
    """
    user_id = ctx.user_id

    # --- Credits ---
    wallet_row = await get_db_pool().fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1", user_id
    )
    credits_remaining = int(wallet_row["balance"]) if wallet_row else 0

    spent_row = await get_db_pool().fetchval(
        """SELECT COALESCE(SUM(ABS(amount)), 0)
           FROM credit_transactions
           WHERE user_id = $1 AND direction = 'debit'""",
        user_id,
    )
    credits_spent = int(spent_row) if spent_row else 0
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

    # --- Videos (YouTube uploads) — table may not exist yet ---
    videos_generated = 0
    video_map: dict[str, int] = {}
    try:
        videos_count = await get_db_pool().fetchval(
            "SELECT COUNT(*) FROM youtube_upload_jobs WHERE user_id = $1", user_id
        )
        videos_generated = int(videos_count) if videos_count else 0
        video_rows = await get_db_pool().fetch(
            """SELECT DATE(created_at) as d, COUNT(*) as cnt
               FROM youtube_upload_jobs WHERE user_id = $1 AND created_at >= $2
               GROUP BY d ORDER BY d""",
            user_id, seven_days_ago,
        )
        video_map = {str(r["d"]): int(r["cnt"]) for r in video_rows}
    except Exception:
        pass

    # --- License / quota ---
    songs_remaining = None
    songs_quota = None
    license_row = await get_db_pool().fetchrow(
        """SELECT l.id, p.monthly_song_quota
           FROM licenses l
           JOIN plans p ON l.plan_id = p.id
           WHERE l.user_id = $1 AND l.status = 'active'
           ORDER BY l.created_at DESC LIMIT 1""",
        user_id,
    )
    if license_row and license_row["monthly_song_quota"]:
        songs_quota = int(license_row["monthly_song_quota"])
        usage_row = await get_db_pool().fetchval(
            """SELECT songs_used FROM plan_usage
               WHERE user_id = $1 AND license_id = $2
               ORDER BY period_start DESC LIMIT 1""",
            user_id,
            license_row["id"],
        )
        used = int(usage_row) if usage_row else 0
        songs_remaining = max(0, songs_quota - used)

    # --- Usage by day (last 7 days) ---
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).date()

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
        usage_by_day.append(DailyUsage(
            date=day,
            songs=song_map.get(day, 0),
            images=image_map.get(day, 0),
            videos=video_map.get(day, 0),
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
            kind="Video",
            detail="YouTube Upload",
            status=str(r["status"]),
        ))

    recent.sort(key=lambda x: x.timestamp, reverse=True)
    recent = recent[:20]

    return DashboardStatsResponse(
        credits_spent=credits_spent,
        credits_remaining=credits_remaining,
        credits_total=credits_total,
        songs_generated=songs_generated,
        songs_remaining=songs_remaining,
        songs_quota=songs_quota,
        images_generated=images_generated,
        videos_generated=videos_generated,
        usage_by_day=usage_by_day,
        recent_activity=recent,
    )
