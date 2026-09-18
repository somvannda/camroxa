"""Database access for the public music streaming catalog."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import json


class StreamingRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def get_track_storage_keys_for_suno_tasks(
        self, suno_task_ids: list[UUID]
    ) -> dict[tuple[str, str], str]:
        """Map (suno_task_id, variant) -> B2 storage_key for already-archived tracks.

        Used by "change run folder + resume" style recovery flows to prefer the
        durable Backblaze copy (uploaded automatically on every successful Suno
        callback) over the original Suno CDN URL, which is not guaranteed to stay
        valid forever.
        """
        if not suno_task_ids:
            return {}
        rows = await self._pool.fetch(
            """
            SELECT suno_task_id, variant, storage_key
            FROM stream_tracks
            WHERE suno_task_id = ANY($1::uuid[])
              AND storage_key IS NOT NULL
              AND storage_key <> ''
            """,
            suno_task_ids,
        )
        return {
            (str(row["suno_task_id"]), str(row["variant"])): str(row["storage_key"])
            for row in rows
        }

    async def create_upload_job(
        self,
        *,
        user_id: UUID,
        kind: str,
        song_id: UUID | None = None,
        batch_id: UUID | None = None,
        suno_task_id: UUID | None = None,
        album_id: UUID | None = None,
        source_url: str | None = None,
        storage_key: str | None = None,
    ) -> UUID:
        job_id = uuid4()
        await self._pool.execute(
            """
            INSERT INTO stream_upload_jobs (
                id, user_id, song_id, batch_id, suno_task_id, album_id,
                kind, source_url, storage_key, status, attempt_count
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', 0)
            """,
            job_id,
            user_id,
            song_id,
            batch_id,
            suno_task_id,
            album_id,
            kind,
            source_url,
            storage_key,
        )
        return job_id

    async def mark_upload_job(
        self,
        job_id: UUID,
        *,
        status: str,
        error: str | None = None,
        storage_key: str | None = None,
        album_id: UUID | None = None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE stream_upload_jobs
            SET status = $2,
                error = $3,
                storage_key = COALESCE($4, storage_key),
                album_id = COALESCE($5, album_id),
                attempt_count = attempt_count + 1,
                last_attempt_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            status,
            error,
            storage_key,
            album_id,
        )

    async def get_upload_job(self, job_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow("SELECT * FROM stream_upload_jobs WHERE id = $1", job_id)
        return dict(row) if row else None

    async def list_upload_jobs(self, *, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        """List upload jobs with user / song / album / track context for admin UI."""
        where = ""
        params: list[Any] = []
        if status:
            params.append(status)
            where = f"WHERE j.status = ${len(params)}"
        params.append(limit)
        limit_placeholder = f"${len(params)}"

        rows = await self._pool.fetch(
            f"""
            SELECT
                j.id,
                j.kind,
                j.status,
                j.source_url,
                j.storage_key,
                j.error,
                j.attempt_count,
                j.permanent_failed,
                j.user_id,
                j.song_id,
                j.batch_id,
                COALESCE(j.album_id, sa_cover.id, st.album_id) AS album_id,
                j.created_at,
                j.updated_at,
                u.email AS user_email,
                u.display_name AS user_display_name,
                s.title AS song_title,
                s.album AS song_album,
                s.batch_index AS song_batch_index,
                COALESCE(sa_direct.album_name, sa_cover.album_name, sa_track.album_name) AS stream_album_name,
                COALESCE(sa_direct.channel_role, sa_cover.channel_role, sa_track.channel_role)
                    AS stream_channel_role,
                COALESCE(
                    sa_direct.publish_status,
                    sa_cover.publish_status,
                    sa_track.publish_status
                ) AS stream_album_publish_status,
                st.publish_status AS stream_track_publish_status,
                st.variant AS stream_track_variant
            FROM stream_upload_jobs j
            LEFT JOIN users u ON u.id = j.user_id
            LEFT JOIN songs s ON s.id = j.song_id
            LEFT JOIN stream_albums sa_direct ON sa_direct.id = j.album_id
            LEFT JOIN stream_albums sa_cover
                ON j.album_id IS NULL
               AND j.kind = 'cover'
               AND sa_cover.user_id = j.user_id
               AND sa_cover.batch_id = j.batch_id
               AND sa_cover.cover_storage_key IS NOT DISTINCT FROM j.storage_key
            LEFT JOIN stream_tracks st
                ON j.song_id IS NOT NULL
               AND st.song_id = j.song_id
               AND (
                    (j.kind = 'mp3_ok' AND lower(st.variant) = 'ok')
                 OR (j.kind = 'mp3_alt' AND lower(st.variant) = 'alt')
               )
            LEFT JOIN stream_albums sa_track ON sa_track.id = st.album_id
            {where}
            ORDER BY j.created_at DESC
            LIMIT {limit_placeholder}
            """,
            *params,
        )
        return [dict(row) for row in rows]

    async def list_retryable_upload_jobs(
        self,
        *,
        window_hours: int = 336,
        max_attempts: int = 6,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """MP3 jobs the backfill sweep may (re)process.

        Includes stuck ``pending`` jobs (older than 2 minutes — e.g. after an
        API restart) and ``failed`` jobs that are not permanently failed.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, kind, status, attempt_count
            FROM stream_upload_jobs
            WHERE kind IN ('mp3_ok', 'mp3_alt')
              AND COALESCE(permanent_failed, false) = false
              AND attempt_count < $1
              AND created_at > now() - make_interval(hours => $2)
              AND (
                status = 'failed'
                OR (status = 'pending' AND updated_at < now() - interval '2 minutes')
              )
            ORDER BY created_at DESC
            LIMIT $3
            """,
            max(1, min(int(max_attempts or 6), 50)),
            max(1, min(int(window_hours or 336), 24 * 90)),
            max(1, min(int(limit or 200), 1000)),
        )
        return [dict(row) for row in rows]

    async def mark_upload_job_permanent_failed(
        self,
        job_id: UUID,
        *,
        error: str | None = None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE stream_upload_jobs
            SET permanent_failed = true,
                status = 'failed',
                error = COALESCE($2, error),
                updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            error,
        )

    async def list_studio_tasks_missing_b2(
        self,
        *,
        window_hours: int = 336,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Studio success tasks within the window whose B2 MP3 copy is missing."""
        rows = await self._pool.fetch(
            """
            SELECT st.id,
                   st.audio_url_ok,
                   st.audio_url_alt,
                   (st.audio_url_ok IS NOT NULL AND NOT EXISTS (
                      SELECT 1 FROM stream_tracks t
                      WHERE t.suno_task_id = st.id AND t.variant = 'ok'
                        AND COALESCE(t.storage_key, '') <> ''
                   )) AS missing_ok,
                   (st.audio_url_alt IS NOT NULL AND NOT EXISTS (
                      SELECT 1 FROM stream_tracks t
                      WHERE t.suno_task_id = st.id AND t.variant = 'alt'
                        AND COALESCE(t.storage_key, '') <> ''
                   )) AS missing_alt
            FROM suno_tasks st
            WHERE st.status = 'success'
              AND COALESCE(st.source, '') <> 'web_music'
              AND st.created_at > now() - make_interval(hours => $1)
              AND (
                (st.audio_url_ok IS NOT NULL AND NOT EXISTS (
                  SELECT 1 FROM stream_tracks t
                  WHERE t.suno_task_id = st.id AND t.variant = 'ok'
                    AND COALESCE(t.storage_key, '') <> ''
                ))
                OR
                (st.audio_url_alt IS NOT NULL AND NOT EXISTS (
                  SELECT 1 FROM stream_tracks t
                  WHERE t.suno_task_id = st.id AND t.variant = 'alt'
                    AND COALESCE(t.storage_key, '') <> ''
                ))
              )
              AND NOT EXISTS (
                SELECT 1 FROM stream_upload_jobs j
                WHERE j.suno_task_id = st.id
                  AND j.kind IN ('mp3_ok', 'mp3_alt')
                  AND COALESCE(j.permanent_failed, false) = false
                  AND j.status IN ('pending', 'failed')
              )
            ORDER BY st.created_at DESC
            LIMIT $2
            """,
            max(1, min(int(window_hours or 336), 24 * 90)),
            max(1, min(int(limit or 200), 1000)),
        )
        return [dict(row) for row in rows]

    async def list_web_music_tasks_missing_wav(
        self,
        *,
        window_hours: int = 336,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Web-music success tasks within the window whose WAV is not in B2."""
        rows = await self._pool.fetch(
            """
            SELECT st.id,
                   (COALESCE(st.b2_wav_storage_key_ok, '') = ''
                    AND COALESCE(st.audio_id_ok, '') <> '') AS missing_wav_ok,
                   (COALESCE(st.b2_wav_storage_key_alt, '') = ''
                    AND COALESCE(st.audio_id_alt, '') <> '') AS missing_wav_alt
            FROM suno_tasks st
            WHERE st.status = 'success'
              AND st.source = 'web_music'
              AND st.created_at > now() - make_interval(hours => $1)
              AND (
                (COALESCE(st.b2_wav_storage_key_ok, '') = ''
                 AND COALESCE(st.audio_id_ok, '') <> '')
                OR
                (COALESCE(st.b2_wav_storage_key_alt, '') = ''
                 AND COALESCE(st.audio_id_alt, '') <> '')
              )
            ORDER BY st.created_at DESC
            LIMIT $2
            """,
            max(1, min(int(window_hours or 336), 24 * 90)),
            max(1, min(int(limit or 20), 200)),
        )
        return [dict(row) for row in rows]

    async def get_or_create_album(
        self,
        *,
        user_id: UUID,
        batch_id: UUID | None,
        album_name: str,
        album_slug: str,
        channel_role: str,
    ) -> UUID:
        row = await self._pool.fetchrow(
            """
            SELECT id FROM stream_albums
            WHERE user_id = $1 AND album_slug = $2
            """,
            user_id,
            album_slug,
        )
        if row:
            return UUID(str(row["id"]))

        album_id = uuid4()
        now = datetime.now(timezone.utc)
        await self._pool.execute(
            """
            INSERT INTO stream_albums (
                id, user_id, batch_id, album_name, album_slug, channel_role,
                publish_status, published_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, 'published', $7)
            """,
            album_id,
            user_id,
            batch_id,
            album_name,
            album_slug,
            channel_role,
            now,
        )
        return album_id

    async def upsert_track(
        self,
        *,
        user_id: UUID,
        album_id: UUID,
        song_id: UUID | None,
        suno_task_id: UUID | None,
        title: str,
        lyrics: str | None,
        variant: str,
        storage_key: str,
        size_bytes: int | None,
        mime_type: str = "audio/mpeg",
        duration_seconds: float | None = None,
        genre: str | None = None,
        track_number: int | None = None,
        cover_storage_key: str | None = None,
        suno_image_url: str | None = None,
        tags: list[str] | None = None,
        genres: list[str] | None = None,
        suno_audio_id: str | None = None,
    ) -> UUID:
        from platform_api.services.suno_lrc import looks_like_lrc

        existing = None
        if suno_task_id is not None:
            existing = await self._pool.fetchrow(
                """
                SELECT id, lyrics FROM stream_tracks
                WHERE suno_task_id = $1 AND variant = $2
                """,
                suno_task_id,
                variant,
            )
        if existing and looks_like_lrc(existing.get("lyrics")) and not looks_like_lrc(lyrics):
            lyrics = str(existing.get("lyrics") or "").strip() or lyrics

        now = datetime.now(timezone.utc)
        tags_json = tags or None
        genres_json = genres or None
        audio_id = str(suno_audio_id or "").strip() or None
        if existing:
            track_id = UUID(str(existing["id"]))
            try:
                await self._pool.execute(
                    """
                    UPDATE stream_tracks
                    SET title = $2,
                        lyrics = $3,
                        storage_key = $4,
                        size_bytes = $5,
                        mime_type = $6,
                        duration_seconds = COALESCE($7, duration_seconds),
                        genre = COALESCE($8, genre),
                        track_number = COALESCE($9, track_number),
                        cover_storage_key = COALESCE($10, cover_storage_key),
                        suno_image_url = COALESCE($11, suno_image_url),
                        tags = COALESCE($12, tags),
                        genres = COALESCE($13::jsonb, genres),
                        suno_audio_id = COALESCE($14, suno_audio_id),
                        publish_status = 'published',
                        published_at = $15,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    track_id,
                    title,
                    lyrics,
                    storage_key,
                    size_bytes,
                    mime_type,
                    duration_seconds,
                    genre,
                    track_number,
                    cover_storage_key,
                    suno_image_url,
                    tags_json,
                    json.dumps(genres_json) if genres_json is not None else None,
                    audio_id,
                    now,
                )
            except Exception:
                await self._pool.execute(
                    """
                    UPDATE stream_tracks
                    SET title = $2,
                        lyrics = $3,
                        storage_key = $4,
                        size_bytes = $5,
                        mime_type = $6,
                        duration_seconds = COALESCE($7, duration_seconds),
                        publish_status = 'published',
                        published_at = $8,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    track_id,
                    title,
                    lyrics,
                    storage_key,
                    size_bytes,
                    mime_type,
                    duration_seconds,
                    now,
                )
            return track_id

        track_id = uuid4()
        try:
            await self._pool.execute(
                """
                INSERT INTO stream_tracks (
                    id, user_id, album_id, song_id, suno_task_id, title, lyrics,
                    variant, storage_key, size_bytes, mime_type, duration_seconds,
                    genre, track_number, cover_storage_key, suno_image_url, tags, genres,
                    suno_audio_id, publish_status, published_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, 'published', $20)
                """,
                track_id,
                user_id,
                album_id,
                song_id,
                suno_task_id,
                title,
                lyrics,
                variant,
                storage_key,
                size_bytes,
                mime_type,
                duration_seconds,
                genre,
                track_number,
                cover_storage_key,
                suno_image_url,
                tags_json,
                json.dumps(genres_json) if genres_json is not None else json.dumps([]),
                audio_id,
                now,
            )
        except Exception:
            await self._pool.execute(
                """
                INSERT INTO stream_tracks (
                    id, user_id, album_id, song_id, suno_task_id, title, lyrics,
                    variant, storage_key, size_bytes, mime_type, duration_seconds,
                    publish_status, published_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'published', $13)
                """,
                track_id,
                user_id,
                album_id,
                song_id,
                suno_task_id,
                title,
                lyrics,
                variant,
                storage_key,
                size_bytes,
                mime_type,
                duration_seconds,
                now,
            )
        return track_id

    async def update_album_genre(
        self,
        album_id: UUID,
        genre: str | None,
        *,
        genres: list[str] | None = None,
        overwrite: bool = False,
    ) -> None:
        if not genre and not genres and not overwrite:
            return
        genres_payload = json.dumps(genres if genres is not None else [])
        try:
            if overwrite:
                await self._pool.execute(
                    """
                    UPDATE stream_albums
                    SET genre = $2,
                        genres = COALESCE($3::jsonb, '[]'::jsonb),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    album_id,
                    genre,
                    genres_payload,
                )
            else:
                await self._pool.execute(
                    """
                    UPDATE stream_albums
                    SET genre = COALESCE(genre, $2),
                        genres = CASE
                            WHEN jsonb_array_length(COALESCE(genres, '[]'::jsonb)) = 0
                                 AND $3::jsonb IS NOT NULL
                            THEN $3::jsonb
                            ELSE genres
                        END,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    album_id,
                    genre,
                    genres_payload if genres else None,
                )
        except Exception:
            return

    async def update_album_cover(self, album_id: UUID, cover_storage_key: str) -> None:
        await self._pool.execute(
            """
            UPDATE stream_albums
            SET cover_storage_key = $2, updated_at = NOW()
            WHERE id = $1
            """,
            album_id,
            cover_storage_key,
        )

    async def find_album_for_batch_role(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        channel_role: str,
    ) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM stream_albums
            WHERE user_id = $1 AND batch_id = $2 AND channel_role = $3
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            batch_id,
            channel_role,
        )
        return dict(row) if row else None

    async def set_track_publish_status(self, track_id: UUID, publish_status: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE stream_tracks
            SET publish_status = $2, updated_at = NOW()
            WHERE id = $1
            """,
            track_id,
            publish_status,
        )
        return result.endswith("1")

    async def set_album_publish_status(self, album_id: UUID, publish_status: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE stream_albums
            SET publish_status = $2, updated_at = NOW()
            WHERE id = $1
            """,
            album_id,
            publish_status,
        )
        return result.endswith("1")

    async def delete_track(self, track_id: UUID) -> bool:
        result = await self._pool.execute("DELETE FROM stream_tracks WHERE id = $1", track_id)
        return result.endswith("1")

    async def delete_album(self, album_id: UUID) -> bool:
        result = await self._pool.execute("DELETE FROM stream_albums WHERE id = $1", album_id)
        return result.endswith("1")

    async def increment_play_count(self, track_id: UUID) -> int:
        value = await self._pool.fetchval(
            """
            UPDATE stream_tracks
            SET play_count = play_count + 1,
                updated_at = NOW()
            WHERE id = $1 AND publish_status = 'published'
            RETURNING play_count
            """,
            track_id,
        )
        return int(value or 0)

    async def list_published_albums(self, *, limit: int = 24, offset: int = 0) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT a.*,
                   u.display_name AS artist_name,
                   COUNT(t.id)::int AS track_count,
                   COALESCE(SUM(t.play_count), 0)::bigint AS play_count
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN stream_tracks t
              ON t.album_id = a.id AND t.publish_status = 'published'
            WHERE a.publish_status = 'published'
            GROUP BY a.id, u.display_name
            HAVING COUNT(t.id) > 0
            ORDER BY a.published_at DESC NULLS LAST, a.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    async def count_published_albums(self) -> int:
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int FROM (
              SELECT a.id
              FROM stream_albums a
              JOIN stream_tracks t
                ON t.album_id = a.id AND t.publish_status = 'published'
              WHERE a.publish_status = 'published'
              GROUP BY a.id
            ) published_albums
            """
        )
        return int(value or 0)

    async def get_published_album(self, album_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT a.*,
                   u.display_name AS artist_name,
                   COALESCE((
                     SELECT SUM(t.play_count)::bigint
                     FROM stream_tracks t
                     WHERE t.album_id = a.id AND t.publish_status = 'published'
                   ), 0) AS play_count,
                   COALESCE((
                     SELECT COUNT(t.id)::int
                     FROM stream_tracks t
                     WHERE t.album_id = a.id AND t.publish_status = 'published'
                   ), 0) AS track_count
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            WHERE a.id = $1 AND a.publish_status = 'published'
            """,
            album_id,
        )
        return dict(row) if row else None

    async def list_published_tracks_for_album(self, album_id: UUID) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM stream_tracks
            WHERE album_id = $1 AND publish_status = 'published'
            ORDER BY created_at ASC, title ASC
            """,
            album_id,
        )
        return [dict(row) for row in rows]

    async def count_published_tracks_for_album(self, album_id: UUID) -> int:
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int FROM stream_tracks
            WHERE album_id = $1 AND publish_status = 'published'
            """,
            album_id,
        )
        return int(value or 0)

    async def get_published_track(self, track_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT t.*, a.album_name, a.cover_storage_key AS album_cover_storage_key,
                   a.genre AS album_genre, u.display_name AS artist_name
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE t.id = $1 AND t.publish_status = 'published' AND a.publish_status = 'published'
            """,
            track_id,
        )
        return dict(row) if row else None

    async def list_recent_published_tracks(self, *, limit: int = 12) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT t.*, a.album_name, a.cover_storage_key AS album_cover_storage_key,
                   a.genre AS album_genre, u.display_name AS artist_name
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE t.publish_status = 'published' AND a.publish_status = 'published'
            ORDER BY t.published_at DESC NULLS LAST, t.created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def list_artists(self, *, limit: int = 48, offset: int = 0) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT u.id AS user_id,
                   u.display_name AS artist_name,
                   u.avatar_url,
                   COUNT(DISTINCT a.id)::int AS album_count,
                   COUNT(t.id)::int AS track_count
            FROM users u
            JOIN stream_albums a ON a.user_id = u.id AND a.publish_status = 'published'
            JOIN stream_tracks t ON t.album_id = a.id AND t.publish_status = 'published'
            GROUP BY u.id, u.display_name, u.avatar_url
            ORDER BY track_count DESC, artist_name ASC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    async def count_artists(self) -> int:
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int FROM (
              SELECT u.id
              FROM users u
              JOIN stream_albums a ON a.user_id = u.id AND a.publish_status = 'published'
              JOIN stream_tracks t ON t.album_id = a.id AND t.publish_status = 'published'
              GROUP BY u.id
            ) published_artists
            """
        )
        return int(value or 0)

    async def list_artist_albums(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT a.*,
                   u.display_name AS artist_name,
                   COUNT(t.id)::int AS track_count,
                   COALESCE(SUM(t.play_count), 0)::bigint AS play_count
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN stream_tracks t
              ON t.album_id = a.id AND t.publish_status = 'published'
            WHERE a.user_id = $1 AND a.publish_status = 'published'
            GROUP BY a.id, u.display_name
            HAVING COUNT(t.id) > 0
            ORDER BY a.published_at DESC NULLS LAST, a.album_name ASC
            """,
            user_id,
        )
        return [dict(row) for row in rows]

    async def list_admin_catalog(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        publish_status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["TRUE"]
        args: list[Any] = []
        if publish_status in {"published", "unpublished"}:
            args.append(publish_status)
            clauses.append(f"t.publish_status = ${len(args)}")
        query = (q or "").strip()
        if query:
            args.append(f"%{query}%")
            idx = len(args)
            clauses.append(
                f"(t.title ILIKE ${idx} OR a.album_name ILIKE ${idx} OR u.display_name ILIKE ${idx})"
            )
        args.extend([limit, offset])
        limit_idx = len(args) - 1
        offset_idx = len(args)
        where_sql = " AND ".join(clauses)
        rows = await self._pool.fetch(
            f"""
            SELECT t.*, a.album_name, a.genre AS album_genre, a.cover_storage_key AS album_cover_storage_key,
                   u.display_name AS artist_name
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE {where_sql}
            ORDER BY t.created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
            """,
            *args,
        )
        return [dict(row) for row in rows]

    async def count_admin_catalog(
        self,
        *,
        q: str | None = None,
        publish_status: str | None = None,
    ) -> int:
        clauses = ["TRUE"]
        args: list[Any] = []
        if publish_status in {"published", "unpublished"}:
            args.append(publish_status)
            clauses.append(f"t.publish_status = ${len(args)}")
        query = (q or "").strip()
        if query:
            args.append(f"%{query}%")
            idx = len(args)
            clauses.append(
                f"(t.title ILIKE ${idx} OR a.album_name ILIKE ${idx} OR u.display_name ILIKE ${idx})"
            )
        where_sql = " AND ".join(clauses)
        value = await self._pool.fetchval(
            f"""
            SELECT COUNT(*)::int
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE {where_sql}
            """,
            *args,
        )
        return int(value or 0)

    async def list_admin_albums(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        publish_status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["TRUE"]
        args: list[Any] = []
        if publish_status in {"published", "unpublished"}:
            args.append(publish_status)
            clauses.append(f"a.publish_status = ${len(args)}")
        query = (q or "").strip()
        if query:
            args.append(f"%{query}%")
            idx = len(args)
            clauses.append(f"(a.album_name ILIKE ${idx} OR u.display_name ILIKE ${idx})")
        args.extend([limit, offset])
        limit_idx = len(args) - 1
        offset_idx = len(args)
        where_sql = " AND ".join(clauses)
        rows = await self._pool.fetch(
            f"""
            SELECT a.*,
                   u.display_name AS artist_name,
                   COUNT(t.id)::int AS track_count,
                   COUNT(t.id) FILTER (WHERE t.publish_status = 'published')::int AS published_track_count,
                   COALESCE(SUM(t.play_count), 0)::bigint AS play_count
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN stream_tracks t ON t.album_id = a.id
            WHERE {where_sql}
            GROUP BY a.id, u.display_name
            ORDER BY a.created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
            """,
            *args,
        )
        return [dict(row) for row in rows]

    async def count_admin_albums(
        self,
        *,
        q: str | None = None,
        publish_status: str | None = None,
    ) -> int:
        clauses = ["TRUE"]
        args: list[Any] = []
        if publish_status in {"published", "unpublished"}:
            args.append(publish_status)
            clauses.append(f"a.publish_status = ${len(args)}")
        query = (q or "").strip()
        if query:
            args.append(f"%{query}%")
            idx = len(args)
            clauses.append(f"(a.album_name ILIKE ${idx} OR u.display_name ILIKE ${idx})")
        where_sql = " AND ".join(clauses)
        value = await self._pool.fetchval(
            f"""
            SELECT COUNT(*)::int
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            WHERE {where_sql}
            """,
            *args,
        )
        return int(value or 0)

    async def list_genres(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT genre,
                   COUNT(DISTINCT album_id)::int AS album_count,
                   COUNT(track_id)::int AS track_count
            FROM (
                SELECT DISTINCT
                       unnest(
                           CASE
                               WHEN jsonb_array_length(COALESCE(t.genres, '[]'::jsonb)) > 0 THEN
                                   ARRAY(SELECT jsonb_array_elements_text(t.genres))
                               WHEN NULLIF(TRIM(t.genre), '') IS NOT NULL THEN ARRAY[t.genre]
                               WHEN jsonb_array_length(COALESCE(a.genres, '[]'::jsonb)) > 0 THEN
                                   ARRAY(SELECT jsonb_array_elements_text(a.genres))
                               WHEN NULLIF(TRIM(a.genre), '') IS NOT NULL THEN ARRAY[a.genre]
                               ELSE ARRAY[]::text[]
                           END
                       ) AS genre,
                       a.id AS album_id,
                       t.id AS track_id
                FROM stream_albums a
                JOIN stream_tracks t
                  ON t.album_id = a.id AND t.publish_status = 'published'
                WHERE a.publish_status = 'published'
            ) grouped
            WHERE genre IS NOT NULL AND TRIM(genre) <> ''
            GROUP BY genre
            ORDER BY track_count DESC, genre ASC
            """
        )
        return [dict(row) for row in rows]

    async def list_published_albums_by_genre(
        self,
        genre: str,
        *,
        limit: int = 24,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT a.*,
                   u.display_name AS artist_name,
                   COUNT(t.id)::int AS track_count,
                   COALESCE(SUM(t.play_count), 0)::bigint AS play_count
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN stream_tracks t
              ON t.album_id = a.id AND t.publish_status = 'published'
            WHERE a.publish_status = 'published'
              AND (
                LOWER(TRIM(COALESCE(a.genre, ''))) = LOWER(TRIM($1))
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(COALESCE(a.genres, '[]'::jsonb)) g
                    WHERE LOWER(TRIM(g)) = LOWER(TRIM($1))
                )
              )
            GROUP BY a.id, u.display_name
            HAVING COUNT(t.id) > 0
            ORDER BY a.published_at DESC NULLS LAST, a.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            genre,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    async def list_published_tracks_by_genre(
        self,
        genre: str,
        *,
        limit: int = 24,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT t.*, a.album_name, a.cover_storage_key AS album_cover_storage_key,
                   a.genre AS album_genre, u.display_name AS artist_name
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE t.publish_status = 'published'
              AND a.publish_status = 'published'
              AND (
                LOWER(TRIM(COALESCE(t.genre, a.genre, ''))) = LOWER(TRIM($1))
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(COALESCE(t.genres, '[]'::jsonb)) g
                    WHERE LOWER(TRIM(g)) = LOWER(TRIM($1))
                )
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(COALESCE(a.genres, '[]'::jsonb)) g
                    WHERE LOWER(TRIM(g)) = LOWER(TRIM($1))
                )
              )
            ORDER BY t.published_at DESC NULLS LAST, t.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            genre,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    async def search_published(
        self, query: str, *, limit: int = 24, offset: int = 0
    ) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        rows = await self._pool.fetch(
            """
            SELECT t.*, a.album_name, a.cover_storage_key AS album_cover_storage_key,
                   a.genre AS album_genre, u.display_name AS artist_name
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE t.publish_status = 'published'
              AND a.publish_status = 'published'
              AND (
                t.title ILIKE $1
                OR a.album_name ILIKE $1
                OR u.display_name ILIKE $1
              )
            ORDER BY t.published_at DESC NULLS LAST
            LIMIT $2 OFFSET $3
            """,
            pattern,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    async def count_search_published(self, query: str) -> int:
        pattern = f"%{query.strip()}%"
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE t.publish_status = 'published'
              AND a.publish_status = 'published'
              AND (
                t.title ILIKE $1
                OR a.album_name ILIKE $1
                OR u.display_name ILIKE $1
              )
            """,
            pattern,
        )
        return int(value or 0)

    async def get_track_for_metadata_sync(self, track_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT t.*,
                   a.album_slug,
                   st.external_task_id,
                   st.audio_id_ok AS suno_task_audio_id_ok,
                   st.audio_id_alt AS suno_task_audio_id_alt,
                   st.style AS suno_style,
                   s.lyrics AS song_lyrics,
                   md.genres AS description_genres
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            LEFT JOIN suno_tasks st ON st.id = t.suno_task_id
            LEFT JOIN songs s ON s.id = t.song_id
            LEFT JOIN music_descriptions md ON md.id = s.description_id
            WHERE t.id = $1
            """,
            track_id,
        )
        return dict(row) if row else None

    async def list_tracks_for_metadata_sync(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT t.id
            FROM stream_tracks t
            ORDER BY t.updated_at ASC NULLS FIRST, t.created_at ASC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]

    async def update_track_metadata_sync(
        self,
        track_id: UUID,
        *,
        lyrics: str | None = None,
        duration_seconds: float | None = None,
        genre: str | None = None,
        suno_image_url: str | None = None,
        tags: list[str] | None = None,
        cover_storage_key: str | None = None,
        genres: list[str] | None = None,
        suno_audio_id: str | None = None,
        overwrite: bool = False,
    ) -> None:
        tags_payload = json.dumps(tags) if tags else None
        genres_payload = json.dumps(genres if genres is not None else [])
        audio_id = str(suno_audio_id or "").strip() or None
        if overwrite:
            await self._pool.execute(
                """
                UPDATE stream_tracks
                SET lyrics = COALESCE($2, lyrics),
                    duration_seconds = COALESCE($3, duration_seconds),
                    genre = $4,
                    suno_image_url = COALESCE($5, suno_image_url),
                    tags = COALESCE($6::jsonb, tags),
                    cover_storage_key = COALESCE($7, cover_storage_key),
                    genres = COALESCE($8::jsonb, '[]'::jsonb),
                    suno_audio_id = COALESCE($9, suno_audio_id),
                    updated_at = NOW()
                WHERE id = $1
                """,
                track_id,
                lyrics,
                duration_seconds,
                genre,
                suno_image_url,
                tags_payload,
                cover_storage_key,
                genres_payload,
                audio_id,
            )
            return

        await self._pool.execute(
            """
            UPDATE stream_tracks
            SET lyrics = COALESCE($2, lyrics),
                duration_seconds = COALESCE($3, duration_seconds),
                genre = COALESCE($4, genre),
                suno_image_url = COALESCE($5, suno_image_url),
                tags = COALESCE($6::jsonb, tags),
                cover_storage_key = COALESCE($7, cover_storage_key),
                genres = COALESCE($8::jsonb, genres),
                suno_audio_id = COALESCE($9, suno_audio_id),
                updated_at = NOW()
            WHERE id = $1
            """,
            track_id,
            lyrics,
            duration_seconds,
            genre,
            suno_image_url,
            tags_payload,
            cover_storage_key,
            genres_payload if genres else None,
            audio_id,
        )

    async def update_track_genre(self, track_id: UUID, genre: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE stream_tracks
            SET genre = $2, updated_at = NOW()
            WHERE id = $1
            """,
            track_id,
            genre.strip(),
        )
        return result.endswith("1")

    async def get_suno_stream_context(self, suno_task_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT st.id AS suno_task_id,
                   st.user_id,
                   st.song_id,
                   st.batch_id,
                   st.external_task_id,
                   st.audio_url_ok,
                   st.audio_url_alt,
                   st.audio_id_ok,
                   st.audio_id_alt,
                   st.style AS suno_style,
                   st.source AS source,
                   s.title AS song_title,
                   s.album AS song_album,
                   s.lyrics AS song_lyrics,
                   s.batch_index,
                   s.description_id,
                   md.genres AS description_genres,
                   b.ok_album,
                   b.alt_album
            FROM suno_tasks st
            LEFT JOIN songs s ON s.id = st.song_id
            LEFT JOIN music_descriptions md ON md.id = s.description_id
            LEFT JOIN batches b ON b.id = st.batch_id
            WHERE st.id = $1
            """,
            suno_task_id,
        )
        return dict(row) if row else None

    async def get_batch_profile_logo_path(self, batch_id: UUID, *, channel_role: str) -> str | None:
        row = await self._pool.fetchrow(
            """
            SELECT cp.logo_path
            FROM batches b
            JOIN channel_profiles cp ON cp.id = CASE
                WHEN $2 = 'alt' THEN b.alt_profile_id
                ELSE b.ok_profile_id
            END
            WHERE b.id = $1
            """,
            batch_id,
            channel_role.lower(),
        )
        if not row:
            return None
        value = str(row.get("logo_path") or "").strip()
        return value or None

    async def list_liked_track_ids(self, user_id: UUID) -> list[UUID]:
        rows = await self._pool.fetch(
            """
            SELECT track_id
            FROM stream_track_likes
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [row["track_id"] for row in rows]

    async def list_liked_tracks(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT t.*, a.album_name, a.cover_storage_key AS album_cover_storage_key,
                   a.genre AS album_genre, u.display_name AS artist_name,
                   l.created_at AS liked_at
            FROM stream_track_likes l
            JOIN stream_tracks t ON t.id = l.track_id
            JOIN stream_albums a ON a.id = t.album_id
            JOIN users u ON u.id = t.user_id
            WHERE l.user_id = $1
              AND t.publish_status = 'published'
              AND a.publish_status = 'published'
            ORDER BY l.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    async def count_liked_tracks(self, user_id: UUID) -> int:
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int
            FROM stream_track_likes l
            JOIN stream_tracks t ON t.id = l.track_id
            JOIN stream_albums a ON a.id = t.album_id
            WHERE l.user_id = $1
              AND t.publish_status = 'published'
              AND a.publish_status = 'published'
            """,
            user_id,
        )
        return int(value or 0)

    async def is_track_liked(self, user_id: UUID, track_id: UUID) -> bool:
        value = await self._pool.fetchval(
            """
            SELECT 1 FROM stream_track_likes
            WHERE user_id = $1 AND track_id = $2
            """,
            user_id,
            track_id,
        )
        return value is not None

    async def like_track(self, user_id: UUID, track_id: UUID) -> bool:
        """Return True if a new like was inserted."""
        result = await self._pool.execute(
            """
            INSERT INTO stream_track_likes (user_id, track_id)
            SELECT $1, t.id
            FROM stream_tracks t
            JOIN stream_albums a ON a.id = t.album_id
            WHERE t.id = $2
              AND t.publish_status = 'published'
              AND a.publish_status = 'published'
            ON CONFLICT (user_id, track_id) DO NOTHING
            """,
            user_id,
            track_id,
        )
        return str(result).split()[-1] == "1"

    async def unlike_track(self, user_id: UUID, track_id: UUID) -> bool:
        result = await self._pool.execute(
            """
            DELETE FROM stream_track_likes
            WHERE user_id = $1 AND track_id = $2
            """,
            user_id,
            track_id,
        )
        return str(result).split()[-1] == "1"
