"""Refresh stream track metadata from Suno record-info and song records."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config
from platform_api.services.streaming_upload_service import StreamingUploadService
from platform_api.services.suno_audio_resolver import SunoTaskDownloadUrls

logger = logging.getLogger(__name__)


class StreamingMetadataSyncService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._repo = StreamingRepository(pool)
        self._upload_service = StreamingUploadService(pool)

    async def sync_track_metadata(self, track_id: UUID) -> dict[str, Any]:
        row = await self._repo.get_track_for_metadata_sync(track_id)
        if not row:
            raise ValueError("Track not found.")

        variant = str(row.get("variant") or "ok").lower()
        refreshed = SunoTaskDownloadUrls()
        external_task_id = str(row.get("external_task_id") or "").strip()
        if external_task_id:
            try:
                refreshed = await self._upload_service._refresh_task_download_urls(
                    {"external_task_id": external_task_id}
                )
            except Exception as exc:
                logger.warning("Metadata sync Suno refresh failed for %s: %s", track_id, exc)

        if variant == "alt":
            duration_seconds = refreshed.duration_alt
            suno_image_url = refreshed.image_url_alt
            tags_text = refreshed.tags_alt
        else:
            duration_seconds = refreshed.duration_ok
            suno_image_url = refreshed.image_url_ok
            tags_text = refreshed.tags_ok

        lyrics = str(row.get("song_lyrics") or row.get("lyrics") or "").strip() or None
        genre = str(row.get("suno_style") or tags_text or row.get("genre") or "").strip() or None
        tags = [part.strip() for part in str(tags_text or "").split(",") if part.strip()] or None

        cover_storage_key = row.get("cover_storage_key")
        album_id = UUID(str(row["album_id"]))
        user_id = UUID(str(row["user_id"]))
        album_slug = str(row.get("album_slug") or "album")

        if suno_image_url and not str(cover_storage_key or "").strip():
            config = await resolve_streaming_storage_config(self._pool)
            if config.configured:
                storage = StorageService.from_config(config)
                uploaded = await self._upload_service._maybe_upload_suno_cover(
                    user_id=user_id,
                    album_id=album_id,
                    album_slug=album_slug,
                    variant=variant,
                    image_url=suno_image_url,
                    storage=storage,
                )
                if uploaded:
                    cover_storage_key = uploaded

        await self._repo.update_track_metadata_sync(
            track_id,
            lyrics=lyrics,
            duration_seconds=duration_seconds,
            genre=genre,
            suno_image_url=suno_image_url or None,
            tags=tags,
            cover_storage_key=cover_storage_key,
        )
        if genre:
            await self._repo.update_album_genre(album_id, genre)

        return {
            "ok": True,
            "track_id": str(track_id),
            "genre": genre,
            "duration_seconds": duration_seconds,
            "has_lyrics": bool(lyrics),
            "refreshed_from_suno": refreshed.refreshed,
        }

    async def sync_all_tracks_metadata(self, *, limit: int = 100) -> dict[str, Any]:
        rows = await self._repo.list_tracks_for_metadata_sync(limit=max(1, min(limit, 500)))
        synced = 0
        failed: list[dict[str, str]] = []
        for row in rows:
            track_id = UUID(str(row["id"]))
            try:
                await self.sync_track_metadata(track_id)
                synced += 1
            except Exception as exc:
                failed.append({"track_id": str(track_id), "error": str(exc)[:200]})
        return {"ok": True, "synced": synced, "failed": failed, "total": len(rows)}
