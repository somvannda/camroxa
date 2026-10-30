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
from platform_api.services.billing_config_service import (
    resolve_chmaba_config,
    resolve_cutluy_config,
)
from platform_api.services.billing_provider_service import (
    BILLING_PORTAL_BASE_URL_SETTING_KEY,
    get_provider_config as load_provider_config,
    resolve_active_provider,
)
from platform_api.services.chmaba_webhook import (
    chmaba_event_type,
    chmaba_webhook_payload,
    find_chmaba_reference_id,
    verify_chmaba_webhook_signature,
)
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

MOCK_TERMINAL_STATUSES = {"paid", "failed", "expired"}
# Self-serve renewal opens this many days before the license expiry (or whenever expired).
RENEWAL_WINDOW_DAYS = 7


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
    chmaba_secret_configured: bool = False
    chmaba_secret_source: str | None = None
    chmaba_store_configured: bool = False
    chmaba_api_base_url: str = "https://pay.chmaba.com"


def _to_cents(amount: str | int | float | Decimal) -> int:
    """Convert decimal USD amount into integer cents."""
    dec = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(dec * 100)


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


def _ensure_mock_checkout_allowed() -> None:
    if not get_settings().debug:
        raise ValidationError("Mock checkout is only available in debug environments.")


async def _get_provider_config(pool: Any) -> BillingProviderConfigResponse:
    """Build provider registry state with enabled/active/available flags."""
    config = await load_provider_config(pool)
    cutluy = await resolve_cutluy_config(pool)
    chmaba = await resolve_chmaba_config(pool)

    return BillingProviderConfigResponse(
        active_provider=config.active_provider,
        paid_checkout_available=config.paid_checkout_available,
        providers=[
            BillingProviderResponse(
                id=row.id,
                label=row.label,
                kind=row.kind,
                description=row.description,
                enabled=row.enabled,
                active=row.active,
                available=row.available,
            )
            for row in config.providers
        ],
        cutluy_secret_configured=bool(cutluy.secret_key),
        cutluy_secret_source=cutluy.secret_source if cutluy.secret_key else None,
        cutluy_api_base_url=cutluy.api_base_url,
        chmaba_secret_configured=bool(chmaba.api_key),
        chmaba_secret_source=chmaba.api_key_source if chmaba.api_key else None,
        chmaba_store_configured=bool(chmaba.store_id),
        chmaba_api_base_url=chmaba.api_base_url,
    )


async def _get_active_provider(pool: Any) -> str | None:
    """Return the currently active enabled provider, or None when paid checkout is off."""
    return await resolve_active_provider(pool)


def _provider_is_usable(config: BillingProviderConfigResponse, provider_id: str) -> bool:
    """True when a specific provider is enabled and has credentials."""
    row = next((item for item in config.providers if item.id == provider_id), None)
    return bool(row is not None and row.enabled and row.available)



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
        plan_id=str(row["plan_id"]) if row["plan_id"] else "",
        plan_name=str(row.get("plan_name") or metadata.get("pack_name") or ""),
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




async def _fetch_payment_row(pool: Any, *, payment_id: UUID, user_id: UUID) -> Any | None:
    """Return a billing payment row for the current user."""
    return await pool.fetchrow(
        """
        SELECT bp.*
        FROM billing_payments bp
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
        SELECT bp.*
        FROM billing_payments bp
        WHERE bp.external_payment_id = $1
          AND bp.user_id = $2
        ORDER BY bp.created_at DESC
        LIMIT 1
        """,
        external_payment_id,
        user_id,
    )




async def _hydrate_created_payment(pool: Any, payment_id: UUID) -> BillingPaymentResponse:
    """Load a newly-created payment for response serialization."""
    row = await pool.fetchrow(
        """
        SELECT bp.*
        FROM billing_payments bp
        WHERE bp.id = $1
        """,
        payment_id,
    )
    if row is None:
        raise NotFoundError("Payment record not found.")
    return _payment_response_from_row(row)


async def _fetch_provider_status_payload(pool: Any, provider: str, external_id: str) -> dict[str, Any]:
    """Ask the external provider for the authoritative status payload."""
    if provider == "chmaba":
        from platform_api.services.shared.chmaba_service import (
            ChmabaAPIError,
            ChmabaConfigurationError,
            ChmabaService,
        )

        chmaba = await resolve_chmaba_config(pool)
        service = ChmabaService(
            api_base_url=chmaba.api_base_url,
            api_key=chmaba.api_key,
            store_id=chmaba.store_id,
            webhook_secret=chmaba.webhook_secret,
        )
        try:
            return await service.get_payment_status(external_id)
        except ChmabaConfigurationError as exc:
            raise ExternalServiceError(
                str(exc),
                details={"provider": "chmaba"},
            ) from exc
        except ChmabaAPIError as exc:
            raise ExternalServiceError(
                str(exc),
                is_retryable=exc.retryable,
                details={"provider": "chmaba", "status_code": exc.status_code},
            ) from exc

    cutluy = await resolve_cutluy_config(pool)
    api_key, _payment_link_id = _ensure_cutluy_ready(cutluy)
    url = f"{cutluy.api_base_url}/v1/payments/{external_id}"

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
    return payload if isinstance(payload, dict) else {}


async def _refresh_external_status(pool: Any, row: Any) -> Any:
    """Pull the latest payment status from the external provider when needed."""
    status = str(row["status"])
    provider = str(row["provider"])
    if status in {"paid", "expired", "failed"} or provider not in {"cutluy", "chmaba"}:
        return row

    payload = await _fetch_provider_status_payload(
        pool,
        provider,
        str(row["external_payment_id"]),
    )

    if provider == "chmaba":
        from platform_api.services.shared.chmaba_service import (
            normalize_chmaba_payment_status,
        )

        next_status = normalize_chmaba_payment_status(payload.get("status"))
        approved_at = datetime.now(timezone.utc) if next_status == "paid" else None
    else:
        next_status = str(payload.get("status") or row["status"])
        approved_at = _parse_cutluy_timestamp(payload.get("approved_at"))

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
        next_status,
        approved_at,
        json.dumps(payload),
    )
    if updated is None:
        raise NotFoundError("Payment record not found.")
    return updated











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

            metadata = locked["metadata"] or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            # Plans, subscriptions, add-ons and billing credit packs are retired.
            # The only pack purchase path is POST /api/v3/topups/purchase.
            raise ValidationError(
                "This billing path is retired. Use POST /api/v3/topups/purchase.",
                details={
                    "error_code": "BILLING_PATH_RETIRED",
                    "payment_id": str(locked["id"]),
                    "product_type": str(metadata.get("product_type") or "plan"),
                },
            )


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


async def _create_chmaba_payment(
    pool: Any,
    *,
    ctx: AuthContext,
    plan_id: UUID,
    plan_name: str,
    amount_cents: int,
    offer_id: UUID | None,
    extra_metadata: dict[str, Any] | None = None,
) -> BillingPaymentResponse:
    """Create a ChmabaPay KHQR payment using the admin-managed plan price."""
    from platform_api.services.shared.chmaba_service import (
        ChmabaAPIError,
        ChmabaConfigurationError,
        ChmabaService,
    )

    chmaba = await resolve_chmaba_config(pool)
    if not chmaba.configured:
        raise ExternalServiceError(
            "ChmabaPay billing is not configured yet. Add the API key and store id "
            "in Admin Settings → Payment.",
            details={"provider": "chmaba"},
        )

    reference_id = f"camxora:{ctx.user_id}:{plan_id}:{uuid4().hex[:12]}"
    metadata: dict[str, Any] = {
        "user_id": ctx.user_id,
        "plan_id": str(plan_id),
        "plan_name": plan_name,
        "offer_id": str(offer_id) if offer_id is not None else None,
        "provider": "chmaba",
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    service = ChmabaService(
        api_base_url=chmaba.api_base_url,
        api_key=chmaba.api_key,
        store_id=chmaba.store_id,
        webhook_secret=chmaba.webhook_secret,
    )
    try:
        payment = await service.create_payment(
            amount_cents=amount_cents,
            reference_id=reference_id,
            metadata=metadata,
        )
    except ChmabaConfigurationError as exc:
        raise ExternalServiceError(str(exc), details={"provider": "chmaba"}) from exc
    except ChmabaAPIError as exc:
        raise ExternalServiceError(
            str(exc),
            is_retryable=exc.retryable,
            details={"provider": "chmaba", "status_code": exc.status_code},
        ) from exc

    metadata["qr_string"] = payment.get("qr_string") or ""

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
            'chmaba',
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            NULL,
            $11::jsonb,
            $12::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """,
        uuid4(),
        payment["payment_id"],
        UUID(ctx.user_id),
        plan_id,
        offer_id,
        reference_id,
        "pending",
        amount_cents,
        "USD",
        payment["checkout_url"],
        json.dumps(metadata),
        json.dumps(
            {
                "provider": "chmaba",
                "id": payment["payment_id"],
                "status": "pending",
                "checkout_url": payment["checkout_url"],
                "qr_string": payment.get("qr_string") or "",
                "expires_at": payment.get("expires_at") or None,
                "amount": f"{amount_cents / 100:.2f}",
            }
        ),
    )
    if created is None:
        raise ExternalServiceError("Payment record could not be created.")

    return await _hydrate_created_payment(pool, UUID(str(created["id"])))


async def _create_provider_checkout(
    provider: str,
    pool: Any,
    *,
    ctx: AuthContext,
    plan_id: UUID | None,
    plan_name: str,
    amount_cents: int,
    offer_id: UUID | None,
    extra_metadata: dict[str, Any] | None = None,
) -> BillingPaymentResponse:
    """Route a checkout to the concrete provider implementation."""
    if provider == "cutluy":
        return await _create_cutluy_payment(
            pool,
            ctx=ctx,
            plan_id=plan_id,
            plan_name=plan_name,
            amount_cents=amount_cents,
            offer_id=offer_id,
            extra_metadata=extra_metadata,
        )
    if provider == "chmaba":
        return await _create_chmaba_payment(
            pool,
            ctx=ctx,
            plan_id=plan_id,
            plan_name=plan_name,
            amount_cents=amount_cents,
            offer_id=offer_id,
            extra_metadata=extra_metadata,
        )
    raise ValidationError("No active billing provider is configured.")




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
        SELECT bp.*
        FROM billing_payments bp
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




@router.get(
    "/chmaba/payments/{payment_id}",
    response_model=BillingPaymentResponse,
    status_code=200,
    summary="Get the latest ChmabaPay payment status for the current user",
)
async def get_chmaba_payment_compat(
    payment_id: UUID,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> BillingPaymentResponse:
    """Status route paired with the ChmabaPay compatibility checkout above."""
    return await _get_payment_response(payment_id, ctx=ctx, pool=pool)


async def _handle_chmaba_billing_webhook(
    request: Request,
    pool: Any,
) -> JSONResponse:
    """Verify a ChmabaPay delivery and settle exactly one ``billing_payments`` row.

    Authenticity rests entirely on the HMAC signature: the provider has no
    sandbox, so an unverifiable delivery must never move money or credits. The
    local row is found by the ``reference_id`` we generated at checkout, which
    the provider echoes back in the event payload.
    """
    raw_body = await request.body()
    chmaba = await resolve_chmaba_config(pool)
    if not chmaba.webhook_secret:
        raise ForbiddenError(
            "ChmabaPay webhook secret is not configured. "
            "Set PLATFORM_CHMABA_WEBHOOK_SECRET or billing.chmaba.webhook_secret.",
            details={"error_code": "CHMABA_WEBHOOK_SECRET_MISSING"},
        )

    signature = request.headers.get("X-ChmabaPay-Signature") or request.headers.get(
        "x-chmabapay-signature"
    )
    if not verify_chmaba_webhook_signature(
        raw_body=raw_body,
        signature_header=signature,
        secret=chmaba.webhook_secret,
    ):
        raise ForbiddenError(
            "Invalid ChmabaPay webhook signature.",
            details={"error_code": "CHMABA_WEBHOOK_SIGNATURE_INVALID"},
        )

    event = chmaba_webhook_payload(raw_body)
    if not event:
        raise ValidationError("Invalid ChmabaPay webhook JSON body.")

    event_type = chmaba_event_type(request.headers) or str(event.get("type") or "")
    reference_id = find_chmaba_reference_id(event)
    if not reference_id:
        return JSONResponse(
            {"received": True, "fulfilled": False, "reason": "missing_reference"}
        )

    row = await pool.fetchrow(
        """
        SELECT *
        FROM billing_payments
        WHERE reference_id = $1
          AND provider = 'chmaba'
        LIMIT 1
        """,
        reference_id,
    )
    if row is None:
        # One ChmabaPay store fronts both plan checkout (`billing_payments`) and
        # music-web credit top-ups (`topup_purchases`), so the same webhook URL
        # has to settle whichever ledger owns this reference.
        try:
            UUID(reference_id)
        except (TypeError, ValueError):
            pass
        else:
            from platform_api.dependencies import get_v2_topup_service

            topup_service = get_v2_topup_service()
            topup_result = await topup_service.settle_chmaba_topup(
                event_type=event_type,
                topup_id=reference_id,
            )
            return JSONResponse(
                {
                    "received": True,
                    "fulfilled": bool(topup_result.get("processed")),
                    "ledger": "topup",
                    "reason": topup_result.get("message"),
                }
            )

        logger.info(
            "ChmabaPay webhook for unknown reference %s (event=%s)",
            reference_id,
            event_type,
        )
        return JSONResponse(
            {"received": True, "fulfilled": False, "reason": "payment_not_found"}
        )

    if event_type == "payment.completed":
        target_status = "paid"
    elif event_type == "payment.reversed":
        target_status = "refunded"
    elif event_type == "payment.superseded":
        # A replacement code was minted; the old one can never settle.
        target_status = "failed"
    elif event_type == "payment.expired":
        # Deliberately not terminal: ChmabaPay keeps confirming a late payment
        # after the code expires and promotes the row to `paid` when it lands,
        # so the status poll must still be able to reconcile it.
        return JSONResponse(
            {"received": True, "fulfilled": False, "reason": "ignored:payment.expired"}
        )
    else:
        return JSONResponse(
            {
                "received": True,
                "fulfilled": False,
                "reason": f"ignored:{event_type or 'unknown'}",
            }
        )

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
        target_status,
        json.dumps({"webhook_event": event, "webhook_event_type": event_type}),
    )
    if updated is None:
        raise NotFoundError("Payment record not found.")

    fulfilled = False
    if str(updated["status"]) == "paid" and updated["fulfilled_at"] is None:
        hydrated = await _fulfill_paid_payment(pool, updated)
        fulfilled = hydrated["fulfilled_at"] is not None

    # A reversal only flips the ledger row. Clawing back delivered credits is a
    # manual/ops decision (see the desk refund path), so nothing is debited here.
    return JSONResponse(
        {
            "received": True,
            "fulfilled": bool(fulfilled),
            "payment_id": str(updated["id"]),
            "status": str(updated["status"]),
            "event_type": event_type,
        }
    )


@router.post(
    "/webhooks/chmaba",
    status_code=200,
    summary="ChmabaPay signed webhook (plan payment fulfillment)",
)
@router.post(
    "/webhooks/chmabapay",
    status_code=200,
    include_in_schema=False,
    summary="ChmabaPay signed webhook alias",
)
async def chmaba_webhook(
    request: Request,
    pool: Any = Depends(get_db_pool),
) -> JSONResponse:
    """Verify ChmabaPay's signature and fulfil the matching billing payment."""
    return await _handle_chmaba_billing_webhook(request, pool)
