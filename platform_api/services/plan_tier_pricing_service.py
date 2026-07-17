"""Channel-tier pricing, billing-term totals, and profile add-on quotes.

Pricing model (plans are the single source of truth):
- Subscription plans (`plan_kind=subscription`) define checkout prices and quotas.
- Profile add-on plans (`plan_kind=profile_addon`) define add-on bundle checkout prices.
- The 2-channel monthly subscription plan is the pricing anchor for admin calculators.
- Term discounts are applied when creating plan rows, not stored in a separate config.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from platform_api.services.channel_pricing_config_service import (
    ChannelPricingConfig,
    default_channel_pricing_config,
)

TIER_CHANNEL_ANCHORS: tuple[int, ...] = (2, 6, 10)
MAX_ACCOUNT_CHANNELS: int = 10
PROFILE_ADDON_STEP: int = 2
SEMI_ANNUAL_MONTHS: int = 6
ANNUAL_MONTHS: int = 12
SEMI_ANNUAL_DISCOUNT: float = 0.15
ANNUAL_DISCOUNT: float = 0.25


@dataclass(frozen=True, slots=True)
class PlanQuotaTemplate:
    profile_allowance: int
    monthly_song_limit: int | None
    monthly_image_limit: int | None
    monthly_draft_limit: int | None
    monthly_video_limit: int | None
    monthly_merge_limit: int | None
    daily_song_limit_per_channel: int
    daily_image_limit_per_channel: int
    daily_draft_limit_per_channel: int
    daily_video_limit: int
    daily_merge_limit: int


@dataclass(frozen=True, slots=True)
class BillingTermQuote:
    label: str
    billing_cycle_days: int
    total_cents: int
    monthly_equivalent_cents: int
    discount_percent: int


@dataclass(frozen=True, slots=True)
class ProfileAddonQuote:
    current_channels: int
    addon_channels: int
    new_total_channels: int
    monthly_addon_cents: int
    capped_by_tier: bool
    next_tier_channels: int | None
    next_tier_monthly_cents: int | None


def round_whole_dollars(cents: int) -> int:
    if cents <= 0:
        return 0
    return int(ceil(cents / 100)) * 100


def scale_int_limit(value: int | None, *, from_channels: int, to_channels: int) -> int | None:
    if value is None:
        return None
    if from_channels <= 0 or to_channels <= 0:
        return value
    ratio = to_channels / from_channels
    return max(0, int(round(value * ratio)))


def scale_plan_quotas(template: PlanQuotaTemplate, target_channels: int) -> PlanQuotaTemplate:
    from_channels = max(1, template.profile_allowance)
    target = max(1, target_channels)
    return PlanQuotaTemplate(
        profile_allowance=target,
        monthly_song_limit=scale_int_limit(
            template.monthly_song_limit, from_channels=from_channels, to_channels=target
        ),
        monthly_image_limit=scale_int_limit(
            template.monthly_image_limit, from_channels=from_channels, to_channels=target
        ),
        monthly_draft_limit=scale_int_limit(
            template.monthly_draft_limit, from_channels=from_channels, to_channels=target
        ),
        monthly_video_limit=scale_int_limit(
            template.monthly_video_limit, from_channels=from_channels, to_channels=target
        ),
        monthly_merge_limit=scale_int_limit(
            template.monthly_merge_limit, from_channels=from_channels, to_channels=target
        ),
        daily_song_limit_per_channel=template.daily_song_limit_per_channel,
        daily_image_limit_per_channel=template.daily_image_limit_per_channel,
        daily_draft_limit_per_channel=template.daily_draft_limit_per_channel,
        daily_video_limit=scale_int_limit(
            template.daily_video_limit, from_channels=from_channels, to_channels=target
        )
        or template.daily_video_limit,
        daily_merge_limit=scale_int_limit(
            template.daily_merge_limit, from_channels=from_channels, to_channels=target
        )
        or template.daily_merge_limit,
    )


def tier_monthly_price_cents(
    base_monthly_cents: int,
    *,
    base_channels: int = TIER_CHANNEL_ANCHORS[0],
    target_channels: int,
) -> int:
    _ = base_channels
    return linear_plan_monthly_from_base(
        base_monthly_cents=base_monthly_cents,
        channel_count=target_channels,
    )


def build_tier_monthly_prices(
    base_monthly_cents: int,
    *,
    base_channels: int = TIER_CHANNEL_ANCHORS[0],
    anchors: tuple[int, ...] = TIER_CHANNEL_ANCHORS,
) -> dict[int, int]:
    _ = base_channels
    return {
        channels: linear_plan_monthly_from_base(
            base_monthly_cents=base_monthly_cents,
            channel_count=channels,
        )
        for channels in anchors
    }


def interpolate_tier_price(channel_count: int, tier_prices: dict[int, int]) -> int:
    if channel_count <= 0:
        return 0
    if channel_count in tier_prices:
        return tier_prices[channel_count]
    block_cents = tier_prices.get(2) or tier_prices.get(min(tier_prices))
    if block_cents is None:
        return 0
    pairs = channel_count / PROFILE_ADDON_STEP
    return round_whole_dollars(int(round(block_cents * pairs)))


def next_tier_anchor(channel_count: int, anchors: tuple[int, ...] = TIER_CHANNEL_ANCHORS) -> int | None:
    for anchor in anchors:
        if anchor > channel_count:
            return anchor
    return None


PLAN_KIND_SUBSCRIPTION = "subscription"
PLAN_KIND_PROFILE_ADDON = "profile_addon"


def is_subscription_plan(plan: Any) -> bool:
    return str(getattr(plan, "plan_kind", PLAN_KIND_SUBSCRIPTION) or PLAN_KIND_SUBSCRIPTION) == PLAN_KIND_SUBSCRIPTION


def is_profile_addon_plan(plan: Any) -> bool:
    return str(getattr(plan, "plan_kind", "") or "") == PLAN_KIND_PROFILE_ADDON


def subscription_plans(plans: list[Any]) -> list[Any]:
    return [plan for plan in plans if is_subscription_plan(plan)]


def profile_addon_plans(plans: list[Any]) -> list[Any]:
    return [plan for plan in plans if is_profile_addon_plan(plan)]


def find_profile_addon_plan(
    plans: list[Any],
    addon_channels: int,
    *,
    billing_cycle_days: int | None = 30,
) -> Any | None:
    """Return the active profile add-on plan row for a bundle size."""
    if addon_channels <= 0 or addon_channels % PROFILE_ADDON_STEP != 0:
        return None

    def _matches(plan: Any, *, require_cycle: bool) -> bool:
        if not is_profile_addon_plan(plan) or not bool(getattr(plan, "is_active", False)):
            return False
        if int(getattr(plan, "profile_allowance", 0) or 0) != addon_channels:
            return False
        if require_cycle and billing_cycle_days is not None:
            return int(getattr(plan, "billing_cycle_days", 0) or 0) == billing_cycle_days
        return True

    exact = [plan for plan in plans if _matches(plan, require_cycle=True)]
    if exact:
        exact.sort(key=lambda plan: int(getattr(plan, "price_cents", 0) or 0))
        return exact[0]

    fallback = [plan for plan in plans if _matches(plan, require_cycle=False)]
    if not fallback:
        return None
    fallback.sort(
        key=lambda plan: (
            0 if int(getattr(plan, "billing_cycle_days", 0) or 0) == 30 else 1,
            int(getattr(plan, "price_cents", 0) or 0),
        )
    )
    return fallback[0]


def linear_plan_monthly_from_base(*, base_monthly_cents: int, channel_count: int) -> int:
    pairs = max(0, channel_count // PROFILE_ADDON_STEP)
    return pairs * base_monthly_cents


def quote_profile_addon_from_plan(
    *,
    current_channels: int,
    addon_channels: int,
    addon_plan: Any,
) -> ProfileAddonQuote:
    new_total = current_channels + addon_channels
    return ProfileAddonQuote(
        current_channels=current_channels,
        addon_channels=addon_channels,
        new_total_channels=new_total,
        monthly_addon_cents=round_whole_dollars(int(getattr(addon_plan, "price_cents", 0) or 0)),
        capped_by_tier=False,
        next_tier_channels=next_tier_anchor(current_channels),
        next_tier_monthly_cents=None,
    )


def quote_profile_addon_for_subscription(
    *,
    current_channels: int,
    addon_channels: int,
    addon_plan: Any,
    subscription_billing_cycle_days: int,
    semi_annual_discount_percent: int = 15,
    annual_discount_percent: int = 25,
) -> ProfileAddonQuote:
    """Quote add-on checkout aligned to the subscriber's billing term."""
    monthly_cents = round_whole_dollars(int(getattr(addon_plan, "price_cents", 0) or 0))
    addon_cycle = int(getattr(addon_plan, "billing_cycle_days", 0) or 0)
    sub_cycle = int(subscription_billing_cycle_days or 30)

    if sub_cycle in (180, 365) and addon_cycle == sub_cycle:
        checkout_cents = monthly_cents
    elif sub_cycle == 30:
        checkout_cents = monthly_cents
    else:
        terms = billing_term_quotes(
            monthly_cents,
            semi_annual_discount_percent=semi_annual_discount_percent,
            annual_discount_percent=annual_discount_percent,
        )
        by_cycle = {term.billing_cycle_days: term for term in terms}
        checkout_cents = by_cycle.get(sub_cycle, terms[0]).total_cents

    new_total = current_channels + addon_channels
    return ProfileAddonQuote(
        current_channels=current_channels,
        addon_channels=addon_channels,
        new_total_channels=new_total,
        monthly_addon_cents=checkout_cents,
        capped_by_tier=False,
        next_tier_channels=next_tier_anchor(current_channels),
        next_tier_monthly_cents=None,
    )


def find_two_channel_monthly_base(plans: list[Any]) -> Any | None:
    candidates = [
        plan
        for plan in subscription_plans(plans)
        if bool(getattr(plan, "is_active", False))
        and int(getattr(plan, "profile_allowance", 0) or 0) == 2
        and int(getattr(plan, "billing_cycle_days", 0) or 0) == 30
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda plan: int(getattr(plan, "price_cents", 0) or 0))
    return candidates[0]


def quote_profile_addon_monthly(
    *,
    current_channels: int,
    addon_channels: int = PROFILE_ADDON_STEP,
    base_monthly_cents: int,
    base_channels: int = TIER_CHANNEL_ANCHORS[0],
    anchors: tuple[int, ...] = TIER_CHANNEL_ANCHORS,
    pricing_config: ChannelPricingConfig | None = None,
) -> ProfileAddonQuote:
    _ = base_channels, anchors, base_monthly_cents
    if addon_channels <= 0 or addon_channels % PROFILE_ADDON_STEP != 0:
        raise ValueError(f"Profile add-ons must be purchased in multiples of {PROFILE_ADDON_STEP}.")

    config = pricing_config or default_channel_pricing_config()
    new_total = current_channels + addon_channels
    fixed_price = round_whole_dollars(config.addon_price_cents(addon_channels))

    return ProfileAddonQuote(
        current_channels=current_channels,
        addon_channels=addon_channels,
        new_total_channels=new_total,
        monthly_addon_cents=fixed_price,
        capped_by_tier=False,
        next_tier_channels=next_tier_anchor(current_channels),
        next_tier_monthly_cents=None,
    )


def billing_term_quotes(
    monthly_cents: int,
    *,
    semi_annual_discount_percent: int = 15,
    annual_discount_percent: int = 25,
    pricing_config: ChannelPricingConfig | None = None,
) -> list[BillingTermQuote]:
    config = pricing_config or default_channel_pricing_config()
    semi_rate = (
        semi_annual_discount_percent
        if pricing_config is None
        else config.semi_annual_discount_percent
    )
    annual_rate = (
        annual_discount_percent
        if pricing_config is None
        else config.annual_discount_percent
    )
    if monthly_cents <= 0:
        return []

    monthly = round_whole_dollars(monthly_cents)
    semi_discount = semi_rate / 100
    annual_discount = annual_rate / 100

    semi_total = round_whole_dollars(int(round(monthly * SEMI_ANNUAL_MONTHS * (1 - semi_discount))))
    annual_total = round_whole_dollars(int(round(monthly * ANNUAL_MONTHS * (1 - annual_discount))))

    return [
        BillingTermQuote(
            label="Monthly",
            billing_cycle_days=30,
            total_cents=monthly,
            monthly_equivalent_cents=monthly,
            discount_percent=0,
        ),
        BillingTermQuote(
            label=f"6 Months ({semi_rate}% OFF)",
            billing_cycle_days=180,
            total_cents=semi_total,
            monthly_equivalent_cents=round_whole_dollars(int(round(semi_total / SEMI_ANNUAL_MONTHS))),
            discount_percent=semi_rate,
        ),
        BillingTermQuote(
            label=f"Annual ({annual_rate}% OFF)",
            billing_cycle_days=365,
            total_cents=annual_total,
            monthly_equivalent_cents=round_whole_dollars(int(round(annual_total / ANNUAL_MONTHS))),
            discount_percent=annual_rate,
        ),
    ]


def combined_billing_term_quotes(
    *,
    plan_monthly_cents: int,
    addon_monthly_cents: int = 0,
    pricing_config: ChannelPricingConfig | None = None,
) -> list[BillingTermQuote]:
    combined = round_whole_dollars(plan_monthly_cents + addon_monthly_cents)
    return billing_term_quotes(combined, pricing_config=pricing_config)


def quota_multiplier(*, plan_channels: int, addon_slots: int) -> float:
    if plan_channels <= 0:
        return 1.0
    return max(1.0, (plan_channels + max(0, addon_slots)) / plan_channels)


def scaled_monthly_limit(base_limit: int | None, *, plan_channels: int, addon_slots: int) -> int | None:
    if base_limit is None:
        return None
    return max(0, int(round(base_limit * quota_multiplier(plan_channels=plan_channels, addon_slots=addon_slots))))


def max_profile_addon_slots(*, plan_channels: int, max_total_channels: int = MAX_ACCOUNT_CHANNELS) -> int:
    remaining = max(0, max_total_channels - plan_channels)
    return remaining - (remaining % PROFILE_ADDON_STEP)


def required_addon_steps(current_total: int, target_total: int) -> int:
    delta = target_total - current_total
    if delta <= 0:
        return 0
    return int(ceil(delta / PROFILE_ADDON_STEP))
