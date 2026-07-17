from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.image_sample_pack_repo import ImageSamplePackRepository


router = APIRouter(prefix="/image-sample-packs", tags=["image-sample-packs"])


async def _get_image_sample_pack_repo() -> ImageSamplePackRepository:
    raise NotImplementedError(
        "ImageSamplePackRepository dependency not configured. Wire via app.dependency_overrides."
    )


UserDep = Annotated[AuthContext, Depends(get_current_user)]
RepoDep = Annotated[ImageSamplePackRepository, Depends(_get_image_sample_pack_repo)]


class ImageSamplePackItem(BaseModel):
    id: str
    category: str
    name: str
    source_type: str
    source_value: str
    version_label: str | None = None
    notes: str | None = None


class ImageSamplePackListResponse(BaseModel):
    items: list[ImageSamplePackItem]


def _raise_image_sample_pack_migration_needed() -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            "Image sample pack storage is not available yet because the database migration has not been applied. "
            "Run `python -m alembic -c platform_api/alembic.ini upgrade head` from the project root."
        ),
    )


def _handle_image_sample_pack_storage_error(exc: Exception) -> None:
    if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
        _raise_image_sample_pack_migration_needed()
    if "image_sample_packs" in str(exc).lower() and "does not exist" in str(exc).lower():
        _raise_image_sample_pack_migration_needed()



@router.get("", response_model=ImageSamplePackListResponse)
async def list_image_sample_packs(
    _ctx: UserDep,
    repo: RepoDep,
) -> ImageSamplePackListResponse:
    try:
        packs = await repo.list_for_user()
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    return ImageSamplePackListResponse(
        items=[
            ImageSamplePackItem(
                id=pack.id,
                category=pack.category,
                name=pack.name,
                source_type=pack.source_type,
                source_value=pack.source_value,
                version_label=pack.version_label,
                notes=pack.notes,
            )
            for pack in packs
        ]
    )
