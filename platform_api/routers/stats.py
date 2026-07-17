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
    try:
        videos_count = await get_db_pool().fetchval("SELECT COUNT(*) FROM youtube_upload_jobs")
        videos_total = int(videos_count) if videos_count else 0
    except Exception:
        videos_total = 0

    return PublicStatsResponse(
        updated_at=now,
        users_total=int(users_total) if users_total else 0,
        profiles_total=int(profiles_total) if profiles_total else 0,
        batches_total=int(batches_total) if batches_total else 0,
        songs_total=int(songs_total) if songs_total else 0,
        images_total=int(images_total) if images_total else 0,
        videos_total=videos_total,
    )


@router.get("/stats/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(ctx: AuthContext = Depends(get_current_user)) -> DashboardStatsResponse:
    """Return aggregated dashboard statistics for the authenticated user.

    Combines data from credit_wallets, credit_transactions, songs, image_jobs,
    youtube_upload_jobs, and licenses/plan_usage tables.
    """
    user_id = ctx.user_id

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).date()

    # --- Credits ---
    wallet_row = await get_db_pool().fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1", user_id
    )
    credits_remaining_units = int(wallet_row["balance"]) if wallet_row else 0

    spent_row = await get_db_pool().fetchval(
        """SELECT COALESCE(SUM(ABS(amount)), 0)
           FROM credit_transactions
           WHERE user_id = $1 AND direction = 'debit'""",
        user_id,
    )
    credits_spent_units = int(spent_row) if spent_row else 0
    credits_remaining = units_to_credits(credits_remaining_units)
    credits_spent = units_to_credits(credits_spent_units)
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
    videos_uploaded = 0
    video_map: dict[str, int] = {}
    try:
        videos_count = await get_db_pool().fetchval(
            "SELECT COUNT(*) FROM youtube_upload_jobs WHERE user_id = $1", user_id
        )
        videos_generated = int(videos_count) if videos_count else 0
        videos_uploaded_count = await get_db_pool().fetchval(
            "SELECT COUNT(*) FROM youtube_upload_jobs WHERE user_id = $1 AND status = 'success'",
            user_id,
        )
        videos_uploaded = int(videos_uploaded_count) if videos_uploaded_count else 0
        video_rows = await get_db_pool().fetch(
            """SELECT DATE(created_at) as d, COUNT(*) as cnt
               FROM youtube_upload_jobs WHERE user_id = $1 AND created_at >= $2
               GROUP BY d ORDER BY d""",
            user_id, seven_days_ago,
        )
        video_map = {str(r["d"]): int(r["cnt"]) for r in video_rows}
    except Exception:
        pass

    # --- License / quota (authoritative: usage_tracking) ---
    from platform_api.dependencies import get_plan_repo, get_usage_tracking_repo
    from platform_api.services.quota_display_service import get_monthly_quota_status

    plan_repo = get_plan_repo()
    usage_repo = get_usage_tracking_repo()
    user_uuid = UUID(user_id)

    songs_quota, songs_remaining = await get_monthly_quota_status(
        user_id=user_uuid,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="songs",
    )
    images_quota, images_remaining = await get_monthly_quota_status(
        user_id=user_uuid,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="images",
    )
    drafts_quota, drafts_remaining = await get_monthly_quota_status(
        user_id=user_uuid,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="drafts",
    )

    if songs_quota is None:
        license_row = await get_db_pool().fetchrow(
            """SELECT l.id, p.monthly_song_limit AS monthly_song_quota
               FROM licenses l
               JOIN plans p ON l.plan_id = p.id
               WHERE l.user_id = $1 AND l.status = 'active'
               ORDER BY l.created_at DESC LIMIT 1""",
            user_id,
        )
        if license_row and license_row["monthly_song_quota"]:
            songs_quota = int(license_row["monthly_song_quota"])
            songs_remaining = songs_quota

    if images_quota is None:
        license_row = await get_db_pool().fetchrow(
            """SELECT l.id, p.monthly_image_limit AS monthly_image_quota
               FROM licenses l
               JOIN plans p ON l.plan_id = p.id
               WHERE l.user_id = $1 AND l.status = 'active'
               ORDER BY l.created_at DESC LIMIT 1""",
            user_id,
        )
        if license_row and license_row["monthly_image_quota"] is not None:
            images_quota = int(license_row["monthly_image_quota"])
            images_remaining = images_quota

    if drafts_quota is None:
        license_row = await get_db_pool().fetchrow(
            """SELECT l.id, p.monthly_draft_limit AS monthly_draft_quota
               FROM licenses l
               JOIN plans p ON l.plan_id = p.id
               WHERE l.user_id = $1 AND l.status = 'active'
               ORDER BY l.created_at DESC LIMIT 1""",
            user_id,
        )
        if license_row and license_row["monthly_draft_quota"] is not None:
            drafts_quota = int(license_row["monthly_draft_quota"])
            drafts_remaining = drafts_quota

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
        images_remaining=images_remaining,
        images_quota=images_quota,
        drafts_remaining=drafts_remaining,
        drafts_quota=drafts_quota,
        images_generated=images_generated,
        videos_generated=videos_generated,
        videos_uploaded=videos_uploaded,
        usage_by_day=usage_by_day,
        recent_activity=recent,
    )
