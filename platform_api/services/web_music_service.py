"""Consumer music-web generation: quota, submit, list, download proxy."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID
from urllib.parse import quote

from platform_api.exceptions import NotFoundError, QuotaExceededError, ValidationError
from platform_api.models.enums import TaskStatus
from platform_api.models.products import (
    SUNO_TASK_SOURCE_WEB_MUSIC,
    WEB_MUSIC_FREE_DAILY_LIMIT_DEFAULT,
    WEB_MUSIC_FREE_DAILY_LIMIT_KEY,
)
from platform_api.ports.generation_port import SunoRequest
from platform_api.services.billing_calendar import billing_today
from platform_api.services.generation_service import GenerationService
from platform_api.services.suno_audio_resolver import (
    download_suno_mp3_bytes,
    refresh_suno_task_download_urls,
    urls_from_generate_poll,
    variant_url_candidates,
)

logger = logging.getLogger(__name__)

_VALID_MODELS = frozenset({"V5", "V5_5"})


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


class WebMusicService:
    def __init__(self, pool: Any, generation_service: GenerationService) -> None:
        self._pool = pool
        self._generation = generation_service

    async def daily_limit(self) -> int:
        row = await self._pool.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1",
            WEB_MUSIC_FREE_DAILY_LIMIT_KEY,
        )
        raw = _row_value(row, "value") if row is not None else None
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = WEB_MUSIC_FREE_DAILY_LIMIT_DEFAULT
        return max(0, limit)

    async def _has_pro(self, user_id: UUID) -> bool:
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM licenses
            WHERE user_id = $1
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            user_id,
        )
        return row is not None

    async def _used_count(self, user_id: UUID) -> int:
        return int(
            await self._pool.fetchval(
                """
                SELECT COALESCE(SUM(generation_count), 0)::int
                FROM web_music_daily_usage
                WHERE user_id = $1
                """,
                user_id,
            )
            or 0
        )

    def _quota_payload(
        self,
        *,
        limit: int,
        used: int,
        is_pro: bool,
    ) -> dict[str, Any]:
        remaining = 0 if is_pro else max(0, limit - used)
        requires_upgrade = (not is_pro) and remaining <= 0
        return {
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "is_pro": is_pro,
            "requires_upgrade": requires_upgrade,
        }

    async def usage_today(self, user_id: UUID, *, usage_date: date | None = None) -> dict[str, Any]:
        del usage_date
        limit = await self.daily_limit()
        is_pro = await self._has_pro(user_id)
        used = await self._used_count(user_id)
        return self._quota_payload(limit=limit, used=used, is_pro=is_pro)

    async def _reserve_daily_slot(self, user_id: UUID) -> dict[str, Any]:
        limit = await self.daily_limit()
        is_pro = await self._has_pro(user_id)
        if is_pro:
            used = await self._used_count(user_id)
            return self._quota_payload(limit=limit, used=used, is_pro=True)
        if limit <= 0:
            raise QuotaExceededError(
                "Upgrade to Pro to create songs.",
                details={"limit": 0, "used": 0, "requires_upgrade": True},
            )
        day = billing_today()
        row = await self._pool.fetchrow(
            """
            INSERT INTO web_music_daily_usage (user_id, usage_date, generation_count)
            SELECT $1, $2, 1
            WHERE (
                SELECT COALESCE(SUM(generation_count), 0)
                FROM web_music_daily_usage
                WHERE user_id = $1
            ) < $3
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET generation_count = web_music_daily_usage.generation_count + 1
            WHERE (
                SELECT COALESCE(SUM(generation_count), 0)
                FROM web_music_daily_usage
                WHERE user_id = $1
            ) < $3
            RETURNING generation_count
            """,
            user_id,
            day,
            limit,
        )
        if row is None:
            used = await self._used_count(user_id)
            raise QuotaExceededError(
                f"You've used your {limit} free songs. Upgrade to Pro to keep creating.",
                details={"limit": limit, "used": used, "requires_upgrade": True},
            )
        used = await self._used_count(user_id)
        return self._quota_payload(limit=limit, used=used, is_pro=False)

    async def _release_daily_slot(self, user_id: UUID) -> None:
        day = billing_today()
        await self._pool.execute(
            """
            UPDATE web_music_daily_usage
            SET generation_count = GREATEST(generation_count - 1, 0)
            WHERE user_id = $1 AND usage_date = $2
            """,
            user_id,
            day,
        )

    async def generate(
        self,
        user_id: UUID,
        *,
        mode: str,
        lyrics: str,
        style: str,
        title: str,
        instrumental: bool,
        model: str,
        prompt: str,
    ) -> dict[str, Any]:
        normalized_model = str(model or "V5").strip().upper()
        if normalized_model not in _VALID_MODELS:
            raise ValidationError(
                "model must be V5 or V5_5.",
                details={"field": "model"},
            )
        mode_key = str(mode or "advanced").strip().lower()
        if mode_key not in ("simple", "advanced"):
            raise ValidationError("mode must be simple or advanced.", details={"field": "mode"})

        safe_style = str(style or "").strip() or "Contemporary pop"
        safe_lyrics = str(lyrics or "").strip()
        safe_title = str(title or "").strip()
        safe_prompt = str(prompt or "").strip()

        if mode_key == "simple":
            if not safe_prompt:
                raise ValidationError(
                    "Describe the song you want to create.",
                    details={"field": "prompt"},
                )
            generated_lyrics, generated_title = await self._generation.generate_suno_lyrics(safe_prompt)
            safe_lyrics = str(generated_lyrics or "").strip() or safe_prompt
            if not safe_title:
                safe_title = str(generated_title or "").strip() or safe_prompt[:80]
        else:
            if not instrumental and not safe_lyrics:
                raise ValidationError("Lyrics are required.", details={"field": "lyrics"})
            if not safe_title:
                first_line = next(
                    (line.strip() for line in safe_lyrics.splitlines() if line.strip()),
                    "",
                )
                safe_title = first_line[:80] or "Untitled"

        quota = await self._reserve_daily_slot(user_id)
        try:
            task_id = await self._generation.submit_suno(
                str(user_id),
                SunoRequest(
                    model=normalized_model,
                    title=safe_title,
                    lyrics=safe_lyrics if not instrumental else (safe_lyrics or "Instrumental"),
                    style=safe_style,
                    instrumental=instrumental,
                ),
                skip_pricing=True,
                source=SUNO_TASK_SOURCE_WEB_MUSIC,
            )
        except Exception:
            await self._release_daily_slot(user_id)
            raise

        return {
            "task_id": str(task_id),
            "status": "PENDING",
            "title": safe_title,
            "style": safe_style,
            "quota": quota,
        }

    async def list_generations(
        self,
        user_id: UUID,
        *,
        limit: int = 40,
        offset: int = 0,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        total = int(
            await self._pool.fetchval(
                """
                SELECT COUNT(*)::int FROM suno_tasks
                WHERE user_id = $1 AND source = $2
                """,
                user_id,
                SUNO_TASK_SOURCE_WEB_MUSIC,
            )
            or 0
        )
        rows = await self._pool.fetch(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at
            FROM suno_tasks
            WHERE user_id = $1 AND source = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
            safe_limit,
            safe_offset,
        )
        return {
            "items": [self._task_payload(row) for row in rows],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    async def get_generation(self, user_id: UUID, task_id: UUID) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        row = await self._refresh_pending_from_suno(row)
        return self._task_payload(row)

    async def _refresh_pending_from_suno(self, row: Any) -> Any:
        """If the callback has not landed yet, poll sunoapi.org record-info."""
        status = str(_row_value(row, "status") or "").strip().lower()
        if status not in {"pending", "running"}:
            return row
        external_id = str(_row_value(row, "external_task_id") or "").strip()
        if not external_id:
            return row
        try:
            polled = await self._generation.poll_suno_generate_status(external_id)
        except Exception as exc:
            logger.warning("Web music Suno poll failed for %s: %s", row["id"], exc)
            return row
        if polled.state == "success":
            urls = urls_from_generate_poll(polled)
            await self._pool.execute(
                """
                UPDATE suno_tasks
                SET status = $2,
                    audio_url_ok = COALESCE(NULLIF(BTRIM($3), ''), audio_url_ok),
                    audio_url_alt = COALESCE(NULLIF(BTRIM($4), ''), audio_url_alt),
                    audio_id_ok = COALESCE(NULLIF(BTRIM($5), ''), audio_id_ok),
                    audio_id_alt = COALESCE(NULLIF(BTRIM($6), ''), audio_id_alt),
                    updated_at = NOW()
                WHERE id = $1
                """,
                row["id"],
                TaskStatus.SUCCESS.value,
                urls.audio_url_ok,
                urls.audio_url_alt,
                urls.audio_id_ok,
                urls.audio_id_alt,
            )
        elif polled.state == "failed":
            await self._pool.execute(
                """
                UPDATE suno_tasks
                SET status = $2,
                    error_message = COALESCE(NULLIF(BTRIM($3), ''), error_message),
                    updated_at = NOW()
                WHERE id = $1
                """,
                row["id"],
                TaskStatus.FAILED.value,
                polled.error or "Suno generation failed.",
            )
        else:
            return row
        refreshed = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id
            FROM suno_tasks
            WHERE id = $1
            """,
            row["id"],
        )
        return refreshed or row

    async def download_mp3(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
    ) -> tuple[bytes, str, str]:
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        row = await self._pool.fetchrow(
            """
            SELECT id, title, status, audio_url_ok, audio_url_alt, external_task_id
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        status = str(row["status"] or "").upper()
        if status != "SUCCESS":
            raise ValidationError(
                "This song is not ready to download yet.",
                details={"status": status},
            )
        external_task_id = str(row["external_task_id"] or "").strip()
        refreshed = None
        if external_task_id:
            try:
                refreshed = await refresh_suno_task_download_urls(
                    external_task_id,
                    poll_status=self._generation.poll_suno_generate_status,
                )
            except Exception as exc:
                logger.warning("Web music URL refresh failed for %s: %s", task_id, exc)
        candidates = variant_url_candidates(
            variant=variant_key,
            stored_ok=str(row["audio_url_ok"] or ""),
            stored_alt=str(row["audio_url_alt"] or ""),
            refreshed=refreshed,
        )
        if not candidates:
            raise NotFoundError("Audio file is not available.")
        data = await download_suno_mp3_bytes(candidates[0], fallback_urls=candidates[1:])
        title = str(row["title"] or "camxora-track").strip() or "camxora-track"
        filename = f"{title}-{variant_key}.mp3"
        return data, filename, "audio/mpeg"

    def _task_payload(self, row: Any) -> dict[str, Any]:
        task_id = str(row["id"])
        created = row["created_at"]
        if isinstance(created, datetime) and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return {
            "id": task_id,
            "title": row["title"] or "Untitled",
            "lyrics": row["lyrics"] or "",
            "style": row["style"] or "",
            "model": row["model"] or "V5",
            "instrumental": bool(row["instrumental"]),
            "status": str(row["status"] or "pending").upper(),
            "error_message": row["error_message"],
            "created_at": created,
            "clips": [
                {
                    "variant": "ok",
                    "label": "Version 1",
                    "audio_url": f"/api/v1/web-music/generations/{task_id}/stream?variant=ok",
                    "download_url": f"/api/v1/web-music/generations/{task_id}/download?variant=ok",
                    "ready": bool(row["audio_url_ok"]),
                },
                {
                    "variant": "alt",
                    "label": "Version 2",
                    "audio_url": f"/api/v1/web-music/generations/{task_id}/stream?variant=alt",
                    "download_url": f"/api/v1/web-music/generations/{task_id}/download?variant=alt",
                    "ready": bool(row["audio_url_alt"]),
                },
            ],
        }


def content_disposition(filename: str, *, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    ascii_name = "".join(ch if ch.isascii() and ch not in '"\\' else "_" for ch in filename) or "track.mp3"
    encoded = quote(filename)
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
