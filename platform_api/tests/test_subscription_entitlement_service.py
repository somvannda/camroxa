"""Tests for profile add-on entitlement validation."""

from __future__ import annotations

import pytest

from platform_api.models.domain import Plan
from platform_api.services.subscription_entitlement_service import (
    effective_daily_limit_for_operation,
    effective_monthly_limit_for_operation,
    validate_profile_addon_reduction,
)


def _plan(profile_allowance: int = 2) -> Plan:
    return Plan(
        id="00000000-0000-0000-0000-000000000001",
        name="Monthly - 2-channel",
        price_cents=7900,
        profile_allowance=profile_allowance,
        is_active=True,
        monthly_song_limit=300,
        monthly_video_limit=300,
        monthly_merge_limit=30,
        daily_song_limit_per_channel=10,
        daily_image_limit_per_channel=2,
        daily_draft_limit_per_channel=21,
        daily_video_limit=10,
        daily_merge_limit=1,
    )


def test_pending_reduction_blocked_when_profiles_exceed_new_allowance() -> None:
    with pytest.raises(ValueError, match="new profile allowance would be 4"):
        validate_profile_addon_reduction(
            plan=_plan(),
            profile_count=5,
            current_addon_slots=0,
            current_addon_pending=4,
            new_addon_pending=2,
        )


def test_pending_reduction_allowed_when_profiles_fit() -> None:
    validate_profile_addon_reduction(
        plan=_plan(),
        profile_count=4,
        current_addon_slots=0,
        current_addon_pending=4,
        new_addon_pending=2,
    )


def test_active_reduction_blocked_when_profiles_exceed_quota_channels() -> None:
    with pytest.raises(ValueError, match="monthly quotas would scale to 2"):
        validate_profile_addon_reduction(
            plan=_plan(),
            profile_count=4,
            current_addon_slots=2,
            current_addon_pending=2,
            new_addon_slots=0,
        )


def test_active_reduction_allowed_when_profiles_fit_quota() -> None:
    validate_profile_addon_reduction(
        plan=_plan(),
        profile_count=2,
        current_addon_slots=2,
        current_addon_pending=0,
        new_addon_slots=0,
    )


def test_active_addon_scales_account_wide_daily_video_merge() -> None:
    plan = _plan()
    assert effective_daily_limit_for_operation(plan, 0, "video") == 10
    assert effective_daily_limit_for_operation(plan, 0, "video_merge") == 1
    assert effective_daily_limit_for_operation(plan, 2, "video") == 20
    assert effective_daily_limit_for_operation(plan, 2, "video_merge") == 2
    assert effective_daily_limit_for_operation(plan, 4, "video") == 30
    assert effective_daily_limit_for_operation(plan, 4, "video_merge") == 3
    assert effective_daily_limit_for_operation(plan, 8, "video") == 50
    assert effective_daily_limit_for_operation(plan, 8, "video_merge") == 5


def test_active_addon_does_not_scale_per_channel_dailies() -> None:
    plan = _plan()
    assert effective_daily_limit_for_operation(plan, 2, "music") == 10
    assert effective_daily_limit_for_operation(plan, 2, "background_image") == 2
    assert effective_daily_limit_for_operation(plan, 2, "draft") == 21


def test_active_addon_scales_period_video_merge() -> None:
    plan = _plan()
    assert effective_monthly_limit_for_operation(plan, 2, "video") == 600
    assert effective_monthly_limit_for_operation(plan, 2, "video_merge") == 60

