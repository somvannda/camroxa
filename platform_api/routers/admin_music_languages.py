"""Admin CRUD for music generation language options."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.routers.music_languages import MusicLanguageOption, _fetch_language_rows

router = APIRouter(prefix="/admin/music-languages", tags=["admin-music-languages"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]
_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,19}$")


class AdminMusicLanguageRow(MusicLanguageOption):
    enabled: bool
    sort_order: int
    created_at: str | None = None
    updated_at: str | None = None


class AdminMusicLanguageListResponse(BaseModel):
    items: list[AdminMusicLanguageRow]


class CreateMusicLanguageRequest(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    label: str = Field(min_length=1, max_length=80)
    enabled: bool = False
    sort_order: int = Field(default=0, ge=0, le=9999)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _CODE_PATTERN.match(normalized):
            raise ValueError("Code must use lowercase letters, numbers, underscores, or hyphens.")
        return normalized

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Label is required.")
        return normalized


class UpdateMusicLanguageRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Label cannot be empty.")
        return normalized


def _row_to_admin_item(row: dict) -> AdminMusicLanguageRow:
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    return AdminMusicLanguageRow(
        code=str(row["code"]),
        label=str(row["label"]),
        enabled=bool(row.get("enabled")),
        sort_order=int(row.get("sort_order") or 0),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


async def _count_enabled_languages(*, exclude_code: str | None = None) -> int:
    pool = get_db_pool()
    if exclude_code:
        return int(
            await pool.fetchval(
                """
                SELECT COUNT(*)::int
                FROM music_languages
                WHERE enabled = TRUE AND code <> $1
                """,
                exclude_code,
            )
            or 0
        )
    return int(
        await pool.fetchval(
            "SELECT COUNT(*)::int FROM music_languages WHERE enabled = TRUE"
        )
        or 0
    )


@router.get("", response_model=AdminMusicLanguageListResponse)
async def list_music_languages_admin(_ctx: AdminDep) -> AdminMusicLanguageListResponse:
    rows = await _fetch_language_rows(enabled_only=False)
    return AdminMusicLanguageListResponse(items=[_row_to_admin_item(row) for row in rows])


@router.post("", response_model=AdminMusicLanguageRow, status_code=201)
async def create_music_language(
    request: CreateMusicLanguageRequest,
    _ctx: AdminDep,
) -> AdminMusicLanguageRow:
    pool = get_db_pool()
    if not request.enabled:
        enabled_count = await _count_enabled_languages()
        if enabled_count == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one language must remain enabled.",
            )

    row = await pool.fetchrow(
        """
        INSERT INTO music_languages (code, label, enabled, sort_order)
        VALUES ($1, $2, $3, $4)
        RETURNING code, label, enabled, sort_order, created_at, updated_at
        """,
        request.code,
        request.label,
        request.enabled,
        request.sort_order,
    )
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create language.")
    return _row_to_admin_item(dict(row))


@router.patch("/{code}", response_model=AdminMusicLanguageRow)
async def update_music_language(
    code: str,
    request: UpdateMusicLanguageRequest,
    _ctx: AdminDep,
) -> AdminMusicLanguageRow:
    normalized_code = code.strip().lower()
    pool = get_db_pool()
    existing = await pool.fetchrow(
        "SELECT code, label, enabled, sort_order FROM music_languages WHERE code = $1",
        normalized_code,
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Language not found.")

    next_enabled = request.enabled if request.enabled is not None else bool(existing["enabled"])
    if not next_enabled:
        remaining = await _count_enabled_languages(exclude_code=normalized_code)
        if remaining == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one language must remain enabled.",
            )

    row = await pool.fetchrow(
        """
        UPDATE music_languages
        SET label = COALESCE($2, label),
            enabled = COALESCE($3, enabled),
            sort_order = COALESCE($4, sort_order),
            updated_at = NOW()
        WHERE code = $1
        RETURNING code, label, enabled, sort_order, created_at, updated_at
        """,
        normalized_code,
        request.label,
        request.enabled,
        request.sort_order,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Language not found.")
    return _row_to_admin_item(dict(row))


@router.delete("/{code}", status_code=204)
async def delete_music_language(code: str, _ctx: AdminDep) -> None:
    normalized_code = code.strip().lower()
    pool = get_db_pool()
    existing = await pool.fetchrow(
        "SELECT enabled FROM music_languages WHERE code = $1",
        normalized_code,
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Language not found.")

    if bool(existing["enabled"]):
        remaining = await _count_enabled_languages(exclude_code=normalized_code)
        if remaining == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last enabled language.",
            )

    result = await pool.execute(
        "DELETE FROM music_languages WHERE code = $1",
        normalized_code,
    )
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="Language not found.")
