"""Channel profile repository with asyncpg-based CRUD operations.

Provides profile creation, update, deletion, listing (ordered by name ASC),
count per user, and uniqueness enforcement (user_id + name).

Requirements: 8.1, 8.2, 8.3, 8.5, 8.6, 8.7
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import ChannelProfile

logger = logging.getLogger(__name__)


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single row."""
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        ...


def _row_to_profile(row: Any) -> ChannelProfile:
    """Convert an asyncpg Record to a ChannelProfile domain object."""
    return ChannelProfile(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        folder_name=row.get("folder_name"),
        run_prefix=row.get("run_prefix"),
        logo_path=row.get("logo_path"),
        video_template_id=row.get("video_template_id"),
        reel_template_id=row.get("reel_template_id"),
        output_resolution=row.get("output_resolution", "1920x1080"),
        image_config=row.get("image_config") or {},
        youtube_config=row.get("youtube_config") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# All columns returned from SELECT queries
_SELECT_COLS = """
    id, user_id, name, folder_name, run_prefix, logo_path,
    video_template_id, reel_template_id, output_resolution,
    image_config, youtube_config, created_at, updated_at
"""


class ProfileRepository:
    """Repository for channel profile CRUD operations using asyncpg.

    Enforces the UNIQUE(user_id, name) constraint at the database level
    and provides ordered listing and count queries.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def create(self, profile: ChannelProfile) -> ChannelProfile:
        """Insert a new channel profile.

        The database enforces the UNIQUE(user_id, name) constraint.
        Callers should catch asyncpg.UniqueViolationError if needed.

        Args:
            profile: The ChannelProfile domain object to persist.

        Returns:
            The persisted ChannelProfile with server-assigned timestamps.
        """
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO channel_profiles (
                id, user_id, name, folder_name, run_prefix, logo_path,
                video_template_id, reel_template_id, output_resolution,
                image_config, youtube_config, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
            RETURNING {_SELECT_COLS}
            """,
            profile.id,
            profile.user_id,
            profile.name,
            profile.folder_name,
            profile.run_prefix,
            profile.logo_path,
            profile.video_template_id,
            profile.reel_template_id,
            profile.output_resolution,
            profile.image_config,
            profile.youtube_config,
        )
        return _row_to_profile(row)

    async def get_by_id(self, profile_id: UUID) -> ChannelProfile | None:
        """Return the profile with the given ID, or None if not found.

        Note: This method does NOT scope by user_id. Use get_by_id_for_user
        for user-scoped access (Requirement 16.2).

        Args:
            profile_id: The UUID of the profile to look up.

        Returns:
            The ChannelProfile domain object, or None if not found.
        """
        row = await self._pool.fetchrow(
            f"""
            SELECT {_SELECT_COLS}
            FROM channel_profiles
            WHERE id = $1
            """,
            profile_id,
        )
        if row is None:
            return None
        return _row_to_profile(row)

    async def get_by_id_for_user(self, profile_id: UUID, user_id: UUID) -> ChannelProfile | None:
        """Return the profile with the given ID, scoped to a specific user.

        Implements user-scoped data isolation (Requirement 16.2):
        User-role requests only see their own profiles.

        Args:
            profile_id: The UUID of the profile to look up.
            user_id: The UUID of the owning user.

        Returns:
            The ChannelProfile domain object, or None if not found or not owned by user.
        """
        row = await self._pool.fetchrow(
            f"""
            SELECT {_SELECT_COLS}
            FROM channel_profiles
            WHERE id = $1 AND user_id = $2
            """,
            profile_id,
            user_id,
        )
        if row is None:
            return None
        return _row_to_profile(row)

    async def get_by_user_and_name(
        self, user_id: UUID, name: str
    ) -> ChannelProfile | None:
        """Return the profile matching a user and name combination.

        Used to check uniqueness before creation.

        Args:
            user_id: The UUID of the user.
            name: The profile name to look up.

        Returns:
            The ChannelProfile domain object, or None if not found.
        """
        row = await self._pool.fetchrow(
            f"""
            SELECT {_SELECT_COLS}
            FROM channel_profiles
            WHERE user_id = $1 AND name = $2
            """,
            user_id,
            name,
        )
        if row is None:
            return None
        return _row_to_profile(row)

    async def update(
        self, profile_id: UUID, user_id: UUID, **fields: Any
    ) -> ChannelProfile | None:
        """Update specified fields on a profile, scoped to the owning user.

        Only the provided keyword arguments are updated. The ``updated_at``
        timestamp is always refreshed. The user_id check ensures that a
        profile cannot be updated by a different user.

        Args:
            profile_id: The UUID of the profile to update.
            user_id: The UUID of the owning user (ownership check).
            **fields: Column names and their new values.

        Returns:
            The updated ChannelProfile, or None if not found / not owned.
        """
        if not fields:
            return await self.get_by_id(profile_id)

        set_parts: list[str] = []
        values: list[Any] = []
        param_idx = 1

        for col, val in fields.items():
            set_parts.append(f"{col} = ${param_idx}")
            values.append(val)
            param_idx += 1

        # Always update updated_at
        set_parts.append(f"updated_at = ${param_idx}")
        values.append(datetime.now(timezone.utc))
        param_idx += 1

        # WHERE clause parameters
        values.append(profile_id)
        id_param = param_idx
        param_idx += 1

        values.append(user_id)
        user_param = param_idx

        query = f"""
            UPDATE channel_profiles
            SET {', '.join(set_parts)}
            WHERE id = ${id_param} AND user_id = ${user_param}
            RETURNING {_SELECT_COLS}
        """

        row = await self._pool.fetchrow(query, *values)
        if row is None:
            return None
        return _row_to_profile(row)

    async def delete(self, profile_id: UUID, user_id: UUID) -> bool:
        """Delete a profile, scoped to the owning user.

        Dissociates the profile from any batch assignments (ok_profile_id,
        alt_profile_id) before removing it, so in-progress batches continue
        using the configuration captured at batch creation.

        Args:
            profile_id: The UUID of the profile to delete.
            user_id: The UUID of the owning user (ownership check).

        Returns:
            True if the profile was found and deleted, False otherwise.
        """
        # First verify ownership
        row = await self._pool.fetchrow(
            """
            SELECT id FROM channel_profiles
            WHERE id = $1 AND user_id = $2
            """,
            profile_id,
            user_id,
        )
        if row is None:
            return False

        # Dissociate from batch assignments
        await self._pool.execute(
            """
            UPDATE batches SET ok_profile_id = NULL
            WHERE ok_profile_id = $1
            """,
            profile_id,
        )
        await self._pool.execute(
            """
            UPDATE batches SET alt_profile_id = NULL
            WHERE alt_profile_id = $1
            """,
            profile_id,
        )

        # Dissociate from image jobs
        await self._pool.execute(
            """
            UPDATE image_jobs SET profile_id = NULL
            WHERE profile_id = $1
            """,
            profile_id,
        )

        # Now delete the profile
        result = await self._pool.execute(
            """
            DELETE FROM channel_profiles
            WHERE id = $1 AND user_id = $2
            """,
            profile_id,
            user_id,
        )
        # asyncpg returns "DELETE N" where N is the affected row count
        return result == "DELETE 1"

    async def list_for_user(self, user_id: UUID) -> list[ChannelProfile]:
        """Return all profiles for a user, ordered by name ascending.

        Args:
            user_id: The UUID of the user.

        Returns:
            List of ChannelProfile domain objects, ordered by name ASC.
        """
        rows = await self._pool.fetch(
            f"""
            SELECT {_SELECT_COLS}
            FROM channel_profiles
            WHERE user_id = $1
            ORDER BY name ASC
            """,
            user_id,
        )
        return [_row_to_profile(row) for row in rows]

    async def count_for_user(self, user_id: UUID) -> int:
        """Return the number of profiles owned by a user.

        Args:
            user_id: The UUID of the user.

        Returns:
            The count of profiles belonging to the user.
        """
        result = await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM channel_profiles WHERE user_id = $1
            """,
            user_id,
        )
        return result or 0
