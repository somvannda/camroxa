"""Profile-scoped video template storage endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user

router = APIRouter(prefix="/profiles", tags=["video-templates"])


class VideoTemplateSummaryResponse(BaseModel):
    id: str
    profile_id: str | None = None
    kind: str
    name: str
    updated_at: datetime
    source: str | None = None


class VideoTemplateDetailResponse(VideoTemplateSummaryResponse):
    template_json: dict[str, Any] = Field(default_factory=dict)


class UpsertProfileVideoTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(default="long", pattern="^(long|reel)$")
    template_json: dict[str, Any] = Field(default_factory=dict)
    source: str | None = Field(default="user", max_length=32)
    set_as_profile_default: bool = True


async def _assert_profile_owner(pool, profile_id: UUID, user_id: UUID) -> dict[str, Any]:
    row = await pool.fetchrow(
        """
        SELECT id, user_id, video_template_id, reel_template_id
        FROM channel_profiles
        WHERE id = $1 AND user_id = $2
        """,
        profile_id,
        user_id,
    )
    if row is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError("Profile not found.")
    return dict(row)


def _normalize_template_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


@router.put(
    "/{profile_id}/video-templates/{template_id}",
    response_model=VideoTemplateDetailResponse,
    summary="Upsert a profile video template body",
)
async def upsert_profile_video_template(
    profile_id: UUID,
    template_id: str,
    request: UpsertProfileVideoTemplateRequest,
    ctx: Annotated[AuthContext, Depends(get_current_user)],
    pool=Depends(get_db_pool),
) -> VideoTemplateDetailResponse:
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        from platform_api.exceptions import ValidationError

        raise ValidationError("Template id is required.")

    profile = await _assert_profile_owner(pool, profile_id, UUID(ctx.user_id))
    now = datetime.now(timezone.utc)
    template_json = _normalize_template_json(request.template_json)

    row = await pool.fetchrow(
        """
        INSERT INTO profile_video_templates (
            id, user_id, profile_id, kind, name, template_json, source, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $8)
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            profile_id = EXCLUDED.profile_id,
            kind = EXCLUDED.kind,
            name = EXCLUDED.name,
            template_json = EXCLUDED.template_json,
            source = EXCLUDED.source,
            updated_at = EXCLUDED.updated_at
        RETURNING id, profile_id, kind, name, template_json, source, updated_at
        """,
        normalized_id,
        UUID(ctx.user_id),
        profile_id,
        request.kind,
        request.name.strip(),
        json.dumps(template_json),
        request.source,
        now,
    )

    if request.set_as_profile_default:
        if request.kind == "reel":
            await pool.execute(
                "UPDATE channel_profiles SET reel_template_id = $1, updated_at = $2 WHERE id = $3",
                normalized_id,
                now,
                profile_id,
            )
        else:
            await pool.execute(
                "UPDATE channel_profiles SET video_template_id = $1, updated_at = $2 WHERE id = $3",
                normalized_id,
                now,
                profile_id,
            )

    return VideoTemplateDetailResponse(
        id=str(row["id"]),
        profile_id=str(row["profile_id"]) if row.get("profile_id") else str(profile_id),
        kind=str(row["kind"]),
        name=str(row["name"]),
        updated_at=row["updated_at"],
        source=str(row.get("source") or "") or None,
        template_json=_normalize_template_json(row.get("template_json")),
    )


@router.get(
    "/{profile_id}/video-templates",
    response_model=list[VideoTemplateSummaryResponse],
    summary="List video templates linked to a profile",
)
async def list_profile_video_templates(
    profile_id: UUID,
    ctx: Annotated[AuthContext, Depends(get_current_user)],
    pool=Depends(get_db_pool),
) -> list[VideoTemplateSummaryResponse]:
    await _assert_profile_owner(pool, profile_id, UUID(ctx.user_id))
    rows = await pool.fetch(
        """
        SELECT id, profile_id, kind, name, source, updated_at
        FROM profile_video_templates
        WHERE user_id = $1 AND profile_id = $2
        ORDER BY updated_at DESC
        """,
        UUID(ctx.user_id),
        profile_id,
    )
    return [
        VideoTemplateSummaryResponse(
            id=str(row["id"]),
            profile_id=str(row["profile_id"]) if row.get("profile_id") else None,
            kind=str(row["kind"]),
            name=str(row["name"]),
            updated_at=row["updated_at"],
            source=str(row.get("source") or "") or None,
        )
        for row in rows
    ]


@router.get(
    "/{profile_id}/video-templates/{template_id}",
    response_model=VideoTemplateDetailResponse,
    summary="Fetch a profile video template body",
)
async def get_profile_video_template(
    profile_id: UUID,
    template_id: str,
    ctx: Annotated[AuthContext, Depends(get_current_user)],
    pool=Depends(get_db_pool),
) -> VideoTemplateDetailResponse:
    await _assert_profile_owner(pool, profile_id, UUID(ctx.user_id))
    row = await pool.fetchrow(
        """
        SELECT id, profile_id, kind, name, template_json, source, updated_at
        FROM profile_video_templates
        WHERE user_id = $1 AND profile_id = $2 AND id = $3
        """,
        UUID(ctx.user_id),
        profile_id,
        str(template_id or "").strip(),
    )
    if row is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError("Video template not found.")
    return VideoTemplateDetailResponse(
        id=str(row["id"]),
        profile_id=str(row["profile_id"]) if row.get("profile_id") else None,
        kind=str(row["kind"]),
        name=str(row["name"]),
        updated_at=row["updated_at"],
        source=str(row.get("source") or "") or None,
        template_json=_normalize_template_json(row.get("template_json")),
    )
