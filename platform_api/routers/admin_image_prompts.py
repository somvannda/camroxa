from __future__ import annotations

import re
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRepository


router = APIRouter(prefix="/admin/image-prompts", tags=["admin"])

PROMPT_TEXT_MAX_CHARS = 3000
VALID_KINDS = {"background", "thumbnail"}


async def _get_image_prompt_repo() -> ImagePromptStyleRepository:
    raise NotImplementedError(
        "ImagePromptStyleRepository dependency not configured. Wire via app.dependency_overrides."
    )


AdminDep = Annotated[AuthContext, Depends(require_admin)]
RepoDep = Annotated[ImagePromptStyleRepository, Depends(_get_image_prompt_repo)]


class ImagePromptStyleItem(BaseModel):
    id: str
    kind: str
    name: str
    prompt_text: str
    text_template: str | None = None
    is_active: bool
    sort_order: int
    notes: str | None = None


class ImagePromptStyleListResponse(BaseModel):
    items: list[ImagePromptStyleItem]


class ImagePromptStyleCreateRequest(BaseModel):
    kind: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=120)
    prompt_text: str = Field(..., min_length=1, max_length=PROMPT_TEXT_MAX_CHARS)
    text_template: str | None = Field(default=None, max_length=200)
    is_active: bool = True
    sort_order: int = 0
    notes: str | None = Field(default=None, max_length=1000)


class ImagePromptStyleUpdateRequest(BaseModel):
    kind: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_text: str | None = Field(default=None, min_length=1, max_length=PROMPT_TEXT_MAX_CHARS)
    text_template: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    sort_order: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


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


def _validate_kind(kind: str) -> str:
    value = str(kind or "").strip().lower()
    if value not in VALID_KINDS:
        raise HTTPException(status_code=422, detail="kind must be background or thumbnail.")
    return value


def _validate_text_template(kind: str, template: str | None) -> str | None:
    if template is None:
        return None
    value = str(template).strip()
    if not value:
        return ""
    if kind != "thumbnail":
        raise HTTPException(
            status_code=422,
            detail="text_template is only available for thumbnail styles.",
        )
    unknown = set(re.findall(r"\{([a-zA-Z_]+)\}", value)) - {"title", "album", "channel"}
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=(
                "Unknown text_template token(s): "
                + ", ".join(sorted(unknown))
                + ". Use {title}, {album}, or {channel}."
            ),
        )
    return value


def _item(record: object) -> ImagePromptStyleItem:
    return ImagePromptStyleItem(
        id=record.id,
        kind=record.kind,
        name=record.name,
        prompt_text=record.prompt_text,
        text_template=record.text_template,
        is_active=record.is_active,
        sort_order=record.sort_order,
        notes=record.notes,
    )


@router.get("", response_model=ImagePromptStyleListResponse)
async def list_image_prompts(
    _ctx: AdminDep,
    repo: RepoDep,
    kind: str | None = None,
) -> ImagePromptStyleListResponse:
    try:
        styles = await repo.list_all(kind=_validate_kind(kind) if kind else None)
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return ImagePromptStyleListResponse(items=[_item(style) for style in styles])


@router.post("", response_model=ImagePromptStyleItem)
async def create_image_prompt(
    _ctx: AdminDep,
    repo: RepoDep,
    request: ImagePromptStyleCreateRequest,
) -> ImagePromptStyleItem:
    kind = _validate_kind(request.kind)
    text_template = _validate_text_template(kind, request.text_template)
    prompt_text = request.prompt_text.strip()
    name = request.name.strip()
    if not prompt_text:
        raise HTTPException(status_code=422, detail="prompt_text cannot be blank.")
    if not name:
        raise HTTPException(status_code=422, detail="name cannot be blank.")
    try:
        style = await repo.create(
            kind=kind,
            name=name,
            prompt_text=prompt_text,
            text_template=text_template,
            is_active=request.is_active,
            sort_order=int(request.sort_order or 0),
            notes=(request.notes or "").strip() or None,
        )
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if style is None:
        raise HTTPException(status_code=500, detail="Could not create image prompt style.")
    return _item(style)


@router.patch("/{style_id}", response_model=ImagePromptStyleItem)
async def update_image_prompt(
    _ctx: AdminDep,
    repo: RepoDep,
    style_id: str,
    request: ImagePromptStyleUpdateRequest,
) -> ImagePromptStyleItem:
    kind = _validate_kind(request.kind) if request.kind else None
    if kind == "background":
        text_template = ""
    elif request.text_template is not None:
        text_template = _validate_text_template(kind or "thumbnail", request.text_template)
    else:
        text_template = None
    if request.name is not None and not request.name.strip():
        raise HTTPException(status_code=422, detail="name cannot be blank.")
    if request.prompt_text is not None and not request.prompt_text.strip():
        raise HTTPException(status_code=422, detail="prompt_text cannot be blank.")
    try:
        style = await repo.update(
            style_id,
            kind=kind,
            name=(
                request.name.strip() if request.name is not None else None
            ),
            prompt_text=(
                request.prompt_text.strip() if request.prompt_text is not None else None
            ),
            text_template=text_template,
            is_active=request.is_active,
            sort_order=request.sort_order,
            notes=(
                (request.notes or "").strip() or None
                if request.notes is not None
                else None
            ),
        )
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if style is None:
        raise HTTPException(status_code=404, detail="Image prompt style not found.")
    return _item(style)


@router.delete("/{style_id}")
async def delete_image_prompt(
    _ctx: AdminDep,
    repo: RepoDep,
    style_id: str,
) -> dict[str, bool]:
    try:
        deleted = await repo.delete(style_id)
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if not deleted:
        raise HTTPException(status_code=404, detail="Image prompt style not found.")
    return {"ok": True}
