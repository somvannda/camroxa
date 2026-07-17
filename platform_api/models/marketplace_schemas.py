"""Pydantic schemas for the Template Marketplace feature.

Defines request/response models for marketplace router endpoints.

Requirements: 1.2, 1.4, 1.5, 2.5, 2.7, 3.1, 3.7
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ManifestSchema(BaseModel):
    """Schema for manifest.json inside a template bundle zip."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    version: str = Field(min_length=1, max_length=50)
    author: str = Field(min_length=1, max_length=200)
    kind: Literal["video", "reel"]
    tags: list[str] = Field(default_factory=list, max_length=20)


class MarketplaceItemResponse(BaseModel):
    """Response model for a single marketplace item."""

    id: UUID
    name: str
    description: str
    version: str
    author: str
    kind: str
    tags: list[str]
    status: str
    preview_url: str
    created_at: datetime


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


class CatalogQueryParams(BaseModel):
    """Query parameters for catalog browsing."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    kind: Literal["video", "reel"] | None = None
    search: str | None = Field(None, min_length=1, max_length=100)
