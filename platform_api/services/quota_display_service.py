"""Read subscription quota status from usage_tracking (authoritative for enforcement)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import Plan
from platform_api.services.billing_mode_service import (
    quota_operation_type,
    song_packages_to_tracks,
)
from platform_api.services.billing_period_service import (
    ActiveSubscriptionContext,
    period_start_for_subscription,
)
from platform_api.services.subscription_entitlement_service import (
    effective_monthly_limit_for_operation,
)


class UsageCountRepoProtocol(Protocol):
    async def get_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int: ...

    async def get_monthly_count(
        self, user_id: UUID, operation_type: str, period_start: date
    ) -> int: ...


class PlanRepoProtocol(Protocol):
    async def get_user_active_subscription_context(
        self, user_id: UUID
    ) -> ActiveSubscriptionContext | None: ...

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None: ...


class ProfileRepoProtocol(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Any]: ...


class CreditRepoProtocol(Protocol):
    async def get_balance(self, user_id: UUID | str) -> int: ...


@dataclass(frozen=True, slots=True)
class ChannelDailyQuota:
    profile_id: str
    profile_name: str
    daily_songs_used: int
    daily_songs_limit: int
    daily_songs_remaining: int
    daily_images_used: int
    daily_images_limit: int
    daily_images_remaining: int


async def resolve_subscription_context(
    plan_repo: PlanRepoProtocol,
    user_id: UUID,
) -> ActiveSubscriptionContext | None:
    getter = getattr(plan_repo, "get_user_active_subscription_context", None)
    if getter is not None:
        ctx = await getter(user_id)
        if ctx is not None:
            return ctx
    plan = await plan_repo.get_user_active_plan(user_id)
    if plan is None:
        return None
    return ActiveSubscriptionContext(
        plan=plan,
        license_id=UUID(int=0),
        activated_at=None,
    )


def period_start_for_context(
    ctx: ActiveSubscriptionContext | None,
    reference_date: date | None = None,
) -> date:
    today = reference_date or date.today()
    if ctx is None:
        return today.replace(day=1)
    return period_start_for_subscription(
        plan=ctx.plan,
        activated_at=ctx.activated_at,
        reference_date=today,
    )


async def get_monthly_quota_status(
    *,
    user_id: UUID,
    plan_repo: PlanRepoProtocol,
    usage_repo: UsageCountRepoProtocol,
    quota_field: str,
) -> tuple[int | None, int | None]:
    """Return (quota_limit, remaining) for songs (Suno packages), drafts, or images."""
    ctx = await resolve_subscription_context(plan_repo, user_id)
    if ctx is None:
        return None, None

    plan = ctx.plan
    addon_slots = int(getattr(ctx, "profile_addon_slots", 0) or 0)
    if quota_field == "songs":
        # Suno packages (1 package = Primary + Secondary channel tracks). Credits also bill once per package.
        limit = effective_monthly_limit_for_operation(plan, addon_slots, "music")
        operation_type = "music"
    elif quota_field == "tracks":
        # Display-only: packages × TRACKS_PER_SONG_PACKAGE
        pkg_limit, pkg_remaining = await get_monthly_quota_status(
            user_id=user_id,
            plan_repo=plan_repo,
            usage_repo=usage_repo,
            quota_field="songs",
        )
        return song_packages_to_tracks(pkg_limit), song_packages_to_tracks(pkg_remaining)
    elif quota_field == "drafts":
        limit = effective_monthly_limit_for_operation(plan, addon_slots, "draft")
        operation_type = "draft"
    elif quota_field == "images":
        limit = effective_monthly_limit_for_operation(plan, addon_slots, "background_image")
        operation_type = "background_image"
    elif quota_field == "videos":
        limit = effective_monthly_limit_for_operation(plan, addon_slots, "video")
        operation_type = "video"
    elif quota_field == "merges":
        limit = effective_monthly_limit_for_operation(plan, addon_slots, "video_merge")
        operation_type = "video_merge"
    else:
        return None, None

    if limit is None:
        return None, None

    period_start = period_start_for_context(ctx)
    used = await usage_repo.get_monthly_count(user_id, operation_type, period_start)
    if quota_field == "images":
        used += await usage_repo.get_monthly_count(
            user_id, "thumbnail_image", period_start
        )
    remaining = max(0, int(limit) - used)
    return int(limit), remaining


async def get_plan_quota_remaining(
    *,
    user_id: UUID,
    plan_repo: PlanRepoProtocol,
    usage_repo: UsageCountRepoProtocol,
) -> int | None:
    """Primary plan quota remaining — songs first, else images."""
    songs_quota, songs_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="songs",
    )
    if songs_remaining is not None:
        return songs_remaining
    _images_quota, images_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="images",
    )
    return images_remaining


async def user_has_generation_capacity(
    *,
    user_id: UUID,
    credit_repo: CreditRepoProtocol,
    plan_repo: PlanRepoProtocol,
    usage_repo: UsageCountRepoProtocol,
    min_credits: int = 1,
) -> bool:
    """True when the user can start generation via wallet or subscription quota."""
    balance = await credit_repo.get_balance(user_id)
    if balance >= min_credits:
        return True
    remaining = await get_plan_quota_remaining(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
    )
    return remaining is not None and remaining > 0


async def get_channel_daily_quotas(
    *,
    user_id: UUID,
    plan_repo: PlanRepoProtocol,
    usage_repo: UsageCountRepoProtocol,
    profile_repo: ProfileRepoProtocol,
    usage_date: date | None = None,
) -> list[ChannelDailyQuota]:
    """Per-channel daily song/image usage and remaining capacity."""
    ctx = await resolve_subscription_context(plan_repo, user_id)
    if ctx is None:
        return []

    plan = ctx.plan
    today = usage_date or date.today()
    profiles = await profile_repo.list_for_user(user_id)
    channels: list[ChannelDailyQuota] = []
    for profile in profiles:
        profile_id = getattr(profile, "id", None)
        if profile_id is None:
            continue
        songs_used = await usage_repo.get_daily_count(
            user_id, profile_id, "music", today
        )
        images_used = await usage_repo.get_daily_count(
            user_id, profile_id, "background_image", today
        )
        images_used += await usage_repo.get_daily_count(
            user_id, profile_id, "thumbnail_image", today
        )
        songs_limit = int(plan.daily_song_limit_per_channel or 0)
        images_limit = int(plan.daily_image_limit_per_channel or 0)
        channels.append(
            ChannelDailyQuota(
                profile_id=str(profile_id),
                profile_name=str(getattr(profile, "name", "") or "Channel"),
                daily_songs_used=songs_used,
                daily_songs_limit=songs_limit,
                daily_songs_remaining=max(0, songs_limit - songs_used),
                daily_images_used=images_used,
                daily_images_limit=images_limit,
                daily_images_remaining=max(0, images_limit - images_used),
            )
        )
    return channels
