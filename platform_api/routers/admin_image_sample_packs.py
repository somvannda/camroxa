from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from platform_api.exceptions import ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.image_sample_pack_repo import ImageSamplePackRepository


router = APIRouter(prefix="/admin/image-sample-packs", tags=["admin"])


async def _get_image_sample_pack_repo() -> ImageSamplePackRepository:
    raise NotImplementedError(
        "ImageSamplePackRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_image_sample_pack_service():
    raise NotImplementedError(
        "ImageSamplePackService dependency not configured. Wire via app.dependency_overrides."
    )


AdminDep = Annotated[AuthContext, Depends(require_admin)]
RepoDep = Annotated[ImageSamplePackRepository, Depends(_get_image_sample_pack_repo)]
ServiceDep = Annotated[object, Depends(_get_image_sample_pack_service)]


class ImageSamplePackItem(BaseModel):
    id: str
    category: str
    name: str
    source_type: str
    source_value: str
    is_active: bool
    sort_order: int
    version_label: str | None = None
    notes: str | None = None
    asset_count: int = 0
    storage_path: str | None = None


def _pack_to_item(pack: object) -> ImageSamplePackItem:
    return ImageSamplePackItem(
        id=pack.id,
        category=pack.category,
        name=pack.name,
        source_type=pack.source_type,
        source_value=pack.source_value,
        is_active=pack.is_active,
        sort_order=pack.sort_order,
        version_label=pack.version_label,
        notes=pack.notes,
        asset_count=getattr(pack, "asset_count", 0) or 0,
        storage_path=getattr(pack, "storage_path", None),
    )


class ImageSamplePackListResponse(BaseModel):
    items: list[ImageSamplePackItem]


class ImageSamplePackCreateRequest(BaseModel):
    category: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    source_type: str = Field(default="vps_upload", min_length=1)
    source_value: str = Field(default="")
    is_active: bool = True
    sort_order: int = 0
    version_label: str | None = None
    notes: str | None = None


class ImageSamplePackUpdateRequest(BaseModel):
    category: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None, min_length=1)
    source_value: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    sort_order: int | None = None
    version_label: str | None = None
    notes: str | None = None


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
    _ctx: AdminDep,
    repo: RepoDep,
) -> ImageSamplePackListResponse:
    try:
        packs = await repo.list_all()
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    return ImageSamplePackListResponse(items=[_pack_to_item(pack) for pack in packs])


@router.post("", response_model=ImageSamplePackItem)
async def create_image_sample_pack(
    _ctx: AdminDep,
    repo: RepoDep,
    request: ImageSamplePackCreateRequest,
) -> ImageSamplePackItem:
    try:
        created = await repo.create(
            category=request.category,
            name=request.name,
            source_type=request.source_type or "vps_upload",
            source_value=request.source_value or "",
            is_active=request.is_active,
            sort_order=request.sort_order,
            version_label=request.version_label,
            notes=request.notes,
        )
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    if not created:
        raise HTTPException(status_code=500, detail="Unable to create sample pack.")
    return _pack_to_item(created)


@router.post("/upload", response_model=ImageSamplePackItem)
async def upload_image_sample_pack(
    _ctx: AdminDep,
    service: ServiceDep,
    file: UploadFile = File(...),
    category: str = Form(...),
    name: str = Form(...),
    is_active: bool = Form(default=True),
    sort_order: int = Form(default=0),
    version_label: str | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> ImageSamplePackItem:
    content = await file.read()
    try:
        created = await service.upload_pack_zip(
            category=category,
            name=name,
            file_content=content,
            is_active=is_active,
            sort_order=sort_order,
            version_label=version_label,
            notes=notes,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    return _pack_to_item(created)


@router.post("/{pack_id}/upload", response_model=ImageSamplePackItem)
async def reupload_image_sample_pack(
    _ctx: AdminDep,
    service: ServiceDep,
    pack_id: str,
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    name: str | None = Form(default=None),
    is_active: bool | None = Form(default=None),
    sort_order: int | None = Form(default=None),
    version_label: str | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> ImageSamplePackItem:
    content = await file.read()
    try:
        updated = await service.upload_pack_zip(
            pack_id=pack_id,
            category=category or "background",
            name=name or "Sample Pack",
            file_content=content,
            is_active=True if is_active is None else is_active,
            sort_order=0 if sort_order is None else sort_order,
            version_label=version_label,
            notes=notes,
        )
    except ValidationError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    return _pack_to_item(updated)


@router.patch("/{pack_id}", response_model=ImageSamplePackItem)
async def update_image_sample_pack(
    _ctx: AdminDep,
    repo: RepoDep,
    pack_id: str,
    request: ImageSamplePackUpdateRequest,
) -> ImageSamplePackItem:
    try:
        updated = await repo.update(
            pack_id,
            category=request.category,
            name=request.name,
            source_type=request.source_type,
            source_value=request.source_value,
            is_active=request.is_active,
            sort_order=request.sort_order,
            version_label=request.version_label,
            notes=request.notes,
        )
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    if not updated:
        raise HTTPException(status_code=404, detail="Sample pack not found.")
    return _pack_to_item(updated)


@router.delete("/{pack_id}")
async def delete_image_sample_pack(
    _ctx: AdminDep,
    repo: RepoDep,
    pack_id: str,
) -> dict[str, bool]:
    try:
        deleted = await repo.delete(pack_id)
    except Exception as exc:
        _handle_image_sample_pack_storage_error(exc)
        raise
    if not deleted:
        raise HTTPException(status_code=404, detail="Sample pack not found.")
    return {"ok": True}
