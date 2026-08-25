"""Marketplace router for template upload, catalog, and management.

Admin endpoints (require admin role):
  POST   /marketplace/upload              — Upload new template bundle
  GET    /marketplace/admin/items         — Paginated admin list
  PATCH  /marketplace/items/{id}          — Update metadata
  POST   /marketplace/items/{id}/enable   — Enable item
  POST   /marketplace/items/{id}/disable  — Disable item
  DELETE /marketplace/items/{id}          — Delete item + files

Public endpoints (require authenticated user):
  GET    /marketplace/catalog             — Browse enabled items (paginated, filterable)
  GET    /marketplace/items/{id}/preview  — Serve preview PNG
  GET    /marketplace/items/{id}/download — Download zip bundle

Requirements: 1.1–1.9, 2.1–2.7, 3.1–3.8, 4.1–4.5
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from platform_api.http_paths import API_V3_PREFIX
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services.marketplace_service import (
    MarketplaceItemUpdate,
    MarketplaceService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


# ---------------------------------------------------------------------------
# Dependency placeholder (wired at startup via wire_dependencies.py)
# ---------------------------------------------------------------------------


async def _get_marketplace_service() -> MarketplaceService:
    raise NotImplementedError(
        "MarketplaceService dependency not configured. Wire via app.dependency_overrides."
    )


# ---------------------------------------------------------------------------
# Type aliases for dependency injection
# ---------------------------------------------------------------------------

AdminDep = Annotated[AuthContext, Depends(require_admin)]
UserDep = Annotated[AuthContext, Depends(get_current_user)]
ServiceDep = Annotated[MarketplaceService, Depends(_get_marketplace_service)]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MarketplaceItemResponse(BaseModel):
    """Response model for a single marketplace item."""

    id: str
    name: str
    description: str
    version: str
    author: str
    kind: str
    tags: list[str]
    status: str
    price: float
    preview_url: str
    created_at: str


class MarketplaceItemListResponse(BaseModel):
    """Paginated list response for marketplace items."""

    items: list[MarketplaceItemResponse]
    total: int
    page: int
    page_size: int


class MarketplaceItemUpdateRequest(BaseModel):
    """Request body for updating marketplace item metadata."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1, max_length=2000)
    tags: list[str] | None = Field(None, max_length=20)
    price: float | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item_to_response(item, request_path: str = "") -> MarketplaceItemResponse:
    """Convert a MarketplaceItemRecord to a response model."""
    return MarketplaceItemResponse(
        id=str(item.id),
        name=item.name,
        description=item.description,
        version=item.version,
        author=item.author,
        kind=item.kind,
        tags=item.tags,
        status=item.status,
        price=item.price,
        preview_url=f"{API_V3_PREFIX}/marketplace/items/{item.id}/preview",
        created_at=item.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Admin endpoints (Task 5.1)
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=201)
async def upload_template(
    _ctx: AdminDep,
    service: ServiceDep,
    file: UploadFile = File(...),
) -> MarketplaceItemResponse:
    """Upload a new template bundle zip file.

    Validates the zip contents (template.json, preview.png, manifest.json),
    extracts metadata from the manifest, stores files on disk, and creates
    a marketplace item record.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9
    """
    content = await file.read()
    filename = file.filename or "upload.zip"

    item = await service.upload_template(content, filename)
    return _item_to_response(item)


@router.get("/admin/items")
async def list_admin_items(
    _ctx: AdminDep,
    service: ServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> MarketplaceItemListResponse:
    """List all marketplace items for admin management (all statuses).

    Requirements: 2.1
    """
    result = await service.list_items(page=page, page_size=page_size)
    return MarketplaceItemListResponse(
        items=[_item_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.patch("/items/{item_id}")
async def update_item(
    item_id: UUID,
    body: MarketplaceItemUpdateRequest,
    _ctx: AdminDep,
    service: ServiceDep,
) -> MarketplaceItemResponse:
    """Update marketplace item metadata (name, description, tags).

    Requirements: 2.5, 2.6, 2.7
    """
    update = MarketplaceItemUpdate(
        name=body.name,
        description=body.description,
        tags=body.tags,
        price=body.price,
    )
    item = await service.update_item(item_id, update)
    return _item_to_response(item)


@router.post("/items/{item_id}/enable")
async def enable_item(
    item_id: UUID,
    _ctx: AdminDep,
    service: ServiceDep,
) -> MarketplaceItemResponse:
    """Enable a marketplace item (makes it visible in the public catalog).

    Requirements: 2.3
    """
    item = await service.enable_item(item_id)
    return _item_to_response(item)


@router.post("/items/{item_id}/disable")
async def disable_item(
    item_id: UUID,
    _ctx: AdminDep,
    service: ServiceDep,
) -> MarketplaceItemResponse:
    """Disable a marketplace item (hides it from the public catalog).

    Requirements: 2.2
    """
    item = await service.disable_item(item_id)
    return _item_to_response(item)


@router.delete("/items/{item_id}", status_code=204, response_class=Response)
async def delete_item(
    item_id: UUID,
    _ctx: AdminDep,
    service: ServiceDep,
) -> Response:
    """Delete a marketplace item and its associated files.

    Requirements: 2.4, 2.6
    """
    await service.delete_item(item_id)
    return Response(status_code=204)


@router.post("/items/{item_id}/preview")
async def upload_preview(
    item_id: UUID,
    _ctx: AdminDep,
    service: ServiceDep,
    file: UploadFile = File(...),
) -> MarketplaceItemResponse:
    """Upload or replace the preview image for a marketplace item.

    Accepts a PNG image file and stores it as the item's preview.
    """
    content = await file.read()
    item = await service.update_preview(item_id, content)
    return _item_to_response(item)


# ---------------------------------------------------------------------------
# Public endpoints (Task 5.2)
# ---------------------------------------------------------------------------


@router.get("/catalog")
async def get_catalog(
    _ctx: UserDep,
    service: ServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    kind: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
) -> MarketplaceItemListResponse:
    """Browse the public marketplace catalog of enabled items.

    Supports pagination, filtering by kind (video/reel), and
    case-insensitive search across name, description, and tags.

    Returns 401 if unauthenticated.

    Requirements: 3.1, 3.2, 3.3, 3.5, 3.6, 3.7
    """
    result = await service.get_catalog(
        page=page,
        page_size=page_size,
        kind=kind,
        search=search,
    )
    return MarketplaceItemListResponse(
        items=[_item_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/items/{item_id}/preview")
async def get_preview(
    item_id: UUID,
    service: ServiceDep,
) -> FileResponse:
    """Serve the preview PNG image for a marketplace item.

    Public endpoint — no auth required since previews are not sensitive.
    Returns the PNG file with content-type image/png.
    Returns 404 if item or file not found.
    """
    preview_path = await service.get_preview_path(item_id)
    return FileResponse(
        path=preview_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/items/{item_id}/download")
async def download_item(
    item_id: UUID,
    _ctx: UserDep,
    service: ServiceDep,
) -> FileResponse:
    """Download the template bundle zip for a marketplace item.

    Returns the zip file with content-type application/zip and
    content-disposition attachment header.

    Returns 401 if unauthenticated, 403 if item is disabled,
    404 if item not found, 500 if file missing on disk.

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """
    zip_path = await service.get_download_path(item_id)
    filename = Path(zip_path).name
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
