"""Admin review APIs for Creator Program applications, verification, and badges."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.creator_program_service import CreatorProgramService
from platform_api.services.creator_release_service import CreatorReleaseService
from platform_api.services.creator_eligibility_service import CreatorEligibilityService
from platform_api.services.creator_payout_service import CreatorPayoutService
from platform_api.services.royalty_engine_service import RoyaltyEngineService

router = APIRouter(prefix="/admin/creators", tags=["creator-admin"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


async def _get_program_service() -> CreatorProgramService:
    raise NotImplementedError("CreatorProgramService dependency not configured.")


async def _get_release_service() -> CreatorReleaseService:
    raise NotImplementedError("CreatorReleaseService dependency not configured.")


async def _get_eligibility_service() -> CreatorEligibilityService:
    raise NotImplementedError("CreatorEligibilityService dependency not configured.")


async def _get_payout_service() -> CreatorPayoutService:
    raise NotImplementedError("CreatorPayoutService dependency not configured.")


async def _get_royalty_engine_service() -> RoyaltyEngineService:
    raise NotImplementedError("RoyaltyEngineService dependency not configured.")


ProgramServiceDep = Annotated[CreatorProgramService, Depends(_get_program_service)]
ReleaseServiceDep = Annotated[CreatorReleaseService, Depends(_get_release_service)]
EligibilityServiceDep = Annotated[CreatorEligibilityService, Depends(_get_eligibility_service)]
PayoutServiceDep = Annotated[CreatorPayoutService, Depends(_get_payout_service)]
RoyaltyEngineDep = Annotated[RoyaltyEngineService, Depends(_get_royalty_engine_service)]


class ApplicationDecisionRequest(BaseModel):
    decision: Literal["approve", "request_changes", "reject"]
    reason: str | None = None


class VerificationDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None


class BadgeGrantRequest(BaseModel):
    badge: Literal[
        "verified",
        "founding",
        "top_creator",
        "partner",
        "label",
        "ai_artist",
        "ai_assisted",
        "staff",
    ]
    expires_at: datetime | None = None
    reason: str | None = None


class ReleaseDecisionRequest(BaseModel):
    decision: Literal["approve", "request_changes", "reject"]
    reason: str | None = None


class KycDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None


class MarkPaidRequest(BaseModel):
    reference: str = Field(..., min_length=1, max_length=120)


class TakedownRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class RoyaltyCalculateRequest(BaseModel):
    period_start: date
    period_end: date
    pool_usd: float | None = None


class PayoutRunRequest(BaseModel):
    period_start: date
    period_end: date


@router.get("/applications")
async def list_applications(
    ctx: AdminDep,
    service: ProgramServiceDep,
    status: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    del ctx
    return await service.list_applications(status=status, limit=limit, offset=offset)


@router.post("/applications/{application_id}/decision")
async def decide_application(
    application_id: str,
    body: ApplicationDecisionRequest,
    ctx: AdminDep,
    service: ProgramServiceDep,
) -> dict:
    return await service.decide_application(
        application_id,
        decision=body.decision,
        reviewer_id=ctx.user_id,
        reason=body.reason,
    )


@router.get("/verifications")
async def list_verifications(
    ctx: AdminDep,
    service: ProgramServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    del ctx
    return await service.list_pending_verifications(limit=limit, offset=offset)


@router.post("/verifications/{verification_id}/decision")
async def decide_verification(
    verification_id: str,
    body: VerificationDecisionRequest,
    ctx: AdminDep,
    service: ProgramServiceDep,
) -> dict:
    return await service.decide_verification(
        verification_id,
        decision=body.decision,
        reviewer_id=ctx.user_id,
        reason=body.reason,
    )


@router.get("/releases")
async def list_releases(
    ctx: AdminDep,
    service: ReleaseServiceDep,
    status: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    del ctx
    return await service.list_admin(status=status, limit=limit, offset=offset)


@router.post("/releases/{release_id}/decision")
async def decide_release(
    release_id: str,
    body: ReleaseDecisionRequest,
    ctx: AdminDep,
    service: ReleaseServiceDep,
) -> dict:
    return await service.decide(
        release_id,
        decision=body.decision,
        reviewer_id=ctx.user_id,
        reason=body.reason,
    )


@router.post("/releases/{release_id}/takedown")
async def takedown_release(
    release_id: str,
    body: TakedownRequest,
    ctx: AdminDep,
    service: ReleaseServiceDep,
) -> dict:
    return {
        "release": await service.admin_takedown(
            release_id, reviewer_id=ctx.user_id, reason=body.reason
        )
    }


@router.post("/eligibility/refresh")
async def refresh_eligibility(
    ctx: AdminDep,
    service: EligibilityServiceDep,
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    del ctx
    return {"refreshed": await service.refresh_all(limit=limit)}


@router.post("/royalty/calculate")
async def calculate_royalty(
    body: RoyaltyCalculateRequest,
    ctx: AdminDep,
    service: RoyaltyEngineDep,
) -> dict:
    del ctx
    return await service.calculate(
        period_start=body.period_start,
        period_end=body.period_end,
        pool_usd=body.pool_usd,
    )


@router.get("/royalty/periods")
async def list_royalty_periods(
    ctx: AdminDep,
    service: RoyaltyEngineDep,
    limit: int = Query(default=24, ge=1, le=100),
) -> dict:
    del ctx
    return await service.list_periods(limit=limit)


@router.post("/royalty/periods/{period_id}/lock")
async def lock_royalty_period(
    period_id: str,
    ctx: AdminDep,
    service: RoyaltyEngineDep,
) -> dict:
    del ctx
    return await service.lock_period(period_id)


@router.post("/payouts/run")
async def create_payout_run(
    body: PayoutRunRequest,
    ctx: AdminDep,
    service: PayoutServiceDep,
) -> dict:
    return await service.create_run(
        period_start=body.period_start,
        period_end=body.period_end,
        created_by=ctx.user_id,
    )


@router.post("/payouts/{payout_id}/approve")
async def approve_payout(
    payout_id: str,
    ctx: AdminDep,
    service: PayoutServiceDep,
) -> dict:
    return await service.approve_payout(payout_id, reviewer_id=ctx.user_id)


@router.get("/payouts/export")
async def export_payouts(
    ctx: AdminDep,
    service: PayoutServiceDep,
    status: str | None = Query(default=None, max_length=20),
) -> Response:
    del ctx
    rows = await service.export_rows(status=status)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "payout_id",
            "creator",
            "email",
            "handle",
            "amount_usd",
            "currency",
            "method",
            "status",
            "requested_at",
            "paid_at",
            "reference",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("user_display_name") or "",
                row.get("email") or "",
                row.get("handle") or "",
                f"{int(row.get('amount_micros') or 0) / 1_000_000:.2f}",
                row.get("currency") or "USD",
                row.get("method") or "",
                row.get("status") or "",
                row.get("requested_at").isoformat() if row.get("requested_at") else "",
                row.get("paid_at").isoformat() if row.get("paid_at") else "",
                row.get("payment_ref") or "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="creator-payouts.csv"',
        },
    )


@router.get("/kyc")
async def list_kyc(
    ctx: AdminDep,
    service: PayoutServiceDep,
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    del ctx
    return await service.list_kyc(status=status, limit=limit, offset=offset)


@router.get("/kyc/{user_id}/documents/{kind}")
async def sign_kyc_document(
    user_id: str,
    kind: Literal["id", "selfie"],
    ctx: AdminDep,
    service: PayoutServiceDep,
) -> dict:
    """Return a short-lived signed URL for a KYC document.

    The admin portal requests this with its bearer token and then opens the
    returned URL, so the raw storage key is never exposed to the browser.
    """
    del ctx
    return await service.signed_kyc_document(user_id, kind=kind)


@router.post("/kyc/{user_id}/decision")
async def decide_kyc(
    user_id: str,
    body: KycDecisionRequest,
    ctx: AdminDep,
    service: PayoutServiceDep,
) -> dict:
    return await service.decide_kyc(
        user_id,
        decision=body.decision,
        reviewer_id=ctx.user_id,
        reason=body.reason,
    )


@router.get("/tax/statements")
async def list_tax_statements(
    ctx: AdminDep,
    service: PayoutServiceDep,
    year: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    del ctx
    return await service.list_statements(year=year, limit=limit)


@router.post("/tax/statements/generate")
async def generate_tax_statements(
    ctx: AdminDep,
    service: PayoutServiceDep,
    year: int = Query(..., ge=2000, le=2100),
) -> dict:
    del ctx
    return await service.generate_statements(year)


@router.get("/payouts")
async def list_payouts(
    ctx: AdminDep,
    service: PayoutServiceDep,
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    del ctx
    return await service.list_payouts(status=status, limit=limit, offset=offset)


@router.post("/payouts/{payout_id}/mark-paid")
async def mark_payout_paid(
    payout_id: str,
    body: MarkPaidRequest,
    ctx: AdminDep,
    service: PayoutServiceDep,
) -> dict:
    return await service.mark_paid(
        payout_id, reference=body.reference, reviewer_id=ctx.user_id
    )


@router.post("/{user_id}/badges")
async def grant_badge(
    user_id: str,
    body: BadgeGrantRequest,
    ctx: AdminDep,
    service: ProgramServiceDep,
) -> dict:
    return await service.grant_badge(
        user_id,
        badge=body.badge,
        reviewer_id=ctx.user_id,
        expires_at=body.expires_at,
        reason=body.reason,
    )


@router.delete("/{user_id}/badges/{badge}")
async def revoke_badge(
    user_id: str,
    badge: str,
    ctx: AdminDep,
    service: ProgramServiceDep,
    reason: str | None = Query(default=None, max_length=500),
) -> dict:
    del ctx
    return await service.revoke_badge(user_id, badge=badge, reason=reason)
