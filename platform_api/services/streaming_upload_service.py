"""Upload generated music and artwork to Backblaze for public streaming."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from platform_api.models.enums import ImageKind
from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.storage_service import StorageService, StorageServiceError
from platform_api.services.streaming_config_service import resolve_streaming_storage_config
from platform_api.services.streaming_slug import slugify
from platform_api.services.music_genre_utils import parse_suno_clip_tags, resolve_stream_genres
from platform_api.services.suno_audio_resolver import (
    SunoTaskDownloadUrls,
    download_suno_mp3_bytes,
    normalize_http_download_url,
    poll_suno_generate_with_pool,
    refresh_suno_task_download_urls,
    variant_url_candidates,
)

import httpx

logger = logging.getLogger(__name__)

_IMAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)",
    "Accept": "image/*,*/*;q=0.8",
}


class StreamingUploadService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._repo = StreamingRepository(pool)

    def schedule_suno_streaming_upload(self, *, suno_task_id: UUID) -> None:
        asyncio.create_task(self._run_suno_streaming_upload(suno_task_id))

    async def _run_suno_streaming_upload(self, suno_task_id: UUID) -> None:
        try:
            context = await self._repo.get_suno_stream_context(suno_task_id)
            if not context:
                return

            refreshed = await self._refresh_task_download_urls(context)
            audio_ok = normalize_http_download_url(
                refreshed.audio_url_ok or context.get("audio_url_ok")
            )
            audio_alt = normalize_http_download_url(
                refreshed.audio_url_alt or context.get("audio_url_alt")
            )
            if refreshed.refreshed and (refreshed.audio_url_ok or refreshed.audio_url_alt):
                await self._persist_refreshed_audio_urls(
                    suno_task_id=suno_task_id,
                    refreshed=refreshed,
                )
            if audio_ok:
                await self._upload_mp3_variant(
                    context=context,
                    variant="ok",
                    source_url=audio_ok,
                    refreshed=refreshed,
                )
            if audio_alt:
                await self._upload_mp3_variant(
                    context=context,
                    variant="alt",
                    source_url=audio_alt,
                    refreshed=refreshed,
                )
        except Exception as exc:
            logger.exception("Streaming upload failed for suno_task_id=%s: %s", suno_task_id, exc)

    async def _refresh_task_download_urls(self, context: dict[str, Any]) -> SunoTaskDownloadUrls:
        external_task_id = str(context.get("external_task_id") or "").strip()
        if not external_task_id:
            return SunoTaskDownloadUrls()
        try:
            return await refresh_suno_task_download_urls(
                external_task_id,
                poll_status=lambda task_id: poll_suno_generate_with_pool(self._pool, task_id),
            )
        except Exception as exc:
            logger.warning(
                "Unable to refresh Suno download URLs for external_task_id=%s: %s",
                external_task_id,
                str(exc)[:200],
            )
            return SunoTaskDownloadUrls()

    async def _persist_refreshed_audio_urls(
        self,
        *,
        suno_task_id: UUID,
        refreshed: SunoTaskDownloadUrls,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET audio_url_ok = CASE WHEN $2 <> '' THEN $2 ELSE audio_url_ok END,
                audio_url_alt = CASE WHEN $3 <> '' THEN $3 ELSE audio_url_alt END,
                updated_at = NOW()
            WHERE id = $1
            """,
            suno_task_id,
            refreshed.audio_url_ok,
            refreshed.audio_url_alt,
        )

    async def _upload_mp3_variant(
        self,
        *,
        context: dict[str, Any],
        variant: str,
        source_url: str,
        refreshed: SunoTaskDownloadUrls | None = None,
    ) -> None:
        user_id = UUID(str(context["user_id"]))
        song_id = UUID(str(context["song_id"])) if context.get("song_id") else None
        batch_id = UUID(str(context["batch_id"])) if context.get("batch_id") else None
        suno_task_id = UUID(str(context["suno_task_id"]))

        if variant == "alt":
            album_name = str(context.get("alt_album") or context.get("song_album") or "Alternate Album").strip()
            channel_role = "alt"
        else:
            album_name = str(context.get("ok_album") or context.get("song_album") or "Album").strip()
            channel_role = "ok"

        title = str(context.get("song_title") or "Untitled").strip() or "Untitled"
        lyrics = str(context.get("song_lyrics") or "").strip() or None
        album_slug = slugify(album_name, fallback="album")
        song_slug = slugify(title, fallback="track")
        storage_key = f"{user_id}/{album_slug}/{song_slug}-{variant}.mp3"

        job_id = await self._repo.create_upload_job(
            user_id=user_id,
            kind=f"mp3_{variant}",
            song_id=song_id,
            batch_id=batch_id,
            suno_task_id=suno_task_id,
            source_url=normalize_http_download_url(source_url) or None,
            storage_key=storage_key,
        )

        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                await self._repo.mark_upload_job(job_id, status="failed", error="Streaming storage is not configured.")
                return

            candidates = variant_url_candidates(
                variant=variant,
                stored_ok=normalize_http_download_url(context.get("audio_url_ok")),
                stored_alt=normalize_http_download_url(context.get("audio_url_alt")),
                refreshed=refreshed,
            )
            primary_url = candidates[0] if candidates else normalize_http_download_url(source_url)
            fallback_urls = candidates[1:] if len(candidates) > 1 else []
            if not primary_url:
                raise StorageServiceError(
                    "No valid Suno download URL available. Re-poll record-info or retry after Suno callback."
                )
            data = await download_suno_mp3_bytes(primary_url, fallback_urls=fallback_urls)
            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=data, content_type="audio/mpeg")

            album_id = await self._repo.get_or_create_album(
                user_id=user_id,
                batch_id=batch_id,
                album_name=album_name,
                album_slug=album_slug,
                channel_role=channel_role,
            )

            duration_seconds = None
            suno_image_url = ""
            tags_text = ""
            if refreshed is not None:
                if variant == "alt":
                    duration_seconds = refreshed.duration_alt
                    suno_image_url = refreshed.image_url_alt
                    tags_text = refreshed.tags_alt
                else:
                    duration_seconds = refreshed.duration_ok
                    suno_image_url = refreshed.image_url_ok
                    tags_text = refreshed.tags_ok

            primary_genre, catalog_genres = resolve_stream_genres(
                description_genres=context.get("description_genres"),
                suno_tags_text=tags_text,
            )
            genre = primary_genre
            tags = parse_suno_clip_tags(tags_text) or None
            track_number = None
            batch_index = context.get("batch_index")
            if batch_index is not None:
                try:
                    track_number = int(batch_index) + 1
                except (TypeError, ValueError):
                    track_number = None

            cover_storage_key = await self._maybe_upload_suno_cover(
                user_id=user_id,
                album_id=album_id,
                album_slug=album_slug,
                variant=variant,
                image_url=suno_image_url,
                storage=storage,
            )

            await self._repo.update_album_genre(album_id, genre, genres=catalog_genres or None)
            await self._repo.upsert_track(
                user_id=user_id,
                album_id=album_id,
                song_id=song_id,
                suno_task_id=suno_task_id,
                title=title,
                lyrics=lyrics,
                variant=variant,
                storage_key=storage_key,
                size_bytes=len(data),
                duration_seconds=duration_seconds,
                genre=genre,
                track_number=track_number,
                cover_storage_key=cover_storage_key,
                suno_image_url=suno_image_url or None,
                tags=tags,
                genres=catalog_genres or None,
            )
            await self._repo.mark_upload_job(job_id, status="success", storage_key=storage_key)
        except Exception as exc:
            await self._repo.mark_upload_job(job_id, status="failed", error=str(exc)[:500])
            logger.warning("MP3 streaming upload failed job=%s: %s", job_id, exc)

    async def _maybe_upload_suno_cover(
        self,
        *,
        user_id: UUID,
        album_id: UUID,
        album_slug: str,
        variant: str,
        image_url: str,
        storage: StorageService,
    ) -> str | None:
        url = str(image_url or "").strip()
        if not url:
            return None
        row = await self._pool.fetchrow(
            "SELECT cover_storage_key FROM stream_albums WHERE id = $1",
            album_id,
        )
        if row and str(row.get("cover_storage_key") or "").strip():
            return None
        try:
            image_bytes = await self._download_image_bytes(url)
        except Exception as exc:
            logger.warning("Suno cover download failed for album %s: %s", album_id, str(exc)[:200])
            return None
        if not image_bytes:
            return None
        storage_key = f"{user_id}/{album_slug}/cover-suno-{variant}.jpg"
        try:
            await storage.upload_bytes(key=storage_key, data=image_bytes, content_type="image/jpeg")
            await self._repo.update_album_cover(album_id, storage_key)
            return storage_key
        except Exception as exc:
            logger.warning("Suno cover upload failed for album %s: %s", album_id, str(exc)[:200])
            return None

    @staticmethod
    async def _download_image_bytes(url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url, headers=_IMAGE_HEADERS)
            response.raise_for_status()
            data = response.content
            if len(data) < 512:
                raise StorageServiceError("Suno image response was too small.")
            return data

    async def upload_album_cover_from_image_job(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        channel_role: str,
        image_bytes: bytes,
        preferred_kind: str,
    ) -> None:
        del preferred_kind
        context_row = await self._pool.fetchrow(
            "SELECT ok_album, alt_album FROM batches WHERE id = $1",
            batch_id,
        )
        if not context_row:
            return

        role = channel_role.lower()
        if role == "alt":
            album_name = str(context_row.get("alt_album") or "Alternate Album").strip()
        else:
            album_name = str(context_row.get("ok_album") or "Album").strip()
        album_slug = slugify(album_name, fallback="album")
        storage_key = f"{user_id}/{album_slug}/cover.jpg"

        job_id = await self._repo.create_upload_job(
            user_id=user_id,
            kind="cover",
            batch_id=batch_id,
            storage_key=storage_key,
        )
        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                await self._repo.mark_upload_job(job_id, status="failed", error="Streaming storage is not configured.")
                return

            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=image_bytes, content_type="image/jpeg")

            album_id = await self._repo.get_or_create_album(
                user_id=user_id,
                batch_id=batch_id,
                album_name=album_name,
                album_slug=album_slug,
                channel_role=role,
            )
            await self._repo.update_album_cover(album_id, storage_key)
            await self._repo.mark_upload_job(job_id, status="success", storage_key=storage_key)
        except Exception as exc:
            await self._repo.mark_upload_job(job_id, status="failed", error=str(exc)[:500])
            logger.warning("Cover streaming upload failed job=%s: %s", job_id, exc)

    async def upload_album_cover_from_profile_logo(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        channel_role: str,
        logo_path: str,
    ) -> None:
        path = Path(logo_path)
        project_root = Path(__file__).resolve().parents[2]
        candidate = path if path.is_absolute() else (project_root / path)
        if not candidate.is_file():
            return
        await self.upload_album_cover_from_image_job(
            user_id=user_id,
            batch_id=batch_id,
            channel_role=channel_role,
            image_bytes=candidate.read_bytes(),
            preferred_kind="logo",
        )

    async def maybe_upload_cover_after_image_job(
        self,
        *,
        user_id: UUID,
        batch_id: UUID | None,
        channel_role: str,
        kind: ImageKind,
        image_bytes: bytes,
    ) -> None:
        if batch_id is None:
            return
        if kind not in {ImageKind.THUMBNAIL, ImageKind.BACKGROUND}:
            return

        role = str(channel_role or "ok").lower()
        album = await self._repo.find_album_for_batch_role(
            user_id=user_id,
            batch_id=batch_id,
            channel_role=role,
        )
        if album and album.get("cover_storage_key"):
            if kind == ImageKind.BACKGROUND:
                return

        await self.upload_album_cover_from_image_job(
            user_id=user_id,
            batch_id=batch_id,
            channel_role=role,
            image_bytes=image_bytes,
            preferred_kind=str(kind.value),
        )

    async def retry_failed_job(self, job_id: UUID) -> dict[str, Any]:
        """Re-run a failed MP3 upload job using its stored source URL."""
        job = await self._repo.get_upload_job(job_id)
        if not job:
            raise ValueError("Upload job not found.")
        if str(job.get("status") or "") != "failed":
            raise ValueError("Only failed upload jobs can be retried.")

        kind = str(job.get("kind") or "")
        if not kind.startswith("mp3_"):
            raise ValueError("Only MP3 upload jobs can be retried from admin.")

        source_url = normalize_http_download_url(job.get("source_url"))
        suno_task_id = job.get("suno_task_id")
        if not suno_task_id:
            raise ValueError("Upload job is missing Suno task reference.")

        variant = kind.removeprefix("mp3_")
        if variant not in {"ok", "alt"}:
            raise ValueError(f"Unsupported MP3 upload kind: {kind}")

        context = await self._repo.get_suno_stream_context(UUID(str(suno_task_id)))
        if not context:
            raise ValueError("Original Suno task context was not found.")

        refreshed = await self._refresh_task_download_urls(context)
        if refreshed.refreshed and (refreshed.audio_url_ok or refreshed.audio_url_alt):
            await self._persist_refreshed_audio_urls(
                suno_task_id=UUID(str(suno_task_id)),
                refreshed=refreshed,
            )
            context = await self._repo.get_suno_stream_context(UUID(str(suno_task_id))) or context

        await self._repo.mark_upload_job(job_id, status="pending", error=None)

        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                await self._repo.mark_upload_job(
                    job_id,
                    status="failed",
                    error="Streaming storage is not configured.",
                )
                raise ValueError("Streaming storage is not configured.")

            if variant == "alt":
                album_name = str(
                    context.get("alt_album") or context.get("song_album") or "Alternate Album"
                ).strip()
                channel_role = "alt"
            else:
                album_name = str(context.get("ok_album") or context.get("song_album") or "Album").strip()
                channel_role = "ok"

            user_id = UUID(str(context["user_id"]))
            song_id = UUID(str(context["song_id"])) if context.get("song_id") else None
            batch_id = UUID(str(context["batch_id"])) if context.get("batch_id") else None
            title = str(context.get("song_title") or "Untitled").strip() or "Untitled"
            lyrics = str(context.get("song_lyrics") or "").strip() or None
            album_slug = slugify(album_name, fallback="album")
            song_slug = slugify(title, fallback="track")
            storage_key = str(job.get("storage_key") or f"{user_id}/{album_slug}/{song_slug}-{variant}.mp3")

            candidates = variant_url_candidates(
                variant=variant,
                stored_ok=normalize_http_download_url(context.get("audio_url_ok")),
                stored_alt=normalize_http_download_url(context.get("audio_url_alt")),
                refreshed=refreshed,
            )
            primary_url = candidates[0] if candidates else source_url
            fallback_urls = candidates[1:] if len(candidates) > 1 else []
            if not primary_url:
                raise ValueError(
                    "No valid Suno download URL available for retry. Check Suno task record-info."
                )
            data = await download_suno_mp3_bytes(primary_url, fallback_urls=fallback_urls)
            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=data, content_type="audio/mpeg")

            album_id = await self._repo.get_or_create_album(
                user_id=user_id,
                batch_id=batch_id,
                album_name=album_name,
                album_slug=album_slug,
                channel_role=channel_role,
            )
            await self._repo.upsert_track(
                user_id=user_id,
                album_id=album_id,
                song_id=song_id,
                suno_task_id=UUID(str(suno_task_id)),
                title=title,
                lyrics=lyrics,
                variant=variant,
                storage_key=storage_key,
                size_bytes=len(data),
            )
            await self._repo.mark_upload_job(job_id, status="success", storage_key=storage_key)
            return {"ok": True, "job_id": str(job_id), "storage_key": storage_key}
        except Exception as exc:
            await self._repo.mark_upload_job(job_id, status="failed", error=str(exc)[:500])
            raise

