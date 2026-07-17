from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.invitation_code_service import (
    InvitationCodeService,
)

router = APIRouter(prefix="/admin/invitations", tags=["admin-invitations"])


async def _get_invitation_code_service() -> InvitationCodeService:
    raise NotImplementedError(
        "InvitationCodeService dependency not configured. Wire via app.dependency_overrides."
    )


AdminDep = Annotated[AuthContext, Depends(require_admin)]
InvitationSvcDep = Annotated[InvitationCodeService, Depends(_get_invitation_code_service)]


class SignupModeResponse(BaseModel):
    mode: str


class SignupModeUpdateRequest(BaseModel):
    mode: str = Field(..., min_length=1, max_length=50)


class CreateInvitationRequest(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    max_uses: int = Field(default=1, ge=1, le=100000)
    expires_at: datetime | None = None
    is_active: bool = True


class UpdateInvitationRequest(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    max_uses: int | None = Field(default=None, ge=1, le=100000)
    expires_at: datetime | None = None
    is_active: bool | None = None


class InvitationCodeItem(BaseModel):
    id: str
    code: str | None = None
    code_hint: str
    label: str | None
    max_uses: int
    current_uses: int
    remaining_uses: int | None
    is_active: bool
    expires_at: str | None
    created_at: str


class InvitationCodeCreateResponse(InvitationCodeItem):
    code: str


@router.get("/signup-mode", response_model=SignupModeResponse, status_code=200)
async def get_signup_mode(ctx: AdminDep, svc: InvitationSvcDep) -> SignupModeResponse:
    del ctx
    return SignupModeResponse(mode=await svc.get_signup_mode())


@router.put("/signup-mode", response_model=SignupModeResponse, status_code=200)
async def update_signup_mode(
    request: SignupModeUpdateRequest,
    ctx: AdminDep,
    svc: InvitationSvcDep,
) -> SignupModeResponse:
    del ctx
    return SignupModeResponse(mode=await svc.set_signup_mode(request.mode))


@router.get("", response_model=list[InvitationCodeItem], status_code=200)
async def list_invitation_codes(ctx: AdminDep, svc: InvitationSvcDep) -> list[InvitationCodeItem]:
    del ctx
    items = await svc.list_admin_codes()
    return [
        InvitationCodeItem(
            id=item.id,
            code=item.code,
            code_hint=item.code_hint,
            label=item.label,
            max_uses=item.max_uses,
            current_uses=item.current_uses,
            remaining_uses=item.remaining_uses,
            is_active=item.is_active,
            expires_at=item.expires_at,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.post("", response_model=InvitationCodeCreateResponse, status_code=201)
async def create_invitation_code(
    request: CreateInvitationRequest,
    ctx: AdminDep,
    svc: InvitationSvcDep,
) -> InvitationCodeCreateResponse:
    del ctx
    result = await svc.create_admin_code(
        label=request.label,
        max_uses=request.max_uses,
        expires_at=request.expires_at,
        is_active=request.is_active,
    )
    return InvitationCodeCreateResponse(
        id=result.id,
        code=result.code,
        code_hint=result.code_hint,
        label=result.label,
        max_uses=result.max_uses,
        current_uses=0,
        remaining_uses=result.max_uses,
        is_active=result.is_active,
        expires_at=result.expires_at,
        created_at=result.created_at,
    )


@router.patch("/{code_id}", status_code=200)
async def update_invitation_code(
    code_id: str,
    request: UpdateInvitationRequest,
    ctx: AdminDep,
    svc: InvitationSvcDep,
) -> dict[str, str]:
    del ctx
    await svc.update_admin_code(
        code_id=code_id,
        label=request.label,
        max_uses=request.max_uses,
        expires_at=request.expires_at,
        is_active=request.is_active,
    )
    return {"message": "Invitation code updated."}


@router.delete("/{code_id}", status_code=200)
async def delete_invitation_code(
    code_id: str,
    ctx: AdminDep,
    svc: InvitationSvcDep,
) -> dict[str, str]:
    del ctx
    try:
        await svc.delete_admin_code(code_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to delete invitation code.") from exc
    return {"message": "Invitation code deleted."}
