"""Read-only Suno blocklist runtime config for authenticated clients."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.dependencies import get_suno_blocklist_service
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.suno_blocklist_service import SunoBlocklistService

router = APIRouter(prefix="/generation", tags=["generation"])


class SunoBlocklistRuntimeResponse(BaseModel):
    replacements: dict[str, str] = Field(default_factory=dict)
    block_terms: list[str] = Field(default_factory=list)
    warn_terms: list[str] = Field(default_factory=list)


@router.get("/suno-blocklist", response_model=SunoBlocklistRuntimeResponse)
async def get_suno_blocklist_runtime(
    _ctx: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[SunoBlocklistService, Depends(get_suno_blocklist_service)],
) -> SunoBlocklistRuntimeResponse:
    config = await service.get_runtime_config()
    return SunoBlocklistRuntimeResponse(
        replacements=dict(config.replacements),
        block_terms=sorted(config.block_terms),
        warn_terms=sorted(config.warn_terms),
    )
