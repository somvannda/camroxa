"""Plan billing mode helpers: subscription quota-first vs wallet (lifetime/overage)."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import Plan
from platform_api.models.enums import PlanType


class UsageCountRepoProtocol(Protocol):
    async def get_monthly_count(
        self, user_id: UUID, operation_type: str, period_start: date
    ) -> int: ...


def normalize_plan_name(plan: Plan) -> str:
    return (plan.name or "").strip().lower()


def is_subscription_plan(plan: Plan | None) -> bool:
    """Monthly/yearly plans bill from quota first, not wallet."""
    if plan is None:
        return False
    name = normalize_plan_name(plan)
    if name in (PlanType.MONTHLY, PlanType.YEARLY):
        return True
    return (
        plan.billing_cycle_days is not None
        and plan.monthly_song_limit is not None
        and plan.price_cents > 0
    )


def is_lifetime_plan(plan: Plan | None) -> bool:
    if plan is None:
        return False
    name = normalize_plan_name(plan)
    if name == PlanType.LIFETIME:
        return True
    return plan.billing_cycle_days is None and plan.price_cents > 0


def quota_operation_type(operation_type: str) -> str:
    """Normalize operation types for product-quota counters.

    - ``music`` / Suno → song meter
    - lyric / title / album → draft meter (plan allowance like credits)
    - images → image meter
    - ``video`` → video meter (local export)
    - ``video_merge`` → merge meter (local ffmpeg concat)
    """
    normalized = str(operation_type or "").strip().lower()
    if normalized in ("music", "music_generation", "batch_generation"):
        return "music"
    if normalized in ("lyric", "title", "album", "lyrics", "draft"):
        return "draft"
    if normalized in (
        "image_generation",
        "background_image",
        "thumbnail_image",
        "channel_setup",
    ):
        return "background_image"
    if normalized in ("video", "video_generation", "video_export", "video_manual"):
        return "video"
    if normalized in ("video_merge", "merge", "auto_merge"):
        return "video_merge"
    return normalized or "music"


def usage_storage_type(operation_type: str) -> str:
    """Counter key written to ``usage_tracking`` (may be finer than quota pool).

    Studio/pipeline exports stay on ``video``. Manual Video-page exports use
    ``video_manual`` so dashboards can split the two while sharing one quota.
    """
    normalized = str(operation_type or "").strip().lower()
    if normalized == "video_manual":
        return "video_manual"
    return quota_operation_type(normalized)


def video_usage_counter_types() -> tuple[str, ...]:
    """All usage_tracking keys that consume monthly/daily video allowance."""
    return ("video", "video_manual")


# One Suno submit returns Primary + Secondary channel tracks — two track files.
TRACKS_PER_SONG_PACKAGE = 2


def song_packages_to_tracks(packages: int | None) -> int | None:
    """Display helper: plan song units → deliverable track count."""
    if packages is None:
        return None
    return int(packages) * TRACKS_PER_SONG_PACKAGE


def counts_toward_song_quota(operation_type: str) -> bool:
    """True when this op should +1 the monthly/daily song package counter.

    One +1 = one Suno request = ``TRACKS_PER_SONG_PACKAGE`` deliverable tracks
    (Primary + Secondary channel). Credits also charge music once per request,
    not once per track.
    """
    return quota_operation_type(operation_type) == "music"


def counts_toward_draft_quota(operation_type: str) -> bool:
    """True when this op should +1 the draft allowance (lyric/title/album)."""
    return quota_operation_type(operation_type) == "draft"


def counts_toward_image_quota(operation_type: str) -> bool:
    """True when this op should +1 the image allowance counter."""
    return quota_operation_type(operation_type) == "background_image"


def counts_toward_video_quota(operation_type: str) -> bool:
    """True when this op should +1 the video export allowance counter."""
    return quota_operation_type(operation_type) == "video"


def counts_toward_merge_quota(operation_type: str) -> bool:
    """True when this op should +1 the video merge allowance counter."""
    return quota_operation_type(operation_type) == "video_merge"


def counts_toward_product_quota(operation_type: str) -> bool:
    return (
        counts_toward_song_quota(operation_type)
        or counts_toward_draft_quota(operation_type)
        or counts_toward_image_quota(operation_type)
        or counts_toward_video_quota(operation_type)
        or counts_toward_merge_quota(operation_type)
    )


def uses_account_daily_quota(operation_type: str) -> bool:
    """Video/merge use account-wide daily caps (not daily_per_channel)."""
    return counts_toward_video_quota(operation_type) or counts_toward_merge_quota(
        operation_type
    )


def monthly_limit_for_operation(plan: Plan, operation_type: str) -> int | None:
    quota_op = quota_operation_type(operation_type)
    if quota_op == "text_generation":
        return None
    if quota_op == "background_image":
        return plan.monthly_image_limit
    if quota_op == "draft":
        return getattr(plan, "monthly_draft_limit", None)
    if quota_op == "video":
        return getattr(plan, "monthly_video_limit", None)
    if quota_op == "video_merge":
        return getattr(plan, "monthly_merge_limit", None)
    if quota_op == "music":
        return plan.monthly_song_limit
    return plan.monthly_song_limit


async def subscription_covers_operation(
    *,
    plan: Plan,
    user_id: UUID,
    operation_type: str,
    usage_repo: UsageCountRepoProtocol,
    period_start: date,
    after_reservation: bool = False,
) -> bool:
    """Return True when an active subscriber should not be charged from wallet.

    When ``after_reservation`` is True, the usage counter already includes this
    unit (reserve-then-deduct image path). Coverage uses ``<=`` so the last
    in-quota unit still settles as plan_allowance instead of a false wallet charge.
    Soft monthly overage (count past limit) still returns False → wallet.
    """
    if not is_subscription_plan(plan):
        return False

    quota_op = quota_operation_type(operation_type)
    monthly_limit = monthly_limit_for_operation(plan, operation_type)
    if monthly_limit is None:
        return True

    def _within(count: int) -> bool:
        return count <= monthly_limit if after_reservation else count < monthly_limit

    if quota_op == "background_image":
        monthly_count = await usage_repo.get_monthly_count(
            user_id, "background_image", period_start
        )
        monthly_count += await usage_repo.get_monthly_count(
            user_id, "thumbnail_image", period_start
        )
        return _within(monthly_count)

    if quota_op == "draft":
        draft_count = await usage_repo.get_monthly_count(user_id, "draft", period_start)
        return _within(draft_count)

    if quota_op == "video":
        video_count = await usage_repo.get_monthly_count(user_id, "video", period_start)
        video_count += await usage_repo.get_monthly_count(
            user_id, "video_manual", period_start
        )
        return _within(video_count)

    if quota_op == "video_merge":
        merge_count = await usage_repo.get_monthly_count(
            user_id, "video_merge", period_start
        )
        return _within(merge_count)

    song_count = await usage_repo.get_monthly_count(user_id, "music", period_start)
    return _within(song_count)


async def subscription_covers_batch(
    *,
    plan: Plan,
    user_id: UUID,
    song_count: int,
    usage_repo: UsageCountRepoProtocol,
    period_start: date,
    image_jobs: int = 0,
    draft_ops: int | None = None,
) -> bool:
    """Return True when a batch fits entirely within subscription quotas.

    ``draft_ops`` defaults to lyric+title per song + one album (~2N+1).
    Song meter is checked only when Auto-GSuno will burn songs; callers that
    draft-only may pass song_count=0 for the song check by using draft_ops.
    """
    if not is_subscription_plan(plan):
        return False

    estimated_drafts = draft_ops if draft_ops is not None else max(0, song_count * 2 + 1)
    if estimated_drafts > 0:
        draft_limit = getattr(plan, "monthly_draft_limit", None)
        if draft_limit is not None:
            draft_count = await usage_repo.get_monthly_count(
                user_id, "draft", period_start
            )
            if draft_count + estimated_drafts > draft_limit:
                return False

    if song_count > 0 and plan.monthly_song_limit is not None:
        music_count = await usage_repo.get_monthly_count(user_id, "music", period_start)
        if music_count + song_count > plan.monthly_song_limit:
            return False

    if image_jobs > 0 and plan.monthly_image_limit is not None:
        image_count = await usage_repo.get_monthly_count(
            user_id, "background_image", period_start
        )
        image_count += await usage_repo.get_monthly_count(
            user_id, "thumbnail_image", period_start
        )
        if image_count + image_jobs > plan.monthly_image_limit:
            return False

    return True


async def grant_included_wallet_credits(
    credit_repo: Any,
    *,
    user_id: UUID,
    plan: Plan,
    license_id: UUID,
) -> int:
    """Credit lifetime (wallet) plan included credits once on purchase."""
    from platform_api.services.credit_units import credits_to_units

    display_credits = float(getattr(plan, "included_wallet_credits", 0) or 0)
    if display_credits <= 0 or not is_lifetime_plan(plan):
        return 0

    units = credits_to_units(display_credits)
    if units <= 0:
        return 0

    await credit_repo.add_credits(
        user_id,
        units,
        reason="plan_purchase",
        ref_id=str(license_id),
    )
    return units
