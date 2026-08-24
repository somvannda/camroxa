"""Tests for profile add-on entitlement validation."""

from __future__ import annotations

import pytest

from platform_api.models.domain import Plan
from platform_api.services.subscription_entitlement_service import (
    effective_daily_limit_for_operation,
    effective_monthly_limit_for_operation,
    resolve_effective_entitlements,
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
        monthly_image_limit=60,
        monthly_draft_limit=630,
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


def test_active_addon_does_not_scale_daily_meters() -> None:
    plan = _plan()
    for slots in (0, 2, 4, 8):
        assert effective_daily_limit_for_operation(plan, slots, "video") == 10
        assert effective_daily_limit_for_operation(plan, slots, "video_merge") == 1
        assert effective_daily_limit_for_operation(plan, slots, "music") == 10
        assert effective_daily_limit_for_operation(plan, slots, "background_image") == 2
        assert effective_daily_limit_for_operation(plan, slots, "draft") == 21


def test_active_addon_does_not_scale_period_meters() -> None:
    plan = _plan()
    for slots in (0, 2, 4, 8):
        assert effective_monthly_limit_for_operation(plan, slots, "music") == plan.monthly_song_limit
        assert effective_monthly_limit_for_operation(plan, slots, "images") == plan.monthly_image_limit
        assert effective_monthly_limit_for_operation(plan, slots, "draft") == plan.monthly_draft_limit
        assert effective_monthly_limit_for_operation(plan, slots, "video") == plan.monthly_video_limit
        assert effective_monthly_limit_for_operation(plan, slots, "video_merge") == plan.monthly_merge_limit
    entitlements = resolve_effective_entitlements(plan, addon_slots=4)
    assert entitlements.monthly_song_limit == plan.monthly_song_limit
    assert entitlements.monthly_image_limit == plan.monthly_image_limit
    assert entitlements.monthly_draft_limit == plan.monthly_draft_limit
    assert entitlements.monthly_video_limit == plan.monthly_video_limit
    assert entitlements.monthly_merge_limit == plan.monthly_merge_limit
    assert entitlements.quota_channels == 6
