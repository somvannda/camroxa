from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import require_admin

router = APIRouter(tags=["blog-posts"])

_SLUGIFY_PATTERN = re.compile(r"[^a-z0-9]+")


class AdminBlogPostResponse(BaseModel):
    id: str
    slug: str
    title: str
    excerpt: str
    content: str
    cover_image_url: str | None = None
    category: str | None = None
    author_name: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    is_published: bool
    published_at: str | None = None
    created_at: str
    updated_at: str


class PublicBlogPostSummaryResponse(BaseModel):
    slug: str
    title: str
    excerpt: str
    cover_image_url: str | None = None
    category: str | None = None
    author_name: str | None = None
    published_at: str
    updated_at: str


class PublicBlogPostDetailResponse(PublicBlogPostSummaryResponse):
    content: str
    seo_title: str | None = None
    seo_description: str | None = None


class BlogPostUpsertRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=180)
    excerpt: str = Field(..., min_length=1, max_length=5000)
    content: str = Field(..., min_length=1)
    cover_image_url: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)
    author_name: str | None = Field(default=None, max_length=120)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=300)
    is_published: bool = False
    published_at: str | None = Field(default=None, max_length=64)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _slugify(value: str) -> str:
    normalized = _SLUGIFY_PATTERN.sub("-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized[:180]


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    candidate = normalized.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _serialize_admin_post(row: Any) -> AdminBlogPostResponse:
    return AdminBlogPostResponse(
        id=str(row["id"]),
        slug=str(row["slug"]),
        title=str(row["title"]),
        excerpt=str(row["excerpt"]),
        content=str(row["content"]),
        cover_image_url=row.get("cover_image_url"),
        category=row.get("category"),
        author_name=row.get("author_name"),
        seo_title=row.get("seo_title"),
        seo_description=row.get("seo_description"),
        is_published=bool(row["is_published"]),
        published_at=_to_iso(row.get("published_at")),
        created_at=_to_iso(row.get("created_at")) or "",
        updated_at=_to_iso(row.get("updated_at")) or "",
    )


def _serialize_public_post(row: Any) -> PublicBlogPostDetailResponse:
    published_at = row.get("published_at") or row.get("updated_at") or row.get("created_at")
    return PublicBlogPostDetailResponse(
        slug=str(row["slug"]),
        title=str(row["title"]),
        excerpt=str(row["excerpt"]),
        content=str(row["content"]),
        cover_image_url=row.get("cover_image_url"),
        category=row.get("category"),
        author_name=row.get("author_name"),
        published_at=_to_iso(published_at) or "",
        updated_at=_to_iso(row.get("updated_at")) or "",
        seo_title=row.get("seo_title"),
        seo_description=row.get("seo_description"),
    )


async def _ensure_unique_slug(pool: Any, slug: str, exclude_post_id: UUID | None = None) -> None:
    existing_id = await pool.fetchval(
        """
        SELECT id
        FROM blog_posts
        WHERE slug = $1
          AND ($2::uuid IS NULL OR id <> $2::uuid)
        """,
        slug,
        exclude_post_id,
    )
    if existing_id is not None:
        raise HTTPException(status_code=409, detail="A blog post with this slug already exists.")


async def _get_post_or_404(post_id: UUID) -> Any:
    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        SELECT
            id,
            slug,
            title,
            excerpt,
            content,
            cover_image_url,
            category,
            author_name,
            seo_title,
            seo_description,
            is_published,
            published_at,
            created_at,
            updated_at
        FROM blog_posts
        WHERE id = $1
        """,
        post_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return row


@router.get("/admin/blog-posts", response_model=list[AdminBlogPostResponse], status_code=200)
async def list_admin_blog_posts(_: Any = require_admin) -> list[AdminBlogPostResponse]:
    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT
            id,
            slug,
            title,
            excerpt,
            content,
            cover_image_url,
            category,
            author_name,
            seo_title,
            seo_description,
            is_published,
            published_at,
            created_at,
            updated_at
        FROM blog_posts
        ORDER BY COALESCE(published_at, created_at) DESC, updated_at DESC
        """
    )
    return [_serialize_admin_post(row) for row in rows]


@router.post("/admin/blog-posts", response_model=AdminBlogPostResponse, status_code=201)
async def create_blog_post(
    request: BlogPostUpsertRequest,
    _: Any = require_admin,
) -> AdminBlogPostResponse:
    pool = get_db_pool()
    slug = _slugify(request.slug or request.title)
    if not slug:
        raise HTTPException(status_code=422, detail="A valid slug or title is required.")
    await _ensure_unique_slug(pool, slug)

    published_at = _parse_optional_datetime(request.published_at)
    if request.is_published and published_at is None:
        published_at = datetime.now(timezone.utc)

    post_id = uuid4()
    row = await pool.fetchrow(
        """
        INSERT INTO blog_posts (
            id,
            slug,
            title,
            excerpt,
            content,
            cover_image_url,
            category,
            author_name,
            seo_title,
            seo_description,
            is_published,
            published_at,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW()
        )
        RETURNING
            id,
            slug,
            title,
            excerpt,
            content,
            cover_image_url,
            category,
            author_name,
            seo_title,
            seo_description,
            is_published,
            published_at,
            created_at,
            updated_at
        """,
        post_id,
        slug,
        request.title.strip(),
        request.excerpt.strip(),
        request.content.strip(),
        _normalize_optional_text(request.cover_image_url),
        _normalize_optional_text(request.category),
        _normalize_optional_text(request.author_name),
        _normalize_optional_text(request.seo_title),
        _normalize_optional_text(request.seo_description),
        request.is_published,
        published_at,
    )
    return _serialize_admin_post(row)


@router.get("/admin/blog-posts/{post_id}", response_model=AdminBlogPostResponse, status_code=200)
async def get_admin_blog_post(post_id: UUID, _: Any = require_admin) -> AdminBlogPostResponse:
    row = await _get_post_or_404(post_id)
    return _serialize_admin_post(row)


@router.put("/admin/blog-posts/{post_id}", response_model=AdminBlogPostResponse, status_code=200)
async def update_blog_post(
    post_id: UUID,
    request: BlogPostUpsertRequest,
    _: Any = require_admin,
) -> AdminBlogPostResponse:
    pool = get_db_pool()
    existing = await _get_post_or_404(post_id)
    slug = _slugify(request.slug or request.title)
    if not slug:
        raise HTTPException(status_code=422, detail="A valid slug or title is required.")
    await _ensure_unique_slug(pool, slug, exclude_post_id=post_id)

    published_at = _parse_optional_datetime(request.published_at)
    if request.is_published and published_at is None:
        existing_published_at = existing.get("published_at")
        published_at = (
            existing_published_at
            if isinstance(existing_published_at, datetime)
            else datetime.now(timezone.utc)
        )

    row = await pool.fetchrow(
        """
        UPDATE blog_posts
        SET
            slug = $2,
            title = $3,
            excerpt = $4,
            content = $5,
            cover_image_url = $6,
            category = $7,
            author_name = $8,
            seo_title = $9,
            seo_description = $10,
            is_published = $11,
            published_at = $12,
            updated_at = NOW()
        WHERE id = $1
        RETURNING
            id,
            slug,
            title,
            excerpt,
            content,
            cover_image_url,
            category,
            author_name,
            seo_title,
            seo_description,
            is_published,
            published_at,
            created_at,
            updated_at
        """,
        post_id,
        slug,
        request.title.strip(),
        request.excerpt.strip(),
        request.content.strip(),
        _normalize_optional_text(request.cover_image_url),
        _normalize_optional_text(request.category),
        _normalize_optional_text(request.author_name),
        _normalize_optional_text(request.seo_title),
        _normalize_optional_text(request.seo_description),
        request.is_published,
        published_at,
    )
    return _serialize_admin_post(row)


@router.delete("/admin/blog-posts/{post_id}", status_code=204, response_class=Response)
async def delete_blog_post(post_id: UUID, _: Any = require_admin) -> Response:
    pool = get_db_pool()
    result = await pool.execute("DELETE FROM blog_posts WHERE id = $1", post_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return Response(status_code=204)


@router.get("/blog-posts/public", response_model=list[PublicBlogPostSummaryResponse], status_code=200)
async def list_public_blog_posts(
    category: str | None = Query(default=None, max_length=120),
) -> list[PublicBlogPostSummaryResponse]:
    pool = get_db_pool()
    normalized_category = _normalize_optional_text(category)
    if normalized_category:
        rows = await pool.fetch(
            """
            SELECT
                slug,
                title,
                excerpt,
                cover_image_url,
                category,
                author_name,
                COALESCE(published_at, updated_at, created_at) AS published_at,
                updated_at
            FROM blog_posts
            WHERE is_published = TRUE
              AND COALESCE(published_at, created_at) <= NOW()
              AND LOWER(TRIM(category)) = LOWER(TRIM($1))
            ORDER BY COALESCE(published_at, created_at) DESC, updated_at DESC
            """,
            normalized_category,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT
                slug,
                title,
                excerpt,
                cover_image_url,
                category,
                author_name,
                COALESCE(published_at, updated_at, created_at) AS published_at,
                updated_at
            FROM blog_posts
            WHERE is_published = TRUE
              AND COALESCE(published_at, created_at) <= NOW()
            ORDER BY COALESCE(published_at, created_at) DESC, updated_at DESC
            """
        )
    return [
        PublicBlogPostSummaryResponse(
            slug=str(row["slug"]),
            title=str(row["title"]),
            excerpt=str(row["excerpt"]),
            cover_image_url=row.get("cover_image_url"),
            category=row.get("category"),
            author_name=row.get("author_name"),
            published_at=_to_iso(row.get("published_at")) or "",
            updated_at=_to_iso(row.get("updated_at")) or "",
        )
        for row in rows
    ]


@router.get("/blog-posts/public/{slug}", response_model=PublicBlogPostDetailResponse, status_code=200)
async def get_public_blog_post(slug: str) -> PublicBlogPostDetailResponse:
    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        SELECT
            slug,
            title,
            excerpt,
            content,
            cover_image_url,
            category,
            author_name,
            seo_title,
            seo_description,
            COALESCE(published_at, updated_at, created_at) AS published_at,
            updated_at
        FROM blog_posts
        WHERE slug = $1
          AND is_published = TRUE
          AND COALESCE(published_at, created_at) <= NOW()
        """,
        slug.strip().lower(),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return _serialize_public_post(row)
