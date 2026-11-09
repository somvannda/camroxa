"""Admin monitoring for failed music charges that were never refunded."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.exceptions import ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.refund_audit_service import (
    collect_unrefunded_music_charges,
    refund_command,
    refund_failed_charges,
    summarize_by_user,
)

router = APIRouter(prefix="/admin/failed-refunds", tags=["admin"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


class RefundFailedRequest(BaseModel):
    """Refund one or more failed debits; ``confirm`` guards accidental clicks."""

    user_id: UUID
    debit_ids: list[UUID] = Field(min_length=1, max_length=500)
    confirm: str = Field(default="", max_length=20)


@router.get("", summary="Failed music charges awaiting a refund")
async def list_failed_refunds(
    _ctx: AdminDep,
    days: int = Query(default=30, ge=1, le=365),
    min_age_minutes: int = Query(default=15, ge=0, le=1440),
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict[str, Any]:
    """Return every charged-but-failed generation with no refund.

    A row is a *real failure* when the charge produced no successful Suno task
    (no task at all, or a failed one) and no refund settled it. The window is a
    time correlation because pre-c23c7b9b desktop debits carry no ``ref_id``.
    """
    pool = get_db_pool()
    rows = await collect_unrefunded_music_charges(
        pool,
        days=days,
        min_age_minutes=min_age_minutes,
    )
    users = summarize_by_user(rows)
    total_credits = round(sum(float(row["credits"]) for row in rows), 2)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "min_age_minutes": min_age_minutes,
        "summary": {
            "charges": len(rows),
            "credits": total_credits,
            "users": len(users),
            "no_task": sum(1 for row in rows if row["reason"] == "no_task"),
            "failed_task": sum(1 for row in rows if row["reason"] == "failed_task"),
        },
        "users": users,
        "rows": rows[:limit],
        "truncated": len(rows) > limit,
        "refund_command": refund_command(int(round(total_credits)), days=days),
    }


@router.post("/refund", summary="Refund selected failed music charges")
async def refund_failed(
    ctx: AdminDep,
    body: RefundFailedRequest,
) -> dict[str, Any]:
    """Refund the selected debits through the idempotent wallet refund.

    Requires ``confirm="REFUND"``. Debits that no longer match the audit
    (already refunded, or a successful task appeared) are left untouched.
    """
    if body.confirm.strip().upper() != "REFUND":
        raise ValidationError(
            "Refund confirmation missing.",
            details={"confirm": "type REFUND to confirm"},
        )
    result = await refund_failed_charges(
        get_db_pool(),
        user_id=body.user_id,
        debit_ids=body.debit_ids,
        admin_id=str(ctx.user_id),
    )
    return result
