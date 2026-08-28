"""Plans router endpoints.

Provides Admin endpoints for plan management: listing plans, updating
plan configuration, and managing promotional offers.

Requirements: 1.1, 1.2, 1.4, 4.1, 4.2, 4.10, 4.12
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from platform_api.dependencies import (
    get_ai_routing_service,
    get_credit_pricing_service,
    get_db_pool,
    get_v3_billing_service,
)
from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.license_repo import PlanRepository
from platform_api.services.pricing_display import (
    resolve_pricing_credit_lines,
    resolve_pricing_features,
)
from platform_api.services.plan_term_discount_service import (
    PlanTermDiscounts,
    load_plan_term_discounts,
    save_plan_term_discounts,
)
from platform_api.services.plan_tier_pricing_service import (
    MAX_ACCOUNT_CHANNELS,
    PROFILE_ADDON_STEP,
    find_profile_addon_plan,
    find_two_channel_monthly_base,
    linear_plan_monthly_from_base,
    max_profile_addon_slots,
    quote_profile_addon_from_plan,
    subscription_plans,
)
from platform_api.services.plan_validation import (
    validate_paid_recurring_finite_meters,
    validate_plan_limits,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/plans", tags=["plans"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    """Response model for a plan configuration."""

    id: str
    name: str
    price_cents: int
    billing_cycle_days: int | None = None
    profile_allowance: int
    monthly_song_limit: int | None = None
    monthly_image_limit: int | None = None
    monthly_draft_limit: int | None = None
    monthly_video_limit: int | None = None
    monthly_merge_limit: int | None = None
    daily_song_limit_per_channel: int
    daily_image_limit_per_channel: int
    daily_draft_limit_per_channel: int = 300
    daily_video_limit: int = 10
    daily_merge_limit: int = 1
    monthly_credits: int = 0
    daily_credits: int = 0
    is_public: bool = False
    is_active: bool
    effective_from: datetime
    created_at: datetime
    updated_at: datetime
    subscriber_count: int = 0
    can_delete: bool = False
    plan_kind: str = "subscription"
    plan_type: str = "desktop_pro"


class PublicPlanOfferResponse(BaseModel):
    """Public-facing promotional offer summary for a plan."""

    id: str
    promo_price_cents: int
    max_redemptions: int
    current_redemptions: int
    remaining_redemptions: int
    is_active: bool


class PublicPlanResponse(BaseModel):
    """Public plan details for website and onboarding pricing surfaces."""

    id: str
    name: str
    price_cents: int
    effective_price_cents: int
    billing_cycle_days: int | None = None
    profile_allowance: int
    monthly_song_limit: int | None = None
    monthly_image_limit: int | None = None
    monthly_draft_limit: int | None = None
    monthly_video_limit: int | None = None
    monthly_merge_limit: int | None = None
    daily_song_limit_per_channel: int
    daily_image_limit_per_channel: int
    daily_draft_limit_per_channel: int = 300
    daily_video_limit: int = 10
    daily_merge_limit: int = 1
    included_wallet_credits: float = 0
    monthly_credits: int = 0
    daily_credits: int = 0
    pricing_features: list[str] = Field(default_factory=list)
    pricing_credit_lines: list[str] = Field(default_factory=list)
    credits_per_generate: float | None = None
    offer: PublicPlanOfferResponse | None = None


class UpdatePlanRequest(BaseModel):
    """Partial plan update — only provided fields are changed."""

    price_cents: int | None = Field(default=None, ge=0, description="Price in cents")
    profile_allowance: int | None = Field(default=None, ge=1, description="Max channel profiles")
    monthly_song_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly Suno package limit — 1 request = Primary + Secondary channel (2 tracks); None for unlimited",
    )
    monthly_image_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly image limit — BG+TH pool (None for unlimited)",
    )
    monthly_draft_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly draft limit — 1 draft = one lyric, title, or album call (None for unlimited)",
    )
    monthly_video_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly video export limit — account pool (None for unlimited)",
    )
    monthly_merge_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly video merge limit — account pool (None for unlimited)",
    )
    daily_song_limit_per_channel: int | None = Field(
        default=None,
        ge=1,
        le=1_000,
        description="Daily Suno package limit per channel",
    )
    daily_image_limit_per_channel: int | None = Field(
        default=None,
        ge=1,
        le=1_000,
        description="Daily image limit per channel (BG+TH)",
    )
    daily_draft_limit_per_channel: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
        description="Daily draft limit per channel (lyric/title/album pool)",
    )
    daily_video_limit: int | None = Field(
        default=None,
        ge=1,
        le=1_000,
        description="Daily video export limit (account-wide)",
    )
    daily_merge_limit: int | None = Field(
        default=None,
        ge=1,
        le=1_000,
        description="Daily video merge limit (account-wide)",
    )
    billing_cycle_days: int | None = Field(default=None, ge=1, description="Billing cycle in days")
    is_active: bool | None = Field(default=None, description="Whether the plan accepts new licenses")


class OfferResponse(BaseModel):
    """Response model for a promotional offer."""

    id: str
    plan_id: str
    promo_price_cents: int
    max_redemptions: int
    current_redemptions: int
    is_active: bool
    created_at: datetime


class CreateOfferRequest(BaseModel):
    """Body for creating a new promotional offer."""

    plan_id: str = Field(..., description="UUID of the plan this offer applies to")
    promo_price_cents: int = Field(..., ge=0, description="Promotional price in cents")
    max_redemptions: int = Field(..., ge=1, description="Maximum number of redemptions")


class PublicUsageRateItem(BaseModel):
    operation_type: str
    label: str
    credits_per_operation: float | None = None
    available: bool = True
    message: str | None = None


class PublicUsageRatesResponse(BaseModel):
    updated_at: str
    items: list[PublicUsageRateItem]
    estimated_full_song_credits: float | None = None
    disclaimer: str


class PublicProfileAddonQuoteResponse(BaseModel):
    """Public quote for purchasing +2 channel profile add-ons."""

    current_channels: int
    addon_channels: int
    new_total_channels: int
    monthly_addon_cents: int
    capped_by_tier: bool
    next_tier_channels: int | None = None
    next_tier_monthly_cents: int | None = None
    max_addon_channels_remaining: int
    two_channel_block_cents: int
    linear_plan_monthly_cents: int
    addon_plan_id: str | None = None
    base_plan_id: str | None = None


class PlanTermDiscountsResponse(BaseModel):
    semi_annual_discount_percent: int
    annual_discount_percent: int


class PublicPlanTermDiscountsResponse(BaseModel):
    semi_annual_discount_percent: int
    annual_discount_percent: int


class UpdatePlanTermDiscountsRequest(BaseModel):
    semi_annual_discount_percent: int = Field(..., ge=0, le=50)
    annual_discount_percent: int = Field(..., ge=0, le=50)


class SyncTermPlanPricesResponse(BaseModel):
    updated_plan_ids: list[str]
    skipped: list[str]


class PlanPriceDriftItemResponse(BaseModel):
    plan_id: str
    plan_name: str
    billing_cycle_days: int
    profile_allowance: int
    stored_cents: int
    expected_cents: int
    plan_kind: str


class PlanPriceDriftResponse(BaseModel):
    drift_count: int
    items: list[PlanPriceDriftItemResponse] = Field(default_factory=list)


class CreatePlanRequest(BaseModel):
    """Body for creating a new subscription plan."""

    name: str = Field(..., min_length=1, max_length=50, description="Plan name (unique)")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    profile_allowance: int = Field(..., ge=1, description="Max channel profiles")
    monthly_song_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly Suno package limit — 1 request = Primary + Secondary channel (2 tracks); None for unlimited",
    )
    monthly_image_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly image limit — BG+TH pool (None for unlimited)",
    )
    monthly_draft_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly draft limit — 1 draft = one lyric, title, or album call (None for unlimited)",
    )
    monthly_video_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly video export limit — account pool (None for unlimited)",
    )
    monthly_merge_limit: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Monthly video merge limit — account pool (None for unlimited)",
    )
    billing_cycle_days: int | None = Field(default=None, ge=1, description="Billing cycle in days (None for lifetime)")
    daily_song_limit_per_channel: int = Field(
        default=7,
        ge=1,
        le=1_000,
        description="Daily Suno package limit per channel",
    )
    daily_image_limit_per_channel: int = Field(
        default=7,
        ge=1,
        le=1_000,
        description="Daily image limit per channel (BG+TH)",
    )
    daily_draft_limit_per_channel: int = Field(
        default=300,
        ge=1,
        le=10_000,
        description="Daily draft limit per channel (lyric/title/album pool)",
    )
    daily_video_limit: int = Field(
        default=10,
        ge=1,
        le=1_000,
        description="Daily video export limit (account-wide)",
    )
    daily_merge_limit: int = Field(
        default=1,
        ge=1,
        le=1_000,
        description="Daily video merge limit (account-wide)",
    )
    plan_kind: str = Field(
        default="subscription",
        description="subscription = base plan row; profile_addon = add-on bundle checkout row",
    )


# ---------------------------------------------------------------------------
# Placeholder Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_plan_repo() -> PlanRepository:
    """Placeholder dependency for PlanRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "PlanRepository dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
PlanRepoDep = Annotated[PlanRepository, Depends(_get_plan_repo)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_to_response(plan: Any, *, subscriber_count: int = 0) -> PlanResponse:
    """Convert a domain Plan object to the response model."""
    return PlanResponse(
        id=str(plan.id),
        name=plan.name,
        price_cents=plan.price_cents,
        billing_cycle_days=plan.billing_cycle_days,
        profile_allowance=plan.profile_allowance,
        monthly_song_limit=plan.monthly_song_limit,
        monthly_image_limit=plan.monthly_image_limit,
        monthly_draft_limit=getattr(plan, "monthly_draft_limit", None),
        monthly_video_limit=getattr(plan, "monthly_video_limit", None),
        monthly_merge_limit=getattr(plan, "monthly_merge_limit", None),
        daily_song_limit_per_channel=plan.daily_song_limit_per_channel,
        daily_image_limit_per_channel=plan.daily_image_limit_per_channel,
        daily_draft_limit_per_channel=int(
            getattr(plan, "daily_draft_limit_per_channel", 300) or 300
        ),
        daily_video_limit=int(getattr(plan, "daily_video_limit", 10) or 10),
        daily_merge_limit=int(getattr(plan, "daily_merge_limit", 1) or 1),
        monthly_credits=int(getattr(plan, "monthly_credits", 0) or 0),
        daily_credits=int(getattr(plan, "daily_credits", 0) or 0),
        is_public=bool(getattr(plan, "is_public", False)),
        is_active=plan.is_active,
        effective_from=plan.effective_from,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        subscriber_count=subscriber_count,
        can_delete=subscriber_count == 0,
        plan_kind=str(getattr(plan, "plan_kind", "subscription") or "subscription"),
        plan_type=str(getattr(plan, "plan_type", "desktop_pro") or "desktop_pro"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/public",
    response_model=list[PublicPlanResponse],
    status_code=200,
    summary="List active public plans",
)
async def list_public_plans(
    plan_repo: PlanRepoDep,
    billing: Annotated[Any, Depends(get_v3_billing_service)],
) -> list[PublicPlanResponse]:
    """Return active **and public** plans plus launch offers for website/user flows.

    Hidden rows (``is_public=false``) stay assignable in Admin / licenses.
    """
    plans = await plan_repo.get_all()
    public_plans = [
        plan
        for plan in subscription_plans(plans)
        if plan.is_active
        and bool(getattr(plan, "is_public", False))
        and not (plan.name or "").strip().lower() == "trial"
    ]
    if not public_plans:
        return []

    offer_rows = await plan_repo._pool.fetch(
        """
        SELECT DISTINCT ON (plan_id)
               id,
               plan_id,
               promo_price_cents,
               max_redemptions,
               current_redemptions,
               is_active
        FROM plan_offers
        WHERE is_active = true
          AND current_redemptions < max_redemptions
          AND plan_id = ANY($1::uuid[])
        ORDER BY plan_id, promo_price_cents ASC, created_at DESC
        """,
        [plan.id for plan in public_plans],
    )
    offer_map = {str(row["plan_id"]): row for row in offer_rows}

    rate = await billing.music_credits_per_generate()
    return [
        _public_plan_to_response(
            plan,
            offer_row=offer_map.get(str(plan.id)),
            credits_per_generate=rate,
        )
        for plan in public_plans
    ]


@router.get(
    "/public/term-discounts",
    response_model=PublicPlanTermDiscountsResponse,
    status_code=200,
    summary="Public billing term discount labels for website pricing",
)
async def get_public_plan_term_discounts(
    pool: Annotated[Any, Depends(get_db_pool)],
) -> PublicPlanTermDiscountsResponse:
    """Return saved 6-month / annual discount percentages for pricing page labels."""
    discounts = await load_plan_term_discounts(pool)
    return PublicPlanTermDiscountsResponse(
        semi_annual_discount_percent=discounts.semi_annual_discount_percent,
        annual_discount_percent=discounts.annual_discount_percent,
    )


async def _resolve_two_channel_monthly_base(plan_repo: PlanRepository) -> Any:
    """Find the active 30-day plan anchored at 2 channel profiles."""
    base_plan = find_two_channel_monthly_base(await plan_repo.get_all())
    if base_plan is None:
        raise NotFoundError(
            message="No active 2-channel monthly base plan found.",
            details={"profile_allowance": 2, "billing_cycle_days": 30},
        )
    return base_plan


@router.get(
    "/public/profile-addon-quote",
    response_model=PublicProfileAddonQuoteResponse,
    status_code=200,
    summary="Quote profile add-on pricing (+2 channels)",
)
async def get_public_profile_addon_quote(
    plan_repo: PlanRepoDep,
    current_channels: int = Query(..., ge=2, le=10, description="Current quota channel count"),
    addon_channels: int = Query(
        default=PROFILE_ADDON_STEP,
        ge=PROFILE_ADDON_STEP,
        le=8,
        description="Add-on bundle size (2, 4, 6, or 8 channels)",
    ),
) -> PublicProfileAddonQuoteResponse:
    """Return profile add-on pricing from active profile_addon plan rows."""
    if addon_channels % PROFILE_ADDON_STEP != 0:
        raise ValidationError(
            message=f"Profile add-ons must be purchased in multiples of {PROFILE_ADDON_STEP}.",
            details={"addon_channels": addon_channels},
        )
    if current_channels + addon_channels > MAX_ACCOUNT_CHANNELS:
        raise ValidationError(
            message=f"Total channels cannot exceed {MAX_ACCOUNT_CHANNELS}.",
            details={"current_channels": current_channels, "addon_channels": addon_channels},
        )

    all_plans = await plan_repo.get_all()
    base_plan = find_two_channel_monthly_base(all_plans)
    if base_plan is None:
        raise NotFoundError(
            message="No active 2-channel monthly subscription plan found.",
            details={"profile_allowance": 2, "billing_cycle_days": 30},
        )
    addon_plan = find_profile_addon_plan(all_plans, addon_channels)
    if addon_plan is None or not bool(getattr(addon_plan, "is_public", False)):
        raise NotFoundError(
            message=f"No public profile add-on plan found for +{addon_channels} channels.",
            details={"addon_channels": addon_channels},
        )

    quote = quote_profile_addon_from_plan(
        current_channels=current_channels,
        addon_channels=addon_channels,
        addon_plan=addon_plan,
    )
    remaining = max(0, MAX_ACCOUNT_CHANNELS - current_channels)
    remaining -= remaining % PROFILE_ADDON_STEP
    block_cents = int(base_plan.price_cents)

    return PublicProfileAddonQuoteResponse(
        current_channels=quote.current_channels,
        addon_channels=quote.addon_channels,
        new_total_channels=quote.new_total_channels,
        monthly_addon_cents=quote.monthly_addon_cents,
        capped_by_tier=quote.capped_by_tier,
        next_tier_channels=quote.next_tier_channels,
        next_tier_monthly_cents=quote.next_tier_monthly_cents,
        max_addon_channels_remaining=remaining,
        two_channel_block_cents=block_cents,
        linear_plan_monthly_cents=linear_plan_monthly_from_base(
            base_monthly_cents=block_cents,
            channel_count=current_channels,
        ),
        addon_plan_id=str(addon_plan.id),
        base_plan_id=str(base_plan.id),
    )


@router.get(
    "/term-discounts",
    response_model=PlanTermDiscountsResponse,
    status_code=200,
    summary="Get 6-month and annual discount settings (Admin)",
)
async def get_plan_term_discounts(
    ctx: AdminDep,
    pool: Annotated[Any, Depends(get_db_pool)],
) -> PlanTermDiscountsResponse:
    """Return persisted term discount percentages used when building/syncing plan rows."""
    discounts = await load_plan_term_discounts(pool)
    return PlanTermDiscountsResponse(
        semi_annual_discount_percent=discounts.semi_annual_discount_percent,
        annual_discount_percent=discounts.annual_discount_percent,
    )


@router.put(
    "/term-discounts",
    response_model=PlanTermDiscountsResponse,
    status_code=200,
    summary="Update 6-month and annual discount settings (Admin)",
)
async def update_plan_term_discounts(
    request: UpdatePlanTermDiscountsRequest,
    ctx: AdminDep,
    pool: Annotated[Any, Depends(get_db_pool)],
) -> PlanTermDiscountsResponse:
    """Save term discount percentages. Checkout prices remain on plan rows until synced."""
    discounts = PlanTermDiscounts(
        semi_annual_discount_percent=int(request.semi_annual_discount_percent),
        annual_discount_percent=int(request.annual_discount_percent),
    )
    await save_plan_term_discounts(pool, discounts)
    return PlanTermDiscountsResponse(
        semi_annual_discount_percent=discounts.semi_annual_discount_percent,
        annual_discount_percent=discounts.annual_discount_percent,
    )


@router.get(
    "/term-price-drift",
    response_model=PlanPriceDriftResponse,
    status_code=200,
    summary="List subscription/add-on rows whose checkout price differs from computed term totals (Admin)",
)
async def get_term_price_drift(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
    pool: Annotated[Any, Depends(get_db_pool)],
) -> PlanPriceDriftResponse:
    from platform_api.services.plan_price_drift_service import (
        compute_profile_addon_term_drift,
        compute_subscription_term_drift,
    )

    discounts = await load_plan_term_discounts(pool)
    all_plans = await plan_repo.get_all()
    items = [
        *compute_subscription_term_drift(
            all_plans,
            semi_annual_discount_percent=discounts.semi_annual_discount_percent,
            annual_discount_percent=discounts.annual_discount_percent,
        ),
        *compute_profile_addon_term_drift(
            all_plans,
            semi_annual_discount_percent=discounts.semi_annual_discount_percent,
            annual_discount_percent=discounts.annual_discount_percent,
        ),
    ]
    return PlanPriceDriftResponse(
        drift_count=len(items),
        items=[
            PlanPriceDriftItemResponse(
                plan_id=item.plan_id,
                plan_name=item.plan_name,
                billing_cycle_days=item.billing_cycle_days,
                profile_allowance=item.profile_allowance,
                stored_cents=item.stored_cents,
                expected_cents=item.expected_cents,
                plan_kind=item.plan_kind,
            )
            for item in items
        ],
    )


@router.post(
    "/sync-term-prices",
    response_model=SyncTermPlanPricesResponse,
    status_code=200,
    summary="Sync 6-month and annual plan prices from monthly rows (Admin)",
)
async def sync_term_plan_prices(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
    pool: Annotated[Any, Depends(get_db_pool)],
) -> SyncTermPlanPricesResponse:
    """Update 6-month and annual subscription plan checkout prices from monthly plan rows."""
    from platform_api.services.plan_tier_pricing_service import billing_term_quotes

    discounts = await load_plan_term_discounts(pool)
    plans = subscription_plans(await plan_repo.get_all())
    updated: list[str] = []
    skipped: list[str] = []

    for channels in (2, 6, 10):
        monthly_candidates = [
            plan
            for plan in plans
            if bool(plan.is_active)
            and int(plan.profile_allowance or 0) == channels
            and int(plan.billing_cycle_days or 0) == 30
        ]
        if not monthly_candidates:
            skipped.append(f"{channels}ch: no active monthly plan")
            continue
        monthly_candidates.sort(key=lambda plan: int(plan.price_cents or 0))
        monthly = monthly_candidates[0]
        terms = billing_term_quotes(
            int(monthly.price_cents),
            semi_annual_discount_percent=discounts.semi_annual_discount_percent,
            annual_discount_percent=discounts.annual_discount_percent,
        )
        term_map = {term.billing_cycle_days: term for term in terms}

        for cycle_days in (180, 365):
            target = term_map.get(cycle_days)
            if target is None:
                continue
            matches = [
                plan
                for plan in plans
                if int(plan.profile_allowance or 0) == channels
                and int(plan.billing_cycle_days or 0) == cycle_days
            ]
            if not matches:
                skipped.append(f"{channels}ch/{cycle_days}d: no plan row")
                continue
            for plan in matches:
                if int(plan.price_cents) == int(target.total_cents):
                    continue
                updated_plan = await plan_repo.update(plan.id, price_cents=int(target.total_cents))
                if updated_plan is not None:
                    updated.append(str(plan.id))

    from platform_api.services.plan_tier_pricing_service import billing_term_quotes, profile_addon_plans

    addon_monthly = [
        plan
        for plan in profile_addon_plans(await plan_repo.get_all())
        if bool(plan.is_active) and int(plan.billing_cycle_days or 0) == 30
    ]
    for monthly_addon in addon_monthly:
        bundle = int(monthly_addon.profile_allowance or 0)
        terms = billing_term_quotes(
            int(monthly_addon.price_cents),
            semi_annual_discount_percent=discounts.semi_annual_discount_percent,
            annual_discount_percent=discounts.annual_discount_percent,
        )
        term_map = {term.billing_cycle_days: term for term in terms}
        for cycle_days in (180, 365):
            target = term_map.get(cycle_days)
            if target is None:
                continue
            matches = [
                plan
                for plan in profile_addon_plans(await plan_repo.get_all())
                if int(plan.profile_allowance or 0) == bundle
                and int(plan.billing_cycle_days or 0) == cycle_days
            ]
            if not matches:
                skipped.append(f"addon +{bundle}/{cycle_days}d: no plan row")
                continue
            for plan in matches:
                if int(plan.price_cents) == int(target.total_cents):
                    continue
                updated_plan = await plan_repo.update(plan.id, price_cents=int(target.total_cents))
                if updated_plan is not None:
                    updated.append(str(plan.id))

    return SyncTermPlanPricesResponse(updated_plan_ids=updated, skipped=skipped)


@router.get(
    "/public/usage-rates",
    response_model=PublicUsageRatesResponse,
    status_code=200,
    summary="Public credit usage rates for website pricing",
)
async def list_public_usage_rates(
    routing_service: Annotated[Any, Depends(get_ai_routing_service)],
    pricing_service: Annotated[Any, Depends(get_credit_pricing_service)],
) -> PublicUsageRatesResponse:
    """Return user-safe per-operation credit costs from live routing + pricing."""
    from platform_api.services.public_usage_rates_service import build_public_usage_rates

    if routing_service is None:
        return PublicUsageRatesResponse(
            updated_at=datetime.now(timezone.utc).isoformat(),
            items=[],
            estimated_full_song_credits=None,
            disclaimer="Usage rates are temporarily unavailable.",
        )

    payload = await build_public_usage_rates(
        routing_service=routing_service,
        pricing_service=pricing_service,
    )
    return PublicUsageRatesResponse(**payload)


@router.get(
    "",
    response_model=list[PlanResponse],
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="List all plans (Admin)",
)
async def list_plans(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> list[PlanResponse]:
    """Return all plans with their configurations.

    Requirement 4.1: Plans are stored as Admin-configurable records with
    pricing, quotas, and profile allowances.
    """
    plans = await plan_repo.get_all()
    subscriber_counts = await plan_repo.get_subscriber_counts([p.id for p in plans])
    return [
        _plan_to_response(p, subscriber_count=subscriber_counts.get(p.id, 0))
        for p in plans
    ]


@router.post(
    "",
    response_model=PlanResponse,
    status_code=201,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        409: {"description": "Plan name already exists"},
    },
    summary="Create a new plan (Admin)",
)
async def create_plan(
    request: CreatePlanRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> PlanResponse:
    """Create a new subscription or profile add-on plan row."""
    plan_kind = (request.plan_kind or "subscription").strip().lower()
    if plan_kind not in ("subscription", "profile_addon"):
        raise ValidationError(
            message="plan_kind must be subscription or profile_addon.",
            details={"plan_kind": request.plan_kind},
        )

    validate_plan_limits(
        monthly_song_limit=request.monthly_song_limit,
        monthly_image_limit=request.monthly_image_limit,
        daily_song_limit_per_channel=request.daily_song_limit_per_channel,
        daily_image_limit_per_channel=request.daily_image_limit_per_channel,
    )
    if plan_kind == "subscription":
        validate_paid_recurring_finite_meters(
            price_cents=request.price_cents,
            billing_cycle_days=request.billing_cycle_days,
            monthly_song_limit=request.monthly_song_limit,
            monthly_image_limit=request.monthly_image_limit,
            monthly_draft_limit=request.monthly_draft_limit,
            monthly_video_limit=request.monthly_video_limit,
            monthly_merge_limit=request.monthly_merge_limit,
            is_active=True,
        )

    plan = await plan_repo.create(
        name=request.name,
        price_cents=request.price_cents,
        profile_allowance=request.profile_allowance,
        monthly_song_limit=request.monthly_song_limit if plan_kind == "subscription" else 0,
        monthly_image_limit=request.monthly_image_limit if plan_kind == "subscription" else 0,
        monthly_draft_limit=request.monthly_draft_limit if plan_kind == "subscription" else 0,
        monthly_video_limit=request.monthly_video_limit if plan_kind == "subscription" else 0,
        monthly_merge_limit=request.monthly_merge_limit if plan_kind == "subscription" else 0,
        billing_cycle_days=request.billing_cycle_days,
        daily_song_limit_per_channel=request.daily_song_limit_per_channel,
        daily_image_limit_per_channel=request.daily_image_limit_per_channel,
        daily_draft_limit_per_channel=request.daily_draft_limit_per_channel,
        daily_video_limit=request.daily_video_limit,
        daily_merge_limit=request.daily_merge_limit,
        plan_kind=plan_kind,
    )
    return _plan_to_response(plan, subscriber_count=0)


from platform_api.routers import web_music_plans_admin  # noqa: E402

router.include_router(web_music_plans_admin.router)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Plan not found"},
    },
    summary="Update plan configuration (Admin)",
)
async def update_plan(
    plan_id: UUID,
    request: UpdatePlanRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> PlanResponse:
    """Update a plan's configuration fields.

    Requirement 1.2: Validates plan limit fields before persisting.
    Requirement 4.2: Changes are stored with an effective date and apply
    to new subscriptions. Existing active subscriptions retain original terms.

    Requirement 4.12: Setting is_active to false prevents new license creation
    for that plan; setting it to true resumes.
    """
    # Build the update dict from non-None fields
    fields: dict[str, Any] = {}
    if request.price_cents is not None:
        fields["price_cents"] = request.price_cents
    if request.profile_allowance is not None:
        fields["profile_allowance"] = request.profile_allowance
    if request.monthly_song_limit is not None:
        fields["monthly_song_limit"] = request.monthly_song_limit
    if request.monthly_image_limit is not None:
        fields["monthly_image_limit"] = request.monthly_image_limit
    if request.monthly_draft_limit is not None:
        fields["monthly_draft_limit"] = request.monthly_draft_limit
    if request.monthly_video_limit is not None:
        fields["monthly_video_limit"] = request.monthly_video_limit
    if request.monthly_merge_limit is not None:
        fields["monthly_merge_limit"] = request.monthly_merge_limit
    if request.daily_song_limit_per_channel is not None:
        fields["daily_song_limit_per_channel"] = request.daily_song_limit_per_channel
    if request.daily_image_limit_per_channel is not None:
        fields["daily_image_limit_per_channel"] = request.daily_image_limit_per_channel
    if request.daily_draft_limit_per_channel is not None:
        fields["daily_draft_limit_per_channel"] = request.daily_draft_limit_per_channel
    if request.daily_video_limit is not None:
        fields["daily_video_limit"] = request.daily_video_limit
    if request.daily_merge_limit is not None:
        fields["daily_merge_limit"] = request.daily_merge_limit
    if request.billing_cycle_days is not None:
        fields["billing_cycle_days"] = request.billing_cycle_days
    if request.is_active is not None:
        fields["is_active"] = request.is_active

    if not fields:
        raise ValidationError(
            message="No fields provided for update.",
            details={
                "allowed_fields": [
                    "price_cents",
                    "profile_allowance",
                    "monthly_song_limit",
                    "monthly_image_limit",
                    "monthly_draft_limit",
                    "monthly_video_limit",
                    "monthly_merge_limit",
                    "daily_song_limit_per_channel",
                    "daily_image_limit_per_channel",
                    "daily_draft_limit_per_channel",
                    "daily_video_limit",
                    "daily_merge_limit",
                    "billing_cycle_days",
                    "is_active",
                ]
            },
        )

    # Validate plan limits if any limit fields are being updated (Requirement 1.2)
    limit_fields_present = any(
        k in fields
        for k in (
            "monthly_song_limit",
            "monthly_image_limit",
            "monthly_draft_limit",
            "monthly_video_limit",
            "monthly_merge_limit",
            "daily_song_limit_per_channel",
            "daily_image_limit_per_channel",
            "daily_draft_limit_per_channel",
            "daily_video_limit",
            "daily_merge_limit",
        )
    )
    current_plan = await plan_repo.get_by_id(plan_id)
    if current_plan is None:
        raise NotFoundError(message="Plan not found.", details={"plan_id": str(plan_id)})

    if limit_fields_present:
        validate_plan_limits(
            monthly_song_limit=fields.get("monthly_song_limit", current_plan.monthly_song_limit),
            monthly_image_limit=fields.get("monthly_image_limit", current_plan.monthly_image_limit),
            daily_song_limit_per_channel=fields.get(
                "daily_song_limit_per_channel", current_plan.daily_song_limit_per_channel
            ),
            daily_image_limit_per_channel=fields.get(
                "daily_image_limit_per_channel", current_plan.daily_image_limit_per_channel
            ),
        )

    merged_price = fields.get("price_cents", current_plan.price_cents)
    merged_cycle = fields.get("billing_cycle_days", current_plan.billing_cycle_days)
    merged_active = fields.get("is_active", current_plan.is_active)
    validate_paid_recurring_finite_meters(
        price_cents=int(merged_price),
        billing_cycle_days=merged_cycle,
        monthly_song_limit=fields.get("monthly_song_limit", current_plan.monthly_song_limit),
        monthly_image_limit=fields.get("monthly_image_limit", current_plan.monthly_image_limit),
        monthly_draft_limit=fields.get(
            "monthly_draft_limit", getattr(current_plan, "monthly_draft_limit", None)
        ),
        monthly_video_limit=fields.get(
            "monthly_video_limit", getattr(current_plan, "monthly_video_limit", None)
        ),
        monthly_merge_limit=fields.get(
            "monthly_merge_limit", getattr(current_plan, "monthly_merge_limit", None)
        ),
        is_active=bool(merged_active),
    )

    updated_plan = await plan_repo.update(plan_id, **fields)
    if updated_plan is None:
        raise NotFoundError(message="Plan not found.", details={"plan_id": str(plan_id)})

    subscriber_counts = await plan_repo.get_subscriber_counts([updated_plan.id])
    return _plan_to_response(
        updated_plan,
        subscriber_count=subscriber_counts.get(updated_plan.id, 0),
    )


def _public_plan_to_response(
    plan: Any,
    *,
    offer_row: Any | None = None,
    credits_per_generate: int | float | None = None,
) -> PublicPlanResponse:
    """Convert a domain plan plus its best active offer to a public response."""
    offer = None
    effective_price_cents = plan.price_cents
    if offer_row is not None:
        remaining = max(
            0,
            int(offer_row["max_redemptions"]) - int(offer_row["current_redemptions"]),
        )
        offer = PublicPlanOfferResponse(
            id=str(offer_row["id"]),
            promo_price_cents=int(offer_row["promo_price_cents"]),
            max_redemptions=int(offer_row["max_redemptions"]),
            current_redemptions=int(offer_row["current_redemptions"]),
            remaining_redemptions=remaining,
            is_active=bool(offer_row["is_active"]),
        )
        effective_price_cents = int(offer_row["promo_price_cents"])

    return PublicPlanResponse(
        id=str(plan.id),
        name=plan.name,
        price_cents=plan.price_cents,
        effective_price_cents=effective_price_cents,
        billing_cycle_days=plan.billing_cycle_days,
        profile_allowance=plan.profile_allowance,
        monthly_song_limit=plan.monthly_song_limit,
        monthly_image_limit=plan.monthly_image_limit,
        monthly_draft_limit=getattr(plan, "monthly_draft_limit", None),
        monthly_video_limit=getattr(plan, "monthly_video_limit", None),
        monthly_merge_limit=getattr(plan, "monthly_merge_limit", None),
        daily_song_limit_per_channel=plan.daily_song_limit_per_channel,
        daily_image_limit_per_channel=plan.daily_image_limit_per_channel,
        daily_draft_limit_per_channel=int(
            getattr(plan, "daily_draft_limit_per_channel", 300) or 300
        ),
        daily_video_limit=int(getattr(plan, "daily_video_limit", 10) or 10),
        daily_merge_limit=int(getattr(plan, "daily_merge_limit", 1) or 1),
        included_wallet_credits=float(getattr(plan, "included_wallet_credits", 0) or 0),
        monthly_credits=int(getattr(plan, "monthly_credits", 0) or 0),
        daily_credits=int(getattr(plan, "daily_credits", 0) or 0),
        pricing_features=resolve_pricing_features(
            getattr(plan, "pricing_features", None),
            name=str(getattr(plan, "name", "") or ""),
            price_cents=int(getattr(plan, "price_cents", 0) or 0),
            daily_credits=int(getattr(plan, "daily_credits", 0) or 0),
            monthly_credits=int(getattr(plan, "monthly_credits", 0) or 0),
        ),
        pricing_credit_lines=resolve_pricing_credit_lines(
            getattr(plan, "pricing_credit_lines", None),
            monthly_credits=int(getattr(plan, "monthly_credits", 0) or 0),
            daily_credits=int(getattr(plan, "daily_credits", 0) or 0),
            credits_per_generate=credits_per_generate,
        ),
        credits_per_generate=credits_per_generate,
        offer=offer,
    )


@router.delete(
    "/{plan_id}",
    status_code=204,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Plan not found"},
        422: {"description": "Plan has subscribed users and cannot be deleted"},
    },
    summary="Permanently delete a plan (Admin)",
)
async def delete_plan(
    plan_id: UUID,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> Response:
    """Permanently delete a plan that has no subscribed users."""
    deleted = await plan_repo.delete_if_no_subscribers(plan_id)
    if not deleted:
        raise NotFoundError(message="Plan not found.", details={"plan_id": str(plan_id)})
    return Response(status_code=204)


@router.get(
    "/offers",
    response_model=list[OfferResponse],
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="List active promotional offers (Admin)",
)
async def list_offers(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> list[OfferResponse]:
    """Return all active promotional offers.

    Requirement 4.10: Admins can view and manage launch offers with
    promotional pricing and redemption limits.
    """
    # Note: The offer querying is handled via raw pool access on PlanRepository.
    # For now, we access the pool directly since PlanRepository doesn't have
    # a dedicated offer method yet. This will be refactored with a proper
    # OfferRepository in a later task.
    rows = await plan_repo._pool.fetch(
        """
        SELECT id, plan_id, promo_price_cents, max_redemptions,
               current_redemptions, is_active, created_at
        FROM plan_offers
        WHERE is_active = true
        ORDER BY created_at DESC
        """
    )
    return [
        OfferResponse(
            id=str(row["id"]),
            plan_id=str(row["plan_id"]),
            promo_price_cents=row["promo_price_cents"],
            max_redemptions=row["max_redemptions"],
            current_redemptions=row["current_redemptions"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.post(
    "/offers",
    response_model=OfferResponse,
    status_code=201,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Plan not found"},
    },
    summary="Create a promotional offer (Admin)",
)
async def create_offer(
    request: CreateOfferRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> OfferResponse:
    """Create a new promotional offer for a plan.

    Requirement 4.10: Admins can set a promotional price and maximum
    redemption count. When the count is reached, the standard price
    applies automatically.
    """
    plan_id = UUID(request.plan_id)

    # Verify the plan exists
    plan = await plan_repo.get_by_id(plan_id)
    if plan is None:
        raise NotFoundError(message="Plan not found.", details={"plan_id": request.plan_id})

    # Insert the offer
    row = await plan_repo._pool.fetchrow(
        """
        INSERT INTO plan_offers (plan_id, promo_price_cents, max_redemptions, is_active, created_at)
        VALUES ($1, $2, $3, true, NOW())
        RETURNING id, plan_id, promo_price_cents, max_redemptions,
                  current_redemptions, is_active, created_at
        """,
        plan_id,
        request.promo_price_cents,
        request.max_redemptions,
    )

    return OfferResponse(
        id=str(row["id"]),
        plan_id=str(row["plan_id"]),
        promo_price_cents=row["promo_price_cents"],
        max_redemptions=row["max_redemptions"],
        current_redemptions=row["current_redemptions"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )
