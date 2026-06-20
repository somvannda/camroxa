"""Batch repository with CRUD, song record management, and status aggregation.

Provides batch creation, song record management, status tracking and
aggregation queries for the batch generation pipeline.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.models.domain import Batch, ImageJob, Song, SunoTask
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
        await self._pool.execute(
            """
            INSERT INTO batches
                (id, user_id, ok_profile_id, alt_profile_id, song_count,
                 language, creativity_level, pairing_mode, status,
                 ok_run_dir, alt_run_dir, created_at, updated_at)
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
        logger.info("Created batch %s for user %s (song_count=%d)", batch.id, batch.user_id, batch.song_count)
        return batch

    async def get_batch_by_id(self, batch_id: UUID) -> Batch | None:
        """Retrieve a batch by its ID.

        Args:
            batch_id: The UUID of the batch.

        Returns:
            The Batch domain object, or None if not found.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                   language, creativity_level, pairing_mode, status,
                   ok_run_dir, alt_run_dir, created_at, updated_at
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
        row = await self._pool.fetchrow(
            """
            SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                   language, creativity_level, pairing_mode, status,
                   ok_run_dir, alt_run_dir, created_at, updated_at
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
        rows = await self._pool.fetch(
            """
            SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                   language, creativity_level, pairing_mode, status,
                   ok_run_dir, alt_run_dir, created_at, updated_at
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
        rows = await self._pool.fetch(
            """
            SELECT id, user_id, ok_profile_id, alt_profile_id, song_count,
                   language, creativity_level, pairing_mode, status,
                   ok_run_dir, alt_run_dir, created_at, updated_at
            FROM batches
            ORDER BY created_at DESC
            """
        )
        return [self._row_to_batch(row) for row in rows]

    async def update_batch_status(self, batch_id: UUID, status: str) -> None:
        """Update the status of a batch.

        Args:
            batch_id: The UUID of the batch to update.
            status: The new status value.
        """
        await self._pool.execute(
            """
            UPDATE batches SET status = $2, updated_at = NOW()
            WHERE id = $1
            """,
            batch_id,
            status,
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
                     description_id, structure_id, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
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
                song.status,
            )
        logger.info("Created %d song records for batch %s", len(songs), songs[0].batch_id if songs else "N/A")
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
                   description_id, structure_id, status, created_at, updated_at
            FROM songs
            WHERE batch_id = $1
            ORDER BY batch_index ASC
            """,
            batch_id,
        )
        return [self._row_to_song(row) for row in rows]

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
                   description_id, structure_id, status, created_at, updated_at
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
                   description_id, structure_id, status, created_at, updated_at
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
                 status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW())
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
        )
        return task

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

    async def create_image_job(self, job: ImageJob) -> ImageJob:
        """Insert an image job record.

        Args:
            job: The ImageJob domain object to persist.

        Returns:
            The persisted ImageJob.
        """
        await self._pool.execute(
            """
            INSERT INTO image_jobs
                (id, song_id, user_id, batch_id, profile_id, kind,
                 channel_role, prompt, provider, resolution, style_strength,
                 status, attempt_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
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
            job.status.value,
            job.attempt_count,
        )
        return job

    async def create_image_jobs(self, jobs: list[ImageJob]) -> list[ImageJob]:
        """Bulk-insert image job records.

        Args:
            jobs: List of ImageJob domain objects to persist.

        Returns:
            The persisted image jobs.
        """
        for job in jobs:
            await self.create_image_job(job)
        if jobs:
            logger.info(
                "Created %d image jobs for batch %s", len(jobs), jobs[0].batch_id
            )
        return jobs

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
                   status, attempt_count, output_image_path, error,
                   created_at, updated_at
            FROM image_jobs
            WHERE batch_id = $1
            """,
            batch_id,
        )
        return [self._row_to_image_job(row) for row in rows]

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
            SELECT COUNT(*) FROM suno_tasks
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
            creativity_level=row["creativity_level"],
            pairing_mode=row["pairing_mode"],
            status=row["status"],
            ok_run_dir=row["ok_run_dir"],
            alt_run_dir=row["alt_run_dir"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_song(row: Any) -> Song:
        """Map a database row to a Song domain object."""
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
            status=row["status"],
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
            status=TaskStatus(row["status"]),
            attempt_count=row["attempt_count"],
            output_image_path=row["output_image_path"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
