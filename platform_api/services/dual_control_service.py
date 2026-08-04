"""Admin dual-control for sensitive credit adjustments (Phase 3 / H6).

When PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS > 0, large wallet adjusts
require a second distinct admin to approve before money moves.
Default threshold 0 disables dual-control so single-admin ops apply immediately.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from platform_api.config import get_settings
from platform_api.exceptions import ForbiddenError, NotFoundError, ValidationError
from platform_api.services.credit_units import credits_to_units, units_to_credits

logger = logging.getLogger(__name__)

OP_CREDIT_ADJUST = "credit.adjust"


def dual_control_threshold_units() -> int:
    """Absolute display-credit threshold above which adjusts need dual control."""
    try:
        credits = float(get_settings().admin_adjust_dual_control_credits)
    except Exception:
        credits = 1000.0
    credits = max(0.0, credits)
    if credits <= 0:
        return 0
    return credits_to_units(credits)


class DualControlService:
    """Queue and approve/reject sensitive admin operations."""

    def __init__(self, pool: Any, credit_service: Any) -> None:
        self._pool = pool
        self._credit_service = credit_service

    async def request_or_apply_credit_adjust(
        self,
        *,
        admin_id: str,
        user_id: str,
        amount_display: float,
        reason: str,
    ) -> dict[str, Any]:
        """Apply immediately under threshold; otherwise queue a pending request."""
        if not reason or not reason.strip():
            raise ValidationError(
                "Adjustment reason is required.",
                details={"reason": reason},
            )
        try:
            amount_units = credits_to_units(amount_display)
        except Exception as exc:
            raise ValidationError(str(exc), details={"amount": amount_display}) from exc
        if amount_units == 0:
            raise ValidationError(
                "Adjustment amount must be non-zero.",
                details={"amount": amount_display},
            )

        threshold = dual_control_threshold_units()
        if threshold <= 0 or abs(amount_units) < threshold:
            new_balance_units = await self._credit_service.admin_adjust(
                user_id=user_id,
                amount=amount_units,
                reason=reason,
            )
            return {
                "status": "applied",
                "pending_id": None,
                "user_id": user_id,
                "new_balance": units_to_credits(new_balance_units),
                "amount_adjusted": amount_display,
                "reason": reason,
                "requires_approval": False,
            }

        pending_id = uuid4()
        payload = {
            "user_id": user_id,
            "amount_display": amount_display,
            "amount_units": amount_units,
        }
        await self._pool.execute(
            """
            INSERT INTO admin_pending_ops (
                id, op_type, status, requested_by, target_user_id, payload, reason
            ) VALUES ($1, $2, 'pending', $3, $4, $5::jsonb, $6)
            """,
            pending_id,
            OP_CREDIT_ADJUST,
            UUID(admin_id),
            UUID(user_id),
            json.dumps(payload),
            reason.strip(),
        )
        logger.info(
            "Queued dual-control credit adjust %s by admin %s for user %s (amount=%s)",
            pending_id,
            admin_id,
            user_id,
            amount_display,
        )
        return {
            "status": "pending",
            "pending_id": str(pending_id),
            "user_id": user_id,
            "new_balance": None,
            "amount_adjusted": amount_display,
            "reason": reason.strip(),
            "requires_approval": True,
            "message": (
                "Adjustment exceeds dual-control threshold and awaits a second admin approval."
            ),
        }

    async def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, op_type, status, requested_by, target_user_id, payload, reason,
                   created_at
            FROM admin_pending_ops
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            max(1, min(limit, 200)),
        )
        return [self._row_to_dict(row) for row in rows]

    async def approve(
        self,
        *,
        pending_id: UUID,
        admin_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        row = await self._lock_pending(pending_id)
        if str(row["requested_by"]) == admin_id:
            raise ForbiddenError(
                "A different admin must approve this request (dual-control).",
                details={"error_code": "DUAL_CONTROL_SAME_ADMIN", "pending_id": str(pending_id)},
            )
        if row["op_type"] != OP_CREDIT_ADJUST:
            raise ValidationError(
                f"Unsupported pending op type: {row['op_type']}",
                details={"op_type": row["op_type"]},
            )

        payload = self._payload(row)
        user_id = str(payload.get("user_id") or row["target_user_id"])
        amount_units = int(payload["amount_units"])
        reason = str(row["reason"])

        new_balance_units = await self._credit_service.admin_adjust(
            user_id=user_id,
            amount=amount_units,
            reason=f"[dual-control approved] {reason}",
        )
        await self._pool.execute(
            """
            UPDATE admin_pending_ops
            SET status = 'approved',
                approved_by = $2,
                decision_note = $3,
                decided_at = NOW()
            WHERE id = $1
            """,
            pending_id,
            UUID(admin_id),
            (note or "").strip() or None,
        )
        amount_display = float(
            payload.get("amount_display")
            if payload.get("amount_display") is not None
            else units_to_credits(amount_units)
        )
        return {
            "status": "approved",
            "pending_id": str(pending_id),
            "user_id": user_id,
            "new_balance": units_to_credits(new_balance_units),
            "amount_adjusted": amount_display,
            "reason": reason,
            "requires_approval": False,
        }

    async def reject(
        self,
        *,
        pending_id: UUID,
        admin_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        await self._lock_pending(pending_id)
        await self._pool.execute(
            """
            UPDATE admin_pending_ops
            SET status = 'rejected',
                rejected_by = $2,
                decision_note = $3,
                decided_at = NOW()
            WHERE id = $1
            """,
            pending_id,
            UUID(admin_id),
            (note or "").strip() or None,
        )
        return {
            "status": "rejected",
            "pending_id": str(pending_id),
            "requires_approval": False,
        }

    async def _lock_pending(self, pending_id: UUID) -> Any:
        row = await self._pool.fetchrow(
            """
            SELECT id, op_type, status, requested_by, target_user_id, payload, reason
            FROM admin_pending_ops
            WHERE id = $1
            """,
            pending_id,
        )
        if row is None:
            raise NotFoundError(
                "Pending admin operation not found.",
                details={"pending_id": str(pending_id)},
            )
        if str(row["status"]) != "pending":
            raise ValidationError(
                f"Pending operation is already {row['status']}.",
                details={"pending_id": str(pending_id), "status": row["status"]},
            )
        return row

    @staticmethod
    def _payload(row: Any) -> dict[str, Any]:
        raw = row["payload"]
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        payload = DualControlService._payload(row)
        created = row["created_at"]
        if isinstance(created, datetime) and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return {
            "id": str(row["id"]),
            "op_type": row["op_type"],
            "status": row["status"],
            "requested_by": str(row["requested_by"]),
            "target_user_id": str(row["target_user_id"]) if row["target_user_id"] else None,
            "payload": payload,
            "reason": row["reason"],
            "created_at": created.isoformat() if isinstance(created, datetime) else created,
        }
