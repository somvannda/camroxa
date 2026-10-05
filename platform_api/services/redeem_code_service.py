"""Redeem code validation and redemption helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.services.credit_ledger import CreditLedger, GrantType
from platform_api.services.credit_units import (
    MAX_CREDIT_UNITS,
    credits_to_units,
    units_to_credits,
)

REWARD_TYPE_DISCOUNT_AMOUNT = "discount_amount"
REWARD_TYPE_DISCOUNT_PERCENTAGE = "discount_percentage"
REWARD_TYPE_CREDIT_GRANT = "credit_grant"

REDEEM_CODE_REWARD_TYPES = {
    REWARD_TYPE_DISCOUNT_AMOUNT,
    REWARD_TYPE_DISCOUNT_PERCENTAGE,
    REWARD_TYPE_CREDIT_GRANT,
}
DISCOUNT_REWARD_TYPES = {
    REWARD_TYPE_DISCOUNT_AMOUNT,
    REWARD_TYPE_DISCOUNT_PERCENTAGE,
}


def normalize_redeem_code(raw: str) -> str:
    """Normalize a user-entered redeem code."""
    return raw.strip().upper()


def validate_redeem_code_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate reward-shape rules for create/update operations."""
    reward_type = str(payload.get("reward_type") or "").strip()
    if reward_type not in REDEEM_CODE_REWARD_TYPES:
        raise ValidationError(
            "Unsupported redeem reward type.",
            details={"allowed_types": sorted(REDEEM_CODE_REWARD_TYPES)},
        )

    code = normalize_redeem_code(str(payload.get("code") or ""))
    if not code:
        raise ValidationError("Redeem code is required.")

    starts_at = payload.get("starts_at")
    expires_at = payload.get("expires_at")
    if starts_at and expires_at and starts_at >= expires_at:
        raise ValidationError("Redeem code start time must be before the expiry time.")

    max_redemptions = payload.get("max_redemptions")
    if max_redemptions is not None and int(max_redemptions) < 1:
        raise ValidationError("Maximum redemptions must be at least 1 when provided.")

    per_user_limit = int(payload.get("per_user_limit") or 1)
    if per_user_limit < 1:
        raise ValidationError("Per-user redemption limit must be at least 1.")

    discount_amount_cents = payload.get("discount_amount_cents")
    discount_percent = payload.get("discount_percent")
    credit_amount = payload.get("credit_amount")
    applicable_plan_id = payload.get("applicable_plan_id")

    if reward_type == REWARD_TYPE_DISCOUNT_AMOUNT:
        if discount_amount_cents is None or int(discount_amount_cents) < 1:
            raise ValidationError("Discount amount codes require a positive amount in cents.")
        if discount_percent is not None or credit_amount is not None:
            raise ValidationError("Discount amount codes cannot also define percent or credit grants.")
    elif reward_type == REWARD_TYPE_DISCOUNT_PERCENTAGE:
        if discount_percent is None or int(discount_percent) < 1 or int(discount_percent) > 100:
            raise ValidationError("Discount percentage codes require a percentage between 1 and 100.")
        if discount_amount_cents is not None or credit_amount is not None:
            raise ValidationError("Discount percentage codes cannot also define amount or credit grants.")
    else:
        if credit_amount is None or int(credit_amount) < 1:
            raise ValidationError("Credit grant codes require a positive credit amount.")
        if discount_amount_cents is not None or discount_percent is not None:
            raise ValidationError("Credit grant codes cannot also define discounts.")
        if applicable_plan_id is not None:
            raise ValidationError("Credit grant codes cannot be restricted to a plan.")

    return {
        "code": code,
        "reward_type": reward_type,
        "description": (str(payload.get("description") or "").strip() or None),
        "discount_amount_cents": int(discount_amount_cents) if discount_amount_cents is not None else None,
        "discount_percent": int(discount_percent) if discount_percent is not None else None,
        "credit_amount": int(credit_amount) if credit_amount is not None else None,
        "applicable_plan_id": UUID(str(applicable_plan_id)) if applicable_plan_id else None,
        "max_redemptions": int(max_redemptions) if max_redemptions is not None else None,
        "per_user_limit": per_user_limit,
        "starts_at": starts_at,
        "expires_at": expires_at,
        "is_active": bool(payload.get("is_active", True)),
    }


async def get_redeem_code_row_by_id(pool: Any, redeem_code_id: UUID) -> Any | None:
    """Fetch a redeem code row by identifier."""
    return await pool.fetchrow(
        """
        SELECT rc.*,
               p.name AS applicable_plan_name
        FROM redeem_codes rc
        LEFT JOIN plans p ON p.id = rc.applicable_plan_id
        WHERE rc.id = $1
        """,
        redeem_code_id,
    )


async def get_redeem_code_row_by_code(pool: Any, code: str) -> Any | None:
    """Fetch a redeem code row by normalized code."""
    return await pool.fetchrow(
        """
        SELECT rc.*,
               p.name AS applicable_plan_name
        FROM redeem_codes rc
        LEFT JOIN plans p ON p.id = rc.applicable_plan_id
        WHERE rc.code = $1
        """,
        normalize_redeem_code(code),
    )


async def list_redeem_codes(pool: Any) -> list[Any]:
    """List redeem codes for admin surfaces."""
    return await pool.fetch(
        """
        SELECT rc.*,
               p.name AS applicable_plan_name
        FROM redeem_codes rc
        LEFT JOIN plans p ON p.id = rc.applicable_plan_id
        ORDER BY rc.created_at DESC, rc.code ASC
        """
    )


async def ensure_plan_exists(pool: Any, plan_id: UUID) -> None:
    """Validate that an applicable plan exists."""
    exists = await pool.fetchval("SELECT 1 FROM plans WHERE id = $1", plan_id)
    if not exists:
        raise NotFoundError("Referenced plan was not found.", details={"plan_id": str(plan_id)})


async def create_redeem_code(pool: Any, payload: dict[str, Any], *, created_by: UUID | None) -> Any:
    """Create a new redeem code row."""
    validated = validate_redeem_code_payload(payload)
    existing = await get_redeem_code_row_by_code(pool, validated["code"])
    if existing is not None:
        raise DuplicateError("Redeem code already exists.", details={"code": validated["code"]})
    if validated["applicable_plan_id"] is not None:
        await ensure_plan_exists(pool, validated["applicable_plan_id"])

    created = await pool.fetchrow(
        """
        INSERT INTO redeem_codes (
            id,
            code,
            description,
            reward_type,
            discount_amount_cents,
            discount_percent,
            credit_amount,
            applicable_plan_id,
            max_redemptions,
            current_redemptions,
            per_user_limit,
            starts_at,
            expires_at,
            is_active,
            created_by,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, 0, $10, $11, $12, $13, $14, NOW(), NOW()
        )
        RETURNING id
        """,
        uuid4(),
        validated["code"],
        validated["description"],
        validated["reward_type"],
        validated["discount_amount_cents"],
        validated["discount_percent"],
        validated["credit_amount"],
        validated["applicable_plan_id"],
        validated["max_redemptions"],
        validated["per_user_limit"],
        validated["starts_at"],
        validated["expires_at"],
        validated["is_active"],
        created_by,
    )
    if created is None:
        raise ValidationError("Redeem code could not be created.")
    return await get_redeem_code_row_by_id(pool, UUID(str(created["id"])))


async def update_redeem_code(pool: Any, redeem_code_id: UUID, payload: dict[str, Any]) -> Any:
    """Update an existing redeem code row."""
    current = await get_redeem_code_row_by_id(pool, redeem_code_id)
    if current is None:
        raise NotFoundError("Redeem code not found.", details={"redeem_code_id": str(redeem_code_id)})

    validated = validate_redeem_code_payload(payload)
    duplicate = await get_redeem_code_row_by_code(pool, validated["code"])
    if duplicate is not None and UUID(str(duplicate["id"])) != redeem_code_id:
        raise DuplicateError("Redeem code already exists.", details={"code": validated["code"]})
    if validated["applicable_plan_id"] is not None:
        await ensure_plan_exists(pool, validated["applicable_plan_id"])

    updated = await pool.fetchrow(
        """
        UPDATE redeem_codes
        SET code = $2,
            description = $3,
            reward_type = $4,
            discount_amount_cents = $5,
            discount_percent = $6,
            credit_amount = $7,
            applicable_plan_id = $8,
            max_redemptions = $9,
            per_user_limit = $10,
            starts_at = $11,
            expires_at = $12,
            is_active = $13,
            updated_at = NOW()
        WHERE id = $1
        RETURNING id
        """,
        redeem_code_id,
        validated["code"],
        validated["description"],
        validated["reward_type"],
        validated["discount_amount_cents"],
        validated["discount_percent"],
        validated["credit_amount"],
        validated["applicable_plan_id"],
        validated["max_redemptions"],
        validated["per_user_limit"],
        validated["starts_at"],
        validated["expires_at"],
        validated["is_active"],
    )
    if updated is None:
        raise NotFoundError("Redeem code not found.", details={"redeem_code_id": str(redeem_code_id)})
    return await get_redeem_code_row_by_id(pool, redeem_code_id)


async def delete_redeem_code(pool: Any, redeem_code_id: UUID) -> None:
    """Delete a redeem code."""
    result = await pool.execute("DELETE FROM redeem_codes WHERE id = $1", redeem_code_id)
    if not str(result).endswith("1"):
        raise NotFoundError("Redeem code not found.", details={"redeem_code_id": str(redeem_code_id)})


async def _count_user_redemptions(pool: Any, redeem_code_id: UUID, user_id: UUID) -> int:
    """Count how many times a user has redeemed the code successfully."""
    return int(
        await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM redeem_code_redemptions
            WHERE redeem_code_id = $1
              AND user_id = $2
            """,
            redeem_code_id,
            user_id,
        )
        or 0
    )


def _compute_percentage_discount(base_amount_cents: int, percent: int) -> int:
    """Compute a rounded percentage discount result in cents."""
    ratio = Decimal(100 - percent) / Decimal(100)
    return int(
        (Decimal(base_amount_cents) * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _validate_code_window(row: Any, *, now: datetime) -> None:
    """Validate active, expiry, and redemption-cap rules."""
    if not bool(row["is_active"]):
        raise ValidationError("This redeem code is inactive.")
    starts_at = row["starts_at"]
    expires_at = row["expires_at"]
    if starts_at is not None and starts_at > now:
        raise ValidationError("This redeem code is not active yet.")
    if expires_at is not None and expires_at < now:
        raise ValidationError("This redeem code has expired.")
    max_redemptions = row["max_redemptions"]
    current_redemptions = int(row["current_redemptions"] or 0)
    if max_redemptions is not None and current_redemptions >= int(max_redemptions):
        raise ValidationError("This redeem code has reached its redemption limit.")


async def preview_redeem_code(
    pool: Any,
    *,
    code: str,
    plan_id: UUID | None = None,
    plan_price_cents: int | None = None,
    public_offer_price_cents: int | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    """Preview how a redeem code would behave for the current user/plan."""
    row = await get_redeem_code_row_by_code(pool, code)
    if row is None:
        raise ValidationError("Redeem code is invalid or unavailable.")

    now = datetime.now(timezone.utc)
    _validate_code_window(row, now=now)

    code_id = UUID(str(row["id"]))
    per_user_limit = int(row["per_user_limit"] or 1)
    user_redemptions = 0
    if user_id is not None:
        user_redemptions = await _count_user_redemptions(pool, code_id, user_id)
        if user_redemptions >= per_user_limit:
            raise ValidationError("Redeem code is invalid or unavailable.")

    reward_type = str(row["reward_type"])
    response: dict[str, Any] = {
        "id": str(row["id"]),
        "code": str(row["code"]),
        "description": row["description"],
        "reward_type": reward_type,
        "discount_amount_cents": row["discount_amount_cents"],
        "discount_percent": row["discount_percent"],
        "credit_amount": row["credit_amount"],
        "applicable_plan_id": str(row["applicable_plan_id"]) if row["applicable_plan_id"] else None,
        "applicable_plan_name": row["applicable_plan_name"],
        "max_redemptions": row["max_redemptions"],
        "current_redemptions": int(row["current_redemptions"] or 0),
        "remaining_redemptions": (
            None
            if row["max_redemptions"] is None
            else max(0, int(row["max_redemptions"]) - int(row["current_redemptions"] or 0))
        ),
        "per_user_limit": per_user_limit,
        "user_redemptions": user_redemptions,
        "is_active": bool(row["is_active"]),
        "starts_at": row["starts_at"],
        "expires_at": row["expires_at"],
        "applied_discount": False,
        "final_amount_cents": None,
        "base_amount_cents": plan_price_cents,
        "best_public_amount_cents": public_offer_price_cents if public_offer_price_cents is not None else plan_price_cents,
        "savings_cents": None,
        "message": None,
    }

    if reward_type == REWARD_TYPE_CREDIT_GRANT:
        response["message"] = (
            f"This code grants {int(row['credit_amount'])} credits after redemption in the signed-in user panel."
        )
        return response

    if plan_id is None or plan_price_cents is None:
        response["message"] = "This discount code is valid. Select a plan to see the final checkout amount."
        return response

    applicable_plan_id = row["applicable_plan_id"]
    if applicable_plan_id is not None and UUID(str(applicable_plan_id)) != plan_id:
        raise ValidationError("Redeem code is invalid or unavailable.")

    best_public_amount = (
        int(public_offer_price_cents)
        if public_offer_price_cents is not None
        else int(plan_price_cents)
    )
    if reward_type == REWARD_TYPE_DISCOUNT_AMOUNT:
        discounted_amount = max(0, int(plan_price_cents) - int(row["discount_amount_cents"]))
    else:
        discounted_amount = max(
            0,
            _compute_percentage_discount(int(plan_price_cents), int(row["discount_percent"])),
        )

    final_amount = min(best_public_amount, discounted_amount)
    applied_discount = discounted_amount < best_public_amount
    response["applied_discount"] = applied_discount
    response["final_amount_cents"] = final_amount
    response["savings_cents"] = max(0, int(plan_price_cents) - final_amount)
    response["message"] = (
        "Redeem code applied to checkout."
        if applied_discount
        else "A public plan offer already provides the best available price, so this code will not be consumed."
    )
    return response


async def redeem_credit_code(pool: Any, *, code: str, user_id: UUID) -> dict[str, Any]:
    """Redeem a credit grant code and apply credits atomically."""
    normalized_code = normalize_redeem_code(code)
    display_amount = 0
    amount_units = 0
    new_balance = 0
    redeem_code_id: UUID | None = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT rc.*,
                       p.name AS applicable_plan_name
                FROM redeem_codes rc
                LEFT JOIN plans p ON p.id = rc.applicable_plan_id
                WHERE rc.code = $1
                FOR UPDATE
                """,
                normalized_code,
            )
            if row is None:
                raise NotFoundError("Redeem code not found.", details={"code": normalized_code})

            now = datetime.now(timezone.utc)
            _validate_code_window(row, now=now)
            if str(row["reward_type"]) != REWARD_TYPE_CREDIT_GRANT:
                raise ValidationError("This redeem code must be used during checkout because it changes plan pricing.")

            redeem_code_id = UUID(str(row["id"]))
            user_redemptions = int(
                await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM redeem_code_redemptions
                    WHERE redeem_code_id = $1
                      AND user_id = $2
                    """,
                    redeem_code_id,
                    user_id,
                )
                or 0
            )
            per_user_limit = int(row["per_user_limit"] or 1)
            if user_redemptions >= per_user_limit:
                raise ValidationError("You have already used this redeem code the maximum number of times.")

            display_amount = int(row["credit_amount"] or 0)
            if display_amount < 1:
                raise ValidationError("Credit grant codes require a positive credit amount.")
            amount_units = credits_to_units(display_amount)
            current_balance = await conn.fetchval(
                "SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if current_balance is None:
                current_balance = 0
                await conn.execute(
                    """
                    INSERT INTO credit_wallets (user_id, balance, updated_at)
                    VALUES ($1, 0, NOW())
                    """,
                    user_id,
                )
            new_balance = int(current_balance) + amount_units
            if new_balance > MAX_CREDIT_UNITS:
                raise ValidationError(
                    "Redeeming this code would exceed the maximum wallet balance.",
                    details={
                        "current_balance": units_to_credits(int(current_balance)),
                        "credit_amount": display_amount,
                        "max_balance": units_to_credits(MAX_CREDIT_UNITS),
                    },
                )

            metadata = {
                "source": "redeem_code",
                "redeem_code_id": str(redeem_code_id),
                "redeem_code": normalized_code,
                "reward_type": str(row["reward_type"]),
            }
            # Route the grant through the single credit primitive. idempotent=False:
            # the per-user redemption guard above already prevents double-redeem,
            # and a code may legitimately be redeemed more than once (per_user_limit
            # > 1), where ref_id (the code id) repeats.
            await CreditLedger(CreditRepository(conn)).grant(
                user_id,
                amount_units,
                grant_type=GrantType.REDEEM,
                ref_id=str(redeem_code_id),
                metadata=metadata,
                idempotent=False,
            )
            redemption_id = uuid4()
            await conn.execute(
                """
                INSERT INTO redeem_code_redemptions (
                    id,
                    redeem_code_id,
                    user_id,
                    billing_payment_id,
                    plan_id,
                    status,
                    amount_cents,
                    credit_amount,
                    metadata,
                    created_at
                )
                VALUES ($1, $2, $3, NULL, NULL, 'redeemed', NULL, $4, $5::jsonb, NOW())
                """,
                redemption_id,
                redeem_code_id,
                user_id,
                display_amount,
                json.dumps(metadata),
            )
            await conn.execute(
                """
                UPDATE redeem_codes
                SET current_redemptions = current_redemptions + 1,
                    is_active = CASE
                        WHEN max_redemptions IS NOT NULL AND current_redemptions + 1 >= max_redemptions THEN false
                        ELSE is_active
                    END,
                    updated_at = NOW()
                WHERE id = $1
                """,
                redeem_code_id,
            )

    refreshed = await preview_redeem_code(pool, code=normalized_code, user_id=user_id)
    refreshed["credit_amount"] = display_amount
    refreshed["new_balance"] = units_to_credits(new_balance)
    refreshed["message"] = f"{display_amount} credits have been added to your account."

    from platform_api.services.credit_audit_service import log_wallet_credit_event

    await log_wallet_credit_event(
        actor_id=user_id,
        user_id=user_id,
        action_type="credit.redeem",
        amount_units=amount_units,
        reason="redeem_code_credit",
        metadata={
            "redeem_code": normalized_code,
            "redeem_code_id": str(redeem_code_id) if redeem_code_id else None,
            "new_balance_units": new_balance,
        },
    )
    return refreshed


async def record_discount_redemption(
    pool: Any,
    *,
    redeem_code_id: UUID,
    code: str,
    user_id: UUID,
    billing_payment_id: UUID,
    plan_id: UUID,
    final_amount_cents: int,
) -> None:
    """Record a successful discount-code redemption after payment fulfillment."""
    metadata = {
        "source": "redeem_code",
        "redeem_code_id": str(redeem_code_id),
        "redeem_code": normalize_redeem_code(code),
        "reward_type": "discount",
    }
    inserted = await pool.fetchval(
        """
        INSERT INTO redeem_code_redemptions (
            id,
            redeem_code_id,
            user_id,
            billing_payment_id,
            plan_id,
            status,
            amount_cents,
            credit_amount,
            metadata,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5, 'redeemed', $6, NULL, $7::jsonb, NOW())
        ON CONFLICT (billing_payment_id) DO NOTHING
        RETURNING id
        """,
        uuid4(),
        redeem_code_id,
        user_id,
        billing_payment_id,
        plan_id,
        final_amount_cents,
        json.dumps(metadata),
    )
    if inserted is None:
        return
    await pool.execute(
        """
        UPDATE redeem_codes
        SET current_redemptions = current_redemptions + 1,
            is_active = CASE
                WHEN max_redemptions IS NOT NULL AND current_redemptions + 1 >= max_redemptions THEN false
                ELSE is_active
            END,
            updated_at = NOW()
        WHERE id = $1
        """,
        redeem_code_id,
    )


async def list_redeem_code_redemptions(
    pool: Any,
    *,
    page: int = 1,
    page_size: int = 50,
    code: str | None = None,
    reward_type: str | None = None,
    status: str | None = None,
) -> tuple[list[Any], int]:
    """List redeem-code redemption ledger entries for admin reporting."""
    filters: list[str] = []
    params: list[Any] = []

    if code:
        params.append(f"%{normalize_redeem_code(code)}%")
        filters.append(f"UPPER(rc.code) LIKE ${len(params)}")
    if reward_type:
        params.append(str(reward_type).strip())
        filters.append(f"rc.reward_type = ${len(params)}")
    if status:
        params.append(str(status).strip())
        filters.append(f"r.status = ${len(params)}")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    count_query = f"""
        SELECT COUNT(*)
        FROM redeem_code_redemptions r
        INNER JOIN redeem_codes rc ON rc.id = r.redeem_code_id
        {where_clause}
    """
    total = int(await pool.fetchval(count_query, *params) or 0)

    params.extend([page_size, (page - 1) * page_size])
    rows = await pool.fetch(
        f"""
        SELECT r.id,
               r.redeem_code_id,
               rc.code,
               rc.description,
               rc.reward_type,
               r.user_id,
               u.email AS user_email,
               u.display_name AS user_display_name,
               r.billing_payment_id,
               r.plan_id,
               p.name AS plan_name,
               r.status,
               r.amount_cents,
               r.credit_amount,
               r.metadata,
               r.created_at
        FROM redeem_code_redemptions r
        INNER JOIN redeem_codes rc ON rc.id = r.redeem_code_id
        INNER JOIN users u ON u.id = r.user_id
        LEFT JOIN plans p ON p.id = r.plan_id
        {where_clause}
        ORDER BY r.created_at DESC
        LIMIT ${len(params) - 1}
        OFFSET ${len(params)}
        """,
        *params,
    )
    return rows, total


async def list_user_redeem_code_redemptions(
    pool: Any,
    *,
    user_id: UUID,
    limit: int = 10,
) -> list[Any]:
    """List a user's most recent redeem-code history entries."""
    return await pool.fetch(
        """
        SELECT r.id,
               r.redeem_code_id,
               rc.code,
               rc.description,
               rc.reward_type,
               r.user_id,
               u.email AS user_email,
               u.display_name AS user_display_name,
               r.billing_payment_id,
               r.plan_id,
               p.name AS plan_name,
               r.status,
               r.amount_cents,
               r.credit_amount,
               r.metadata,
               r.created_at
        FROM redeem_code_redemptions r
        INNER JOIN redeem_codes rc ON rc.id = r.redeem_code_id
        INNER JOIN users u ON u.id = r.user_id
        LEFT JOIN plans p ON p.id = r.plan_id
        WHERE r.user_id = $1
        ORDER BY r.created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
