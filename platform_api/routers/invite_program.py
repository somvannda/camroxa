"""Invite-a-friend program endpoints for music.camxora.com + admin.camxora.com."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.exceptions import NotFoundError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services import invite_program_service as invite_service

router = APIRouter(tags=["invite-program"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


class RewardRulePatch(BaseModel):
    mode: Literal["percent", "fixed"] | None = None
    value: float | None = Field(default=None, ge=0)


class InviteSettingsPatch(BaseModel):
    enabled: bool | None = None
    inviter: RewardRulePatch | None = None
    invitee: RewardRulePatch | None = None


@router.get("/web-music/invite", summary="The caller's referral code, terms and invited friends")
async def get_web_music_invite(ctx: CurrentUserDep) -> dict:
    return await invite_service.get_user_invite_view(get_db_pool(), user_id=ctx.user_id)


@router.get("/admin/invite-program", summary="List the referral pipeline and current settings")
async def list_invite_program(
    ctx: AdminDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> dict:
    del ctx
    return await invite_service.list_admin_referrals(
        get_db_pool(),
        page=page,
        page_size=page_size,
        status=status,
        query=q,
    )


@router.put("/admin/invite-program/settings", summary="Update invite reward settings")
async def update_invite_program_settings(payload: InviteSettingsPatch, ctx: AdminDep) -> dict:
    del ctx
    db = get_db_pool()
    current = await invite_service.load_invite_settings(db)
    patch = payload.model_dump(exclude_unset=True, exclude_none=True)
    merged = invite_service.merge_invite_settings(current, patch)
    await invite_service.save_invite_settings(db, merged)
    return invite_service.serialize_invite_settings(merged)


@router.post("/admin/invite-program/{invite_id}/reject", summary="Reject a pending referral")
async def reject_invite_program(invite_id: str, ctx: AdminDep) -> dict:
    del ctx
    ok = await invite_service.reject_referral(get_db_pool(), invite_id)
    if not ok:
        raise NotFoundError("Only a pending referral can be rejected.")
    return {"ok": True}


@router.post("/admin/invite-program/{invite_id}/restore", summary="Restore a rejected/skipped referral")
async def restore_invite_program(invite_id: str, ctx: AdminDep) -> dict:
    del ctx
    ok = await invite_service.restore_referral(get_db_pool(), invite_id)
    if not ok:
        raise NotFoundError("Only a rejected or skipped referral can be restored.")
    return {"ok": True}
