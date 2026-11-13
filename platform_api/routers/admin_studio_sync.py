"""Admin view of the Suno Studio project mirror.

The mirror itself lives in musicapi; this route forwards its health payload so the
admin console can show pinned accounts, outbox pressure and field coverage
without exposing musicapi to the browser.
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Query

from platform_api.config import get_settings
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.routers.web_music import WebMusicServiceDep

router = APIRouter(prefix="/admin", tags=["admin"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


@router.get("/studio-sync")
async def studio_sync_health(_admin: AdminDep) -> dict[str, Any]:
    settings = get_settings()
    token = str(settings.studio_internal_token or "").strip()
    base = str(settings.suno_api_base_url or "").rstrip("/")
    if not token or not base:
        return {"configured": False, "ok": False}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{base}/internal/studio/sync/health",
                headers={"x-internal-token": token},
            )
    except Exception:
        return {"configured": True, "ok": False}
    if response.status_code >= 400:
        return {"configured": True, "ok": False, "status": response.status_code}
    try:
        payload = response.json() or {}
    except ValueError:
        return {"configured": True, "ok": False}
    if not isinstance(payload, dict):
        return {"configured": True, "ok": False}
    return {"configured": True, "ok": True, **payload}


@router.post("/studio-sync/backfill")
async def backfill_studio_sync(
    service: WebMusicServiceDep,
    _admin: AdminDep,
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, int]:
    """Queue mirror links for a bounded batch of existing projects."""
    return await service.backfill_studio_mirror(limit)
