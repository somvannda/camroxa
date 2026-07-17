"""Public catalog queries and signed playback URLs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config
from platform_api.services.streaming_slug import slugify


class StreamingCatalogService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._repo = StreamingRepository(pool)

    async def _cover_url(self, storage_key: str | None) -> str | None:
        if not storage_key:
            return None
        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return None
        storage = StorageService.from_config(config)
        return await storage.get_signed_get_url(storage_key)

    @staticmethod
    def _track_cover_key(track: dict[str, Any]) -> str | None:
        return track.get("cover_storage_key") or track.get("album_cover_storage_key")

    async def _decorate_track(self, track: dict[str, Any]) -> None:
        track["cover_url"] = await self._cover_url(self._track_cover_key(track))
        if track.get("genre") is None and track.get("album_genre"):
            track["genre"] = track.get("album_genre")

    async def _decorate_album(self, album: dict[str, Any]) -> None:
        album["cover_url"] = await self._cover_url(album.get("cover_storage_key"))

    async def get_home(self) -> dict[str, Any]:
        recent_tracks = await self._repo.list_recent_published_tracks(limit=12)
        albums = await self._repo.list_published_albums(limit=12)
        for track in recent_tracks:
            await self._decorate_track(track)
        for album in albums:
            await self._decorate_album(album)
        return {"recent_tracks": recent_tracks, "albums": albums}

    async def list_albums(self, *, limit: int = 24, offset: int = 0) -> list[dict[str, Any]]:
        albums = await self._repo.list_published_albums(limit=limit, offset=offset)
        for album in albums:
            await self._decorate_album(album)
        return albums

    async def get_album(self, album_id: UUID) -> dict[str, Any] | None:
        album = await self._repo.get_published_album(album_id)
        if not album:
            return None
        tracks = await self._repo.list_published_tracks_for_album(album_id)
        if not tracks:
            return None
        await self._decorate_album(album)
        for track in tracks:
            track["album_cover_storage_key"] = album.get("cover_storage_key")
            track["album_genre"] = album.get("genre")
            await self._decorate_track(track)
        album["tracks"] = tracks
        return album

    async def list_genres(self) -> list[dict[str, Any]]:
        rows = await self._repo.list_genres()
        items: list[dict[str, Any]] = []
        for row in rows:
            genre = str(row.get("genre") or "").strip()
            if not genre:
                continue
            items.append(
                {
                    "genre": genre,
                    "slug": slugify(genre),
                    "album_count": int(row.get("album_count") or 0),
                    "track_count": int(row.get("track_count") or 0),
                }
            )
        return items

    async def get_genre(self, slug: str) -> dict[str, Any] | None:
        normalized = slugify(slug, fallback="")
        if not normalized:
            return None
        genres = await self.list_genres()
        match = next((item for item in genres if item["slug"] == normalized), None)
        if match is None:
            return None
        genre = str(match["genre"])
        albums = await self._repo.list_published_albums_by_genre(genre, limit=24, offset=0)
        tracks = await self._repo.list_published_tracks_by_genre(genre, limit=24, offset=0)
        for album in albums:
            await self._decorate_album(album)
        for track in tracks:
            await self._decorate_track(track)
        return {
            "genre": genre,
            "slug": match["slug"],
            "album_count": match["album_count"],
            "track_count": match["track_count"],
            "albums": albums,
            "tracks": tracks,
        }

    async def list_artists(self, *, limit: int = 48, offset: int = 0) -> list[dict[str, Any]]:
        return await self._repo.list_artists(limit=limit, offset=offset)

    async def get_artist(self, user_id: UUID) -> dict[str, Any] | None:
        albums = await self._repo.list_artist_albums(user_id)
        if not albums:
            return None
        for album in albums:
            album["cover_url"] = await self._cover_url(album.get("cover_storage_key"))
        return {
            "user_id": str(user_id),
            "artist_name": albums[0].get("artist_name"),
            "albums": albums,
        }

    async def search(self, query: str, *, limit: int = 24) -> list[dict[str, Any]]:
        tracks = await self._repo.search_published(query, limit=limit)
        for track in tracks:
            await self._decorate_track(track)
        return tracks

    async def get_play_url(self, track_id: UUID) -> dict[str, Any] | None:
        track = await self._repo.get_published_track(track_id)
        if not track:
            return None
        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return None
        storage = StorageService.from_config(config)
        url = await storage.get_signed_get_url(str(track["storage_key"]))
        expires_at = datetime.now(timezone.utc).timestamp() + config.stream_url_ttl_seconds
        return {
            "track_id": str(track_id),
            "url": url,
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "title": track.get("title"),
            "album_name": track.get("album_name"),
            "artist_name": track.get("artist_name"),
            "variant": track.get("variant"),
            "cover_url": await self._cover_url(self._track_cover_key(track)),
            "duration_seconds": track.get("duration_seconds"),
            "genre": track.get("genre") or track.get("album_genre"),
        }

    async def unpublish_track(self, track_id: UUID) -> bool:
        return await self._repo.set_track_publish_status(track_id, "unpublished")

    async def republish_track(self, track_id: UUID) -> bool:
        return await self._repo.set_track_publish_status(track_id, "published")

    async def unpublish_album(self, album_id: UUID) -> bool:
        return await self._repo.set_album_publish_status(album_id, "unpublished")

    async def republish_album(self, album_id: UUID) -> bool:
        published_count = await self._repo.count_published_tracks_for_album(album_id)
        if published_count == 0:
            return False
        return await self._repo.set_album_publish_status(album_id, "published")

    async def delete_track(self, track_id: UUID) -> bool:
        return await self._repo.delete_track(track_id)

    async def delete_album(self, album_id: UUID) -> bool:
        return await self._repo.delete_album(album_id)
