"""Public catalog queries and proxied playback URLs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from platform_api.exceptions import NotFoundError
from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.audio_origin_proxy import is_initial_play_range, proxy_origin_audio
from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config
from platform_api.services.streaming_slug import slugify
from platform_api.services.music_genre_utils import parse_genre_list

_PUBLIC_TRACK_KEYS = {
    "id",
    "title",
    "album_id",
    "album_name",
    "user_id",
    "artist_name",
    "variant",
    "cover_url",
    "genre",
    "genres",
    "genre_slug",
    "album_genre",
    "duration_seconds",
    "play_count",
    "valid_streams",
    "lyrics",
    "published_at",
    "created_at",
    "track_number",
    "tags",
    "added_at",
    "package_status",
}

_PUBLIC_ALBUM_KEYS = {
    "id",
    "album_name",
    "artist_name",
    "user_id",
    "cover_url",
    "genre",
    "genres",
    "genre_slug",
    "track_count",
    "play_count",
    "published_at",
    "created_at",
    "tracks",
    "avatar_url",
}


class StreamingCatalogService:
    def __init__(self, pool: Any, redis: Any | None = None) -> None:
        self._pool = pool
        self._redis = redis
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

    @staticmethod
    def _decorate_genre_fields(row: dict[str, Any]) -> None:
        genres = parse_genre_list(row.get("genres"))
        if not genres:
            primary = str(row.get("genre") or row.get("album_genre") or "").strip()
            genres = [primary] if primary else []
        row["genres"] = genres
        row["genre_slug"] = slugify(genres[0]) if genres else None
        if not row.get("genre") and genres:
            row["genre"] = genres[0]

    async def _decorate_track(self, track: dict[str, Any]) -> None:
        track["cover_url"] = await self._cover_url(self._track_cover_key(track))
        if track.get("genre") is None and track.get("album_genre"):
            track["genre"] = track.get("album_genre")
        track["play_count"] = int(track.get("play_count") or 0)
        track["valid_streams"] = int(track.get("valid_streams") or 0)
        self._decorate_genre_fields(track)
        self._expose_public_track(track)

    async def _decorate_tracks(self, tracks: list[dict[str, Any]]) -> None:
        await self._attach_valid_streams(tracks)
        for track in tracks:
            await self._decorate_track(track)

    async def _attach_valid_streams(self, tracks: list[dict[str, Any]]) -> None:
        ids = [track["id"] for track in tracks if track.get("id")]
        if not ids:
            return
        try:
            rows = await self._pool.fetch(
                """
                SELECT subject_id, COUNT(*) FILTER (
                    WHERE listener_user_id <> owner_user_id
                )::int AS valid_streams
                FROM valid_streams
                WHERE subject_type = 'stream_track' AND subject_id = ANY($1::uuid[])
                GROUP BY subject_id
                """,
                ids,
            )
        except Exception:
            return
        counts = {row["subject_id"]: int(row["valid_streams"] or 0) for row in rows}
        for track in tracks:
            track["valid_streams"] = counts.get(track["id"], int(track.get("valid_streams") or 0))

    async def _decorate_album(self, album: dict[str, Any]) -> None:
        album["cover_url"] = await self._cover_url(album.get("cover_storage_key"))
        album["play_count"] = int(album.get("play_count") or 0)
        self._decorate_genre_fields(album)
        self._expose_public_album(album)

    @staticmethod
    def _expose_public_track(track: dict[str, Any]) -> None:
        for key in list(track.keys()):
            if key not in _PUBLIC_TRACK_KEYS:
                track.pop(key, None)

    @staticmethod
    def _expose_public_album(album: dict[str, Any]) -> None:
        for key in list(album.keys()):
            if key not in _PUBLIC_ALBUM_KEYS:
                album.pop(key, None)

    @staticmethod
    def _catalog_stream_url(track_id: UUID) -> str:
        return f"/api/v1/public/streaming/tracks/{track_id}/stream"

    async def get_home(self) -> dict[str, Any]:
        recent_tracks = await self._repo.list_recent_published_tracks(limit=12)
        albums = await self._repo.list_published_albums(limit=12)
        await self._decorate_tracks(recent_tracks)
        for album in albums:
            await self._decorate_album(album)
        return {"recent_tracks": recent_tracks, "albums": albums}

    async def list_albums(self, *, limit: int = 24, offset: int = 0) -> dict[str, Any]:
        albums = await self._repo.list_published_albums(limit=limit, offset=offset)
        total = await self._repo.count_published_albums()
        for album in albums:
            await self._decorate_album(album)
        return {"items": albums, "total": total, "limit": limit, "offset": offset}

    async def get_album(self, album_id: UUID) -> dict[str, Any] | None:
        album = await self._repo.get_published_album(album_id)
        if not album:
            return None
        tracks = await self._repo.list_published_tracks_for_album(album_id)
        if not tracks:
            return None
        album_cover_key = album.get("cover_storage_key")
        album_genre = album.get("genre")
        await self._decorate_album(album)
        for track in tracks:
            track["album_cover_storage_key"] = album_cover_key
            track["album_genre"] = album_genre
        await self._decorate_tracks(tracks)
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
                    "genres": [genre],
                    "slug": slugify(genre),
                    "genre_slug": slugify(genre),
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
        await self._decorate_tracks(tracks)
        return {
            "genre": genre,
            "slug": match["slug"],
            "album_count": match["album_count"],
            "track_count": match["track_count"],
            "albums": albums,
            "tracks": tracks,
        }

    async def list_artists(self, *, limit: int = 48, offset: int = 0) -> dict[str, Any]:
        artists = await self._repo.list_artists(limit=limit, offset=offset)
        total = await self._repo.count_artists()
        items = []
        for artist in artists:
            user_id = str(artist.get("user_id"))
            avatar_raw = str(artist.get("avatar_url") or "").strip()
            items.append(
                {
                    "user_id": user_id,
                    "artist_name": artist.get("artist_name"),
                    "album_count": int(artist.get("album_count") or 0),
                    "track_count": int(artist.get("track_count") or 0),
                    "avatar_url": f"/api/v1/media/users/{user_id}/avatar" if avatar_raw else None,
                }
            )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def get_artist(self, user_id: UUID) -> dict[str, Any] | None:
        albums = await self._repo.list_artist_albums(user_id)
        if not albums:
            return None
        for album in albums:
            await self._decorate_album(album)
        return {
            "user_id": str(user_id),
            "artist_name": albums[0].get("artist_name"),
            "albums": albums,
        }

    async def search(self, query: str, *, limit: int = 24, offset: int = 0) -> dict[str, Any]:
        tracks = await self._repo.search_published(query, limit=limit, offset=offset)
        total = await self._repo.count_search_published(query)
        await self._decorate_tracks(tracks)
        return {"items": tracks, "total": total, "limit": limit, "offset": offset}

    async def get_play_url(self, track_id: UUID) -> dict[str, Any] | None:
        track = await self._repo.get_published_track(track_id)
        if not track:
            return None
        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return None
        pkg = str(track.get("package_status") or "none")
        has_audio = bool(str(track.get("storage_key") or "").strip()) or pkg == "ready"
        if not has_audio:
            return None
        await self._attach_valid_streams([track])
        expires_at = datetime.now(timezone.utc).timestamp() + config.stream_url_ttl_seconds
        return {
            "track_id": str(track_id),
            "url": self._catalog_stream_url(track_id),
            "package_status": pkg,
            "subject_type": "stream_track",
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "title": track.get("title"),
            "album_id": str(track["album_id"]) if track.get("album_id") else None,
            "album_name": track.get("album_name"),
            "user_id": str(track["user_id"]) if track.get("user_id") else None,
            "artist_name": track.get("artist_name"),
            "variant": track.get("variant"),
            "cover_url": await self._cover_url(self._track_cover_key(track)),
            "duration_seconds": track.get("duration_seconds"),
            "play_count": int(track.get("play_count") or 0),
            "valid_streams": int(track.get("valid_streams") or 0),
            "genre": track.get("genre") or track.get("album_genre"),
            "lyrics": track.get("lyrics"),
            "genres": parse_genre_list(track.get("genres"))
            or (
                [str(track.get("genre") or track.get("album_genre")).strip()]
                if str(track.get("genre") or track.get("album_genre") or "").strip()
                else []
            ),
            "genre_slug": slugify(
                str(track.get("genre") or track.get("album_genre") or ""),
                fallback="",
            )
            or None,
        }

    async def proxy_track_audio(
        self,
        track_id: UUID,
        *,
        range_header: str | None = None,
    ):
        """Stream catalog audio through the API. Never return the B2 URL to the browser."""
        track = await self._repo.get_published_track(track_id)
        if not track:
            raise NotFoundError("Track not found or streaming is not configured.")
        if str(track.get("package_status") or "") == "ready":
            raise NotFoundError("This track requires the encrypted player.")
        storage_key = str(track.get("storage_key") or "").strip()
        if not storage_key:
            raise NotFoundError("Track not found or streaming is not configured.")
        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            raise NotFoundError("Track not found or streaming is not configured.")
        storage = StorageService.from_config(config)
        origin_url = await storage.get_signed_get_url(storage_key)
        if not origin_url:
            raise NotFoundError("Track not found or streaming is not configured.")
        if is_initial_play_range(range_header):
            await self._repo.increment_play_count(track_id)
        return await proxy_origin_audio(origin_url, range_header=range_header)

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

    async def list_liked_track_ids(self, user_id: UUID) -> list[str]:
        ids = await self._repo.list_liked_track_ids(user_id)
        return [str(item) for item in ids]

    async def list_liked_tracks(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        rows = await self._repo.list_liked_tracks(user_id, limit=limit, offset=offset)
        total = await self._repo.count_liked_tracks(user_id)
        for track in rows:
            if not track.get("added_at") and track.get("liked_at"):
                track["added_at"] = track.get("liked_at")
        await self._decorate_tracks(rows)
        for track in rows:
            track["id"] = str(track["id"])
            if track.get("album_id"):
                track["album_id"] = str(track["album_id"])
            if track.get("user_id"):
                track["user_id"] = str(track["user_id"])
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    async def like_track(self, user_id: UUID, track_id: UUID) -> dict[str, Any]:
        track = await self._repo.get_published_track(track_id)
        if not track:
            return {"ok": False, "liked": False, "reason": "not_found"}
        inserted = await self._repo.like_track(user_id, track_id)
        return {"ok": True, "liked": True, "created": inserted}

    async def unlike_track(self, user_id: UUID, track_id: UUID) -> dict[str, Any]:
        removed = await self._repo.unlike_track(user_id, track_id)
        return {"ok": True, "liked": False, "removed": removed}
