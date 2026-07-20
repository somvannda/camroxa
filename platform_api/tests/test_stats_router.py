from __future__ import annotations

from datetime import datetime, timezone

import pytest

from platform_api.middleware.auth import AuthContext
from platform_api.routers import stats


class FakeStatsPool:
    async def fetchrow(self, query: str, *args):
        if "FROM credit_wallets" in query:
            return {"balance": 10_000}
        if "FROM licenses l" in query:
            return {
                "id": "license-1",
                "monthly_song_quota": 40,
                "monthly_image_quota": 60,
                "monthly_draft_quota": 100,
            }
        return None

    async def fetchval(self, query: str, *args):
        if "FROM credit_transactions" in query:
            return 5_000
        if "COUNT(*) FROM songs" in query:
            return 8
        if "COUNT(*) FROM image_jobs" in query:
            return 3
        if "FROM youtube_upload_jobs" in query:
            if "status = 'success'" in query:
                return 2
            return 4
        if "operation_type = 'video_manual'" in query:
            return 3
        if "operation_type = 'video'" in query:
            return 5
        if "SELECT songs_used FROM plan_usage" in query:
            return 9
        return 0

    async def fetch(self, query: str, *args):
        if "FROM youtube_upload_jobs" in query:
            return []
        if "FROM usage_tracking" in query:
            return []
        return []


@pytest.mark.asyncio
async def test_dashboard_stats_uses_monthly_song_limit_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _quota_status(**kwargs):
        if kwargs.get("quota_field") == "songs":
            return 40, 31
        if kwargs.get("quota_field") == "images":
            return 60, 55
        return None, None

    monkeypatch.setattr(stats, "get_db_pool", lambda: FakeStatsPool())
    monkeypatch.setattr(
        "platform_api.dependencies.get_plan_repo",
        lambda: object(),
    )
    monkeypatch.setattr(
        "platform_api.dependencies.get_usage_tracking_repo",
        lambda: object(),
    )
    monkeypatch.setattr(
        "platform_api.services.quota_display_service.get_monthly_quota_status",
        _quota_status,
    )

    result = await stats.get_dashboard_stats(
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        )
    )

    assert result.credits_remaining == 1.0
    assert result.credits_spent == 0.5
    assert result.songs_generated == 8
    assert result.images_generated == 3
    assert result.studio_exports == 5
    assert result.manual_exports == 3
    assert result.youtube_uploads == 2
    assert result.videos_generated == 8
    assert result.videos_uploaded == 2
    assert result.songs_quota == 40
    assert result.songs_remaining == 31
    assert result.images_quota == 60
    assert result.images_remaining == 55
    assert isinstance(result.usage_by_day, list)
    assert len(result.usage_by_day) == 7
    today = datetime.now(timezone.utc).date().isoformat()
    assert result.usage_by_day[-1].date == today


class FakePublicStatsPool:
    async def fetchval(self, query: str, *args):
        if "FROM users" in query:
            return 12
        if "FROM channel_profiles" in query:
            return 34
        if "FROM batches" in query:
            return 56
        if "FROM songs" in query:
            return 78
        if "FROM image_jobs" in query:
            return 90
        if "operation_type = 'video_manual'" in query:
            return 7
        if "operation_type = 'video'" in query:
            return 11
        if "FROM youtube_upload_jobs" in query:
            if "status = 'success'" in query:
                return 2
            return 5
        return 0


@pytest.mark.asyncio
async def test_public_stats_returns_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stats, "get_db_pool", lambda: FakePublicStatsPool())

    result = await stats.get_public_stats()

    assert result.users_total == 12
    assert result.profiles_total == 34
    assert result.batches_total == 56
    assert result.songs_total == 78
    assert result.images_total == 90
    assert result.videos_total == 5
    assert result.studio_exports_total == 11
    assert result.manual_exports_total == 7
    assert result.youtube_uploads_total == 2
    assert isinstance(result.updated_at, datetime)
