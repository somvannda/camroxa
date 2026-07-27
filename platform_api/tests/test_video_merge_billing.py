"""Focused tests for video/merge quota + auto-merge branch gating."""

from __future__ import annotations

from platform_api.models.domain import Plan
from platform_api.services.billing_mode_service import (
    counts_toward_merge_quota,
    counts_toward_product_quota,
    counts_toward_video_quota,
    monthly_limit_for_operation,
    quota_operation_type,
    uses_account_daily_quota,
)
from platform_api.services.usage_enforcement_service import UsageEnforcementService


def test_quota_operation_type_video_and_merge() -> None:
    assert quota_operation_type("video") == "video"
    assert quota_operation_type("video_export") == "video"
    assert quota_operation_type("video_manual") == "video"
    assert quota_operation_type("video_merge") == "video_merge"
    assert quota_operation_type("auto_merge") == "video_merge"
    assert counts_toward_video_quota("video")
    assert counts_toward_merge_quota("video_merge")
    assert counts_toward_product_quota("video")
    assert counts_toward_product_quota("video_merge")
    assert uses_account_daily_quota("video")
    assert uses_account_daily_quota("video_merge")
    assert not uses_account_daily_quota("music")


def test_plan_limits_video_merge() -> None:
    plan = Plan(
        name="monthly",
        profile_allowance=2,
        monthly_song_limit=300,
        monthly_image_limit=120,
        monthly_draft_limit=1260,
        monthly_video_limit=300,
        monthly_merge_limit=30,
        daily_video_limit=10,
        daily_merge_limit=1,
    )
    assert monthly_limit_for_operation(plan, "video") == 300
    assert monthly_limit_for_operation(plan, "video_merge") == 30
    assert UsageEnforcementService._get_daily_limit(plan, "video") == 10
    assert UsageEnforcementService._get_daily_limit(plan, "video_merge") == 1
    assert UsageEnforcementService._get_daily_limit(plan, "video", addon_slots=2) == 20
    assert UsageEnforcementService._get_daily_limit(plan, "video_merge", addon_slots=2) == 2
    assert UsageEnforcementService._get_monthly_limit(plan, "video") == 300
    assert UsageEnforcementService._get_monthly_limit(plan, "video_merge") == 30
