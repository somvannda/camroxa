"""Admin-only Camxora Music generation browser for user detail."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])
AdminUserDep = Annotated[AuthContext, Depends(require_admin)]

WEB_MUSIC_SOURCE = "web_music"
_LRC_LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$")


class AdminWebMusicWorkspaceResponse(BaseModel):
    id: str
    name: str
    is_default: bool = False
    created_at: str | None = None


class AdminWebMusicWorkspaceListResponse(BaseModel):
    items: list[AdminWebMusicWorkspaceResponse] = Field(default_factory=list)


class AdminWebMusicClipResponse(BaseModel):
    variant: str
    label: str
    title: str | None = None
    audio_url: str = ""
    download_url: str = ""
    ready: bool = False
    image_url: str | None = None
    duration_seconds: float | None = None


class AdminWebMusicGenerationResponse(BaseModel):
    id: str
    title: str
    lyrics: str = ""
    style: str = ""
    model: str = "V5"
    instrumental: bool = False
    status: str = "PENDING"
    error_message: str | None = None
    created_at: str | None = None
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = None
    weirdness_constraint: float | None = None
    audio_weight: float | None = None
    clips: list[AdminWebMusicClipResponse] = Field(default_factory=list)


class AdminWebMusicGenerationListResponse(BaseModel):
    items: list[AdminWebMusicGenerationResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 40
    offset: int = 0


def _is_missing_schema(exc: Exception) -> bool:
    message = str(exc).lower()
    return "does not exist" in message or "undefined" in message


async def _fetch_rows(pool, query: str, *args) -> list[Any]:
    try:
        return await pool.fetch(query, *args)
    except Exception as exc:
        if _is_missing_schema(exc):
            return []
        raise


async def _fetch_row(pool, query: str, *args) -> Any | None:
    try:
        return await pool.fetchrow(query, *args)
    except Exception as exc:
        if _is_missing_schema(exc):
            return None
        raise


async def _fetch_val(pool, query: str, *args) -> Any:
    try:
        return await pool.fetchval(query, *args)
    except Exception as exc:
        if _is_missing_schema(exc):
            return None
        raise


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _content_disposition(filename: str, *, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    ascii_name = filename.encode("ascii", "ignore").decode() or "download"
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _lrc_to_srt(lrc: str) -> str:
    entries: list[tuple[float, str]] = []
    for raw in str(lrc or "").splitlines():
        match = _LRC_LINE.match(raw.strip())
        if not match:
            continue
        minutes, seconds, millis, text = match.groups()
        cleaned = str(text or "").strip()
        if not cleaned:
            continue
        total = int(minutes) * 60 + int(seconds)
        if millis:
            if len(millis) == 1:
                total += int(millis) / 10.0
            elif len(millis) == 2:
                total += int(millis) / 100.0
            else:
                total += int(millis[:3]) / 1000.0
        entries.append((max(0.0, float(total)), cleaned))
    if not entries:
        return ""
    chunks: list[str] = []
    for index, (start, text) in enumerate(entries):
        end = entries[index + 1][0] if index + 1 < len(entries) else start + 3.0
        if end <= start:
            end = start + 1.5
        start_ms = max(0, int(round(start * 1000)))
        end_ms = max(start_ms + 200, int(round(end * 1000)))

        def _clock(total_ms: int) -> str:
            hours, rem = divmod(total_ms, 3_600_000)
            minutes, rem = divmod(rem, 60_000)
            secs, millis = divmod(rem, 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        chunks.append(f"{index + 1}\n{_clock(start_ms)} --> {_clock(end_ms)}\n{text}\n")
    return "\n".join(chunks)


async def _require_user(pool, user_id: UUID) -> None:
    row = await _fetch_row(pool, "SELECT 1 FROM users WHERE id = $1", user_id)
    if row is None:
        raise NotFoundError("User not found.", details={"user_id": str(user_id)})


def _clip_payload(
    *,
    user_id: UUID,
    task_id: str,
    title: str,
    variant: str,
    ready: bool,
    image_url: str | None,
    duration_seconds: float | None,
) -> dict[str, Any]:
    audio_url = (
        f"/api/v1/users/{user_id}/web-music/generations/{task_id}/audio?variant={variant}"
        if ready
        else ""
    )
    download_url = (
        f"/api/v1/users/{user_id}/web-music/generations/{task_id}/download?variant={variant}"
        if ready
        else ""
    )
    return {
        "variant": variant,
        "label": title,
        "title": title,
        "audio_url": audio_url,
        "download_url": download_url,
        "ready": ready,
        "image_url": image_url,
        "duration_seconds": duration_seconds,
    }


def _generation_payload(row: Any, user_id: UUID) -> dict[str, Any]:
    task_id = str(row["id"])
    title = str(_row_get(row, "title") or "Untitled")
    ok_ready = bool(
        _row_get(row, "audio_url_ok")
        or _row_get(row, "b2_storage_key_ok")
        or _row_get(row, "encrypted_original_key_ok")
        or str(_row_get(row, "package_status_ok") or "") == "ready"
    )
    alt_ready = bool(
        _row_get(row, "audio_url_alt")
        or _row_get(row, "b2_storage_key_alt")
        or _row_get(row, "encrypted_original_key_alt")
        or str(_row_get(row, "package_status_alt") or "") == "ready"
    )
    image_ok = str(_row_get(row, "image_url_ok") or "").strip() or None
    image_alt = str(_row_get(row, "image_url_alt") or "").strip() or None
    return {
        "id": task_id,
        "title": title,
        "lyrics": str(_row_get(row, "lyrics") or ""),
        "style": str(_row_get(row, "style") or ""),
        "model": str(_row_get(row, "model") or "V5"),
        "instrumental": bool(_row_get(row, "instrumental") or False),
        "status": str(_row_get(row, "status") or "pending").upper(),
        "error_message": _row_get(row, "error_message"),
        "created_at": _iso(_row_get(row, "created_at")),
        "negative_tags": str(_row_get(row, "negative_tags") or "").strip() or None,
        "vocal_gender": str(_row_get(row, "vocal_gender") or "").strip() or None,
        "style_weight": _float_or_none(_row_get(row, "style_weight")),
        "weirdness_constraint": _float_or_none(_row_get(row, "weirdness_constraint")),
        "audio_weight": _float_or_none(_row_get(row, "audio_weight")),
        "clips": [
            _clip_payload(
                user_id=user_id,
                task_id=task_id,
                title=title,
                variant="ok",
                ready=ok_ready,
                image_url=image_ok,
                duration_seconds=_float_or_none(_row_get(row, "duration_ok")),
            ),
            _clip_payload(
                user_id=user_id,
                task_id=task_id,
                title=title,
                variant="alt",
                ready=alt_ready,
                image_url=image_alt,
                duration_seconds=_float_or_none(_row_get(row, "duration_alt")),
            ),
        ],
    }


_GENERATION_SELECTS: tuple[str, ...] = (
    """
    SELECT id, title, lyrics, style, model, instrumental, status,
           audio_url_ok, audio_url_alt, error_message, created_at,
           negative_tags, vocal_gender, style_weight, weirdness_constraint, audio_weight,
           b2_storage_key_ok, b2_storage_key_alt, workspace_id,
           image_url_ok, image_url_alt, duration_ok, duration_alt,
           encrypted_original_key_ok, encrypted_original_key_alt,
           package_status_ok, package_status_alt,
           content_key_id_ok, content_key_id_alt
    FROM suno_tasks
    """,
    """
    SELECT id, title, lyrics, style, model, instrumental, status,
           audio_url_ok, audio_url_alt, error_message, created_at,
           negative_tags, vocal_gender, style_weight, weirdness_constraint, audio_weight,
           b2_storage_key_ok, b2_storage_key_alt,
           image_url_ok, image_url_alt
    FROM suno_tasks
    """,
    """
    SELECT id, title, lyrics, style, model, instrumental, status,
           audio_url_ok, audio_url_alt, error_message, created_at
    FROM suno_tasks
    """,
)


async def _list_generation_rows(
    pool,
    user_id: UUID,
    *,
    workspace_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Any], int]:
    filters: list[tuple[str, tuple[Any, ...]]] = [
        ("WHERE user_id = $1 AND source = $2 AND workspace_id = $3", (user_id, WEB_MUSIC_SOURCE, workspace_id))
        if workspace_id is not None
        else ("WHERE user_id = $1 AND source = $2", (user_id, WEB_MUSIC_SOURCE)),
        ("WHERE user_id = $1 AND source = $2", (user_id, WEB_MUSIC_SOURCE)),
        ("WHERE user_id = $1", (user_id,)),
    ]
    if workspace_id is None:
        filters = filters[1:]

    last_missing: Exception | None = None
    for select_sql in _GENERATION_SELECTS:
        for where_sql, where_args in filters:
            limit_index = len(where_args) + 1
            offset_index = len(where_args) + 2
            list_sql = (
                f"{select_sql} {where_sql} ORDER BY created_at DESC "
                f"LIMIT ${limit_index} OFFSET ${offset_index}"
            )
            try:
                rows = await pool.fetch(list_sql, *where_args, limit, offset)
            except Exception as exc:
                if _is_missing_schema(exc):
                    last_missing = exc
                    continue
                raise
            count_sql = f"SELECT COUNT(*)::int FROM suno_tasks {where_sql}"
            counted = await _fetch_val(pool, count_sql, *where_args)
            total = int(counted) if counted is not None else len(rows) + offset
            return rows, total
    if last_missing:
        logger.info("Admin web-music generations query fell back to empty: %s", last_missing)
    return [], 0


async def _load_clip_audio(pool, user_id: UUID, task_id: UUID, variant: str) -> tuple[bytes, str, str]:
    variant_key = str(variant or "ok").strip().lower()
    if variant_key not in {"ok", "alt"}:
        raise ValidationError("variant must be ok or alt.", details={"field": "variant"})

    row = await _fetch_row(
        pool,
        """
        SELECT id, title, status, audio_url_ok, audio_url_alt,
               b2_storage_key_ok, b2_storage_key_alt, source,
               encrypted_original_key_ok, encrypted_original_key_alt,
               content_key_id_ok, content_key_id_alt,
               package_status_ok, package_status_alt
        FROM suno_tasks
        WHERE id = $1 AND user_id = $2
        """,
        task_id,
        user_id,
    )
    if row is None:
        row = await _fetch_row(
            pool,
            """
            SELECT id, title, status, audio_url_ok, audio_url_alt
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2
            """,
            task_id,
            user_id,
        )
    if row is None:
        raise NotFoundError("Generation not found.")

    source = str(_row_get(row, "source") or "").strip()
    if source and source != WEB_MUSIC_SOURCE:
        raise NotFoundError("Generation not found.")

    status = str(_row_get(row, "status") or "").upper()
    if status not in {"SUCCESS", "COMPLETED", "READY"}:
        # Production stores SUCCESS; allow play when audio bytes exist anyway.
        ready = bool(
            _row_get(row, f"audio_url_{variant_key}")
            or _row_get(row, f"b2_storage_key_{variant_key}")
        )
        if not ready:
            raise ValidationError("This song is not ready to play yet.", details={"status": status})

    title = str(_row_get(row, "title") or "camxora-track").strip() or "camxora-track"
    filename = f"{title}-{variant_key}.mp3"
    enc_key = _row_get(row, f"encrypted_original_key_{variant_key}")
    key_id = _row_get(row, f"content_key_id_{variant_key}")
    if enc_key and key_id:
        try:
            from platform_api.services.audio_package_service import AudioPackageService
            from platform_api.services.storage_service import StorageService
            from platform_api.services.streaming_config_service import resolve_streaming_storage_config

            config = await resolve_streaming_storage_config(pool)
            if config.configured:
                wrapped = await pool.fetchval(
                    "SELECT wrapped_key FROM content_keys WHERE id = $1 AND status = 'active'",
                    key_id,
                )
                if wrapped:
                    storage = StorageService.from_config(config)
                    data = await AudioPackageService(pool).decrypt_stored_original(
                        storage, str(enc_key), wrapped
                    )
                    if data:
                        return data, filename, "audio/mpeg"
        except Exception as exc:
            logger.warning("Admin encrypted original decrypt failed task=%s: %s", task_id, exc)

    b2_key = _row_get(row, f"b2_storage_key_{variant_key}")
    if b2_key:
        try:
            from platform_api.services.storage_service import StorageService
            from platform_api.services.streaming_config_service import resolve_streaming_storage_config

            config = await resolve_streaming_storage_config(pool)
            if config.configured:
                data = await StorageService.from_config(config).download_bytes(key=str(b2_key))
                if data:
                    from platform_api.services.audio_package_service import AudioPackageService
                    from platform_api.services.audio_packager import looks_like_camxora_audio

                    if looks_like_camxora_audio(data):
                        if key_id:
                            wrapped = await pool.fetchval(
                                "SELECT wrapped_key FROM content_keys WHERE id = $1 AND status = 'active'",
                                key_id,
                            )
                            if wrapped:
                                data = AudioPackageService(pool)._decrypt_with_wrapped(
                                    data, bytes(wrapped)
                                )
                                if data:
                                    return data, filename, "audio/mpeg"
                        logger.warning(
                            "Admin B2 object is ciphertext task=%s variant=%s",
                            task_id,
                            variant_key,
                        )
                    else:
                        return data, filename, "audio/mpeg"
        except Exception as exc:
            logger.warning("Admin B2 audio read failed task=%s variant=%s: %s", task_id, variant_key, exc)

    audio_url = str(_row_get(row, f"audio_url_{variant_key}") or "").strip()
    if audio_url:
        from platform_api.services.suno_audio_resolver import download_suno_mp3_bytes

        data = await download_suno_mp3_bytes(audio_url)
        return data, filename, "audio/mpeg"

    raise NotFoundError("Audio file is not available for this clip.")


async def _load_lyrics_file(
    pool,
    user_id: UUID,
    task_id: UUID,
    *,
    variant: str,
    lyric_format: str,
) -> tuple[bytes, str, str]:
    variant_key = str(variant or "ok").strip().lower()
    format_key = str(lyric_format or "lrc").strip().lower()
    if variant_key not in {"ok", "alt"}:
        raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
    if format_key not in {"lrc", "srt"}:
        raise ValidationError("format must be lrc or srt.", details={"field": "format"})

    row = await _fetch_row(
        pool,
        """
        SELECT id, title, instrumental, lyrics,
               b2_lrc_storage_key_ok, b2_lrc_storage_key_alt
        FROM suno_tasks
        WHERE id = $1 AND user_id = $2
        """,
        task_id,
        user_id,
    )
    if row is None:
        row = await _fetch_row(
            pool,
            "SELECT id, title, instrumental, lyrics FROM suno_tasks WHERE id = $1 AND user_id = $2",
            task_id,
            user_id,
        )
    if row is None:
        raise NotFoundError("Generation not found.")
    if bool(_row_get(row, "instrumental")):
        raise ValidationError("Timed lyrics are not available for instrumental tracks.")

    title = str(_row_get(row, "title") or "camxora-track").strip() or "camxora-track"
    lrc_text = ""
    b2_key = _row_get(row, f"b2_lrc_storage_key_{variant_key}")
    if b2_key:
        try:
            from platform_api.services.storage_service import StorageService
            from platform_api.services.streaming_config_service import resolve_streaming_storage_config

            config = await resolve_streaming_storage_config(pool)
            if config.configured:
                raw = await StorageService.from_config(config).download_bytes(key=str(b2_key))
                from platform_api.services.audio_package_service import AudioPackageService

                raw = await AudioPackageService(pool).decrypt_suno_export(
                    raw,
                    subject_id=task_id,
                    variant=variant_key,
                )
                lrc_text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Admin B2 LRC read failed task=%s: %s", task_id, exc)

    if not lrc_text.strip():
        lrc_text = str(_row_get(row, "lyrics") or "")

    from platform_api.services.suno_lrc import looks_like_lrc

    if format_key == "srt":
        if not looks_like_lrc(lrc_text):
            raise ValidationError("Timed lyrics are not available for this clip yet.")
        body = _lrc_to_srt(lrc_text)
        if not body.strip():
            raise ValidationError("Could not convert timed lyrics to SRT.")
        return body.encode("utf-8"), f"{title}.srt", "application/x-subrip; charset=utf-8"

    if not lrc_text.strip():
        raise ValidationError("Lyrics are not available for this clip.")
    return lrc_text.encode("utf-8"), f"{title}.lrc", "text/plain; charset=utf-8"


@router.get(
    "/{user_id}/web-music/workspaces",
    response_model=AdminWebMusicWorkspaceListResponse,
    summary="List a user's Camxora Music workspaces (Admin)",
)
async def list_user_web_music_workspaces(
    user_id: UUID,
    ctx: AdminUserDep,
) -> AdminWebMusicWorkspaceListResponse:
    del ctx
    pool = get_db_pool()
    await _require_user(pool, user_id)
    rows = await _fetch_rows(
        pool,
        """
        SELECT id, name, is_default, created_at
        FROM web_music_workspaces
        WHERE user_id = $1
        ORDER BY is_default DESC, created_at ASC
        """,
        user_id,
    )
    return AdminWebMusicWorkspaceListResponse(
        items=[
            AdminWebMusicWorkspaceResponse(
                id=str(row["id"]),
                name=str(row["name"] or "Workspace"),
                is_default=bool(_row_get(row, "is_default") or False),
                created_at=_iso(_row_get(row, "created_at")),
            )
            for row in rows
        ]
    )


@router.get(
    "/{user_id}/web-music/generations",
    response_model=AdminWebMusicGenerationListResponse,
    summary="List a user's Camxora Music generations (Admin)",
)
async def list_user_web_music_generations(
    user_id: UUID,
    ctx: AdminUserDep,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    workspace_id: UUID | None = None,
) -> AdminWebMusicGenerationListResponse:
    del ctx
    pool = get_db_pool()
    await _require_user(pool, user_id)
    if workspace_id is not None:
        workspace = await _fetch_row(
            pool,
            "SELECT id FROM web_music_workspaces WHERE id = $1 AND user_id = $2",
            workspace_id,
            user_id,
        )
        if workspace is None:
            raise NotFoundError("Workspace not found.", details={"workspace_id": str(workspace_id)})
    rows, total = await _list_generation_rows(
        pool,
        user_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return AdminWebMusicGenerationListResponse(
        items=[AdminWebMusicGenerationResponse(**_generation_payload(row, user_id)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{user_id}/web-music/generations/{task_id}/audio",
    summary="Stream a user's generated clip (Admin)",
)
async def stream_user_web_music_clip(
    user_id: UUID,
    task_id: UUID,
    ctx: AdminUserDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    del ctx
    pool = get_db_pool()
    data, filename, content_type = await _load_clip_audio(pool, user_id, task_id, variant)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": _content_disposition(filename, inline=True),
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/{user_id}/web-music/generations/{task_id}/download",
    summary="Download a user's generated MP3 (Admin)",
)
async def download_user_web_music_clip(
    user_id: UUID,
    task_id: UUID,
    ctx: AdminUserDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    del ctx
    pool = get_db_pool()
    data, filename, content_type = await _load_clip_audio(pool, user_id, task_id, variant)
    try:
        from platform_api.services.content_license_service import ContentLicenseService

        await ContentLicenseService(pool).record_export_event(
            user_id=user_id,
            suno_task_id=task_id,
            variant=variant,
            format="mp3",
            actor="admin",
        )
    except Exception as exc:
        logger.warning("Admin export_events insert failed: %s", exc)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": _content_disposition(filename, inline=False),
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/{user_id}/web-music/generations/{task_id}/timed-lyrics",
    summary="Download LRC or SRT for a user's generated clip (Admin)",
)
async def download_user_web_music_lyrics(
    user_id: UUID,
    task_id: UUID,
    ctx: AdminUserDep,
    variant: Literal["ok", "alt"] = "ok",
    format: Literal["lrc", "srt"] = "lrc",
) -> Response:
    del ctx
    pool = get_db_pool()
    data, filename, content_type = await _load_lyrics_file(
        pool,
        user_id,
        task_id,
        variant=variant,
        lyric_format=format,
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": _content_disposition(filename, inline=False)},
    )
