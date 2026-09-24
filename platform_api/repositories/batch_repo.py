"""Batch repository with CRUD, song record management, and status aggregation.

Provides batch creation, song record management, status tracking and
aggregation queries for the batch generation pipeline.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.models.domain import Batch, BatchChannelAssets, ImageJob, Song, SunoTask
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database Protocol
# ---------------------------------------------------------------------------


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        ...

    async def execute(self, query: str, *args: Any) -> str:
        ...


# ---------------------------------------------------------------------------
# Batch Repository
# ---------------------------------------------------------------------------


class BatchRepository:
    """Repository for batch and song record operations.

    Manages batch CRUD, song record creation and status updates,
    image job creation, and status aggregation queries.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    @staticmethod
    def _is_batch_schema_drift(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "does not exist" in message
            and (
                "planned_from_date" in message
                or "planned_to_date" in message
                or "auto_gen_image" in message
                or "auto_gsuno" in message
            )
        )

    @staticmethod
    def _row_value(row: Any, key: str, default: Any = None) -> Any:
        try:
            return row[key]
        except (KeyError, IndexError):
            return default

    # ------------------------------------------------------------------
    # Batch CRUD
    # ------------------------------------------------------------------

    async def create_batch(self, batch: Batch) -> Batch:
        """Insert a new batch record.

        Args:
            batch: The Batch domain object to persist.

        Returns:
            The persisted Batch with generated timestamps.
        """
        try:
            await self._pool.execute(
                """
                INSERT INTO batches
                    (id, user_id, ok_profile_id, alt_profile_id, song_count,
                     language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image, auto_gsuno,
                     planned_from_date, planned_to_date, ok_run_dir, alt_run_dir, structure_mode, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, NOW(), NOW())
                """,
                batch.id,
                batch.user_id,
                batch.ok_profile_id,
                batch.alt_profile_id,
                batch.song_count,
                batch.language,
                batch.secondary_language,
                batch.creativity_level,
                batch.pairing_mode,
                batch.status,
                batch.auto_gen_image,
                batch.auto_gsuno,
                batch.planned_from_date,
                batch.planned_to_date,
                batch.ok_run_dir,
                batch.alt_run_dir,
                getattr(batch, "structure_mode", "template") or "template",
            )
        except Exception as error:
            if not self._is_batch_schema_drift(error):
                raise
            try:
                await self._pool.execute(
                    """
                    INSERT INTO batches
                        (id, user_id, ok_profile_id, alt_profile_id, song_count,
                         language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image, auto_gsuno,
                         planned_from_date, planned_to_date, ok_run_dir, alt_run_dir, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW(), NOW())
                    """,
                    batch.id,
                    batch.user_id,
                    batch.ok_profile_id,
                    batch.alt_profile_id,
                    batch.song_count,
                    batch.language,
                    batch.secondary_language,
                    batch.creativity_level,
                    batch.pairing_mode,
                    batch.status,
                    batch.auto_gen_image,
                    batch.auto_gsuno,
                    batch.planned_from_date,
                    batch.planned_to_date,
                    batch.ok_run_dir,
                    batch.alt_run_dir,
                )
            except Exception as second_error:
                if not self._is_batch_schema_drift(second_error):
                    raise
                try:
                    await self._pool.execute(
                        """
                        INSERT INTO batches
                            (id, user_id, ok_profile_id, alt_profile_id, song_count,
                             language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image,
                             planned_from_date, planned_to_date, ok_run_dir, alt_run_dir, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW(), NOW())
                        """,
                        batch.id,
                        batch.user_id,
                        batch.ok_profile_id,
                        batch.alt_profile_id,
                        batch.song_count,
                        batch.language,
                        batch.creativity_level,
                        batch.pairing_mode,
                        batch.status,
                        batch.auto_gen_image,
                        batch.planned_from_date,
                        batch.planned_to_date,
                        batch.ok_run_dir,
                        batch.alt_run_dir,
                    )
                except Exception as third_error:
                    if not self._is_batch_schema_drift(third_error):
                        raise
                    await self._pool.execute(
                        """
                        INSERT INTO batches
                            (id, user_id, ok_profile_id, alt_profile_id, song_count,
                             language, secondary_language, creativity_level, pairing_mode, status,
                             ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                        """,
                        batch.id,
                        batch.user_id,
                        batch.ok_profile_id,
                        batch.alt_profile_id,
                        batch.song_count,
                        batch.language,
                        batch.creativity_level,
                        batch.pairing_mode,
                        batch.status,
                        batch.ok_run_dir,
                        batch.alt_run_dir,
                    )
        logger.debug("Created batch %s for user %s (song_count=%d)", batch.id, batch.user_id, batch.song_count)
        return batch

    async def get_batch_by_id(self, batch_id: UUID) -> Batch | None:
        """Retrieve a batch by its ID.

        Args:
            batch_id: The UUID of the batch.

        Returns:
            The Batch domain object, or None if not found.
        """
        try:
            row = await self._pool.fetchrow(
                """
                SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                       language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image, auto_gsuno,
                       planned_from_date, planned_to_date,
                       ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                FROM batches
                WHERE id = $1
                """,
                batch_id,
            )
        except Exception as error:
            if not self._is_batch_schema_drift(error):
                raise
            try:
                row = await self._pool.fetchrow(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           auto_gen_image,
                           false AS auto_gsuno,
                           planned_from_date, planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    WHERE id = $1
                    """,
                    batch_id,
                )
            except Exception as second_error:
                if not self._is_batch_schema_drift(second_error):
                    raise
                row = await self._pool.fetchrow(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           false AS auto_gen_image,
                           false AS auto_gsuno,
                           NULL::date AS planned_from_date, NULL::date AS planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    WHERE id = $1
                    """,
                    batch_id,
                )
        if row is None:
            return None
        return self._row_to_batch(row)

    async def get_batch_for_user(self, batch_id: UUID, user_id: UUID) -> Batch | None:
        """Retrieve a batch by ID scoped to a specific user.

        Args:
            batch_id: The UUID of the batch.
            user_id: The UUID of the owning user.

        Returns:
            The Batch domain object, or None if not found or not owned by user.
        """
        try:
            row = await self._pool.fetchrow(
                """
                SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                       language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image, auto_gsuno,
                       planned_from_date, planned_to_date,
                       ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                FROM batches
                WHERE id = $1 AND user_id = $2
                """,
                batch_id,
                user_id,
            )
        except Exception as error:
            if not self._is_batch_schema_drift(error):
                raise
            try:
                row = await self._pool.fetchrow(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           auto_gen_image,
                           false AS auto_gsuno,
                           planned_from_date, planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    WHERE id = $1 AND user_id = $2
                    """,
                    batch_id,
                    user_id,
                )
            except Exception as second_error:
                if not self._is_batch_schema_drift(second_error):
                    raise
                row = await self._pool.fetchrow(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           false AS auto_gen_image,
                           false AS auto_gsuno,
                           NULL::date AS planned_from_date, NULL::date AS planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    WHERE id = $1 AND user_id = $2
                    """,
                    batch_id,
                    user_id,
                )
        if row is None:
            return None
        return self._row_to_batch(row)

    async def list_batches_for_user(self, user_id: UUID) -> list[Batch]:
        """Return all batches belonging to a user, ordered by creation date descending.

        Implements user-scoped data isolation (Requirement 16.2):
        User-role requests only see their own batches.

        Args:
            user_id: The UUID of the user.

        Returns:
            List of Batch domain objects, ordered by created_at DESC.
        """
        try:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                       language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image, auto_gsuno,
                       planned_from_date, planned_to_date,
                       ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                FROM batches
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id,
            )
        except Exception as error:
            if not self._is_batch_schema_drift(error):
                raise
            try:
                rows = await self._pool.fetch(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           auto_gen_image,
                           false AS auto_gsuno,
                           planned_from_date, planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
            except Exception as second_error:
                if not self._is_batch_schema_drift(second_error):
                    raise
                rows = await self._pool.fetch(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           false AS auto_gen_image,
                           false AS auto_gsuno,
                           NULL::date AS planned_from_date, NULL::date AS planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
        return [self._row_to_batch(row) for row in rows]

    async def list_all_batches(self) -> list[Batch]:
        """Return all batches (Admin bypass — no user scoping).

        Admin-role requests bypass user-scoping per Requirement 16.2.

        Returns:
            List of all Batch domain objects, ordered by created_at DESC.
        """
        try:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                       language, secondary_language, creativity_level, pairing_mode, status, auto_gen_image, auto_gsuno,
                       planned_from_date, planned_to_date,
                       ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                FROM batches
                ORDER BY created_at DESC
                """
            )
        except Exception as error:
            if not self._is_batch_schema_drift(error):
                raise
            try:
                rows = await self._pool.fetch(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           auto_gen_image,
                           false AS auto_gsuno,
                           planned_from_date, planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    ORDER BY created_at DESC
                    """
                )
            except Exception as second_error:
                if not self._is_batch_schema_drift(second_error):
                    raise
                rows = await self._pool.fetch(
                    """
                    SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                           language, secondary_language, creativity_level, pairing_mode, status,
                           false AS auto_gen_image,
                           false AS auto_gsuno,
                           NULL::date AS planned_from_date, NULL::date AS planned_to_date,
                           ok_run_dir, alt_run_dir, ok_album, alt_album, structure_mode,
                       created_at, updated_at
                    FROM batches
                    ORDER BY created_at DESC
                    """
                )
        return [self._row_to_batch(row) for row in rows]

    async def update_batch_status(self, batch_id: UUID, status: str) -> None:
        """Update the status of a batch.

        No-ops (including `updated_at`) when the stored status is already
        `$2`, so desktop Progress sync heartbeats do not look like live work.

        Args:
            batch_id: The UUID of the batch to update.
            status: The new status value.
        """
        await self._pool.execute(
            """
            UPDATE batches SET status = $2, updated_at = NOW()
            WHERE id = $1
              AND status IS DISTINCT FROM $2
            """,
            batch_id,
            status,
        )

    async def update_batch_run_directories(
        self,
        batch_id: UUID,
        *,
        ok_run_dir: str | None,
        alt_run_dir: str | None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE batches
            SET ok_run_dir = $2,
                alt_run_dir = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            batch_id,
            str(ok_run_dir or "").strip() or None,
            str(alt_run_dir or "").strip() or None,
        )

    async def claim_batch_run_directories(
        self,
        batch_id: UUID,
        *,
        ok_run_dir: str | None,
        alt_run_dir: str | None,
    ) -> tuple[str | None, str | None]:
        """First writer wins for run dirs; later drafts keep the locked paths."""
        row = await self._pool.fetchrow(
            """
            UPDATE batches
            SET ok_run_dir = COALESCE(ok_run_dir, $2),
                alt_run_dir = COALESCE(alt_run_dir, $3),
                updated_at = NOW()
            WHERE id = $1
            RETURNING ok_run_dir, alt_run_dir
            """,
            batch_id,
            str(ok_run_dir or "").strip() or None,
            str(alt_run_dir or "").strip() or None,
        )
        if row is None:
            return None, None
        return (
            str(row["ok_run_dir"] or "").strip() or None,
            str(row["alt_run_dir"] or "").strip() or None,
        )

    async def update_batch_channel_albums(
        self,
        batch_id: UUID,
        *,
        ok_album: str | None,
        alt_album: str | None,
    ) -> None:
        try:
            await self._pool.execute(
                """
                UPDATE batches
                SET ok_album = $2,
                    alt_album = $3,
                    updated_at = NOW()
                WHERE id = $1
                """,
                batch_id,
                str(ok_album or "").strip() or None,
                str(alt_album or "").strip() or None,
            )
        except Exception as error:
            if "ok_album" in str(error).lower() or "alt_album" in str(error).lower():
                logger.warning("Skipping batch channel album update because columns are missing.")
                return
            raise

    async def claim_batch_channel_albums(
        self,
        batch_id: UUID,
        *,
        ok_album: str | None,
        alt_album: str | None,
    ) -> tuple[str | None, str | None]:
        """First writer wins for Album 1 / Album 2; parallel drafts cannot overwrite."""
        try:
            row = await self._pool.fetchrow(
                """
                UPDATE batches
                SET ok_album = COALESCE(ok_album, $2),
                    alt_album = COALESCE(alt_album, $3),
                    updated_at = NOW()
                WHERE id = $1
                RETURNING ok_album, alt_album
                """,
                batch_id,
                str(ok_album or "").strip() or None,
                str(alt_album or "").strip() or None,
            )
        except Exception as error:
            if "ok_album" in str(error).lower() or "alt_album" in str(error).lower():
                logger.warning("Skipping batch channel album claim because columns are missing.")
                return (
                    str(ok_album or "").strip() or None,
                    str(alt_album or "").strip() or None,
                )
            raise
        if row is None:
            return None, None
        return (
            str(row["ok_album"] or "").strip() or None,
            str(row["alt_album"] or "").strip() or None,
        )

    # ------------------------------------------------------------------
    # Song Record Management
    # ------------------------------------------------------------------

    async def create_songs(self, songs: list[Song]) -> list[Song]:
        """Bulk-insert song records for a batch.

        Args:
            songs: List of Song domain objects to persist.

        Returns:
            The persisted songs (same objects, timestamps set by DB).
        """
        for song in songs:
            await self._pool.execute(
                """
                INSERT INTO songs
                    (id, batch_id, batch_index, user_id, title, album, lyrics,
                     description_id, structure_id, mood_id, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                """,
                song.id,
                song.batch_id,
                song.batch_index,
                song.user_id,
                song.title,
                song.album,
                song.lyrics,
                song.description_id,
                song.structure_id,
                song.mood_id,
                song.status,
            )
        logger.debug("Created %d song records for batch %s", len(songs), songs[0].batch_id if songs else "N/A")
        return songs

    async def get_songs_by_batch(self, batch_id: UUID) -> list[Song]:
        """Retrieve all songs for a batch, ordered by batch_index.

        Args:
            batch_id: The UUID of the batch.

        Returns:
            List of Song domain objects ordered by batch_index.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, batch_id, batch_index, user_id, title, album, lyrics,
                   description_id, structure_id, mood_id, status, created_at, updated_at
            FROM songs
            WHERE batch_id = $1
            ORDER BY batch_index ASC
            """,
            batch_id,
        )
        return [self._row_to_song(row) for row in rows]

    async def get_song_by_id(self, song_id: UUID) -> Song | None:
        """Retrieve a single song by ID."""
        row = await self._pool.fetchrow(
            """
            SELECT id, batch_id, batch_index, user_id, title, album, lyrics,
                   description_id, structure_id, mood_id, status, created_at, updated_at
            FROM songs
            WHERE id = $1
            """,
            song_id,
        )
        if row is None:
            return None
        return self._row_to_song(row)

    async def get_songs_for_user(self, user_id: UUID) -> list[Song]:
        """Return all songs belonging to a user, ordered by creation date descending.

        Implements user-scoped data isolation (Requirement 16.2):
        User-role requests only see their own songs.

        Args:
            user_id: The UUID of the user.

        Returns:
            List of Song domain objects ordered by created_at DESC.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, batch_id, batch_index, user_id, title, album, lyrics,
                   description_id, structure_id, mood_id, status, created_at, updated_at
            FROM songs
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [self._row_to_song(row) for row in rows]

    async def get_songs_for_user_batch(self, batch_id: UUID, user_id: UUID) -> list[Song]:
        """Retrieve all songs for a batch, scoped to a specific user.

        Ensures a user can only see songs from their own batches.
        Implements user-scoped data isolation (Requirement 16.2).

        Args:
            batch_id: The UUID of the batch.
            user_id: The UUID of the owning user.

        Returns:
            List of Song domain objects ordered by batch_index, or empty if
            the batch doesn't belong to the user.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, batch_id, batch_index, user_id, title, album, lyrics,
                   description_id, structure_id, mood_id, status, created_at, updated_at
            FROM songs
            WHERE batch_id = $1 AND user_id = $2
            ORDER BY batch_index ASC
            """,
            batch_id,
            user_id,
        )
        return [self._row_to_song(row) for row in rows]

    async def update_song_status(self, song_id: UUID, status: str) -> None:
        """Update the status of a song.

        Args:
            song_id: The UUID of the song to update.
            status: The new status value.
        """
        await self._pool.execute(
            """
            UPDATE songs SET status = $2, updated_at = NOW()
            WHERE id = $1
            """,
            song_id,
            status,
        )

    async def update_song_draft(
        self, song_id: UUID, title: str, album: str, lyrics: str
    ) -> None:
        """Update a song with draft generation results.

        Args:
            song_id: The UUID of the song.
            title: The generated title.
            album: The generated album name.
            lyrics: The generated lyrics.
        """
        await self._pool.execute(
            """
            UPDATE songs
            SET title = $2, album = $3, lyrics = $4,
                status = 'draft_ready', updated_at = NOW()
            WHERE id = $1
            """,
            song_id,
            title,
            album,
            lyrics,
        )

    async def update_song_title_keep_status(self, song_id: UUID, title: str) -> None:
        """Update song title without changing status or lyrics."""
        await self._pool.execute(
            """
            UPDATE songs
            SET title = $2, updated_at = NOW()
            WHERE id = $1
            """,
            song_id,
            title,
        )

    async def update_batch_songs_album(self, batch_id: UUID, album: str) -> None:
        """Set album on every song in a batch without changing status/lyrics."""
        await self._pool.execute(
            """
            UPDATE songs
            SET album = $2, updated_at = NOW()
            WHERE batch_id = $1
            """,
            batch_id,
            album,
        )

    async def update_song_suno_sanitize_metadata(
        self,
        song_id: UUID,
        metadata: dict[str, Any],
    ) -> None:
        """Persist Suno sanitize replacement metadata on a song."""
        import json

        await self._pool.execute(
            """
            UPDATE songs
            SET suno_last_sanitize = $2::jsonb,
                updated_at = NOW()
            WHERE id = $1
            """,
            song_id,
            json.dumps(metadata),
        )

    async def increment_suno_auto_retry_count(self, song_id: UUID) -> int:
        """Increment and return the song's Suno auto-retry counter."""
        row = await self._pool.fetchrow(
            """
            UPDATE songs
            SET suno_auto_retry_count = COALESCE(suno_auto_retry_count, 0) + 1,
                updated_at = NOW()
            WHERE id = $1
            RETURNING suno_auto_retry_count
            """,
            song_id,
        )
        if row is None:
            return 0
        return int(row["suno_auto_retry_count"] or 0)

    async def get_suno_auto_retry_count(self, song_id: UUID) -> int:
        """Return how many automatic Suno retries have been attempted for a song."""
        value = await self._pool.fetchval(
            """
            SELECT COALESCE(suno_auto_retry_count, 0)
            FROM songs
            WHERE id = $1
            """,
            song_id,
        )
        return int(value or 0)

    async def count_suno_tasks_for_song(self, song_id: UUID) -> int:
        """Return total Suno task rows linked to a song."""
        value = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int
            FROM suno_tasks
            WHERE song_id = $1
            """,
            song_id,
        )
        return int(value or 0)

    async def list_stuck_suno_pending_songs(
        self,
        *,
        user_id: UUID,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Songs stuck at suno_pending while the latest Suno task is terminal failure."""
        rows = await self._pool.fetch(
            """
            SELECT
                s.id AS song_id,
                s.batch_id,
                st.status AS suno_status,
                st.error_message
            FROM songs s
            JOIN LATERAL (
                SELECT status, error_message
                FROM suno_tasks
                WHERE song_id = s.id
                ORDER BY created_at DESC
                LIMIT 1
            ) st ON TRUE
            WHERE s.user_id = $1
              AND s.status = 'suno_pending'
              AND st.status IN ('failed', 'error', 'cancelled', 'timeout')
            ORDER BY s.updated_at ASC
            LIMIT $2
            """,
            user_id,
            max(1, min(int(limit or 25), 50)),
        )
        return [dict(row) for row in rows]

    async def list_suno_failure_metrics_rows(
        self,
        *,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Return failed Suno tasks with submit-order hints for admin metrics."""
        rows = await self._pool.fetch(
            """
            SELECT
                st.id,
                st.song_id,
                st.status,
                st.error_message,
                st.created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY st.song_id
                    ORDER BY st.created_at ASC, st.id ASC
                ) AS submit_order
            FROM suno_tasks st
            WHERE st.status IN ('failed', 'error', 'cancelled', 'timeout')
              AND st.created_at >= NOW() - make_interval(days => $1)
            ORDER BY st.created_at DESC
            """,
            max(1, min(int(days or 30), 365)),
        )
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Suno Task Management
    # ------------------------------------------------------------------

    async def create_suno_task(self, task: SunoTask) -> SunoTask:
        """Insert a Suno task record linked to a song and batch.

        Args:
            task: The SunoTask domain object to persist.

        Returns:
            The persisted SunoTask.
        """
        await self._pool.execute(
            """
            INSERT INTO suno_tasks
                (id, song_id, user_id, batch_id, request_hash, model,
                 title, lyrics, style, instrumental, external_task_id,
                 status, source, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
            """,
            task.id,
            task.song_id,
            task.user_id,
            task.batch_id,
            task.request_hash,
            task.model,
            task.title,
            task.lyrics,
            task.style,
            task.instrumental,
            task.external_task_id,
            task.status.value,
            getattr(task, "source", None) or "studio",
        )
        return task

    async def create(self, task: SunoTask) -> SunoTask:
        """Compatibility alias for GenerationService task persistence."""
        return await self.create_suno_task(task)

    async def find_by_hash(self, user_id: UUID, request_hash: str) -> SunoTask | None:
        """Find an existing Suno task by request hash for deduplication."""
        row = await self._pool.fetchrow(
            """
            SELECT id, song_id, user_id, batch_id, request_hash, model,
                   title, lyrics, style, instrumental, external_task_id,
                   status, audio_url_ok, audio_url_alt, output_dir_ok,
                   output_dir_alt, downloaded_ok, downloaded_alt,
                   created_at, updated_at
            FROM suno_tasks
            WHERE user_id = $1 AND request_hash = $2
            """,
            user_id,
            request_hash,
        )
        if row is None:
            return None
        return self._row_to_suno_task(row)

    async def link_suno_task(self, task_id: UUID, song_id: UUID, batch_id: UUID) -> None:
        """Attach a persisted Suno task to its owning song and batch."""
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET song_id = $2, batch_id = $3, updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            song_id,
            batch_id,
        )

    async def find_by_external_id(self, external_task_id: str) -> dict[str, Any] | None:
        """Return callback-oriented task data by external Suno task ID."""
        row = await self._pool.fetchrow(
            """
            SELECT id, user_id, song_id, batch_id, external_task_id, status, source
            FROM suno_tasks
            WHERE external_task_id = $1
            """,
            external_task_id,
        )
        if row is None:
            return None
        source = ""
        try:
            source = str(row["source"] or "")
        except (KeyError, TypeError):
            source = ""
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "song_id": row["song_id"],
            "batch_id": row["batch_id"],
            "external_task_id": row["external_task_id"],
            "status": row["status"],
            "source": source,
        }

    async def update_status(
        self,
        task_id: UUID,
        *,
        status: TaskStatus,
        audio_url_ok: str | None = None,
        audio_url_alt: str | None = None,
        audio_id_ok: str | None = None,
        audio_id_alt: str | None = None,
        image_url_ok: str | None = None,
        image_url_alt: str | None = None,
        duration_ok: float | None = None,
        duration_alt: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Compatibility update surface for the callbacks router."""
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET status = $2,
                audio_url_ok = COALESCE(NULLIF(BTRIM($3), ''), audio_url_ok),
                audio_url_alt = COALESCE(NULLIF(BTRIM($4), ''), audio_url_alt),
                error_message = COALESCE($5, error_message),
                audio_id_ok = COALESCE(NULLIF(BTRIM($6), ''), audio_id_ok),
                audio_id_alt = COALESCE(NULLIF(BTRIM($7), ''), audio_id_alt),
                image_url_ok = COALESCE(NULLIF(BTRIM($8), ''), image_url_ok),
                image_url_alt = COALESCE(NULLIF(BTRIM($9), ''), image_url_alt),
                duration_ok = COALESCE($10::double precision, duration_ok),
                duration_alt = COALESCE($11::double precision, duration_alt),
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            status.value,
            audio_url_ok,
            audio_url_alt,
            error_message,
            audio_id_ok,
            audio_id_alt,
            image_url_ok,
            image_url_alt,
            duration_ok,
            duration_alt,
        )

    async def list_pending_suno_downloads(
        self,
        *,
        user_id: UUID,
        limit: int = 20,
        max_age_days: int = 30,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT
                st.id,
                st.song_id,
                st.batch_id,
                st.title,
                st.audio_url_ok,
                st.audio_url_alt,
                st.audio_id_ok,
                st.audio_id_alt,
                st.output_dir_ok,
                st.output_dir_alt,
                st.downloaded_ok,
                st.downloaded_alt,
                s.batch_index,
                b.ok_run_dir,
                b.alt_run_dir,
                altp.folder_name AS alt_profile_folder,
                altp.name AS alt_profile_name
            FROM suno_tasks st
            LEFT JOIN songs s ON s.id = st.song_id
            LEFT JOIN batches b ON b.id = st.batch_id
            LEFT JOIN channel_profiles altp ON altp.id = b.alt_profile_id
            LEFT JOIN batch_channel_assets bca_ok
                ON bca_ok.batch_id = st.batch_id
               AND bca_ok.profile_id = b.ok_profile_id
               AND bca_ok.role = 'OK'
            LEFT JOIN batch_channel_assets bca_alt
                ON bca_alt.batch_id = st.batch_id
               AND bca_alt.profile_id = b.alt_profile_id
               AND bca_alt.role = 'ALT'
            WHERE st.user_id = $1
              AND st.status = $2
              AND COALESCE(st.source, '') <> 'web_music'
              AND (
                (
                  (
                    st.audio_url_ok IS NOT NULL
                    OR COALESCE(NULLIF(BTRIM(st.audio_id_ok), ''), NULL) IS NOT NULL
                  )
                  AND COALESCE(st.downloaded_ok, false) = false
                  AND COALESCE(st.download_unavailable_ok, false) = false
                  AND COALESCE(bca_ok.pipeline_complete, false) = false
                )
                OR
                (
                  (
                    st.audio_url_alt IS NOT NULL
                    OR COALESCE(NULLIF(BTRIM(st.audio_id_alt), ''), NULL) IS NOT NULL
                  )
                  AND COALESCE(st.downloaded_alt, false) = false
                  AND COALESCE(st.download_unavailable_alt, false) = false
                  AND COALESCE(bca_alt.pipeline_complete, false) = false
                )
              )
              AND (
                b.id IS NULL
                OR b.updated_at >= NOW() - make_interval(days => $4)
              )
            ORDER BY st.updated_at DESC, st.created_at DESC
            LIMIT $3
            """,
            user_id,
            TaskStatus.SUCCESS.value,
            max(1, min(int(limit or 20), 100)),
            max(1, min(int(max_age_days or 30), 365)),
        )
        return [dict(row) for row in rows]

    async def list_suno_download_health_candidates(
        self,
        *,
        user_id: UUID,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Success tasks with an undownloaded, not-yet-terminal channel URL.

        Used by the background health probe to detect permanently-dead Suno
        temp URLs and stop the desktop from retrying them forever.
        """
        rows = await self._pool.fetch(
            """
            SELECT st.id,
                   st.external_task_id,
                   st.audio_url_ok,
                   st.audio_url_alt,
                   st.audio_id_ok,
                   st.audio_id_alt,
                   st.downloaded_ok,
                   st.downloaded_alt,
                   st.download_unavailable_ok,
                   st.download_unavailable_alt
            FROM suno_tasks st
            WHERE st.user_id = $1
              AND st.status = $2
              AND COALESCE(st.source, '') <> 'web_music'
              AND (
                (
                  COALESCE(st.downloaded_ok, false) = false
                  AND COALESCE(st.download_unavailable_ok, false) = false
                  AND (
                    st.audio_url_ok IS NOT NULL
                    OR COALESCE(NULLIF(BTRIM(st.audio_id_ok), ''), NULL) IS NOT NULL
                  )
                )
                OR
                (
                  COALESCE(st.downloaded_alt, false) = false
                  AND COALESCE(st.download_unavailable_alt, false) = false
                  AND (
                    st.audio_url_alt IS NOT NULL
                    OR COALESCE(NULLIF(BTRIM(st.audio_id_alt), ''), NULL) IS NOT NULL
                  )
                )
              )
            ORDER BY st.updated_at DESC, st.created_at DESC
            LIMIT $3
            """,
            user_id,
            TaskStatus.SUCCESS.value,
            max(1, min(int(limit or 12), 50)),
        )
        return [dict(row) for row in rows]

    async def mark_suno_download_unavailable(
        self,
        *,
        task_id: UUID,
        variant: str,
        unavailable: bool = True,
    ) -> None:
        """Set/clear the terminal 'source URL is gone' flag for one channel."""
        column = "alt" if str(variant).lower() in {"alt", "secondary"} else "ok"
        await self._pool.execute(
            f"""
            UPDATE suno_tasks
            SET download_unavailable_{column} = $2,
                download_unavailable_at_{column} = CASE WHEN $2 THEN NOW() ELSE NULL END,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            bool(unavailable),
        )

    async def set_suno_audio_url(
        self,
        *,
        task_id: UUID,
        variant: str,
        url: str,
    ) -> None:
        """Point a channel at a working URL and clear its terminal flag."""
        column = "alt" if str(variant).lower() in {"alt", "secondary"} else "ok"
        await self._pool.execute(
            f"""
            UPDATE suno_tasks
            SET audio_url_{column} = $2,
                download_unavailable_{column} = false,
                download_unavailable_at_{column} = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            str(url),
        )

    async def list_stuck_batches(
        self,
        *,
        min_age_seconds: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Account-wide: non-terminal batches with no pipeline activity for a while.

        Used by the pipeline stuck-batch housekeeping scan
        (`PipelineStuckAlertService`, `docs/PLATFORM_WORKERS_REQUIREMENTS.md` §8).

        "Activity" is the most recent `updated_at` across the batch row itself and
        every song/suno_task/image_job/batch_channel_assets row belonging to it —
        not a single `stage` column (this codebase derives that per-role, on read,
        for the desktop/admin progress views; this query intentionally avoids that
        heavier per-role join for a lightweight scheduled scan).

        A batch only counts as "done" (excluded here) once every channel role it's
        actually configured for (OK and/or ALT) has a `batch_channel_assets` row
        with `pipeline_complete = true`. A configured role with no such row yet is
        treated as still running, not stuck-and-abandoned — it only shows up here
        once it's also past `min_age_seconds` with no activity.
        """
        rows = await self._pool.fetch(
            """
            WITH batch_activity AS (
                SELECT
                    b.id AS batch_id,
                    b.user_id,
                    b.status,
                    b.ok_profile_id,
                    b.alt_profile_id,
                    GREATEST(
                        b.updated_at,
                        COALESCE(
                            (SELECT MAX(s.updated_at) FROM songs s WHERE s.batch_id = b.id),
                            b.updated_at
                        ),
                        COALESCE(
                            (SELECT MAX(st.updated_at) FROM suno_tasks st WHERE st.batch_id = b.id),
                            b.updated_at
                        ),
                        COALESCE(
                            (SELECT MAX(ij.updated_at) FROM image_jobs ij WHERE ij.batch_id = b.id),
                            b.updated_at
                        ),
                        COALESCE(
                            (
                                SELECT MAX(bca.updated_at)
                                FROM batch_channel_assets bca
                                WHERE bca.batch_id = b.id
                            ),
                            b.updated_at
                        )
                    ) AS last_activity_at
                FROM batches b
                WHERE b.status = ANY($1::text[])
            ),
            role_completion AS (
                SELECT
                    ba.batch_id,
                    BOOL_AND(COALESCE(bca.pipeline_complete, false)) AS all_roles_complete
                FROM batch_activity ba
                JOIN LATERAL (
                    SELECT 'OK'::text AS role, ba.ok_profile_id AS profile_id
                    WHERE ba.ok_profile_id IS NOT NULL
                    UNION ALL
                    SELECT 'ALT'::text AS role, ba.alt_profile_id AS profile_id
                    WHERE ba.alt_profile_id IS NOT NULL
                ) roles ON true
                LEFT JOIN batch_channel_assets bca
                    ON bca.batch_id = ba.batch_id
                   AND bca.profile_id = roles.profile_id
                   AND bca.role = roles.role
                GROUP BY ba.batch_id
            )
            SELECT
                ba.batch_id,
                ba.user_id,
                u.email AS user_email,
                ba.status,
                ba.last_activity_at,
                EXTRACT(EPOCH FROM (NOW() - ba.last_activity_at))::bigint AS age_seconds
            FROM batch_activity ba
            JOIN role_completion rc ON rc.batch_id = ba.batch_id
            LEFT JOIN users u ON u.id = ba.user_id
            WHERE rc.all_roles_complete = false
              AND (NOW() - ba.last_activity_at) >= make_interval(secs => $2::double precision)
            ORDER BY ba.last_activity_at ASC
            LIMIT $3
            """,
            ["pending", "processing", "partial"],
            max(60, int(min_age_seconds or 900)),
            max(1, min(int(limit or 100), 500)),
        )
        return [dict(row) for row in rows]

    async def list_suno_audio_for_batch(
        self,
        *,
        batch_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Successful Suno audio URLs for one batch, regardless of `downloaded_*` flags.

        Used by the "change run folder + resume" recovery flow, which must be able to
        re-fetch tracks the account already marked downloaded (into a *new* folder) —
        unlike `list_pending_suno_downloads`, which intentionally excludes those.
        """
        rows = await self._pool.fetch(
            """
            SELECT
                st.id,
                st.song_id,
                st.title,
                st.audio_url_ok,
                st.audio_url_alt,
                st.audio_id_ok,
                st.audio_id_alt,
                st.download_unavailable_ok,
                st.download_unavailable_alt,
                s.batch_index
            FROM suno_tasks st
            LEFT JOIN songs s ON s.id = st.song_id
            WHERE st.batch_id = $1
              AND st.user_id = $2
              AND st.status = $3
            ORDER BY s.batch_index ASC NULLS LAST, st.created_at ASC
            """,
            batch_id,
            user_id,
            TaskStatus.SUCCESS.value,
        )
        return [dict(row) for row in rows]

    async def list_reconcilable_suno_tasks(
        self,
        *,
        user_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return Suno tasks that need API polling (pending or success without URLs)."""
        rows = await self._pool.fetch(
            """
            SELECT id, user_id, song_id, batch_id, external_task_id, status,
                   audio_url_ok, audio_url_alt, audio_id_ok, audio_id_alt
            FROM suno_tasks
            WHERE user_id = $1
              AND external_task_id IS NOT NULL
              AND BTRIM(external_task_id) <> ''
              AND (
                status = $2
                OR (
                  status = $3
                  AND (
                    (
                      COALESCE(NULLIF(BTRIM(audio_url_ok), ''), NULL) IS NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM stream_tracks t
                        WHERE t.suno_task_id = suno_tasks.id
                          AND t.variant = 'ok'
                          AND COALESCE(t.storage_key, '') <> ''
                      )
                    )
                    OR (
                      COALESCE(NULLIF(BTRIM(audio_url_alt), ''), NULL) IS NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM stream_tracks t
                        WHERE t.suno_task_id = suno_tasks.id
                          AND t.variant = 'alt'
                          AND COALESCE(t.storage_key, '') <> ''
                      )
                    )
                  )
                )
              )
            ORDER BY created_at ASC
            LIMIT $4
            """,
            user_id,
            TaskStatus.PENDING.value,
            TaskStatus.SUCCESS.value,
            max(1, min(int(limit or 10), 25)),
        )
        return [dict(row) for row in rows]

    async def update_suno_download_state(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        downloaded_ok: bool | None = None,
        downloaded_alt: bool | None = None,
        output_dir_ok: str | None = None,
        output_dir_alt: str | None = None,
    ) -> bool:
        command = await self._pool.execute(
            """
            UPDATE suno_tasks
            SET downloaded_ok = CASE WHEN $3::boolean IS NULL THEN downloaded_ok ELSE $3 END,
                downloaded_alt = CASE WHEN $4::boolean IS NULL THEN downloaded_alt ELSE $4 END,
                output_dir_ok = COALESCE($5, output_dir_ok),
                output_dir_alt = COALESCE($6, output_dir_alt),
                updated_at = NOW()
            WHERE id = $1
              AND user_id = $2
            """,
            task_id,
            user_id,
            downloaded_ok,
            downloaded_alt,
            str(output_dir_ok or "").strip() or None,
            str(output_dir_alt or "").strip() or None,
        )
        return str(command).strip().upper() != "UPDATE 0"

    async def get_suno_tasks_by_batch(self, batch_id: UUID) -> list[SunoTask]:
        """Retrieve all Suno tasks for a batch.

        Args:
            batch_id: The UUID of the batch.

        Returns:
            List of SunoTask domain objects.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, song_id, user_id, batch_id, request_hash, model,
                   title, lyrics, style, instrumental, external_task_id,
                   status, audio_url_ok, audio_url_alt, output_dir_ok,
                   output_dir_alt, downloaded_ok, downloaded_alt,
                   created_at, updated_at
            FROM suno_tasks
            WHERE batch_id = $1
            """,
            batch_id,
        )
        return [self._row_to_suno_task(row) for row in rows]

    async def get_latest_suno_task_for_song(self, song_id: UUID) -> SunoTask | None:
        """Return the most recent Suno task linked to a song, if any."""
        row = await self._pool.fetchrow(
            """
            SELECT id, song_id, user_id, batch_id, request_hash, model,
                   title, lyrics, style, instrumental, external_task_id,
                   status, audio_url_ok, audio_url_alt, output_dir_ok,
                   output_dir_alt, downloaded_ok, downloaded_alt,
                   download_unavailable_ok, download_unavailable_alt,
                   error_message,
                   created_at, updated_at
            FROM suno_tasks
            WHERE song_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            song_id,
        )
        if row is None:
            return None
        return self._row_to_suno_task(row)

    async def get_suno_task_for_user(self, task_id: UUID, user_id: UUID) -> SunoTask | None:
        """Retrieve a Suno task by ID scoped to a specific user.

        Implements user-scoped data isolation (Requirement 16.2):
        User-role requests only see their own Suno tasks.

        Args:
            task_id: The UUID of the Suno task.
            user_id: The UUID of the owning user.

        Returns:
            The SunoTask domain object, or None if not found or not owned by user.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, song_id, user_id, batch_id, request_hash, model,
                   title, lyrics, style, instrumental, external_task_id,
                   status, audio_url_ok, audio_url_alt, output_dir_ok,
                   output_dir_alt, downloaded_ok, downloaded_alt,
                   created_at, updated_at
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2
            """,
            task_id,
            user_id,
        )
        if row is None:
            return None
        return self._row_to_suno_task(row)

    async def get_suno_task_by_id(self, task_id: UUID) -> SunoTask | None:
        """Retrieve a Suno task by ID without user scoping (Admin bypass).

        Admin-role requests bypass user-scoping per Requirement 16.2.

        Args:
            task_id: The UUID of the Suno task.

        Returns:
            The SunoTask domain object, or None if not found.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, song_id, user_id, batch_id, request_hash, model,
                   title, lyrics, style, instrumental, external_task_id,
                   status, audio_url_ok, audio_url_alt, output_dir_ok,
                   output_dir_alt, downloaded_ok, downloaded_alt,
                   created_at, updated_at
            FROM suno_tasks
            WHERE id = $1
            """,
            task_id,
        )
        if row is None:
            return None
        return self._row_to_suno_task(row)

    async def get_suno_tasks_for_user(self, user_id: UUID) -> list[SunoTask]:
        """Return all Suno tasks belonging to a user, ordered by creation date descending.

        Implements user-scoped data isolation (Requirement 16.2):
        User-role requests only see their own Suno tasks.

        Args:
            user_id: The UUID of the user.

        Returns:
            List of SunoTask domain objects ordered by created_at DESC.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, song_id, user_id, batch_id, request_hash, model,
                   title, lyrics, style, instrumental, external_task_id,
                   status, audio_url_ok, audio_url_alt, output_dir_ok,
                   output_dir_alt, downloaded_ok, downloaded_alt,
                   created_at, updated_at
            FROM suno_tasks
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [self._row_to_suno_task(row) for row in rows]

    # ------------------------------------------------------------------
    # Image Job Management
    # ------------------------------------------------------------------

    async def create_image_job(self, job: ImageJob) -> ImageJob | None:
        """Insert an image job record.

        Album slots are unique per ``(batch_id, profile_id, kind, channel_role)``.
        Concurrent Suno completions may race; conflicts are ignored.

        Args:
            job: The ImageJob domain object to persist.

        Returns:
            The persisted ImageJob, or ``None`` when the album slot already exists.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO image_jobs
                (id, song_id, user_id, batch_id, profile_id, kind,
                 channel_role, prompt, provider, resolution, style_strength,
                 input_image_path, style_reference_path, source_job_id,
                 status, attempt_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW(), NOW())
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            job.id,
            job.song_id,
            job.user_id,
            job.batch_id,
            job.profile_id,
            job.kind.value,
            job.channel_role.value,
            job.prompt,
            job.provider,
            job.resolution,
            job.style_strength,
            job.input_image_path,
            job.style_reference_path,
            job.source_job_id,
            job.status.value,
            job.attempt_count,
        )
        return job if row is not None else None

    async def create_image_jobs(self, jobs: list[ImageJob]) -> list[ImageJob]:
        """Bulk-insert image job records.

        When a background insert loses a race (``ON CONFLICT DO NOTHING``), later
        thumbnails in the same payload that pointed at the discarded background id
        are remapped onto the existing album-slot background before insert.

        Args:
            jobs: List of ImageJob domain objects to persist.

        Returns:
            The persisted image jobs (skips album-slot conflicts).
        """
        created: list[ImageJob] = []
        background_id_remap: dict[UUID, UUID] = {}
        for job in jobs:
            if job.kind == ImageKind.THUMBNAIL and job.source_job_id is not None:
                remapped = background_id_remap.get(job.source_job_id)
                if remapped is not None:
                    job.source_job_id = remapped
                else:
                    source = await self.get_image_job_by_id(job.source_job_id, job.user_id)
                    if source is None and job.profile_id is not None and job.batch_id is not None:
                        existing_bg = await self.get_image_job_for_album_slot(
                            batch_id=job.batch_id,
                            profile_id=job.profile_id,
                            kind=ImageKind.BACKGROUND,
                            channel_role=job.channel_role,
                        )
                        if existing_bg is not None:
                            background_id_remap[job.source_job_id] = existing_bg.id
                            job.source_job_id = existing_bg.id

            persisted = await self.create_image_job(job)
            if persisted is not None:
                created.append(persisted)
                if job.kind == ImageKind.BACKGROUND:
                    background_id_remap[job.id] = job.id
            elif (
                job.kind == ImageKind.BACKGROUND
                and job.profile_id is not None
                and job.batch_id is not None
            ):
                existing_bg = await self.get_image_job_for_album_slot(
                    batch_id=job.batch_id,
                    profile_id=job.profile_id,
                    kind=ImageKind.BACKGROUND,
                    channel_role=job.channel_role,
                )
                if existing_bg is not None:
                    background_id_remap[job.id] = existing_bg.id
                    logger.info(
                        "Remapped raced background %s -> existing %s for batch %s",
                        job.id,
                        existing_bg.id,
                        job.batch_id,
                    )
        if created:
            logger.info(
                "Created %d image jobs for batch %s", len(created), created[0].batch_id
            )
        skipped = len(jobs) - len(created)
        if skipped:
            logger.info(
                "Skipped %d duplicate album image job(s) for batch %s",
                skipped,
                jobs[0].batch_id,
            )
        return created

    async def get_image_job_for_album_slot(
        self,
        *,
        batch_id: UUID,
        profile_id: UUID,
        kind: ImageKind | str,
        channel_role: ChannelRole | str,
    ) -> ImageJob | None:
        """Return the image job for one album slot, if present."""
        kind_value = kind.value if isinstance(kind, ImageKind) else str(kind)
        role_value = (
            channel_role.value if isinstance(channel_role, ChannelRole) else str(channel_role)
        )
        row = await self._pool.fetchrow(
            """
            SELECT id, song_id, user_id, batch_id, profile_id, kind,
                   channel_role, prompt, provider, resolution, style_strength,
                   input_image_path, style_reference_path, source_job_id,
                   status, attempt_count, output_image_path, error,
                   created_at, updated_at
            FROM image_jobs
            WHERE batch_id = $1
              AND profile_id = $2
              AND kind = $3
              AND channel_role = $4
            ORDER BY created_at ASC
            LIMIT 1
            """,
            batch_id,
            profile_id,
            kind_value,
            role_value,
        )
        return self._row_to_image_job(row) if row is not None else None

    async def get_image_jobs_by_batch(self, batch_id: UUID) -> list[ImageJob]:
        """Retrieve all image jobs for a batch.

        Args:
            batch_id: The UUID of the batch.

        Returns:
            List of ImageJob domain objects.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, song_id, user_id, batch_id, profile_id, kind,
                   channel_role, prompt, provider, resolution, style_strength,
                   input_image_path, style_reference_path, source_job_id,
                   status, attempt_count, output_image_path, storage_key, error,
                   created_at, updated_at
            FROM image_jobs
            WHERE batch_id = $1
            """,
            batch_id,
        )
        return [self._row_to_image_job(row) for row in rows]

    async def upsert_batch_channel_assets(
        self,
        asset: BatchChannelAssets,
    ) -> BatchChannelAssets:
        row = await self._pool.fetchrow(
            """
            INSERT INTO batch_channel_assets
                (id, batch_id, user_id, profile_id, role, run_dir, source_mode,
                 background_16x9_path, background_9x16_path,
                 thumbnail_16x9_path, thumbnail_9x16_path,
                 pipeline_complete, pipeline_completed_at,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
            ON CONFLICT (batch_id, profile_id, role)
            DO UPDATE SET
                run_dir = COALESCE(NULLIF(EXCLUDED.run_dir, ''), batch_channel_assets.run_dir),
                source_mode = EXCLUDED.source_mode,
                background_16x9_path = COALESCE(
                    NULLIF(EXCLUDED.background_16x9_path, ''),
                    batch_channel_assets.background_16x9_path
                ),
                background_9x16_path = COALESCE(
                    NULLIF(EXCLUDED.background_9x16_path, ''),
                    batch_channel_assets.background_9x16_path
                ),
                thumbnail_16x9_path = COALESCE(
                    NULLIF(EXCLUDED.thumbnail_16x9_path, ''),
                    batch_channel_assets.thumbnail_16x9_path
                ),
                thumbnail_9x16_path = COALESCE(
                    NULLIF(EXCLUDED.thumbnail_9x16_path, ''),
                    batch_channel_assets.thumbnail_9x16_path
                ),
                pipeline_complete = batch_channel_assets.pipeline_complete OR EXCLUDED.pipeline_complete,
                pipeline_completed_at = CASE
                    WHEN batch_channel_assets.pipeline_complete THEN batch_channel_assets.pipeline_completed_at
                    WHEN EXCLUDED.pipeline_complete THEN COALESCE(
                        EXCLUDED.pipeline_completed_at, NOW()
                    )
                    ELSE batch_channel_assets.pipeline_completed_at
                END,
                updated_at = NOW()
            RETURNING id, batch_id, user_id, profile_id, role, run_dir, source_mode,
                      background_16x9_path, background_9x16_path,
                      thumbnail_16x9_path, thumbnail_9x16_path,
                      pipeline_complete, pipeline_completed_at,
                      created_at, updated_at
            """,
            asset.id,
            asset.batch_id,
            asset.user_id,
            asset.profile_id,
            asset.role.value,
            asset.run_dir,
            asset.source_mode,
            asset.background_16x9_path,
            asset.background_9x16_path,
            asset.thumbnail_16x9_path,
            asset.thumbnail_9x16_path,
            bool(asset.pipeline_complete),
            asset.pipeline_completed_at,
        )
        return self._row_to_batch_channel_assets(row)

    async def get_batch_channel_assets_for_batches(
        self,
        user_id: UUID,
        batch_ids: list[UUID],
    ) -> list[BatchChannelAssets]:
        if not batch_ids:
            return []
        rows = await self._pool.fetch(
            """
            SELECT id, batch_id, user_id, profile_id, role, run_dir, source_mode,
                   background_16x9_path, background_9x16_path,
                   thumbnail_16x9_path, thumbnail_9x16_path,
                   pipeline_complete, pipeline_completed_at,
                   created_at, updated_at
            FROM batch_channel_assets
            WHERE user_id = $1 AND batch_id = ANY($2::uuid[])
            """,
            user_id,
            batch_ids,
        )
        return [self._row_to_batch_channel_assets(row) for row in rows]

    async def get_image_jobs_for_user(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None = None,
        statuses: list[str] | None = None,
        limit: int = 200,
    ) -> list[ImageJob]:
        query = """
            SELECT id, song_id, user_id, batch_id, profile_id, kind,
                   channel_role, prompt, provider, resolution, style_strength,
                   input_image_path, style_reference_path, source_job_id,
                   status, attempt_count, output_image_path, storage_key, error,
                   created_at, updated_at
            FROM image_jobs
            WHERE user_id = $1
        """
        args: list[Any] = [user_id]
        param = 2

        if batch_id is not None:
            query += f" AND batch_id = ${param}"
            args.append(batch_id)
            param += 1

        if statuses:
            query += f" AND status = ANY(${param}::text[])"
            args.append(statuses)
            param += 1

        query += f" ORDER BY updated_at DESC LIMIT ${param}"
        args.append(max(1, min(500, int(limit or 200))))

        rows = await self._pool.fetch(query, *args)
        return [self._row_to_image_job(row) for row in rows]

    async def claim_image_jobs_for_run(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None,
        statuses: list[str],
        limit: int,
        job_ids: list[UUID] | None = None,
    ) -> list[ImageJob]:
        if limit <= 0:
            return []

        resolved_statuses = [str(value or "").strip() for value in (statuses or []) if str(value or "").strip()]
        if not resolved_statuses:
            return []
        resolved_job_ids = [job_id for job_id in (job_ids or []) if job_id is not None]
        if job_ids is not None and not resolved_job_ids:
            return []

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    WITH candidates AS (
                        SELECT id
                        FROM image_jobs
                        WHERE user_id = $1
                          AND ($2::uuid IS NULL OR batch_id = $2)
                          AND status = ANY($3::text[])
                          AND ($6::uuid[] IS NULL OR id = ANY($6::uuid[]))
                        ORDER BY updated_at DESC
                        FOR UPDATE SKIP LOCKED
                        LIMIT $4
                    )
                    UPDATE image_jobs AS j
                    SET status = $5,
                        error = NULL,
                        updated_at = NOW()
                    FROM candidates
                    WHERE j.id = candidates.id
                    RETURNING j.id, j.song_id, j.user_id, j.batch_id, j.profile_id, j.kind,
                              j.channel_role, j.prompt, j.provider, j.resolution, j.style_strength,
                              j.input_image_path, j.style_reference_path, j.source_job_id,
                              j.status, j.attempt_count, j.output_image_path, j.error,
                              j.created_at, j.updated_at
                    """,
                    user_id,
                    batch_id,
                    resolved_statuses,
                    max(1, min(200, int(limit))),
                    TaskStatus.RUNNING.value,
                    resolved_job_ids or None,
                )
        return [self._row_to_image_job(row) for row in rows]

    async def get_image_job_by_id(self, job_id: UUID, user_id: UUID) -> ImageJob | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, song_id, user_id, batch_id, profile_id, kind,
                   channel_role, prompt, provider, resolution, style_strength,
                   input_image_path, style_reference_path, source_job_id,
                   status, attempt_count, output_image_path, storage_key, error,
                   created_at, updated_at
            FROM image_jobs
            WHERE id = $1 AND user_id = $2
            """,
            job_id,
            user_id,
        )
        if row is None:
            return None
        return self._row_to_image_job(row)

    async def update_image_job_storage_key(self, job_id: UUID, user_id: UUID, *, storage_key: str) -> None:
        """Record the durable Backblaze key for an image job's archived output.

        Best-effort archival metadata — never blocks the primary local-cache path.
        """
        await self._pool.execute(
            """
            UPDATE image_jobs
            SET storage_key = $3,
                updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            """,
            job_id,
            user_id,
            storage_key,
        )

    async def update_image_job_prompt(
        self,
        job_id: UUID,
        user_id: UUID,
        *,
        prompt: str,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE image_jobs
            SET prompt = $3,
                updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            """,
            job_id,
            user_id,
            prompt,
        )

    async def update_image_job_status(
        self,
        job_id: UUID,
        user_id: UUID,
        *,
        status: TaskStatus,
        output_image_path: str | None = None,
        error: str | None = None,
        provider: str | None = None,
        attempt_count: int | None = None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE image_jobs
            SET status = $3,
                output_image_path = COALESCE($4, output_image_path),
                error = $5,
                provider = COALESCE($6, provider),
                attempt_count = COALESCE($7, attempt_count),
                updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            """,
            job_id,
            user_id,
            status.value,
            output_image_path,
            error,
            provider,
            attempt_count,
        )

    async def requeue_auto_retry_failed_jobs(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None = None,
        max_attempts: int = 3,
        limit: int = 200,
    ) -> int:
        """Re-queue failed jobs that still have auto-retry attempts left.

        Skips fail-budget / quota messages so we do not spin forever when blocked.
        """
        max_attempts = max(1, min(8, int(max_attempts)))
        limit = max(1, min(500, int(limit)))
        result = await self._pool.execute(
            """
            UPDATE image_jobs
            SET status = 'pending',
                updated_at = NOW()
            WHERE id IN (
                SELECT id
                FROM image_jobs
                WHERE user_id = $1
                  AND ($2::uuid IS NULL OR batch_id = $2)
                  AND status = 'failed'
                  AND COALESCE(attempt_count, 0) < $3
                  AND COALESCE(error, '') !~* 'daily fail/retry budget exceeded'
                  AND COALESCE(error, '') !~* 'insufficient credits'
                  AND COALESCE(error, '') !~* 'quota exceeded'
                ORDER BY updated_at ASC
                LIMIT $4
            )
            """,
            user_id,
            batch_id,
            max_attempts,
            limit,
        )
        return int(str(result).split()[-1]) if result else 0

    async def reset_image_jobs(
        self,
        user_id: UUID,
        *,
        job_ids: list[UUID] | None = None,
        batch_id: UUID | None = None,
        include_success: bool = False,
    ) -> int:
        if not job_ids and batch_id is None:
            return 0

        query = """
            UPDATE image_jobs
            SET status = $2,
                error = NULL,
                output_image_path = NULL,
                attempt_count = 0,
                updated_at = NOW()
            WHERE user_id = $1
        """
        args: list[Any] = [user_id, TaskStatus.PENDING.value]
        param = 3

        if batch_id is not None:
            query += f" AND batch_id = ${param}"
            args.append(batch_id)
            param += 1

        if job_ids:
            query += f" AND id = ANY(${param}::uuid[])"
            args.append(job_ids)
            param += 1

        if include_success:
            # Force regenerate: reset any status and drop locked sample refs so a new
            # Category sample can be chosen (or Prompt only can run without the old base).
            query = """
                UPDATE image_jobs
                SET status = $2,
                    error = NULL,
                    output_image_path = NULL,
                    input_image_path = NULL,
                    style_reference_path = NULL,
                    attempt_count = 0,
                    updated_at = NOW()
                WHERE user_id = $1
            """
            args = [user_id, TaskStatus.PENDING.value]
            param = 3
            if batch_id is not None:
                query += f" AND batch_id = ${param}"
                args.append(batch_id)
                param += 1
            if job_ids:
                query += f" AND id = ANY(${param}::uuid[])"
                args.append(job_ids)
                param += 1
        else:
            query += """
                AND (
                    status = ANY(ARRAY['failed','cancelled','running']::text[])
                    OR (status = 'pending' AND error IS NOT NULL)
                )
            """
        result = await self._pool.execute(query, *args)
        return int(str(result).split()[-1]) if result else 0

    async def clear_image_jobs(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None = None,
        statuses: list[str] | None = None,
    ) -> int:
        query = "DELETE FROM image_jobs WHERE user_id = $1"
        args: list[Any] = [user_id]
        param = 2

        if batch_id is not None:
            query += f" AND batch_id = ${param}"
            args.append(batch_id)
            param += 1

        if statuses:
            query += f" AND status = ANY(${param}::text[])"
            args.append(statuses)
            param += 1

        result = await self._pool.execute(query, *args)
        return int(str(result).split()[-1]) if result else 0

    # ------------------------------------------------------------------
    # Status Aggregation Queries (Requirement 13.5)
    # ------------------------------------------------------------------

    async def get_batch_status_counters(self, batch_id: UUID) -> dict[str, int]:
        """Aggregate batch status counters across songs, suno tasks, and image jobs.

        Returns a dict with keys:
            total_songs, drafts_completed, drafts_failed,
            suno_submitted, suno_completed, suno_failed,
            audio_downloaded, images_completed

        Args:
            batch_id: The UUID of the batch.

        Returns:
            Status counter dictionary.
        """
        # Song status counts
        song_rows = await self._pool.fetch(
            """
            SELECT status, COUNT(*) as cnt
            FROM songs
            WHERE batch_id = $1
            GROUP BY status
            """,
            batch_id,
        )
        song_counts: dict[str, int] = {row["status"]: row["cnt"] for row in song_rows}
        total_songs = sum(song_counts.values())

        # Suno task status counts
        suno_rows = await self._pool.fetch(
            """
            SELECT status, COUNT(*) as cnt
            FROM suno_tasks
            WHERE batch_id = $1
            GROUP BY status
            """,
            batch_id,
        )
        suno_counts: dict[str, int] = {row["status"]: row["cnt"] for row in suno_rows}

        # Suno download counts
        downloaded_count = await self._pool.fetchval(
            """
            SELECT COUNT(DISTINCT song_id) FROM suno_tasks
            WHERE batch_id = $1 AND (downloaded_ok = true OR downloaded_alt = true)
            """,
            batch_id,
        ) or 0

        # Image job completed count
        images_completed = await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM image_jobs
            WHERE batch_id = $1 AND status = 'success'
            """,
            batch_id,
        ) or 0

        return {
            "total_songs": total_songs,
            "drafts_completed": song_counts.get("draft_ready", 0)
            + song_counts.get("suno_pending", 0)
            + song_counts.get("suno_success", 0)
            + song_counts.get("suno_failed", 0),
            "drafts_failed": song_counts.get("draft_failed", 0),
            "suno_submitted": sum(suno_counts.values()),
            "suno_completed": suno_counts.get("success", 0),
            "suno_failed": suno_counts.get("failed", 0),
            "audio_downloaded": downloaded_count,
            "images_completed": images_completed,
        }

    # ------------------------------------------------------------------
    # Row Mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_batch(row: Any) -> Batch:
        """Map a database row to a Batch domain object."""
        return Batch(
            id=row["id"],
            user_id=row["user_id"],
            ok_profile_id=row["ok_profile_id"],
            alt_profile_id=row["alt_profile_id"],
            song_count=row["song_count"],
            language=row["language"],
            secondary_language=BatchRepository._row_value(row, "secondary_language"),
            creativity_level=row["creativity_level"],
            pairing_mode=row["pairing_mode"],
            status=row["status"],
            auto_gen_image=bool(BatchRepository._row_value(row, "auto_gen_image", False)),
            auto_gsuno=bool(BatchRepository._row_value(row, "auto_gsuno", False)),
            planned_from_date=BatchRepository._row_value(row, "planned_from_date"),
            planned_to_date=BatchRepository._row_value(row, "planned_to_date"),
            ok_run_dir=row["ok_run_dir"],
            alt_run_dir=row["alt_run_dir"],
            ok_album=BatchRepository._row_value(row, "ok_album"),
            alt_album=BatchRepository._row_value(row, "alt_album"),
            structure_mode=str(BatchRepository._row_value(row, "structure_mode") or "template"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def delete_batch_cascade(self, batch_id: UUID, user_id: UUID) -> bool:
        """Hard-delete a batch and dependent pipeline rows owned by the user.

        Child tables that reference songs/batches without ON DELETE CASCADE are
        cleared first. Streaming catalog rows that optionally reference the batch
        are nulled rather than deleted.

        Returns:
            True when the batch row was deleted.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                owned = await conn.fetchval(
                    """
                    SELECT 1 FROM batches
                    WHERE id = $1 AND user_id = $2
                    """,
                    batch_id,
                    user_id,
                )
                if owned is None:
                    return False

                await conn.execute(
                    """
                    DELETE FROM youtube_upload_jobs
                    WHERE batch_id = $1
                       OR song_id IN (SELECT id FROM songs WHERE batch_id = $1)
                    """,
                    batch_id,
                )
                await conn.execute(
                    """
                    DELETE FROM image_jobs
                    WHERE batch_id = $1
                       OR song_id IN (SELECT id FROM songs WHERE batch_id = $1)
                    """,
                    batch_id,
                )
                await conn.execute(
                    """
                    DELETE FROM suno_tasks
                    WHERE batch_id = $1
                       OR song_id IN (SELECT id FROM songs WHERE batch_id = $1)
                    """,
                    batch_id,
                )
                # Optional FKs (ON DELETE SET NULL) — clear before song/batch delete.
                # Stream tables may be absent on older local DBs; ignore missing relations.
                for query in (
                    """
                    UPDATE stream_tracks
                    SET song_id = NULL
                    WHERE song_id IN (SELECT id FROM songs WHERE batch_id = $1)
                    """,
                    """
                    UPDATE stream_upload_jobs
                    SET song_id = NULL,
                        batch_id = NULL
                    WHERE batch_id = $1
                       OR song_id IN (SELECT id FROM songs WHERE batch_id = $1)
                    """,
                    """
                    UPDATE stream_albums
                    SET batch_id = NULL
                    WHERE batch_id = $1
                    """,
                ):
                    try:
                        await conn.execute(query, batch_id)
                    except Exception as exc:
                        if "does not exist" not in str(exc).lower():
                            raise
                        logger.debug(
                            "Skipping stream cleanup for batch %s: %s",
                            batch_id,
                            exc,
                        )
                await conn.execute(
                    "DELETE FROM songs WHERE batch_id = $1",
                    batch_id,
                )
                # batch_channel_assets cascades from batches
                result = await conn.execute(
                    """
                    DELETE FROM batches
                    WHERE id = $1 AND user_id = $2
                    """,
                    batch_id,
                    user_id,
                )
                deleted = int(str(result).split()[-1]) if result else 0
                return deleted > 0

    @staticmethod
    def _row_to_song(row: Any) -> Song:
        """Map a database row to a Song domain object."""
        suno_last_sanitize = BatchRepository._row_value(row, "suno_last_sanitize")
        if isinstance(suno_last_sanitize, str):
            import json

            try:
                suno_last_sanitize = json.loads(suno_last_sanitize)
            except json.JSONDecodeError:
                suno_last_sanitize = None
        return Song(
            id=row["id"],
            batch_id=row["batch_id"],
            batch_index=row["batch_index"],
            user_id=row["user_id"],
            title=row["title"],
            album=row["album"],
            lyrics=row["lyrics"],
            description_id=row["description_id"],
            structure_id=row["structure_id"],
            mood_id=BatchRepository._row_value(row, "mood_id"),
            status=row["status"],
            suno_last_sanitize=suno_last_sanitize if isinstance(suno_last_sanitize, dict) else None,
            suno_auto_retry_count=int(BatchRepository._row_value(row, "suno_auto_retry_count", 0) or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_suno_task(row: Any) -> SunoTask:
        """Map a database row to a SunoTask domain object."""
        return SunoTask(
            id=row["id"],
            song_id=row["song_id"],
            user_id=row["user_id"],
            batch_id=row["batch_id"],
            request_hash=row["request_hash"],
            model=row["model"],
            title=row["title"],
            lyrics=row["lyrics"],
            style=row["style"],
            instrumental=row["instrumental"],
            external_task_id=row["external_task_id"],
            status=TaskStatus(row["status"]),
            audio_url_ok=row["audio_url_ok"],
            audio_url_alt=row["audio_url_alt"],
            output_dir_ok=row["output_dir_ok"],
            output_dir_alt=row["output_dir_alt"],
            downloaded_ok=row["downloaded_ok"],
            downloaded_alt=row["downloaded_alt"],
            download_unavailable_ok=(
                bool(row["download_unavailable_ok"])
                if "download_unavailable_ok" in row
                else False
            ),
            download_unavailable_alt=(
                bool(row["download_unavailable_alt"])
                if "download_unavailable_alt" in row
                else False
            ),
            error_message=row["error_message"] if "error_message" in row else None,
            source=str(row["source"] or "studio") if "source" in row else "studio",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_image_job(row: Any) -> ImageJob:
        """Map a database row to an ImageJob domain object."""
        return ImageJob(
            id=row["id"],
            song_id=row["song_id"],
            user_id=row["user_id"],
            batch_id=row["batch_id"],
            profile_id=row["profile_id"],
            kind=ImageKind(row["kind"]),
            channel_role=ChannelRole(row["channel_role"]),
            prompt=row["prompt"],
            provider=row["provider"],
            resolution=row["resolution"],
            style_strength=float(row["style_strength"]) if row["style_strength"] else 0.6,
            input_image_path=row.get("input_image_path"),
            style_reference_path=row.get("style_reference_path"),
            source_job_id=row.get("source_job_id"),
            status=TaskStatus(row["status"]),
            attempt_count=row["attempt_count"],
            output_image_path=row["output_image_path"],
            storage_key=row.get("storage_key"),
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_batch_channel_assets(row: Any) -> BatchChannelAssets:
        return BatchChannelAssets(
            id=row["id"],
            batch_id=row["batch_id"],
            user_id=row["user_id"],
            profile_id=row["profile_id"],
            role=ChannelRole(row["role"]),
            run_dir=row["run_dir"],
            source_mode=row["source_mode"],
            background_16x9_path=row["background_16x9_path"],
            background_9x16_path=row["background_9x16_path"],
            thumbnail_16x9_path=row["thumbnail_16x9_path"],
            thumbnail_9x16_path=row["thumbnail_9x16_path"],
            pipeline_complete=bool(row.get("pipeline_complete", False)),
            pipeline_completed_at=row.get("pipeline_completed_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
