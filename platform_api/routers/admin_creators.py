"""Admin review APIs for Creator Program applications, verification, and badges."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.creator_program_service import CreatorProgramService
from platform_api.services.creator_release_service import CreatorReleaseService

router = APIRouter(prefix="/admin/creators", tags=["creator-admin"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


async def _get_program_service() -> CreatorProgramService:
    raise NotImplementedError("CreatorProgramService dependency not configured.")


async def _get_release_service() -> CreatorReleaseService:
    raise NotImplementedError("CreatorReleaseService dependency not configured.")


ProgramServiceDep = Annotated[CreatorProgramService, Depends(_get_program_service)]
ReleaseServiceDep = Annotated[CreatorReleaseService, Depends(_get_release_service)]


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
