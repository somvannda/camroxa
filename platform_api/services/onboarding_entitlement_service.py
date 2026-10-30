"""Payment-gated onboarding AI with per-operation caps (no wallet credits)."""

from __future__ import annotations

import json
import logging
from uuid import uuid4
from typing import Any, Awaitable, Callable, TypeVar
from uuid import UUID

from platform_api.exceptions import ForbiddenError, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Max AI calls per operation while completing initial channel onboarding (2 profiles).
ONBOARDING_AI_LIMITS: dict[str, int] = {
    "channel_name": 3,
    "channel_logo": 6,
    "channel_cover": 12,
    "channel_description": 10,
    "channel_keywords": 8,
    "channel_tags": 8,
}

ONBOARDING_PROFILE_TARGET = 2

_ONBOARDING_PURPOSE_LABELS: dict[str, str] = {
    "channel_name": "Onboarding AI: Channel names",
    "channel_logo": "Onboarding AI: Channel logo",
    "channel_cover": "Onboarding AI: Channel cover",
    "channel_description": "Onboarding AI: Channel description",
    "channel_keywords": "Onboarding AI: Channel keywords",
    "channel_tags": "Onboarding AI: Channel tags",
}


async def user_has_paid_for_onboarding(pool: Any, user_id: UUID) -> bool:
    """True when the user completed a paid checkout (fulfilled payment or paid plan license)."""
    fulfilled = await pool.fetchrow(
        """
        SELECT 1
        FROM billing_payments
        WHERE user_id = $1
          AND status = 'paid'
          AND fulfilled_at IS NOT NULL
        LIMIT 1
        """,
        user_id,
    )
    if fulfilled is not None:
        return True

    from platform_api.services.tier_service import is_pro

    return await is_pro(pool, user_id)


async def get_onboarding_profile_target(pool: Any, user_id: UUID) -> int:
    """Profiles the user should finish before onboarding AI turns off.

    Plans and add-ons are retired, so the target is the fixed base allowance.
    """
    del pool, user_id
    return ONBOARDING_PROFILE_TARGET


async def user_in_onboarding(pool: Any, user_id: UUID) -> bool:
    """True while the user still needs to finish channel profiles (initial or add-on)."""
    row = await pool.fetchrow(
        "SELECT COUNT(*)::int AS cnt FROM channel_profiles WHERE user_id = $1",
        user_id,
    )
    count = int(row["cnt"] or 0) if row else 0
    target = await get_onboarding_profile_target(pool, user_id)
    return count < target


async def effective_onboarding_ai_limit(
    pool: Any,
    user_id: UUID,
    operation_type: str,
) -> int:
    """Per-operation cap scaled by how many 2-channel onboarding bundles are open."""
    if operation_type not in ONBOARDING_AI_LIMITS:
        raise ValidationError(
            "Unsupported onboarding AI operation.",
            details={"operation_type": operation_type},
        )
    target = await get_onboarding_profile_target(pool, user_id)
    bundles = max(1, (target + ONBOARDING_PROFILE_TARGET - 1) // ONBOARDING_PROFILE_TARGET)
    return int(ONBOARDING_AI_LIMITS[operation_type]) * bundles


async def get_onboarding_usage(pool: Any, user_id: UUID, operation_type: str) -> int:
    row = await pool.fetchrow(
        """
        SELECT usage_count
        FROM onboarding_ai_usage
        WHERE user_id = $1 AND operation_type = $2
        """,
        user_id,
        operation_type,
    )
    return int(row["usage_count"] or 0) if row else 0


async def assert_onboarding_ai_allowed(
    pool: Any,
    user_id: UUID,
    operation_type: str,
    *,
    increment: int = 1,
) -> None:
    """Raise if onboarding AI is not allowed or the per-operation cap is exceeded."""
    if operation_type not in ONBOARDING_AI_LIMITS:
        raise ValidationError(
            "Unsupported onboarding AI operation.",
            details={"operation_type": operation_type},
        )

    if not await user_has_paid_for_onboarding(pool, user_id):
        raise ForbiddenError(
            "Complete payment before using onboarding AI features.",
            details={"error_code": "ONBOARDING_PAYMENT_REQUIRED"},
        )

    if not await user_in_onboarding(pool, user_id):
        raise ForbiddenError(
            "Onboarding AI is only available while finishing channel setup "
            "(including newly purchased add-on profiles).",
            details={"error_code": "ONBOARDING_ALREADY_COMPLETE"},
        )

    limit = await effective_onboarding_ai_limit(pool, user_id, operation_type)
    current = await get_onboarding_usage(pool, user_id, operation_type)
    if current + increment > limit:
        raise ForbiddenError(
            f"Onboarding limit reached for {operation_type.replace('_', ' ')}.",
            details={
                "error_code": "ONBOARDING_AI_LIMIT_EXCEEDED",
                "operation_type": operation_type,
                "limit": limit,
                "current_usage": current,
            },
        )


async def record_onboarding_ai_usage(
    pool: Any,
    user_id: UUID,
    operation_type: str,
    *,
    increment: int = 1,
) -> None:
    await pool.execute(
        """
        INSERT INTO onboarding_ai_usage (user_id, operation_type, usage_count, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id, operation_type)
        DO UPDATE SET
            usage_count = onboarding_ai_usage.usage_count + EXCLUDED.usage_count,
            updated_at = NOW()
        """,
        user_id,
        operation_type,
        increment,
    )


def _build_onboarding_event_metadata(
    operation_type: str,
    *,
    count: int,
    usage_metadata: dict[str, Any] | None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "category": "onboarding_ai",
        "source": "onboarding",
        "operation": operation_type,
        "purpose": _ONBOARDING_PURPOSE_LABELS.get(
            operation_type,
            f"Onboarding AI: {operation_type.replace('_', ' ')}",
        ),
        "status": status,
        "count": count,
        "line_items": [
            {
                "operation": operation_type,
                "provider": (usage_metadata or {}).get("provider"),
                "model": (usage_metadata or {}).get("model") or (usage_metadata or {}).get("sub_model"),
                "sub_model": (usage_metadata or {}).get("sub_model"),
                "amount_units": 0,
            }
        ],
    }
    if usage_metadata:
        metadata.update(usage_metadata)
    if error_code:
        metadata["error_code"] = error_code
    if error_message:
        metadata["error_message"] = error_message[:500]
    return metadata


async def record_onboarding_ai_event(
    pool: Any,
    user_id: UUID,
    operation_type: str,
    *,
    count: int,
    usage_metadata: dict[str, Any] | None = None,
    status: str = "success",
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    metadata = _build_onboarding_event_metadata(
        operation_type,
        count=count,
        usage_metadata=usage_metadata,
        status=status,
        error_code=error_code,
        error_message=error_message,
    )
    await pool.execute(
        """
        INSERT INTO credit_transactions
            (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
        VALUES ($1, $2, 0, 'debit', $3, $4, $5::jsonb, NOW())
        """,
        uuid4(),
        user_id,
        operation_type,
        f"onboarding:{operation_type}:{uuid4()}",
        json.dumps(metadata),
    )


async def _safe_record_onboarding_ai_event(
    pool: Any,
    user_id: UUID,
    operation_type: str,
    *,
    count: int,
    usage_metadata: dict[str, Any] | None = None,
    status: str = "success",
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        await record_onboarding_ai_event(
            pool,
            user_id,
            operation_type,
            count=count,
            usage_metadata=usage_metadata,
            status=status,
            error_code=error_code,
            error_message=error_message,
        )
    except Exception as exc:
        logger.exception(
            "Failed to record onboarding AI usage event: user=%s op=%s status=%s error=%s",
            user_id,
            operation_type,
            status,
            exc,
        )


async def run_onboarding_ai_operation(
    pool: Any,
    user_id: UUID,
    operation_type: str,
    operation: Callable[[], Awaitable[T]],
    *,
    count: int = 1,
    usage_metadata: dict[str, Any] | None = None,
) -> T:
    """Gate, execute, and record a payment-gated onboarding AI call (no wallet charge)."""
    try:
        await assert_onboarding_ai_allowed(pool, user_id, operation_type, increment=count)
    except Exception as exc:
        await _safe_record_onboarding_ai_event(
            pool,
            user_id,
            operation_type,
            count=count,
            usage_metadata=usage_metadata,
            status="blocked",
            error_code=getattr(exc, "error_code", None),
            error_message=str(exc),
        )
        raise
    try:
        result = await operation()
    except Exception as exc:
        await _safe_record_onboarding_ai_event(
            pool,
            user_id,
            operation_type,
            count=count,
            usage_metadata=usage_metadata,
            status="failed",
            error_code=getattr(exc, "error_code", None),
            error_message=str(exc),
        )
        raise
    await record_onboarding_ai_usage(pool, user_id, operation_type, increment=count)
    await _safe_record_onboarding_ai_event(
        pool,
        user_id,
        operation_type,
        count=count,
        usage_metadata=usage_metadata,
        status="success",
    )
    logger.info(
        "Onboarding AI used: user=%s op=%s count=%d",
        user_id,
        operation_type,
        count,
    )
    return result
