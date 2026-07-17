"""Tests for extended platform API methods."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared.models.platform import ProgressFilters
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError


@pytest.fixture
def api() -> PlatformApi:
    client = MagicMock()
    return PlatformApi(client)


def test_get_dashboard_overview_aggregates(api: PlatformApi) -> None:
    def _mock_request(path: str, **_kwargs):
        if path == "/users/me":
            return {
                "id": "user-1",
                "email": "user@example.com",
                "email_confirmed": True,
                "display_name": "User",
                "credit_balance": 50,
            }
        if path == "/profiles":
            return [
                {
                    "id": "profile-1",
                    "user_id": "user-1",
                    "name": "Primary",
                }
            ]
        if path == "/licenses/validate":
            return {
                "plan_type": "monthly",
                "profile_allowance": 2,
                "monthly_song_quota": 40,
                "songs_remaining": 30,
                "wallet_balance": 50,
            }
        if path == "/stats/dashboard":
            return {
                "credits_spent": 10,
                "credits_remaining": 40,
                "credits_total": 50,
                "songs_generated": 2,
                "images_generated": 1,
                "videos_generated": 0,
                "usage_by_day": [],
                "recent_activity": [],
            }
        if path == "/credits/quota-status":
            return {
                "songs_remaining": 30,
                "songs_quota": 40,
                "wallet_balance": 50,
                "channels": [
                    {
                        "profile_id": "profile-1",
                        "profile_name": "Primary",
                        "daily_songs_used": 1,
                        "daily_songs_limit": 7,
                        "daily_songs_remaining": 6,
                        "daily_images_used": 0,
                        "daily_images_limit": 7,
                        "daily_images_remaining": 7,
                    }
                ],
            }
        raise AssertionError(f"Unexpected path: {path}")

    api._client.request.side_effect = _mock_request

    overview = api.get_dashboard_overview()
    assert overview.me.email == "user@example.com"
    assert len(overview.profiles) == 1
    assert overview.license is not None
    assert overview.stats.songs_generated == 2
    assert overview.quota is not None
    assert len(overview.quota.channels) == 1


def test_get_me_parses_fractional_credit_balance(api: PlatformApi) -> None:
    api._client.request.return_value = {
        "id": "user-1",
        "email": "user@example.com",
        "email_confirmed": True,
        "display_name": "User",
        "credit_balance": 99014.5678,
        "plan_name": "Monthly",
        "profile_allowance": 2,
        "channel_profile_count": 1,
        "role": "user",
        "status": "active",
        "onboarding_paid": True,
        "created_at": "2026-01-01T00:00:00",
    }

    me = api.get_me()
    assert me.credit_balance == 99014.5678


def test_validate_license_returns_none_on_404(api: PlatformApi) -> None:
    api._client.request.side_effect = PlatformApiError(404, "No license")
    assert api.validate_license() is None


def test_list_progress_passes_query_params(api: PlatformApi) -> None:
    api._client.request.return_value = {
        "rows": [],
        "summary": "Ready",
        "updated_at": "2026-07-07T07:00:00Z",
    }
    filters = ProgressFilters(limit=25, active_only=True, from_date="2026-07-07", to_date="2026-07-07")
    result = api.list_progress(filters)
    assert result.summary == "Ready"
    api._client.request.assert_called_once_with(
        "/progress",
        auth=True,
        params={
            "limit": 25,
            "active_only": True,
            "from_date": "2026-07-07",
            "to_date": "2026-07-07",
        },
    )
