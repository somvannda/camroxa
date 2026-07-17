"""Tests for platform DTO parsing."""

from shared.models.platform import (
    DashboardOverview,
    DashboardStatsResponse,
    ProgressListResponse,
    ProgressRow,
    ValidateLicenseResponse,
    profile_image_mode,
    profile_visibility,
)
from shared.models.auth import ProfileResponse, UserMeResponse


def test_dashboard_stats_parses_usage_and_activity() -> None:
    stats = DashboardStatsResponse.model_validate(
        {
            "credits_spent": 10,
            "credits_remaining": 90,
            "credits_total": 100,
            "songs_generated": 3,
            "usage_by_day": [{"date": "2026-07-07", "songs": 2, "images": 1, "videos": 0}],
            "recent_activity": [
                {
                    "timestamp": "2026-07-07T08:00:00Z",
                    "kind": "Song",
                    "detail": "Track A",
                    "status": "success",
                }
            ],
        }
    )
    assert stats.credits_spent == 10
    assert len(stats.usage_by_day) == 1
    assert stats.recent_activity[0].kind == "Song"


def test_progress_row_parses_meta() -> None:
    payload = ProgressListResponse.model_validate(
        {
            "rows": [
                {
                    "batch": "abc123",
                    "run_date": "2026-07-07",
                    "channel": "Primary",
                    "status": "Generating",
                    "music": "1/5",
                    "image": "PENDING",
                    "converter": "Missing",
                    "merge": "Pending",
                    "youtube": "—",
                    "stage": "Music",
                    "notes": "In progress",
                    "updated": "14:00:00",
                    "meta": {
                        "batch_id": "batch-1",
                        "profile_id": "profile-1",
                        "role": "OK",
                        "expected": 5,
                        "saved": 1,
                    },
                }
            ],
            "summary": "1 rows loaded",
            "updated_at": "2026-07-07T07:00:00Z",
        }
    )
    row = payload.rows[0]
    assert isinstance(row, ProgressRow)
    assert row.meta.expected == 5
    assert row.meta.saved == 1


def test_dashboard_overview_composition() -> None:
    overview = DashboardOverview(
        me=UserMeResponse(
            id="user-1",
            email="user@example.com",
            email_confirmed=True,
            display_name="User",
            credit_balance=100,
        ),
        profiles=[
            ProfileResponse(
                id="profile-1",
                user_id="user-1",
                name="Primary",
                image_config={"mode": "bg_only"},
                youtube_config={"visibility": "private"},
            )
        ],
        license=ValidateLicenseResponse(
            plan_type="monthly",
            profile_allowance=3,
            monthly_song_quota=100,
            songs_remaining=80,
            wallet_balance=100,
        ),
        stats=DashboardStatsResponse(credits_spent=5),
    )
    profile = overview.profiles[0]
    assert profile_image_mode(profile) == "Background only"
    assert profile_visibility(profile) == "private"


def test_user_me_response_accepts_fractional_credit_balance() -> None:
    me = UserMeResponse.model_validate(
        {
            "id": "user-1",
            "email": "user@example.com",
            "email_confirmed": True,
            "display_name": "User",
            "credit_balance": 99014.1234,
            "plan_name": "Monthly",
            "profile_allowance": 2,
            "channel_profile_count": 1,
            "role": "user",
            "status": "active",
            "onboarding_paid": True,
            "created_at": "2026-01-01T00:00:00",
        }
    )
    assert me.credit_balance == 99014.1234
