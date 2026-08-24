"""Apply profile add-on slots to plan entitlements.

Active and pending add-on slots add profile-creation capacity only.
They must not scale any billing meters (song, draft, image, video, merge)
monthly or daily. Daily per-channel song/image/draft limits stay unchanged;
account-wide daily video/merge stay at the plan values.

Pending add-on slots (profile_addon_pending) allow profile creation only —
quotas activate after onboarding completes and pending moves to active.
"""

from __future__ import annotations

from dataclasses import dataclass

from platform_api.models.domain import Plan
from platform_api.services.plan_tier_pricing_service import (
    MAX_ACCOUNT_CHANNELS,
    PROFILE_ADDON_STEP,
)


@dataclass(frozen=True, slots=True)
class EffectiveEntitlements:
    plan_channels: int
    addon_slots: int
    addon_pending: int
    total_channels: int
    quota_channels: int
    monthly_song_limit: int | None
    monthly_image_limit: int | None
    monthly_draft_limit: int | None
    monthly_video_limit: int | None
    monthly_merge_limit: int | None


def effective_profile_creation_allowance(
    plan: Plan,
    addon_slots: int = 0,
    addon_pending: int = 0,
) -> int:
    """Profiles the user may create (includes paid-but-not-onboarded pending slots)."""
    base = max(0, int(plan.profile_allowance or 0))
    active = max(0, int(addon_slots or 0))
    pending = max(0, int(addon_pending or 0))
    return base + active + pending


def effective_quota_channels(plan: Plan, addon_slots: int = 0) -> int:
    """Channel count for profile capacity (active slots only). Does not scale billing meters."""
    base = max(0, int(plan.profile_allowance or 0))
    active = max(0, int(addon_slots or 0))
    return base + active


def effective_profile_allowance(plan: Plan, addon_slots: int = 0) -> int:
    """Backward-compatible alias for quota channel count."""
    return effective_quota_channels(plan, addon_slots)


def resolve_effective_entitlements(
    plan: Plan,
    addon_slots: int = 0,
    addon_pending: int = 0,
) -> EffectiveEntitlements:
    plan_channels = max(1, int(plan.profile_allowance or 1))
    active = max(0, int(addon_slots or 0))
    pending = max(0, int(addon_pending or 0))
    quota_channels = effective_quota_channels(plan, active)
    return EffectiveEntitlements(
        plan_channels=plan_channels,
        addon_slots=active,
        addon_pending=pending,
        total_channels=plan_channels + active + pending,
        quota_channels=quota_channels,
        monthly_song_limit=plan.monthly_song_limit,
        monthly_image_limit=plan.monthly_image_limit,
        monthly_draft_limit=getattr(plan, "monthly_draft_limit", None),
        monthly_video_limit=getattr(plan, "monthly_video_limit", None),
        monthly_merge_limit=getattr(plan, "monthly_merge_limit", None),
    )


def validate_profile_addon_request(
    *,
    plan: Plan,
    current_addon_slots: int,
    current_addon_pending: int = 0,
    add_channels: int,
) -> None:
    if add_channels <= 0 or add_channels % PROFILE_ADDON_STEP != 0:
        raise ValueError(f"Profile add-ons must be purchased in multiples of {PROFILE_ADDON_STEP}.")
    base = int(plan.profile_allowance or 0)
    new_total = base + int(current_addon_slots or 0) + int(current_addon_pending or 0) + add_channels
    if new_total > MAX_ACCOUNT_CHANNELS:
        raise ValueError(f"Total channel profiles cannot exceed {MAX_ACCOUNT_CHANNELS}.")


def validate_profile_addon_reduction(
    *,
    plan: Plan,
    profile_count: int,
    current_addon_slots: int,
    current_addon_pending: int,
    new_addon_slots: int | None = None,
    new_addon_pending: int | None = None,
) -> None:
    """Block admin add-on removal that would orphan existing channel profiles."""
    active = int(current_addon_slots if new_addon_slots is None else new_addon_slots)
    pending = int(current_addon_pending if new_addon_pending is None else new_addon_pending)
    creation_allowance = effective_profile_creation_allowance(plan, active, pending)
    if profile_count > creation_allowance:
        raise ValueError(
            f"Cannot reduce add-ons: user has {profile_count} channel profile(s) "
            f"but the new profile allowance would be {creation_allowance}. "
            "Delete channel profiles first."
        )
    if new_addon_slots is not None and int(new_addon_slots) < int(current_addon_slots or 0):
        quota_channels = effective_quota_channels(plan, active)
        if profile_count > quota_channels:
            raise ValueError(
                f"Cannot reduce active add-ons: user has {profile_count} channel profile(s) "
                f"but monthly quotas would scale to {quota_channels} channel(s). "
                "Delete channel profiles first."
            )


def effective_monthly_limit_for_operation(
    plan: Plan,
    addon_slots: int,
    operation_type: str,
) -> int | None:
    entitlements = resolve_effective_entitlements(plan, addon_slots)
    normalized = operation_type.strip().lower()
    if normalized in (
        "image_generation",
        "background_image",
        "thumbnail_image",
        "channel_setup",
        "images",
    ):
        return entitlements.monthly_image_limit
    if normalized in ("draft", "lyric", "title", "album", "lyrics", "drafts"):
        return entitlements.monthly_draft_limit
    if normalized in ("video", "video_generation", "video_export", "video_manual", "videos"):
        return entitlements.monthly_video_limit
    if normalized in ("video_merge", "merge", "auto_merge", "merges"):
        return entitlements.monthly_merge_limit
    if normalized in ("text_generation",):
        return None
    return entitlements.monthly_song_limit


def effective_daily_limit_for_operation(
    plan: Plan,
    addon_slots: int,
    operation_type: str,
) -> int:
    """Daily limit for an operation. Add-on slots do not scale any meters."""
    normalized = operation_type.strip().lower()

    if normalized in (
        "image_generation",
        "background_image",
        "thumbnail_image",
        "channel_setup",
        "images",
    ):
        return int(plan.daily_image_limit_per_channel or 0)
    if normalized in ("draft", "lyric", "title", "album", "lyrics", "drafts"):
        return int(getattr(plan, "daily_draft_limit_per_channel", 300) or 300)
    if normalized in ("video", "video_generation", "video_export", "video_manual", "videos"):
        return int(getattr(plan, "daily_video_limit", 10) or 10)
    if normalized in ("video_merge", "merge", "auto_merge", "merges"):
        return int(getattr(plan, "daily_merge_limit", 1) or 1)
    return int(plan.daily_song_limit_per_channel or 0)
