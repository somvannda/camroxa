from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRepository


router = APIRouter(prefix="/image-prompts", tags=["image-prompts"])


async def _get_image_prompt_repo() -> ImagePromptStyleRepository:
    raise NotImplementedError(
        "ImagePromptStyleRepository dependency not configured. Wire via app.dependency_overrides."
    )


UserDep = Annotated[AuthContext, Depends(get_current_user)]
RepoDep = Annotated[ImagePromptStyleRepository, Depends(_get_image_prompt_repo)]


class ImagePromptSummary(BaseModel):
    background: int = 0
    thumbnail: int = 0


class ImagePromptSummaryResponse(BaseModel):
    counts: ImagePromptSummary


class ImagePromptPublicItem(BaseModel):
    id: str
    kind: str
    name: str
    text_template: str | None = None


class ImagePromptPublicListResponse(BaseModel):
    items: list[ImagePromptPublicItem] = Field(default_factory=list)


def _raise_migration_needed() -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            "Image prompt storage is not available yet because the database migration "
            "has not been applied. Run `python -m alembic -c platform_api/alembic.ini "
            "upgrade head` from the project root."
        ),
    )


def _handle_storage_error(exc: Exception) -> None:
    if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
        _raise_migration_needed()
    if "image_prompt_styles" in str(exc).lower() and "does not exist" in str(exc).lower():
        _raise_migration_needed()


@router.get("/summary", response_model=ImagePromptSummaryResponse)
async def image_prompt_summary(
    _ctx: UserDep,
    repo: RepoDep,
) -> ImagePromptSummaryResponse:
    try:
        counts = await repo.count_active()
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return ImagePromptSummaryResponse(
        counts=ImagePromptSummary(
            background=int(counts.get("background", 0)),
            thumbnail=int(counts.get("thumbnail", 0)),
        )
    )


@router.get("", response_model=ImagePromptPublicListResponse)
async def list_image_prompts(
    _ctx: UserDep,
    repo: RepoDep,
    kind: str | None = None,
) -> ImagePromptPublicListResponse:
    kind_value = str(kind or "").strip().lower() or None
    if kind_value not in {None, "background", "thumbnail"}:
        raise HTTPException(status_code=422, detail="kind must be background or thumbnail.")
    try:
        if kind_value:
            styles = await repo.list_active(kind=kind_value)
        else:
            styles = [
                *await repo.list_active(kind="background"),
                *await repo.list_active(kind="thumbnail"),
            ]
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return ImagePromptPublicListResponse(
        items=[
            ImagePromptPublicItem(
                id=style.id,
                kind=style.kind,
                name=style.name,
                text_template=style.text_template,
            )
            for style in styles
        ]
    )
