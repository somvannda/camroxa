"""Billing endpoints for KHQR provider switching, checkout, and payment reconciliation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from platform_api.config import get_settings
from platform_api.dependencies import get_db_pool
from platform_api.exceptions import ExternalServiceError, ForbiddenError, NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.license_repo import LicenseRepository, PlanRepository
from platform_api.services.billing_config_service import resolve_cutluy_config
from platform_api.services.cutluy_webhook import (
    cutluy_event_type,
    verify_cutluy_webhook_signature,
)
from platform_api.services.redeem_code_service import (
    REWARD_TYPE_CREDIT_GRANT,
    preview_redeem_code,
    record_discount_redemption,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]

BILLING_ACTIVE_PROVIDER_SETTING_KEY = "billing.active_provider"
BILLING_PORTAL_BASE_URL_SETTING_KEY = "billing.portal_base_url"
MOCK_TERMINAL_STATUSES = {"paid", "failed", "expired"}
# Self-serve renewal opens this many days before the license expiry (or whenever expired).
RENEWAL_WINDOW_DAYS = 7

PROVIDER_REGISTRY: dict[str, dict[str, str]] = {
    "mock": {
        "label": "Mock Checkout",
        "kind": "khqr",
        "description": "Development-only hosted checkout simulator for testing onboarding and billing flows.",
    },
    "cutluy": {
        "label": "CutLuy KHQR",
        "kind": "khqr",
        "description": "Production KHQR checkout via CutLuy hosted payment pages.",
    },
}


class CreatePaymentRequest(BaseModel):
    """Create a hosted checkout payment for a specific plan."""

    plan_id: str = Field(..., description="UUID of the selected plan")
    redeem_code: str | None = Field(default=None, description="Optional redeem code for discount pricing")


class CreateProfileAddonPaymentRequest(BaseModel):
    """Create a hosted checkout payment for +2 channel profile add-ons."""

    addon_channels: int = Field(
        default=2,
        ge=2,
        le=8,
        description="Number of add-on channel slots to purchase (multiples of 2)",
    )


class CreateCreditPackPaymentRequest(BaseModel):
    """Create a hosted checkout payment for a wallet credit pack."""

    pack_id: str = Field(..., description="UUID of the credit pack to purchase")


class ScheduleDowngradeRequest(BaseModel):
    """Schedule a lower-tier plan to take effect at the current period end."""

    plan_id: str = Field(..., description="UUID of the target plan at renewal")


class QuotaRenewalResponse(BaseModel):
    """The signed-in user's own plan, exposed for the renew flow (hidden plans allowed)."""

    eligible: bool
    plan_id: str | None = None
    plan_name: str | None = None
    price_cents: int | None = None
    billing_cycle_days: int | None = None
    expires_at: datetime | None = None
    days_left: int | None = None
    expired: bool = False
    renewable: bool = False
    renewal_opens_in_days: int | None = None
    renewal_window_days: int = 7


class AddonRenewalResponse(BaseModel):
    """Renewable add-on channel blocks for the signed-in user."""

    eligible: bool
    addon_channels: int | None = None
    blocks: int | None = None
    credits: int | None = None
    price_cents: int | None = None
    credits_per_block: int | None = None
    price_per_block_cents: int | None = None
    expires_at: datetime | None = None
    renewable: bool = False
    renewal_opens_in_days: int | None = None
    renewal_window_days: int = 7


class AddonRenewalRequest(BaseModel):
    """How many 2-channel blocks of add-on channels to renew."""

    blocks: int | None = Field(default=None, ge=1, description="Number of 2-channel blocks to renew")


class CompleteMockPaymentRequest(BaseModel):
    """Transition a mock payment into a terminal test state."""

    status: str = Field(..., description="One of: paid, failed, expired")


class BillingPaymentResponse(BaseModel):
    """User-facing payment state for the onboarding billing flow."""

    id: str
    provider: str
    external_payment_id: str
    plan_id: str
    plan_name: str
    amount_cents: int
    currency: str
    status: str
    checkout_url: str
    approved_at: datetime | None = None
    fulfilled_at: datetime | None = None
    original_amount_cents: int | None = None
    redeem_code: str | None = None
    product_type: str = "plan"
    addon_channels: int | None = None
    qr_string: str | None = None
    created_at: datetime
    updated_at: datetime


class BillingProviderResponse(BaseModel):
    """Provider registry entry exposed to admin/user clients."""

    id: str
    label: str
    kind: str
    description: str
    enabled: bool
    active: bool
    available: bool


class BillingProviderConfigResponse(BaseModel):
    """Current provider config used by onboarding/admin surfaces."""

    active_provider: str | None = None
    paid_checkout_available: bool = False
    providers: list[BillingProviderResponse]
    cutluy_secret_configured: bool = False
    cutluy_secret_source: str | None = None
    cutluy_api_base_url: str = "https://cutluy.com"


def _provider_enabled_setting_key(provider_id: str) -> str:
    return f"billing.provider.{provider_id}.enabled"


def _to_cents(amount: str | int | float | Decimal) -> int:
    """Convert decimal USD amount into integer cents."""
    dec = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(dec * 100)


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return default


async def _load_system_setting(pool: Any, key: str) -> str | None:
    """Fetch a raw system setting value by key."""
    row = await pool.fetchrow(
        """
        SELECT value
        FROM system_settings
        WHERE key = $1
        """,
        key,
    )
    if row is None:
        return None
    value = row.get("value")
    if value is None:
        return None
    return str(value).strip()


async def _provider_available(pool: Any, provider_id: str) -> bool:
    """Return whether the provider can currently be used."""
    settings = get_settings()
    if provider_id == "mock":
        return bool(settings.debug)
    if provider_id == "cutluy":
        cutluy = await resolve_cutluy_config(pool)
        return bool(cutluy.secret_key)
    return False


def _ensure_mock_checkout_allowed() -> None:
    if not get_settings().debug:
        raise ValidationError("Mock checkout is only available in debug environments.")


def _default_provider_enabled(provider_id: str) -> bool:
    """Return the implicit enabled state when admin has not saved a setting yet."""
    settings = get_settings()
    if provider_id == "mock":
        return bool(settings.debug)
    if provider_id == "cutluy":
        return not settings.debug
    return False


async def _is_provider_enabled(pool: Any, provider_id: str) -> bool:
    """Resolve provider enabled state from admin settings or defaults."""
    raw = await _load_system_setting(pool, _provider_enabled_setting_key(provider_id))
    return _parse_bool(raw, _default_provider_enabled(provider_id))


async def _get_provider_config(pool: Any) -> BillingProviderConfigResponse:
    """Build provider registry state with enabled/active/available flags."""
    raw_active = await _load_system_setting(pool, BILLING_ACTIVE_PROVIDER_SETTING_KEY)
    configured_active = (raw_active or "").strip().lower()
    explicit_off = configured_active in {"none", "off", "disabled"}
    if not configured_active:
        configured_active = "mock" if get_settings().debug else "cutluy"

    provider_rows: list[BillingProviderResponse] = []
    resolved_active: str | None = None
    cutluy = await resolve_cutluy_config(pool)

    for provider_id, meta in PROVIDER_REGISTRY.items():
        enabled = await _is_provider_enabled(pool, provider_id)
        available = await _provider_available(pool, provider_id)
        is_active = enabled and available and configured_active == provider_id
        if is_active:
            resolved_active = provider_id
        provider_rows.append(
            BillingProviderResponse(
                id=provider_id,
                label=meta["label"],
                kind=meta["kind"],
                description=meta["description"],
                enabled=enabled,
                active=is_active,
                available=available,
            )
        )

    if resolved_active is None and not explicit_off:
        fallback = next((item.id for item in provider_rows if item.enabled and item.available), None)
        resolved_active = fallback
        provider_rows = [
            BillingProviderResponse(
                **{
                    **item.model_dump(),
                    "active": item.id == resolved_active,
                }
            )
            for item in provider_rows
        ]

    return BillingProviderConfigResponse(
        active_provider=resolved_active,
        paid_checkout_available=resolved_active is not None,
        providers=provider_rows,
        cutluy_secret_configured=bool(cutluy.secret_key),
        cutluy_secret_source=cutluy.secret_source if cutluy.secret_key else None,
        cutluy_api_base_url=cutluy.api_base_url,
    )


async def _get_active_provider(pool: Any) -> str | None:
    """Return the currently active enabled provider, or None when paid checkout is off."""
    config = await _get_provider_config(pool)
    return config.active_provider


async def _get_portal_base_url(pool: Any) -> str:
    """Resolve the user portal base URL for hosted mock checkout links."""
    configured = (await _load_system_setting(pool, BILLING_PORTAL_BASE_URL_SETTING_KEY) or "").strip()
    if configured:
        return configured.rstrip("/")

    settings = get_settings()
    if settings.debug:
        return "http://localhost:3001"
    return "https://account.camxora.com"


def _parse_cutluy_timestamp(value: Any) -> datetime | None:
    """Normalize CutLuy ISO timestamp strings for asyncpg timestamptz columns."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            logger.warning("Unable to parse CutLuy timestamp: %s", value)
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _ensure_cutluy_ready(cutluy: Any) -> tuple[str, str | None]:
    """Return CutLuy credentials or fail with a clear setup message."""
    api_key = cutluy.secret_key.strip()
    if not api_key:
        raise ExternalServiceError(
            "CutLuy billing is not configured yet. Add the API key in Admin Settings → Payment.",
            details={"provider": "cutluy"},
        )
    return api_key, cutluy.payment_link_id


def _payment_response_from_row(row: Any) -> BillingPaymentResponse:
    """Convert a billing_payments row into the public response shape."""
    metadata = row["metadata"] or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return BillingPaymentResponse(
        id=str(row["id"]),
        provider=str(row["provider"]),
        external_payment_id=str(row["external_payment_id"]),
        plan_id=str(row["plan_id"]),
        plan_name=str(row["plan_name"]),
        amount_cents=int(row["amount_cents"]),
        currency=str(row["currency"]),
        status=str(row["status"]),
        checkout_url=str(row["checkout_url"]),
        approved_at=row["approved_at"],
        fulfilled_at=row["fulfilled_at"],
        original_amount_cents=metadata.get("original_amount_cents"),
        redeem_code=metadata.get("redeem_code"),
        product_type=str(metadata.get("product_type") or "plan"),
        addon_channels=int(metadata["addon_channels"]) if metadata.get("addon_channels") is not None else None,
        qr_string=metadata.get("qr_string"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _get_best_offer_row(pool: Any, plan_id: UUID) -> Any | None:
    """Return the cheapest active remaining offer for a plan, if any."""
    return await pool.fetchrow(
        """
        SELECT id, plan_id, promo_price_cents, max_redemptions, current_redemptions, is_active
        FROM plan_offers
        WHERE plan_id = $1
          AND is_active = true
          AND current_redemptions < max_redemptions
        ORDER BY promo_price_cents ASC, created_at DESC
        LIMIT 1
        """,
        plan_id,
    )


async def _fetch_payment_row(pool: Any, *, payment_id: UUID, user_id: UUID) -> Any | None:
    """Return a billing payment joined with its plan name for the current user."""
    return await pool.fetchrow(
        """
        SELECT bp.*,
               p.name AS plan_name
        FROM billing_payments bp
        INNER JOIN plans p ON p.id = bp.plan_id
        WHERE bp.id = $1
          AND bp.user_id = $2
        """,
        payment_id,
        user_id,
    )


async def _fetch_payment_row_by_external_id(
    pool: Any,
    *,
    external_payment_id: str,
    user_id: UUID,
) -> Any | None:
    """Return the user's billing payment row for a provider external payment id."""
    return await pool.fetchrow(
        """
        SELECT bp.*,
               p.name AS plan_name
        FROM billing_payments bp
        INNER JOIN plans p ON p.id = bp.plan_id
        WHERE bp.external_payment_id = $1
          AND bp.user_id = $2
        ORDER BY bp.created_at DESC
        LIMIT 1
        """,
        external_payment_id,
        user_id,
    )


async def _fetch_existing_pending_payment(pool: Any, *, user_id: UUID, plan_id: UUID) -> Any | None:
    """Return the most recent unfinished payment for the user and plan."""
    return await pool.fetchrow(
        """
        SELECT bp.*, p.name AS plan_name
        FROM billing_payments bp
        INNER JOIN plans p ON p.id = bp.plan_id
        WHERE bp.user_id = $1
          AND bp.plan_id = $2
          AND bp.status IN ('pending', 'scanned')
        ORDER BY bp.created_at DESC
        LIMIT 1
        """,
        user_id,
        plan_id,
    )


async def _hydrate_created_payment(pool: Any, payment_id: UUID) -> BillingPaymentResponse:
    """Load a newly-created payment with plan metadata for response serialization."""
    row = await pool.fetchrow(
        """
        SELECT bp.*, p.name AS plan_name
        FROM billing_payments bp
        INNER JOIN plans p ON p.id = bp.plan_id
        WHERE bp.id = $1
        """,
        payment_id,
    )
    if row is None:
        raise NotFoundError("Payment record not found.")
    return _payment_response_from_row(row)


async def _refresh_external_status(pool: Any, row: Any) -> Any:
    """Pull the latest payment status from the external provider when needed."""
    status = str(row["status"])
    provider = str(row["provider"])
    if status in {"paid", "expired", "failed"} or provider != "cutluy":
        return row

    cutluy = await resolve_cutluy_config(pool)
    api_key, _payment_link_id = _ensure_cutluy_ready(cutluy)
    url = f"{cutluy.api_base_url}/v1/payments/{row['external_payment_id']}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        message = exc.response.text or "Unable to refresh payment status from CutLuy."
        raise ExternalServiceError(
            f"CutLuy status check failed: {message}",
            is_retryable=exc.response.status_code >= 500,
            details={"provider": "cutluy", "status_code": exc.response.status_code},
        ) from exc
    except httpx.RequestError as exc:
        raise ExternalServiceError(
            "CutLuy status check failed.",
            is_retryable=True,
            details={"provider": "cutluy", "reason": type(exc).__name__},
        ) from exc

    updated = await pool.fetchrow(
        """
        UPDATE billing_payments
        SET status = $2,
            approved_at = CASE
                WHEN $3::timestamptz IS NULL THEN approved_at
                ELSE $3::timestamptz
            END,
            raw_response = $4::jsonb,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        row["id"],
        payload.get("status", row["status"]),
        _parse_cutluy_timestamp(payload.get("approved_at")),
        json.dumps(payload),
    )
    if updated is None:
        raise NotFoundError("Payment record not found.")
    return updated


async def _fulfill_profile_addon_payment(
    pool: Any,
    row: Any,
    metadata: dict[str, Any],
    *,
    conn: Any | None = None,
) -> Any:
    """Grant pending add-on slots after payment — quotas activate after onboarding."""
    from platform_api.repositories.license_repo import LicenseRepository, PlanRepository
    from platform_api.services.plan_tier_pricing_service import PROFILE_ADDON_STEP
    from platform_api.services.subscription_entitlement_service import validate_profile_addon_request

    addon_channels = int(metadata.get("addon_channels") or PROFILE_ADDON_STEP)
    license_id_raw = metadata.get("license_id")
    if not license_id_raw:
        raise ValidationError(
            "Profile add-on payment is missing license metadata.",
            details={"payment_id": str(row["id"])},
        )

    async def _run(connection: Any) -> Any:
        locked = await connection.fetchrow(
            """
            SELECT bp.*
            FROM billing_payments bp
            WHERE bp.id = $1
              AND bp.user_id = $2
            FOR UPDATE
            """,
            row["id"],
            row["user_id"],
        )
        if locked is None:
            raise NotFoundError("Payment record not found.")
        if locked["fulfilled_at"] is not None or str(locked["status"]) != "paid":
            return locked

        license_repo = LicenseRepository(pool=connection)
        plan_repo = PlanRepository(pool=connection)
        license_id = UUID(str(license_id_raw))
        license_obj = await license_repo.get_by_id(license_id)
        if license_obj is None or license_obj.user_id != UUID(str(locked["user_id"])):
            raise ValidationError("Add-on license is not active for this user.")

        plan = await plan_repo.get_by_id(license_obj.plan_id)
        if plan is None:
            raise NotFoundError("Associated plan not found.")

        try:
            validate_profile_addon_request(
                plan=plan,
                current_addon_slots=int(license_obj.profile_addon_slots or 0),
                current_addon_pending=int(getattr(license_obj, "profile_addon_pending", 0) or 0),
                add_channels=addon_channels,
            )
            await license_repo.add_profile_addon_pending(license_id, addon_channels)
        except ValueError as exc:
            raise ValidationError(str(exc), details={"addon_channels": addon_channels}) from exc

        fulfilled = await connection.fetchrow(
            """
            UPDATE billing_payments
            SET fulfilled_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
              AND fulfilled_at IS NULL
            RETURNING *
            """,
            locked["id"],
        )
        if fulfilled is None:
            raise NotFoundError("Payment record not found.")
        return fulfilled

    if conn is not None:
        return await _run(conn)

    async with pool.acquire() as acquired:
        async with acquired.transaction():
            return await _run(acquired)


async def _fulfill_credit_pack_payment(
    pool: Any,
    row: Any,
    metadata: dict[str, Any],
    *,
    conn: Any | None = None,
) -> Any:
    """Mint wallet credits after verified CutLuy credit-pack checkout."""
    from platform_api.dependencies import get_credit_service
    from platform_api.repositories.credit_repo import CreditRepository

    pack_id = str(metadata.get("pack_id") or "").strip()
    if not pack_id:
        raise ValidationError(
            "Credit pack payment is missing pack metadata.",
            details={"payment_id": str(row["id"])},
        )

    async def _run(connection: Any) -> Any:
        locked = await connection.fetchrow(
            """
            SELECT bp.*
            FROM billing_payments bp
            WHERE bp.id = $1
              AND bp.user_id = $2
            FOR UPDATE
            """,
            row["id"],
            row["user_id"],
        )
        if locked is None:
            raise NotFoundError("Payment record not found.")
        if locked["fulfilled_at"] is not None or str(locked["status"]) != "paid":
            return locked

        credit_repo = CreditRepository(pool=connection)
        from platform_api.repositories.license_repo import LicenseRepository, PlanRepository
        from platform_api.services.credit_service import CreditService

        credit_service = CreditService(
            credit_repo=credit_repo,
            license_repo=LicenseRepository(pool=connection),
            plan_repo=PlanRepository(pool=connection),
            pack_repo=credit_repo,
        )
        payment_ref = str(locked.get("external_payment_id") or locked["id"])
        await credit_service.purchase_pack(
            user_id=str(locked["user_id"]),
            pack_id=pack_id,
            payment_ref=payment_ref,
        )

        fulfilled = await connection.fetchrow(
            """
            UPDATE billing_payments
            SET fulfilled_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
              AND fulfilled_at IS NULL
            RETURNING *
            """,
            locked["id"],
        )
        if fulfilled is None:
            raise NotFoundError("Payment record not found.")
        return fulfilled

    if conn is not None:
        return await _run(conn)

    async with pool.acquire() as acquired:
        async with acquired.transaction():
            return await _run(acquired)


async def _resolve_billing_anchor_plan_id(pool: Any, user_id: UUID) -> UUID:
    license_repo = LicenseRepository(pool=pool)
    plan_repo = PlanRepository(pool=pool)
    active = await license_repo.get_active_for_user(user_id)
    if active is not None:
        return active.plan_id
    for plan in await plan_repo.get_all():
        if plan.is_active and str(getattr(plan, "plan_kind", "subscription")) == "subscription":
            return plan.id
    raise ValidationError(
        "No active subscription plan is available to anchor billing.",
        details={"error_code": "BILLING_ANCHOR_PLAN_MISSING"},
    )


async def _fulfill_addon_renewal_payment(
    pool: Any,
    row: Any,
    metadata: dict[str, Any],
    *,
    conn: Any | None = None,
) -> Any:
    """Grant plan-rate credits for renewed add-on channel blocks (slots unchanged)."""
    from platform_api.repositories.credit_repo import CreditRepository
    from platform_api.services.credit_units import credits_to_units
    from platform_api.services.v3.store import V3BillingStore

    credits = int(metadata.get("credits") or 0)

    async def _run(connection: Any) -> Any:
        locked = await connection.fetchrow(
            """
            SELECT bp.*
            FROM billing_payments bp
            WHERE bp.id = $1
              AND bp.user_id = $2
            FOR UPDATE
            """,
            row["id"],
            row["user_id"],
        )
        if locked is None:
            raise NotFoundError("Payment record not found.")
        if locked["fulfilled_at"] is not None or str(locked["status"]) != "paid":
            return locked

        owner = UUID(str(locked["user_id"]))
        if credits > 0:
            units = credits_to_units(credits)
            # Non-expiring: add-on channels are permanent, so their credits persist too.
            await V3BillingStore(pool=connection).insert_lot(
                user_id=owner,
                tag="pack",
                amount_units=units,
                expires_at=None,
                period_start=None,
            )
            await CreditRepository(pool=connection).add_credits(
                owner,
                units,
                reason="v3_addon_renewal",
                ref_id=f"addon_renewal:{locked['id']}",
            )

        fulfilled = await connection.fetchrow(
            """
            UPDATE billing_payments
            SET fulfilled_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
              AND fulfilled_at IS NULL
            RETURNING *
            """,
            locked["id"],
        )
        if fulfilled is None:
            raise NotFoundError("Payment record not found.")
        return fulfilled

    if conn is not None:
        return await _run(conn)

    async with pool.acquire() as acquired:
        async with acquired.transaction():
            return await _run(acquired)


async def _fulfill_paid_payment(pool: Any, row: Any) -> Any:
    """Assign the purchased plan and mark the local payment as fulfilled once."""
    if row["fulfilled_at"] is not None or str(row["status"]) != "paid":
        return row

    amount_cents_int: int | None
    try:
        amount_cents_int = int(row["amount_cents"])
    except (KeyError, TypeError, ValueError):
        amount_cents_int = None
    if amount_cents_int is not None and amount_cents_int <= 0:
        from platform_api.services.abuse_alert_service import maybe_note_zero_dollar_fulfill

        external_id = None
        try:
            external_id = str(row["external_payment_id"]) if row["external_payment_id"] else None
        except (KeyError, TypeError):
            external_id = None
        await maybe_note_zero_dollar_fulfill(
            payment_id=str(row["id"]),
            external_payment_id=external_id,
            amount_cents=amount_cents_int,
        )
        raise ValidationError(
            "Refusing to fulfill a zero-dollar payment.",
            details={
                "error_code": "ZERO_DOLLAR_FULFILL_BLOCKED",
                "payment_id": str(row["id"]),
                "amount_cents": amount_cents_int,
            },
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            locked = await conn.fetchrow(
                """
                SELECT bp.*,
                       p.name AS plan_name
                FROM billing_payments bp
                INNER JOIN plans p ON p.id = bp.plan_id
                WHERE bp.id = $1
                  AND bp.user_id = $2
                FOR UPDATE
                """,
                row["id"],
                row["user_id"],
            )
            if locked is None:
                raise NotFoundError("Payment record not found.")
            if locked["fulfilled_at"] is not None or str(locked["status"]) != "paid":
                return locked

            user_id = UUID(str(locked["user_id"]))
            plan_id = UUID(str(locked["plan_id"]))
            offer_id = locked["offer_id"]
            metadata = locked["metadata"] or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            if str(metadata.get("product_type") or "plan") == "profile_addon":
                return await _fulfill_profile_addon_payment(pool, locked, metadata, conn=conn)

            if str(metadata.get("product_type") or "plan") == "credit_pack":
                return await _fulfill_credit_pack_payment(pool, locked, metadata, conn=conn)

            if str(metadata.get("product_type") or "plan") == "addon_renewal":
                return await _fulfill_addon_renewal_payment(pool, locked, metadata, conn=conn)

            plan_repo = PlanRepository(pool=conn)
            license_repo = LicenseRepository(pool=conn)
            plan = await plan_repo.get_by_id(plan_id)
            if plan is None:
                raise NotFoundError("Purchased plan not found.", details={"plan_id": str(plan_id)})

            active_license = await license_repo.get_active_for_user(user_id)
            # Renewals must reuse the existing license (even when lapsed) so add-on
            # slots and the plan association are preserved instead of creating a
            # duplicate license.
            target_license = active_license
            if target_license is None:
                target_license = await license_repo.get_latest_license_for_user(user_id)
            same_plan = (
                target_license is not None
                and UUID(str(target_license.plan_id)) == plan_id
            )

            from platform_api.repositories.credit_repo import (
                CreditRepository as _CreditRepository,
            )
            from platform_api.services.v3.period_grant_service import PeriodGrantService
            from platform_api.services.v3.store import V3BillingStore

            grant_service = PeriodGrantService(
                store=V3BillingStore(pool=conn),
                credit_repo=_CreditRepository(pool=conn),
                plan_repo=PlanRepository(pool=conn),
            )

            if same_plan and active_license is not None:
                # Active same-plan renewal: stack the new period on the current expiry so
                # renewing early never drops remaining days.
                cycle_days = int(plan.billing_cycle_days or 30)
                assigned_license = await license_repo.extend_license(
                    active_license.id, cycle_days
                )
                if assigned_license is None:
                    raise NotFoundError(
                        "Active license not found during renewal.",
                        details={"license_id": str(active_license.id)},
                    )
                # Carry unused grant credits into the new period: leftover + allowance,
                # expiring with the new period (no loss at renewal, still expires).
                await grant_service.carryover_period_grant(
                    user_id=user_id,
                    monthly_credits=int(plan.monthly_credits or 0),
                    billing_cycle_days=cycle_days,
                    new_expires_at=assigned_license.expires_at or datetime.now(timezone.utc),
                )
            elif target_license is not None:
                # Lapsed same-plan renewal or plan change: reactivate the existing
                # license in place (keeps add-on slots; resets the period).
                assigned_license = await license_repo.change_plan(
                    target_license.id, plan_id, plan
                )
                if assigned_license is None:
                    raise NotFoundError(
                        "License not found during plan change.",
                        details={"license_id": str(target_license.id)},
                    )
            else:
                created_license = await license_repo.create(plan_id)
                assigned_license = await license_repo.assign_to_user(
                    created_license.id, user_id, plan
                )

            # Mint this period's grant immediately on payment so users do not have to
            # open the portal to receive their credits. Idempotent per period.
            await grant_service.ensure_period_grant(user_id)

            from platform_api.repositories.credit_repo import CreditRepository
            from platform_api.services.billing_mode_service import grant_included_wallet_credits

            credit_repo = CreditRepository(pool=conn)
            await grant_included_wallet_credits(
                credit_repo,
                user_id=user_id,
                plan=plan,
                license_id=assigned_license.id,
            )

            if offer_id is not None:
                await conn.execute(
                    """
                    UPDATE plan_offers
                    SET current_redemptions = current_redemptions + 1,
                        is_active = CASE
                            WHEN current_redemptions + 1 >= max_redemptions THEN false
                            ELSE is_active
                        END
                    WHERE id = $1
                      AND is_active = true
                      AND current_redemptions < max_redemptions
                    """,
                    offer_id,
                )

            redeem_code_id = metadata.get("redeem_code_id")
            redeem_code = metadata.get("redeem_code")
            if redeem_code_id and redeem_code:
                await record_discount_redemption(
                    conn,
                    redeem_code_id=UUID(str(redeem_code_id)),
                    code=str(redeem_code),
                    user_id=user_id,
                    billing_payment_id=UUID(str(locked["id"])),
                    plan_id=plan_id,
                    final_amount_cents=int(locked["amount_cents"]),
                )

            fulfilled = await conn.fetchrow(
                """
                UPDATE billing_payments
                SET fulfilled_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                  AND fulfilled_at IS NULL
                RETURNING *
                """,
                locked["id"],
            )
            if fulfilled is None:
                raise NotFoundError("Payment record not found.")
            return fulfilled


async def _create_mock_payment(
    pool: Any,
    *,
    ctx: AuthContext,
    plan_id: UUID,
    plan_name: str,
    amount_cents: int,
    offer_id: UUID | None,
    extra_metadata: dict[str, Any] | None = None,
) -> BillingPaymentResponse:
    """Create a local mock hosted checkout payment for development use."""
    payment_id = uuid4()
    external_payment_id = f"mock_{payment_id.hex}"
    reference_id = f"camxora:mock:{ctx.user_id}:{plan_id}:{uuid4().hex[:12]}"
    portal_base_url = await _get_portal_base_url(pool)
    checkout_url = f"{portal_base_url}/checkout/mock/{payment_id}"
    metadata = {
        "user_id": ctx.user_id,
        "plan_id": str(plan_id),
        "plan_name": plan_name,
        "offer_id": str(offer_id) if offer_id is not None else None,
        "mode": "mock",
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    created = await pool.fetchrow(
        """
        INSERT INTO billing_payments (
            id,
            provider,
            external_payment_id,
            user_id,
            plan_id,
            offer_id,
            reference_id,
            status,
            amount_cents,
            currency,
            checkout_url,
            approved_at,
            metadata,
            raw_response,
            created_at,
            updated_at
        )
        VALUES (
            $1,
            'mock',
            $2,
            $3,
            $4,
            $5,
            $6,
            'pending',
            $7,
            'USD',
            $8,
            NULL,
            $9::jsonb,
            $10::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """,
        payment_id,
        external_payment_id,
        UUID(ctx.user_id),
        plan_id,
        offer_id,
        reference_id,
        amount_cents,
        checkout_url,
        json.dumps(metadata),
        json.dumps(
            {
                "provider": "mock",
                "status": "pending",
                "checkout_url": checkout_url,
                "amount": f"{amount_cents / 100:.2f}",
            }
        ),
    )
    if created is None:
        raise ExternalServiceError("Mock payment record could not be created.")

    return await _hydrate_created_payment(pool, payment_id)


async def _create_cutluy_payment(
    pool: Any,
    *,
    ctx: AuthContext,
    plan_id: UUID,
    plan_name: str,
    amount_cents: int,
    offer_id: UUID | None,
    extra_metadata: dict[str, Any] | None = None,
) -> BillingPaymentResponse:
    """Create a real CutLuy hosted checkout using the admin-managed plan price."""
    cutluy = await resolve_cutluy_config(pool)
    api_key, payment_link_id = _ensure_cutluy_ready(cutluy)
    amount_usd = f"{amount_cents / 100:.2f}"
    reference_id = f"camxora:{ctx.user_id}:{plan_id}:{uuid4().hex[:12]}"
    metadata = {
        "user_id": ctx.user_id,
        "plan_id": str(plan_id),
        "plan_name": plan_name,
        "offer_id": str(offer_id) if offer_id is not None else None,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    payload: dict[str, Any] = {
        "amount": float(amount_usd),
        "reference_id": reference_id,
        "metadata": metadata,
        "idempotency_key": reference_id,
    }
    if payment_link_id is not None:
        payload["payment_link_id"] = payment_link_id

    url = f"{cutluy.api_base_url}/v1/payments"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            payment = response.json()
    except httpx.HTTPStatusError as exc:
        message = exc.response.text or "Unable to create payment with CutLuy."
        raise ExternalServiceError(
            f"CutLuy payment creation failed: {message}",
            is_retryable=exc.response.status_code >= 500,
            details={"provider": "cutluy", "status_code": exc.response.status_code},
        ) from exc
    except httpx.RequestError as exc:
        raise ExternalServiceError(
            "CutLuy payment creation failed.",
            is_retryable=True,
            details={"provider": "cutluy", "reason": type(exc).__name__},
        ) from exc

    from platform_api.services.shared.cutluy_service import extract_cutluy_qr_string

    metadata["qr_string"] = extract_cutluy_qr_string(payment) or ""

    created = await pool.fetchrow(
        """
        INSERT INTO billing_payments (
            id,
            provider,
            external_payment_id,
            user_id,
            plan_id,
            offer_id,
            reference_id,
            status,
            amount_cents,
            currency,
            checkout_url,
            approved_at,
            metadata,
            raw_response,
            created_at,
            updated_at
        )
        VALUES (
            $1,
            'cutluy',
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            $11::timestamptz,
            $12::jsonb,
            $13::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """,
        uuid4(),
        payment["id"],
        UUID(ctx.user_id),
        plan_id,
        offer_id,
        reference_id,
        payment.get("status", "pending"),
        _to_cents(payment.get("amount", amount_usd)),
        payment.get("currency", "USD"),
        payment["checkout_url"],
        _parse_cutluy_timestamp(payment.get("approved_at")),
        json.dumps(metadata),
        json.dumps(payment),
    )
    if created is None:
        raise ExternalServiceError("Payment record could not be created.")

    return await _hydrate_created_payment(pool, UUID(str(created["id"])))


async def _create_payment_response(
    request: CreatePaymentRequest,
    *,
    provider: str,
    ctx: AuthContext,
    pool: Any,
    return_path: str | None = None,
) -> BillingPaymentResponse:
    """Create a payment through the resolved active provider."""
    user_id = UUID(ctx.user_id)
    plan_id = UUID(request.plan_id)
    plan_repo = PlanRepository(pool=pool)
    plan = await plan_repo.get_by_id(plan_id)
    if plan is None or not plan.is_active:
        raise NotFoundError("Plan not found.", details={"plan_id": request.plan_id})
    if (plan.name or "").strip().lower() == "trial":
        raise ValidationError("Trial does not require payment.")

    existing_pending = await _fetch_existing_pending_payment(pool, user_id=user_id, plan_id=plan_id)
    if existing_pending is not None:
        return _payment_response_from_row(existing_pending)

    license_repo = LicenseRepository(pool=pool)
    active_license = await license_repo.get_active_for_user(user_id)
    extra_metadata: dict[str, Any] = {"original_amount_cents": int(plan.price_cents), "product_type": "plan"}
    if return_path:
        extra_metadata["return_path"] = return_path
    amount_cents = int(plan.price_cents)
    offer_id: UUID | None = None
    use_public_offer = True

    if active_license is not None:
        current_plan = await plan_repo.get_by_id(active_license.plan_id)
        if current_plan is not None and current_plan.id != plan.id:
            from platform_api.services.plan_change_service import resolve_plan_change_checkout

            use_public_offer = False
            change_amount, change_meta = resolve_plan_change_checkout(
                current_plan=current_plan,
                target_plan=plan,
                license_expires_at=active_license.expires_at,
                list_price_cents=int(plan.price_cents),
            )
            amount_cents = change_amount
            extra_metadata.update(change_meta)

    if use_public_offer:
        offer_row = await _get_best_offer_row(pool, plan_id)
        best_public_amount_cents = (
            int(offer_row["promo_price_cents"]) if offer_row is not None else int(plan.price_cents)
        )
        amount_cents = best_public_amount_cents
        offer_id = UUID(str(offer_row["id"])) if offer_row is not None else None
        extra_metadata["public_offer_price_cents"] = best_public_amount_cents

    redeem_code = (request.redeem_code or "").strip()
    if redeem_code:
        preview = await preview_redeem_code(
            pool,
            code=redeem_code,
            plan_id=plan_id,
            plan_price_cents=int(plan.price_cents),
            public_offer_price_cents=best_public_amount_cents,
            user_id=user_id,
        )
        if preview["reward_type"] == REWARD_TYPE_CREDIT_GRANT:
            raise ValidationError(
                "This code grants wallet credits. Redeem it from the signed-in user panel instead of checkout."
            )
        amount_cents = int(preview["final_amount_cents"] or amount_cents)
        if bool(preview["applied_discount"]):
            offer_id = None
            extra_metadata.update(
                {
                    "redeem_code_id": preview["id"],
                    "redeem_code": preview["code"],
                    "redeem_reward_type": preview["reward_type"],
                    "public_offer_price_cents": best_public_amount_cents,
                }
            )

    if amount_cents <= 0:
        payment_id = uuid4()
        portal_base_url = await _get_portal_base_url(pool)
        checkout_url = f"{portal_base_url}/onboarding?payment_id={payment_id}"
        created = await pool.fetchrow(
            """
            INSERT INTO billing_payments (
                id,
                provider,
                external_payment_id,
                user_id,
                plan_id,
                offer_id,
                reference_id,
                status,
                amount_cents,
                currency,
                checkout_url,
                approved_at,
                metadata,
                raw_response,
                created_at,
                updated_at
            )
            VALUES (
                $1,
                'redeem_code',
                $2,
                $3,
                $4,
                $5,
                $6,
                'paid',
                0,
                'USD',
                $7,
                NOW(),
                $8::jsonb,
                $9::jsonb,
                NOW(),
                NOW()
            )
            RETURNING id
            """,
            payment_id,
            f"redeem_{payment_id.hex}",
            user_id,
            plan_id,
            offer_id,
            f"camxora:redeem:{ctx.user_id}:{plan_id}:{uuid4().hex[:12]}",
            checkout_url,
            json.dumps(extra_metadata),
            json.dumps(
                {
                    "provider": "redeem_code",
                    "status": "paid",
                    "checkout_url": checkout_url,
                    "amount": "0.00",
                }
            ),
        )
        if created is None:
            raise ExternalServiceError("Redeem-code payment record could not be created.")
        return await _get_payment_response(payment_id, ctx=ctx, pool=pool)

    if not provider:
        raise ValidationError(
            "Paid checkout is currently unavailable. Enable a KHQR provider in Admin Settings first."
        )

    if provider == "mock":
        _ensure_mock_checkout_allowed()
        return await _create_mock_payment(
            pool,
            ctx=ctx,
            plan_id=plan_id,
            plan_name=plan.name,
            amount_cents=amount_cents,
            offer_id=offer_id,
            extra_metadata=extra_metadata,
        )

    if provider == "cutluy":
        return await _create_cutluy_payment(
            pool,
            ctx=ctx,
            plan_id=plan_id,
            plan_name=plan.name,
            amount_cents=amount_cents,
            offer_id=offer_id,
            extra_metadata=extra_metadata,
        )

    raise ValidationError("Unsupported billing provider.", details={"provider": provider})


async def _get_payment_response(payment_id: UUID, *, ctx: AuthContext, pool: Any) -> BillingPaymentResponse:
    """Return local payment state, refresh provider state, and fulfill paid purchases."""
    row = await _fetch_payment_row(pool, payment_id=payment_id, user_id=UUID(ctx.user_id))
    if row is None:
        raise NotFoundError("Payment not found.", details={"payment_id": str(payment_id)})

    try:
        row = await _refresh_external_status(pool, row)
    except ExternalServiceError:
        logger.warning("Unable to refresh payment %s", payment_id, exc_info=True)

    if str(row["status"]) == "paid" and row["fulfilled_at"] is None:
        row = await _fulfill_paid_payment(pool, row)

    hydrated = await _fetch_payment_row(pool, payment_id=payment_id, user_id=UUID(ctx.user_id))
    if hydrated is None:
        raise NotFoundError("Payment not found.", details={"payment_id": str(payment_id)})
    return _payment_response_from_row(hydrated)


@router.get(
    "/providers",
    response_model=BillingProviderConfigResponse,
    status_code=200,
    summary="Get KHQR billing provider configuration",
)
async def list_billing_providers(pool: Any = Depends(get_db_pool)) -> BillingProviderConfigResponse:
    """Return enabled/active/available provider state for admin and onboarding UIs."""
    return await _get_provider_config(pool)


@router.post(
    "/payments",
    response_model=BillingPaymentResponse,
    status_code=201,
    summary="Create a checkout payment using the active billing provider",
)
async def create_payment(
    request: CreatePaymentRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Create a payment using the active enabled provider configured in admin settings."""
    provider = await _get_active_provider(pool)
    return await _create_payment_response(request, provider=provider or "", ctx=ctx, pool=pool)


async def _resolve_renewable_license(pool: Any, user_id: UUID) -> tuple[Any, Any] | None:
    """Return (license, plan) for the user's renewable paid plan, hidden plans included.

    Prefers the active license; falls back to the most recent non-revoked license so a
    lapsed desktop plan can still be renewed. Returns None when there is nothing payable.
    """
    repo = LicenseRepository(pool=pool)
    license_obj = await repo.get_active_for_user(user_id)
    if license_obj is None:
        license_obj = await repo.get_latest_license_for_user(user_id)
    if license_obj is None:
        return None

    plan = await PlanRepository(pool=pool).get_by_id(license_obj.plan_id)
    if plan is None:
        return None
    if int(plan.price_cents or 0) <= 0:
        return None
    if plan.billing_cycle_days is None or int(plan.billing_cycle_days) <= 0:
        return None
    return license_obj, plan


def _renewal_window(
    expires_at: datetime | None, now: datetime
) -> tuple[bool, int | None, bool, int | None]:
    """Return ``(renewable, days_left, expired, opens_in_days)``.

    Renewal opens ``RENEWAL_WINDOW_DAYS`` before expiry and stays open once
    expired. An open-ended license (no expiry) is always renewable.
    """
    if expires_at is None:
        return True, None, False, None
    expired = expires_at <= now
    days_left = (expires_at - now).days
    renewable = expired or days_left <= RENEWAL_WINDOW_DAYS
    opens_in_days = None if renewable else days_left - RENEWAL_WINDOW_DAYS
    return renewable, days_left, expired, opens_in_days


async def _resolve_addon_channels(pool: Any, user_id: UUID) -> tuple[Any, Any, int] | None:
    """Return (license, plan, addon_channels) for the user's renewable add-on channels."""
    from platform_api.services.plan_tier_pricing_service import PROFILE_ADDON_STEP

    repo = LicenseRepository(pool=pool)
    license_obj = await repo.get_active_for_user(user_id)
    if license_obj is None:
        license_obj = await repo.get_latest_license_for_user(user_id)
    if license_obj is None:
        return None
    addon_channels = int(getattr(license_obj, "profile_addon_slots", 0) or 0)
    if addon_channels < PROFILE_ADDON_STEP:
        return None
    plan = await PlanRepository(pool=pool).get_by_id(license_obj.plan_id)
    if plan is None or int(plan.monthly_credits or 0) <= 0 or int(plan.price_cents or 0) <= 0:
        return None
    return license_obj, plan, addon_channels


@router.get(
    "/renewals/quota",
    response_model=QuotaRenewalResponse,
    status_code=200,
    summary="Get the signed-in user's renewable plan details",
)
async def get_quota_renewal(
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> QuotaRenewalResponse:
    """Return the user's own plan (hidden plans included) so they can renew it.

    The plan is intentionally resolved from the user's own license, never from the
    public catalog, so a hidden legacy plan like the $79 desktop plan stays invisible
    to everyone else while its owner can still pay for the next period. ``eligible``
    is true whenever the user has a renewable paid plan; ``renewable`` is true only
    inside the renewal window (``RENEWAL_WINDOW_DAYS`` before expiry, or once expired).
    """
    resolved = await _resolve_renewable_license(pool, UUID(ctx.user_id))
    if resolved is None:
        return QuotaRenewalResponse(eligible=False)

    license_obj, plan = resolved
    expires_at = license_obj.expires_at
    now = datetime.now(timezone.utc)
    renewable, days_left, expired, opens_in_days = _renewal_window(expires_at, now)
    return QuotaRenewalResponse(
        eligible=True,
        plan_id=str(plan.id),
        plan_name=str(plan.name),
        price_cents=int(plan.price_cents or 0),
        billing_cycle_days=int(plan.billing_cycle_days or 0),
        expires_at=expires_at,
        days_left=days_left,
        expired=expired,
        renewable=renewable,
        renewal_opens_in_days=opens_in_days,
        renewal_window_days=RENEWAL_WINDOW_DAYS,
    )


@router.post(
    "/renewals/quota",
    response_model=BillingPaymentResponse,
    status_code=201,
    summary="Create a checkout to renew the signed-in user's plan",
)
async def create_quota_renewal(
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Start a one-cycle renewal checkout for the user's own plan.

    Fulfillment reuses the standard plan-payment path: the same plan id resets the
    license period through ``change_plan`` (or assigns a fresh license when the old
    one lapsed), and the next ``/api/v3/me/credits`` read mints the new period grant.
    """
    resolved = await _resolve_renewable_license(pool, UUID(ctx.user_id))
    if resolved is None:
        raise NotFoundError(
            "No renewable paid plan was found for this account.",
            details={"error_code": "NO_RENEWABLE_PLAN"},
        )
    license_obj, plan = resolved
    renewable, days_left, expired, opens_in_days = _renewal_window(
        license_obj.expires_at, datetime.now(timezone.utc)
    )
    if not renewable:
        raise ValidationError(
            f"Renewal opens {RENEWAL_WINDOW_DAYS} days before your plan ends.",
            details={
                "error_code": "RENEWAL_NOT_YET_OPEN",
                "days_left": days_left,
                "renewal_opens_in_days": opens_in_days,
                "renewal_window_days": RENEWAL_WINDOW_DAYS,
            },
        )
    provider = await _get_active_provider(pool)
    portal_base_url = await _get_portal_base_url(pool)
    request = CreatePaymentRequest(plan_id=str(plan.id))
    return await _create_payment_response(
        request,
        provider=provider or "",
        ctx=ctx,
        pool=pool,
        return_path=f"{portal_base_url}/dashboard/billing",
    )


@router.get(
    "/renewals/addons",
    response_model=AddonRenewalResponse,
    status_code=200,
    summary="Get the signed-in user's renewable add-on channels",
)
async def get_addon_renewal(
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> AddonRenewalResponse:
    """Return the user's add-on channel blocks and what renewing them grants.

    Channels are permanent and add-on renewal is open at any time; each renewed
    2-channel block grants credits at the plan rate so the user can keep running
    those channels without buying more-expensive packs.
    """
    from platform_api.services.plan_tier_pricing_service import PROFILE_ADDON_STEP

    resolved = await _resolve_addon_channels(pool, UUID(ctx.user_id))
    if resolved is None:
        return AddonRenewalResponse(eligible=False)
    _license_obj, plan, addon_channels = resolved
    blocks = addon_channels // PROFILE_ADDON_STEP
    credits_per_block = int(plan.monthly_credits or 0)
    price_per_block = int(plan.price_cents or 0)
    return AddonRenewalResponse(
        eligible=True,
        addon_channels=addon_channels,
        blocks=blocks,
        credits=blocks * credits_per_block,
        price_cents=blocks * price_per_block,
        credits_per_block=credits_per_block,
        price_per_block_cents=price_per_block,
        expires_at=_license_obj.expires_at,
        renewable=True,
        renewal_window_days=RENEWAL_WINDOW_DAYS,
    )


@router.post(
    "/renewals/addons",
    response_model=BillingPaymentResponse,
    status_code=201,
    summary="Create a checkout to renew the signed-in user's add-on channels",
)
async def create_addon_renewal(
    request: AddonRenewalRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Start a renewal checkout for a chosen number of 2-channel add-on blocks."""
    from platform_api.services.plan_tier_pricing_service import PROFILE_ADDON_STEP

    resolved = await _resolve_addon_channels(pool, UUID(ctx.user_id))
    if resolved is None:
        raise NotFoundError(
            "No add-on channels were found to renew for this account.",
            details={"error_code": "NO_ADDON_CHANNELS"},
        )
    license_obj, plan, addon_channels = resolved
    blocks_total = addon_channels // PROFILE_ADDON_STEP
    blocks = int(request.blocks or blocks_total)
    blocks = max(1, min(blocks, blocks_total))
    price_cents = blocks * int(plan.price_cents or 0)
    credits = blocks * int(plan.monthly_credits or 0)
    provider = await _get_active_provider(pool)
    portal_base_url = await _get_portal_base_url(pool)
    plan_name = f"{plan.name} · renew {blocks * PROFILE_ADDON_STEP} add-on channels"
    extra_metadata: dict[str, Any] = {
        "product_type": "addon_renewal",
        "addon_channels": blocks * PROFILE_ADDON_STEP,
        "blocks": blocks,
        "credits": credits,
        "license_id": str(license_obj.id),
        "return_path": f"{portal_base_url}/dashboard/billing",
    }
    if provider == "mock":
        _ensure_mock_checkout_allowed()
        return await _create_mock_payment(
            pool,
            ctx=ctx,
            plan_id=plan.id,
            plan_name=plan_name,
            amount_cents=price_cents,
            offer_id=None,
            extra_metadata=extra_metadata,
        )
    if provider != "cutluy":
        raise ValidationError("No active billing provider is configured.")
    return await _create_cutluy_payment(
        pool,
        ctx=ctx,
        plan_id=plan.id,
        plan_name=plan_name,
        amount_cents=price_cents,
        offer_id=None,
        extra_metadata=extra_metadata,
    )


async def _create_profile_addon_payment_response(
    request: CreateProfileAddonPaymentRequest,
    *,
    provider: str,
    ctx: AuthContext,
    pool: Any,
) -> BillingPaymentResponse:
    """Create checkout for +2 channel add-ons on the user's active subscription."""
    from platform_api.repositories.license_repo import LicenseRepository, PlanRepository
    from platform_api.services.plan_tier_pricing_service import (
        PROFILE_ADDON_STEP,
        find_profile_addon_plan,
        quote_profile_addon_for_subscription,
    )
    from platform_api.services.plan_term_discount_service import load_plan_term_discounts
    from platform_api.services.subscription_entitlement_service import (
        effective_quota_channels,
        validate_profile_addon_request,
    )

    if request.addon_channels % PROFILE_ADDON_STEP != 0:
        raise ValidationError(
            message=f"Profile add-ons must be purchased in multiples of {PROFILE_ADDON_STEP}.",
            details={"addon_channels": request.addon_channels},
        )

    user_id = UUID(ctx.user_id)
    license_repo = LicenseRepository(pool=pool)
    plan_repo = PlanRepository(pool=pool)
    license_obj = await license_repo.get_active_for_user(user_id)
    if license_obj is None:
        raise NotFoundError("No active subscription found for profile add-ons.")

    plan = await plan_repo.get_by_id(license_obj.plan_id)
    if plan is None:
        raise NotFoundError("Associated plan not found.")

    validate_profile_addon_request(
        plan=plan,
        current_addon_slots=int(license_obj.profile_addon_slots or 0),
        current_addon_pending=int(getattr(license_obj, "profile_addon_pending", 0) or 0),
        add_channels=request.addon_channels,
    )

    all_plans = await plan_repo.get_all()
    billing_cycle_days = int(plan.billing_cycle_days or 30)
    addon_plan = find_profile_addon_plan(
        all_plans,
        request.addon_channels,
        billing_cycle_days=billing_cycle_days,
    )
    if addon_plan is None:
        raise NotFoundError(
            f"No active profile add-on plan found for +{request.addon_channels} channels."
        )

    current_channels = effective_quota_channels(
        plan,
        int(license_obj.profile_addon_slots or 0),
    )
    discounts = await load_plan_term_discounts(pool)
    quote = quote_profile_addon_for_subscription(
        current_channels=current_channels,
        addon_channels=request.addon_channels,
        addon_plan=addon_plan,
        subscription_billing_cycle_days=billing_cycle_days,
        semi_annual_discount_percent=discounts.semi_annual_discount_percent,
        annual_discount_percent=discounts.annual_discount_percent,
    )
    amount_cents = int(quote.monthly_addon_cents)
    if amount_cents <= 0:
        raise ValidationError("Unable to quote a positive add-on price.")

    portal_base_url = await _get_portal_base_url(pool)
    return_path = f"{portal_base_url}/onboarding?mode=addon"
    extra_metadata: dict[str, Any] = {
        "product_type": "profile_addon",
        "addon_channels": request.addon_channels,
        "addon_plan_id": str(addon_plan.id),
        "license_id": str(license_obj.id),
        "quoted_cents": amount_cents,
        "current_channels": current_channels,
        "new_total_channels": quote.new_total_channels,
        "return_path": return_path,
    }

    if provider == "mock":
        _ensure_mock_checkout_allowed()
        payment_id = uuid4()
        checkout_url = f"{portal_base_url}/checkout/mock/{payment_id}?mode=addon"
        metadata = {
            "user_id": ctx.user_id,
            "plan_id": str(plan.id),
            "plan_name": f"{plan.name} · +{request.addon_channels} channels",
            **extra_metadata,
            "mode": "mock",
        }
        created = await pool.fetchrow(
            """
            INSERT INTO billing_payments (
                id, provider, external_payment_id, user_id, plan_id, offer_id,
                reference_id, status, amount_cents, currency, checkout_url,
                approved_at, metadata, raw_response, created_at, updated_at
            )
            VALUES (
                $1, 'mock', $2, $3, $4, NULL, $5, 'pending', $6, 'USD', $7,
                NULL, $8::jsonb, $9::jsonb, NOW(), NOW()
            )
            RETURNING id
            """,
            payment_id,
            f"mock_{payment_id.hex[:12]}",
            user_id,
            plan.id,
            f"addon:{ctx.user_id}:{uuid4().hex[:12]}",
            amount_cents,
            checkout_url,
            json.dumps(metadata),
            json.dumps({"provider": "mock", "status": "pending", "checkout_url": checkout_url}),
        )
        if created is None:
            raise ExternalServiceError("Mock payment record could not be created.")
        return await _hydrate_created_payment(pool, payment_id)

    if provider != "cutluy":
        raise ValidationError("No active billing provider is configured.")

    return await _create_cutluy_payment(
        pool,
        ctx=ctx,
        plan_id=plan.id,
        plan_name=f"{plan.name} · +{request.addon_channels} channels",
        amount_cents=amount_cents,
        offer_id=None,
        extra_metadata=extra_metadata,
    )


@router.post(
    "/profile-addon/payments",
    response_model=BillingPaymentResponse,
    status_code=201,
    summary="Create checkout for +2 channel profile add-ons",
)
async def create_profile_addon_payment(
    request: CreateProfileAddonPaymentRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Checkout for additional channel profiles; onboarding activates quotas."""
    provider = await _get_active_provider(pool)
    return await _create_profile_addon_payment_response(
        request,
        provider=provider or "",
        ctx=ctx,
        pool=pool,
    )


async def _create_credit_pack_payment_response(
    request: CreateCreditPackPaymentRequest,
    *,
    provider: str,
    ctx: AuthContext,
    pool: Any,
) -> BillingPaymentResponse:
    from platform_api.repositories.credit_repo import CreditRepository

    user_id = UUID(ctx.user_id)
    pack_id = UUID(request.pack_id)
    credit_repo = CreditRepository(pool=pool)
    pack = await credit_repo.get_by_id(pack_id)
    if pack is None or not pack.get("is_active", False):
        raise NotFoundError("Credit pack not found.", details={"pack_id": request.pack_id})

    amount_cents = int(pack["price_cents"] or 0)
    if amount_cents <= 0:
        raise ValidationError("Credit pack price must be greater than zero.")

    anchor_plan_id = await _resolve_billing_anchor_plan_id(pool, user_id)
    pack_name = str(pack.get("name") or "Credit pack")
    portal_base_url = await _get_portal_base_url(pool)
    extra_metadata: dict[str, Any] = {
        "product_type": "credit_pack",
        "pack_id": str(pack_id),
        "pack_name": pack_name,
        "return_path": f"{portal_base_url}/dashboard/billing?tab=credits",
    }

    if provider == "mock":
        _ensure_mock_checkout_allowed()
        payment_id = uuid4()
        checkout_url = f"{portal_base_url}/checkout/mock/{payment_id}?mode=credit_pack"
        metadata = {
            "user_id": ctx.user_id,
            "plan_id": str(anchor_plan_id),
            "plan_name": pack_name,
            **extra_metadata,
            "mode": "mock",
        }
        created = await pool.fetchrow(
            """
            INSERT INTO billing_payments (
                id, provider, external_payment_id, user_id, plan_id, offer_id,
                reference_id, status, amount_cents, currency, checkout_url,
                approved_at, metadata, raw_response, created_at, updated_at
            )
            VALUES (
                $1, 'mock', $2, $3, $4, NULL, $5, 'pending', $6, 'USD', $7,
                NULL, $8::jsonb, $9::jsonb, NOW(), NOW()
            )
            RETURNING id
            """,
            payment_id,
            f"mock_{payment_id.hex[:12]}",
            user_id,
            anchor_plan_id,
            f"pack:{ctx.user_id}:{uuid4().hex[:12]}",
            amount_cents,
            checkout_url,
            json.dumps(metadata),
            json.dumps({"provider": "mock", "status": "pending", "checkout_url": checkout_url}),
        )
        if created is None:
            raise ExternalServiceError("Mock payment record could not be created.")
        return await _hydrate_created_payment(pool, payment_id)

    if provider != "cutluy":
        raise ValidationError("No active billing provider is configured.")

    return await _create_cutluy_payment(
        pool,
        ctx=ctx,
        plan_id=anchor_plan_id,
        plan_name=pack_name,
        amount_cents=amount_cents,
        offer_id=None,
        extra_metadata=extra_metadata,
    )


@router.post(
    "/credit-pack/payments",
    response_model=BillingPaymentResponse,
    status_code=201,
    summary="Create checkout for a wallet credit pack",
)
async def create_credit_pack_payment(
    request: CreateCreditPackPaymentRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Checkout for wallet top-ups via CutLuy; credits mint after webhook fulfillment."""
    provider = await _get_active_provider(pool)
    return await _create_credit_pack_payment_response(
        request,
        provider=provider or "",
        ctx=ctx,
        pool=pool,
    )


@router.post(
    "/schedule-downgrade",
    status_code=200,
    summary="Schedule a plan downgrade at the current period end",
)
async def schedule_downgrade(
    request: ScheduleDowngradeRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> dict[str, str]:
    from platform_api.services.plan_change_service import is_plan_downgrade

    user_id = UUID(ctx.user_id)
    target_plan_id = UUID(request.plan_id)
    license_repo = LicenseRepository(pool=pool)
    plan_repo = PlanRepository(pool=pool)

    active = await license_repo.get_active_for_user(user_id)
    if active is None:
        raise NotFoundError("No active subscription found.")

    current_plan = await plan_repo.get_by_id(active.plan_id)
    target_plan = await plan_repo.get_by_id(target_plan_id)
    if current_plan is None or target_plan is None or not target_plan.is_active:
        raise NotFoundError("Plan not found.")

    if not is_plan_downgrade(current_plan, target_plan):
        raise ValidationError(
            "Only downgrades can be scheduled. Use checkout to upgrade or change billing term.",
            details={"error_code": "NOT_A_DOWNGRADE"},
        )

    if active.expires_at is None:
        raise ValidationError(
            "This subscription has no renewal date; contact support to change plans.",
            details={"error_code": "DOWNGRADE_NO_RENEWAL_DATE"},
        )

    updated = await license_repo.schedule_pending_plan(
        active.id,
        target_plan_id,
        effective_at=active.expires_at,
    )
    if updated is None:
        raise NotFoundError("Active license not found.")

    return {
        "status": "scheduled",
        "effective_at": active.expires_at.isoformat(),
        "pending_plan_id": str(target_plan_id),
    }


@router.get(
    "/payments",
    response_model=list[BillingPaymentResponse],
    status_code=200,
    summary="List recent billing payments for the current user",
)
async def list_payments(
    ctx: CurrentUserDep,
    limit: int = Query(default=8, ge=1, le=25),
    pool: Any = Depends(get_db_pool),
) -> list[BillingPaymentResponse]:
    """Return recent billing payments for the authenticated user."""
    rows = await pool.fetch(
        """
        SELECT bp.*,
               p.name AS plan_name
        FROM billing_payments bp
        INNER JOIN plans p ON p.id = bp.plan_id
        WHERE bp.user_id = $1
        ORDER BY bp.created_at DESC
        LIMIT $2
        """,
        UUID(ctx.user_id),
        limit,
    )
    return [_payment_response_from_row(row) for row in rows]


@router.get(
    "/payments/resolve",
    response_model=BillingPaymentResponse,
    status_code=200,
    summary="Resolve a payment by CutLuy external id for the current user",
)
async def resolve_payment(
    external_payment_id: str,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Map a hosted-checkout return (CutLuy payment id) to the local billing record."""
    external_id = external_payment_id.strip()
    if not external_id:
        raise ValidationError("external_payment_id is required.")

    row = await _fetch_payment_row_by_external_id(
        pool,
        external_payment_id=external_id,
        user_id=UUID(ctx.user_id),
    )
    if row is None:
        raise NotFoundError(
            "Payment not found.",
            details={"external_payment_id": external_id},
        )

    try:
        row = await _refresh_external_status(pool, row)
    except ExternalServiceError:
        logger.warning(
            "Unable to refresh payment %s during external resolve",
            external_id,
            exc_info=True,
        )

    if str(row["status"]) == "paid" and row["fulfilled_at"] is None:
        row = await _fulfill_paid_payment(pool, row)

    hydrated = await _fetch_payment_row_by_external_id(
        pool,
        external_payment_id=external_id,
        user_id=UUID(ctx.user_id),
    )
    if hydrated is None:
        raise NotFoundError(
            "Payment not found.",
            details={"external_payment_id": external_id},
        )
    return _payment_response_from_row(hydrated)


@router.get(
    "/payments/{payment_id}",
    response_model=BillingPaymentResponse,
    status_code=200,
    summary="Get the latest payment status for the current user",
)
async def get_payment(
    payment_id: UUID,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Return the latest payment state for the current user."""
    return await _get_payment_response(payment_id, ctx=ctx, pool=pool)


@router.post(
    "/payments/{payment_id}/mock-complete",
    response_model=BillingPaymentResponse,
    status_code=200,
    summary="Complete a mock payment in development",
)
async def complete_mock_payment(
    payment_id: UUID,
    request: CompleteMockPaymentRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Move a mock payment into a terminal state for development checkout testing."""
    _ensure_mock_checkout_allowed()
    target_status = request.status.strip().lower()
    if target_status not in MOCK_TERMINAL_STATUSES:
        raise ValidationError(
            "Unsupported mock payment status.",
            details={"allowed_statuses": sorted(MOCK_TERMINAL_STATUSES)},
        )

    row = await _fetch_payment_row(pool, payment_id=payment_id, user_id=UUID(ctx.user_id))
    if row is None:
        raise NotFoundError("Payment not found.", details={"payment_id": str(payment_id)})
    if str(row["provider"]) != "mock":
        raise ValidationError("Only mock payments can be completed from the development checkout page.")

    updated = await pool.fetchrow(
        """
        UPDATE billing_payments
        SET status = $2::varchar,
            approved_at = CASE
                WHEN $2::varchar = 'paid'::varchar THEN COALESCE(approved_at, NOW())
                ELSE approved_at
            END,
            updated_at = NOW(),
            raw_response = COALESCE(raw_response, '{}'::jsonb) || $3::jsonb
        WHERE id = $1
        RETURNING *
        """,
        payment_id,
        target_status,
        json.dumps({"mock_status": target_status, "completed_at": datetime.utcnow().isoformat()}),
    )
    if updated is None:
        raise NotFoundError("Payment not found.", details={"payment_id": str(payment_id)})

    hydrated = await _fetch_payment_row(pool, payment_id=payment_id, user_id=UUID(ctx.user_id))
    if hydrated is None:
        raise NotFoundError("Payment not found.", details={"payment_id": str(payment_id)})
    return _payment_response_from_row(hydrated)


@router.post(
    "/cutluy/payments",
    response_model=BillingPaymentResponse,
    status_code=201,
    summary="Create a CutLuy checkout payment for a selected plan",
)
async def create_cutluy_payment_compat(
    request: CreatePaymentRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Compatibility endpoint that always creates a CutLuy payment."""
    provider_config = await _get_provider_config(pool)
    cutluy_provider = next((item for item in provider_config.providers if item.id == "cutluy"), None)
    if cutluy_provider is None or not cutluy_provider.enabled or not cutluy_provider.available:
        raise ValidationError("CutLuy checkout is not enabled for this environment.")
    return await _create_payment_response(request, provider="cutluy", ctx=ctx, pool=pool)


@router.get(
    "/cutluy/payments/{payment_id}",
    response_model=BillingPaymentResponse,
    status_code=200,
    summary="Get the latest CutLuy payment status for the current user",
)
async def get_cutluy_payment_compat(
    payment_id: UUID,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Compatibility endpoint for older clients using the previous CutLuy route."""
    return await _get_payment_response(payment_id, ctx=ctx, pool=pool)


@router.post(
    "/webhooks/cutluy",
    status_code=200,
    summary="CutLuy signed webhook (plan payment fulfillment)",
)
async def cutluy_webhook(
    request: Request,
    pool: Any = Depends(get_db_pool),
) -> JSONResponse:
    """Verify CutLuy signature and fulfill matching plan payments.

    Credit pack mint via ``POST /credits/purchase`` remains disabled until a
    verified CutLuy pack product path exists — this webhook only reconciles
    ``billing_payments`` plan checkouts.
    """
    raw_body = await request.body()
    cutluy = await resolve_cutluy_config(pool)
    if not cutluy.webhook_secret:
        raise ForbiddenError(
            "CutLuy webhook secret is not configured. "
            "Set PLATFORM_CUTLUY_WEBHOOK_SECRET or billing.cutluy.webhook_secret.",
            details={"error_code": "CUTLUY_WEBHOOK_SECRET_MISSING"},
        )

    signature = request.headers.get("X-CutLuy-Signature") or request.headers.get(
        "x-cutluy-signature"
    )
    if not verify_cutluy_webhook_signature(
        raw_body=raw_body,
        signature_header=signature,
        secret=cutluy.webhook_secret,
    ):
        raise ForbiddenError(
            "Invalid CutLuy webhook signature.",
            details={"error_code": "CUTLUY_WEBHOOK_SIGNATURE_INVALID"},
        )

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid CutLuy webhook JSON body.") from exc

    event_type = cutluy_event_type(request.headers) or str(event.get("type") or "")
    payment_data = ((event.get("data") or {}) if isinstance(event, dict) else {}).get("payment")
    if not isinstance(payment_data, dict):
        return JSONResponse({"received": True, "fulfilled": False, "reason": "no_payment"})

    external_payment_id = str(payment_data.get("id") or "").strip()
    status = str(payment_data.get("status") or "").strip().lower()
    if not external_payment_id:
        return JSONResponse({"received": True, "fulfilled": False, "reason": "missing_payment_id"})

    row = await pool.fetchrow(
        """
        SELECT *
        FROM billing_payments
        WHERE external_payment_id = $1
          AND provider = 'cutluy'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        external_payment_id,
    )
    if row is None:
        logger.info(
            "CutLuy webhook for unknown payment %s (event=%s)",
            external_payment_id,
            event_type,
        )
        return JSONResponse(
            {"received": True, "fulfilled": False, "reason": "payment_not_found"}
        )

    # Cast $2 explicitly: asyncpg otherwise fails with
    # "inconsistent types deduced for parameter $2: text versus character varying"
    # when the same param is assigned to a varchar column and compared to a literal.
    updated = await pool.fetchrow(
        """
        UPDATE billing_payments
        SET status = $2::varchar,
            approved_at = CASE
                WHEN $2::varchar = 'paid'::varchar THEN COALESCE(approved_at, NOW())
                ELSE approved_at
            END,
            raw_response = COALESCE(raw_response, '{}'::jsonb) || $3::jsonb,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        row["id"],
        status or row["status"],
        json.dumps({"webhook_event": event, "webhook_event_type": event_type}),
    )
    if updated is None:
        raise NotFoundError("Payment record not found.")

    fulfilled = False
    if str(updated["status"]) == "paid":
        hydrated = await _fulfill_paid_payment(pool, updated)
        fulfilled = hydrated["fulfilled_at"] is not None

    return JSONResponse(
        {
            "received": True,
            "fulfilled": bool(fulfilled),
            "payment_id": str(updated["id"]),
            "status": str(updated["status"]),
            "event_type": event_type,
        }
    )
