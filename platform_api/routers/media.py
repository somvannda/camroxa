from __future__ import annotations

import json
import mimetypes
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.utils.upload_paths import resolve_upload_path

router = APIRouter(prefix="/media", tags=["media"])


async def _get_profile_media_row(*, profile_id: UUID) -> dict:
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, logo_path, image_config
        FROM channel_profiles
        WHERE id = $1
        """,
        profile_id,
    )
    if not row:
        raise NotFoundError("Profile not found.")
    return dict(row)


def _is_admin(ctx: AuthContext) -> bool:
    return str(getattr(ctx, "role", "") or "").strip().lower() == "admin"


def _parse_json_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


@router.get("/channel-profiles/{profile_id}/logo")
async def get_channel_profile_logo(
    profile_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
) -> FileResponse:
    row = await _get_profile_media_row(profile_id=profile_id)
    if not _is_admin(ctx) and str(row.get("user_id")) != str(ctx.user_id):
        raise NotFoundError("Profile not found.")
    path = resolve_upload_path(row.get("logo_path"))
    if path is None or not path.exists() or not path.is_file():
        raise NotFoundError("Logo not found.")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@router.get("/channel-profiles/{profile_id}/covers/{index}")
async def get_channel_profile_cover(
    profile_id: UUID,
    index: int,
    ctx: AuthContext = Depends(get_current_user),
) -> FileResponse:
    try:
        idx = int(index)
    except Exception:
        raise ValidationError("Invalid cover index.")
    if idx < 0 or idx > 20:
        raise ValidationError("Invalid cover index.")

    row = await _get_profile_media_row(profile_id=profile_id)
    if not _is_admin(ctx) and str(row.get("user_id")) != str(ctx.user_id):
        raise NotFoundError("Profile not found.")

    image_cfg = _parse_json_dict(row.get("image_config"))
    cover_paths = image_cfg.get("cover_paths") if isinstance(image_cfg, dict) else None
    cover_list = cover_paths if isinstance(cover_paths, list) else []
    if idx >= len(cover_list):
        raise NotFoundError("Cover not found.")

    path = resolve_upload_path(cover_list[idx])
    if path is None or not path.exists() or not path.is_file():
        raise NotFoundError("Cover not found.")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@router.get("/users/{user_id}/avatar")
async def get_user_avatar(user_id: UUID) -> FileResponse:
    """Public profile photo for music web artist cards and headers."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    row = await pool.fetchrow("SELECT avatar_url FROM users WHERE id = $1", user_id)
    if not row:
        raise NotFoundError("Avatar not found.")
    path = resolve_upload_path(row.get("avatar_url"))
    if path is None or not path.exists() or not path.is_file():
        raise NotFoundError("Avatar not found.")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media_type or "application/octet-stream")
