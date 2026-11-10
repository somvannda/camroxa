"""Authenticated Creator Studio identity endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.creators_public import CreatorLink, CreatorPublicProfile
from platform_api.services.creator_profile_service import CreatorProfileService
from platform_api.services.creator_program_service import CreatorProgramService
from platform_api.services.creator_release_service import CreatorReleaseService
from platform_api.services.creator_eligibility_service import CreatorEligibilityService
from platform_api.services.creator_payout_service import CreatorPayoutService

router = APIRouter(prefix="/creator", tags=["creator-studio"])


async def _get_creator_service() -> CreatorProfileService:
    raise NotImplementedError("CreatorProfileService dependency not configured.")


async def _get_program_service() -> CreatorProgramService:
    raise NotImplementedError("CreatorProgramService dependency not configured.")


async def _get_release_service() -> CreatorReleaseService:
    raise NotImplementedError("CreatorReleaseService dependency not configured.")


async def _get_eligibility_service() -> CreatorEligibilityService:
    raise NotImplementedError("CreatorEligibilityService dependency not configured.")


async def _get_payout_service() -> CreatorPayoutService:
    raise NotImplementedError("CreatorPayoutService dependency not configured.")


CreatorServiceDep = Annotated[CreatorProfileService, Depends(_get_creator_service)]
ProgramServiceDep = Annotated[CreatorProgramService, Depends(_get_program_service)]
ReleaseServiceDep = Annotated[CreatorReleaseService, Depends(_get_release_service)]
EligibilityServiceDep = Annotated[CreatorEligibilityService, Depends(_get_eligibility_service)]
PayoutServiceDep = Annotated[CreatorPayoutService, Depends(_get_payout_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class CreatorStudioProfile(CreatorPublicProfile):
    user_id: str
    payout_currency: str = "USD"
    status: str = "active"
    pronouns: str | None = None
    program_joined_at: datetime | None = None


class CreatorChecklist(BaseModel):
    handle: bool = False
    display_name: bool = False
    bio: bool = False
    avatar: bool = False
    genre: bool = False
    first_release: bool = False
    verified: bool = False
    payout_ready: bool = False


class CreatorStudioResponse(BaseModel):
    profile: CreatorStudioProfile | None = None
    checklist: CreatorChecklist


class ClaimCreatorRequest(BaseModel):
    handle: str = Field(..., min_length=3, max_length=30)
    display_name: str = Field(..., min_length=1, max_length=50)
    tagline: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    links: list[CreatorLink] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    influences: list[str] = Field(default_factory=list)
    pronouns: str | None = Field(default=None, max_length=20)
    ai_disclosure: Literal["none", "ai_assisted", "ai_artist"] = "none"
    support_enabled: bool = False
    payout_currency: Literal["USD", "KHR"] = "USD"


class UpdateCreatorRequest(BaseModel):
    handle: str | None = Field(default=None, min_length=3, max_length=30)
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    tagline: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    links: list[CreatorLink] | None = None
    genres: list[str] | None = None
    influences: list[str] | None = None
    pronouns: str | None = Field(default=None, max_length=20)
    ai_disclosure: Literal["none", "ai_assisted", "ai_artist"] | None = None
    support_enabled: bool | None = None
    payout_currency: Literal["USD", "KHR"] | None = None


class HandleAvailabilityResponse(BaseModel):
    handle: str
    available: bool
    reason: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class ApplicationRequest(BaseModel):
    pitch: str = Field(..., min_length=50, max_length=500)
    links: list[CreatorLink] = Field(default_factory=list)
    track_ids: list[str] = Field(default_factory=list)
    rights_attested: bool = False
    requested_tier: Literal["verified"] = "verified"
    identity: dict | None = None


class VerificationRequest(BaseModel):
    kind: Literal["identity", "authenticity", "business", "voice_consent"]
    evidence_ref: str = Field(..., min_length=1, max_length=1000)


class ReleaseCreateRequest(BaseModel):
    source_task_id: str
    variant: Literal["ok", "alt"] = "ok"
    metadata: dict = Field(default_factory=dict)


class ReleaseUpdateRequest(BaseModel):
    metadata: dict = Field(default_factory=dict)


class KycRequest(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=120)
    date_of_birth: str = Field(..., min_length=10, max_length=10)
    country_code: str = Field(..., min_length=2, max_length=2)
    id_type: Literal["passport", "national_id", "drivers_license"]
    id_last4: str = Field(..., min_length=4, max_length=4)
    id_document_ref: str = Field(..., min_length=1, max_length=1000)
    selfie_ref: str | None = Field(default=None, max_length=1000)
    tax_id: str | None = Field(default=None, max_length=40)


class PayoutAccountRequest(BaseModel):
    method: Literal["aba", "wing", "khqr", "bank", "paypal", "wise"]
    account_name: str = Field(..., min_length=2, max_length=120)
    account_last4: str = Field(..., min_length=4, max_length=4)
    bank_code: str | None = Field(default=None, max_length=30)
    currency: Literal["USD", "KHR"] = "USD"


@router.get("/me", response_model=CreatorStudioResponse)
async def get_my_creator_profile(
    ctx: CurrentUserDep, service: CreatorServiceDep
) -> CreatorStudioResponse:
    payload = await service.get_studio(ctx.user_id)
    return CreatorStudioResponse.model_validate(payload)


@router.post("/claim", response_model=CreatorStudioResponse, status_code=201)
async def claim_creator_profile(
    body: ClaimCreatorRequest,
    ctx: CurrentUserDep,
    service: CreatorServiceDep,
) -> CreatorStudioResponse:
    payload = await service.claim(ctx.user_id, body.model_dump(exclude_unset=True))
    return CreatorStudioResponse.model_validate(payload)


@router.patch("/me", response_model=CreatorStudioResponse)
async def update_my_creator_profile(
    body: UpdateCreatorRequest,
    ctx: CurrentUserDep,
    service: CreatorServiceDep,
) -> CreatorStudioResponse:
    payload = await service.update(ctx.user_id, body.model_dump(exclude_unset=True))
    return CreatorStudioResponse.model_validate(payload)


@router.post("/me/media")
async def upload_creator_media(
    ctx: CurrentUserDep,
    service: CreatorServiceDep,
    kind: Literal["avatar", "banner"] = Query(...),
    file: UploadFile = File(...),
) -> dict:
    return await service.upload_media(
        ctx.user_id,
        kind=kind,
        content_type=str(file.content_type or "image/jpeg"),
        data=await file.read(),
    )


@router.get("/handle-available", response_model=HandleAvailabilityResponse)
async def check_handle(
    service: CreatorServiceDep,
    handle: str = Query(..., min_length=1, max_length=30),
) -> HandleAvailabilityResponse:
    return HandleAvailabilityResponse.model_validate(await service.availability(handle))


@router.get("/application")
async def get_application_status(
    ctx: CurrentUserDep, service: ProgramServiceDep
) -> dict:
    return await service.get_status(ctx.user_id)


@router.post("/application", status_code=201)
async def submit_application(
    body: ApplicationRequest,
    ctx: CurrentUserDep,
    service: ProgramServiceDep,
) -> dict:
    return await service.submit_application(ctx.user_id, body.model_dump(exclude_unset=True))


@router.post("/application/withdraw")
async def withdraw_application(
    ctx: CurrentUserDep, service: ProgramServiceDep
) -> dict:
    return await service.withdraw_application(ctx.user_id)


@router.get("/verification")
async def get_verification_status(
    ctx: CurrentUserDep, service: ProgramServiceDep
) -> dict:
    return await service.get_status(ctx.user_id)


@router.post("/verification", status_code=201)
async def submit_verification(
    body: VerificationRequest,
    ctx: CurrentUserDep,
    service: ProgramServiceDep,
) -> dict:
    return await service.submit_verification(
        ctx.user_id, kind=body.kind, evidence_ref=body.evidence_ref
    )


@router.get("/releases")
async def list_releases(ctx: CurrentUserDep, service: ReleaseServiceDep) -> dict:
    return {"items": await service.list_for_creator(ctx.user_id)}


@router.post("/releases", status_code=201)
async def create_release(
    body: ReleaseCreateRequest,
    ctx: CurrentUserDep,
    service: ReleaseServiceDep,
) -> dict:
    return {
        "release": await service.create_draft(
            ctx.user_id,
            source_task_id=body.source_task_id,
            variant=body.variant,
            metadata=body.metadata,
        )
    }


@router.post("/releases/quick-publish", status_code=201)
async def quick_publish_release(
    body: ReleaseCreateRequest,
    ctx: CurrentUserDep,
    service: ReleaseServiceDep,
) -> dict:
    """Publish a finished generation in one call.

    Creates the creator profile when needed, fills missing details from the
    generation, and puts the release live immediately.
    """
    return {
        "release": await service.quick_publish(
            ctx.user_id,
            source_task_id=body.source_task_id,
            variant=body.variant,
            metadata=body.metadata,
        )
    }


@router.get("/releases/{release_id}")
async def get_release(
    release_id: str, ctx: CurrentUserDep, service: ReleaseServiceDep
) -> dict:
    return {"release": await service.get_for_creator(ctx.user_id, release_id)}


@router.patch("/releases/{release_id}")
async def update_release(
    release_id: str,
    body: ReleaseUpdateRequest,
    ctx: CurrentUserDep,
    service: ReleaseServiceDep,
) -> dict:
    return {
        "release": await service.update_draft(ctx.user_id, release_id, body.metadata)
    }


@router.post("/releases/{release_id}/submit")
async def submit_release(
    release_id: str, ctx: CurrentUserDep, service: ReleaseServiceDep
) -> dict:
    return {"release": await service.submit(ctx.user_id, release_id)}


@router.post("/releases/{release_id}/withdraw")
async def withdraw_release(
    release_id: str, ctx: CurrentUserDep, service: ReleaseServiceDep
) -> dict:
    return {"release": await service.withdraw(ctx.user_id, release_id)}


@router.post("/releases/{release_id}/unpublish")
async def unpublish_release(
    release_id: str, ctx: CurrentUserDep, service: ReleaseServiceDep
) -> dict:
    return {"release": await service.unpublish(ctx.user_id, release_id)}


@router.get("/eligibility")
async def get_eligibility(
    ctx: CurrentUserDep, service: EligibilityServiceDep
) -> dict:
    return await service.list_creator(ctx.user_id)


@router.post("/eligibility/refresh")
async def refresh_eligibility(
    ctx: CurrentUserDep, service: EligibilityServiceDep
) -> dict:
    refreshed = await service.refresh_creator(ctx.user_id)
    payload = await service.list_creator(ctx.user_id)
    return {"refreshed": refreshed, **payload}


@router.get("/payouts")
async def get_payout_status(
    ctx: CurrentUserDep, service: PayoutServiceDep
) -> dict:
    return await service.get_status(ctx.user_id)


@router.post("/kyc")
async def submit_kyc(
    body: KycRequest,
    ctx: CurrentUserDep,
    service: PayoutServiceDep,
) -> dict:
    return await service.submit_kyc(ctx.user_id, body.model_dump(exclude_unset=True))


@router.post("/kyc/document")
async def upload_kyc_document(
    ctx: CurrentUserDep,
    service: PayoutServiceDep,
    kind: Literal["id", "selfie"] = Query(...),
    file: UploadFile = File(...),
) -> dict:
    return await service.upload_kyc_document(
        ctx.user_id,
        kind=kind,
        content_type=str(file.content_type or "application/octet-stream"),
        data=await file.read(),
    )


@router.put("/payout-account")
async def save_payout_account(
    body: PayoutAccountRequest,
    ctx: CurrentUserDep,
    service: PayoutServiceDep,
) -> dict:
    return await service.upsert_payout_account(ctx.user_id, body.model_dump(exclude_unset=True))


@router.post("/payouts/request")
async def request_payout(
    ctx: CurrentUserDep, service: PayoutServiceDep
) -> dict:
    return await service.request_payout(ctx.user_id)
