"""Read-only music language options for authenticated clients."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user

router = APIRouter(prefix="/music", tags=["music"])


class MusicLanguageOption(BaseModel):
    code: str
    label: str


class MusicLanguageListResponse(BaseModel):
    items: list[MusicLanguageOption]


async def _fetch_language_rows(*, enabled_only: bool) -> list[dict[str, Any]]:
    pool = get_db_pool()
    if enabled_only:
        rows = await pool.fetch(
            """
            SELECT code, label
            FROM music_languages
            WHERE enabled = TRUE
            ORDER BY sort_order ASC, code ASC
            """
        )
    else:
        rows = await pool.fetch(
            """
            SELECT code, label, enabled, sort_order, created_at, updated_at
            FROM music_languages
            ORDER BY sort_order ASC, code ASC
            """
        )
    return [dict(row) for row in rows]


@router.get("/languages", response_model=MusicLanguageListResponse)
async def list_enabled_music_languages(
    _ctx: Annotated[AuthContext, Depends(get_current_user)],
) -> MusicLanguageListResponse:
    """Return enabled music generation languages for desktop/web clients."""
    rows = await _fetch_language_rows(enabled_only=True)
    return MusicLanguageListResponse(
        items=[MusicLanguageOption(code=str(row["code"]), label=str(row["label"])) for row in rows]
    )
