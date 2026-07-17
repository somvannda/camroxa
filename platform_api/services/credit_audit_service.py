"""Audit log helpers for wallet credit changes."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from platform_api.services.credit_units import units_to_credits

logger = logging.getLogger(__name__)


def display_credits_to_audit_impact(display_credits: float) -> int:
    """Map wallet change to audit credit_impact (positive = debit, negative = credit added)."""
    if display_credits == 0:
        return 0
    magnitude = max(1, int(round(abs(display_credits))))
    return -magnitude if display_credits > 0 else magnitude


async def log_wallet_credit_event(
    *,
    actor_id: str | UUID | None,
    user_id: str | UUID,
    action_type: str,
    amount_units: int,
    reason: str,
    outcome: str = "success",
    target_resource: str | None = None,
    payment_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append an audit row when wallet credits are minted, redeemed, or adjusted."""
    if amount_units == 0:
        return

    display_amount = units_to_credits(abs(amount_units))
    signed_display = display_amount if amount_units > 0 else -display_amount
    credit_impact = display_credits_to_audit_impact(signed_display)

    payload: dict[str, Any] = {
        "user_id": str(user_id),
        "credit_reason": reason,
        "amount_units": amount_units,
        "amount_display_credits": display_amount,
    }
    if payment_ref:
        payload["payment_ref"] = payment_ref
    if metadata:
        payload.update(metadata)

    try:
        from platform_api.dependencies import get_audit_service

        audit_service = get_audit_service()
        await audit_service.log_event(
            actor_id=str(actor_id) if actor_id else str(user_id),
            action_type=action_type,
            target_resource=target_resource or f"credit_wallet:{user_id}",
            credit_impact=credit_impact,
            outcome=outcome,
            metadata=payload,
        )
    except Exception:
        logger.warning(
            "Failed to audit wallet credit event action=%s user=%s",
            action_type,
            user_id,
            exc_info=True,
        )
