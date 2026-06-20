"""Music prompt repository with asyncpg-based CRUD operations.

Provides CRUD for music_descriptions and music_structures tables,
matchKey-based pairing lookup for batch generation.

Requirements: 9.1, 9.2, 9.3, 9.6
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import MusicDescription, MusicStructure

logger = logging.getLogger(__name__)


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> str: ...


# ---------------------------------------------------------------------------
# Row converters
# ---------------------------------------------------------------------------

_DESC_SELECT_COLS = "id, name, content, match_key, created_at, updated_at"
_STRUCT_SELECT_COLS = "id, name, content, match_key, created_at, updated_at"


def _row_to_description(row: Any) -> MusicDescription:
    """Convert an asyncpg Record to a MusicDescription domain object."""
    return MusicDescription(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        match_key=row["match_key"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_structure(row: Any) -> MusicStructure:
    """Convert an asyncpg Record to a MusicStructure domain object."""
    return MusicStructure(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        match_key=row["match_key"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Prompt Repository
# ---------------------------------------------------------------------------


class PromptRepository:
    """Repository for music description and structure CRUD operations.

    Handles persistence for the music_descriptions and music_structures
    tables, including matchKey-based pairing lookup for batch generation.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    # -----------------------------------------------------------------------
    # Music Descriptions
    # -----------------------------------------------------------------------

    async def create_description(self, desc: MusicDescription) -> MusicDescription:
        """Insert a new music description.

        The database enforces the UNIQUE(name) constraint.

        Args:
            desc: The MusicDescription domain object to persist.

        Returns:
            The persisted MusicDescription with server-assigned timestamps.
        """
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO music_descriptions (id, name, content, match_key, created_at, updated_at)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            RETURNING {_DESC_SELECT_COLS}
            """,
            desc.id,
            desc.name,
            desc.content,
            desc.match_key,
        )
        return _row_to_description(row)

    async def get_description_by_id(self, desc_id: UUID) -> MusicDescription | None:
        """Return the description with the given ID, or None if not found."""
        row = await self._pool.fetchrow(
            f"SELECT {_DESC_SELECT_COLS} FROM music_descriptions WHERE id = $1",
            desc_id,
        )
        if row is None:
            return None
        return _row_to_description(row)

    async def get_description_by_name(self, name: str) -> MusicDescription | None:
        """Return the description matching the given name, or None."""
        row = await self._pool.fetchrow(
            f"SELECT {_DESC_SELECT_COLS} FROM music_descriptions WHERE name = $1",
            name,
        )
        if row is None:
            return None
        return _row_to_description(row)

    async def list_descriptions(self) -> list[MusicDescription]:
        """Return all music descriptions ordered by name ascending."""
        rows = await self._pool.fetch(
            f"SELECT {_DESC_SELECT_COLS} FROM music_descriptions ORDER BY name ASC"
        )
        return [_row_to_description(row) for row in rows]

    async def update_description(
        self, desc_id: UUID, **fields: Any
    ) -> MusicDescription | None:
        """Update specified fields on a music description.

        Args:
            desc_id: The UUID of the description to update.
            **fields: Column names and their new values.

        Returns:
            The updated MusicDescription, or None if not found.
        """
        if not fields:
            return await self.get_description_by_id(desc_id)

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

        # WHERE clause
        values.append(desc_id)
        id_param = param_idx

        query = f"""
            UPDATE music_descriptions
            SET {', '.join(set_parts)}
            WHERE id = ${id_param}
            RETURNING {_DESC_SELECT_COLS}
        """
        row = await self._pool.fetchrow(query, *values)
        if row is None:
            return None
        return _row_to_description(row)

    async def delete_description(self, desc_id: UUID) -> bool:
        """Delete a music description by ID.

        Dissociates from songs referencing this description (sets to NULL).

        Args:
            desc_id: The UUID of the description to delete.

        Returns:
            True if the description was found and deleted, False otherwise.
        """
        # Dissociate from songs
        await self._pool.execute(
            "UPDATE songs SET description_id = NULL WHERE description_id = $1",
            desc_id,
        )
        result = await self._pool.execute(
            "DELETE FROM music_descriptions WHERE id = $1",
            desc_id,
        )
        return result == "DELETE 1"

    # -----------------------------------------------------------------------
    # Music Structures
    # -----------------------------------------------------------------------

    async def create_structure(self, struct: MusicStructure) -> MusicStructure:
        """Insert a new music structure.

        The database enforces the UNIQUE(name) constraint.

        Args:
            struct: The MusicStructure domain object to persist.

        Returns:
            The persisted MusicStructure with server-assigned timestamps.
        """
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO music_structures (id, name, content, match_key, created_at, updated_at)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            RETURNING {_STRUCT_SELECT_COLS}
            """,
            struct.id,
            struct.name,
            struct.content,
            struct.match_key,
        )
        return _row_to_structure(row)

    async def get_structure_by_id(self, struct_id: UUID) -> MusicStructure | None:
        """Return the structure with the given ID, or None if not found."""
        row = await self._pool.fetchrow(
            f"SELECT {_STRUCT_SELECT_COLS} FROM music_structures WHERE id = $1",
            struct_id,
        )
        if row is None:
            return None
        return _row_to_structure(row)

    async def get_structure_by_name(self, name: str) -> MusicStructure | None:
        """Return the structure matching the given name, or None."""
        row = await self._pool.fetchrow(
            f"SELECT {_STRUCT_SELECT_COLS} FROM music_structures WHERE name = $1",
            name,
        )
        if row is None:
            return None
        return _row_to_structure(row)

    async def list_structures(self) -> list[MusicStructure]:
        """Return all music structures ordered by name ascending."""
        rows = await self._pool.fetch(
            f"SELECT {_STRUCT_SELECT_COLS} FROM music_structures ORDER BY name ASC"
        )
        return [_row_to_structure(row) for row in rows]

    async def update_structure(
        self, struct_id: UUID, **fields: Any
    ) -> MusicStructure | None:
        """Update specified fields on a music structure.

        Args:
            struct_id: The UUID of the structure to update.
            **fields: Column names and their new values.

        Returns:
            The updated MusicStructure, or None if not found.
        """
        if not fields:
            return await self.get_structure_by_id(struct_id)

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

        # WHERE clause
        values.append(struct_id)
        id_param = param_idx

        query = f"""
            UPDATE music_structures
            SET {', '.join(set_parts)}
            WHERE id = ${id_param}
            RETURNING {_STRUCT_SELECT_COLS}
        """
        row = await self._pool.fetchrow(query, *values)
        if row is None:
            return None
        return _row_to_structure(row)

    async def delete_structure(self, struct_id: UUID) -> bool:
        """Delete a music structure by ID.

        Dissociates from songs referencing this structure (sets to NULL).

        Args:
            struct_id: The UUID of the structure to delete.

        Returns:
            True if the structure was found and deleted, False otherwise.
        """
        # Dissociate from songs
        await self._pool.execute(
            "UPDATE songs SET structure_id = NULL WHERE structure_id = $1",
            struct_id,
        )
        result = await self._pool.execute(
            "DELETE FROM music_structures WHERE id = $1",
            struct_id,
        )
        return result == "DELETE 1"

    # -----------------------------------------------------------------------
    # matchKey Pairing Lookups
    # -----------------------------------------------------------------------

    async def get_descriptions_with_match_key(self) -> list[MusicDescription]:
        """Return all descriptions that have a non-null match_key."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_DESC_SELECT_COLS}
            FROM music_descriptions
            WHERE match_key IS NOT NULL
            ORDER BY name ASC
            """
        )
        return [_row_to_description(row) for row in rows]

    async def get_structures_with_match_key(self) -> list[MusicStructure]:
        """Return all structures that have a non-null match_key."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_STRUCT_SELECT_COLS}
            FROM music_structures
            WHERE match_key IS NOT NULL
            ORDER BY name ASC
            """
        )
        return [_row_to_structure(row) for row in rows]

    async def get_matched_pairs(
        self,
    ) -> list[tuple[MusicDescription, MusicStructure]]:
        """Return description-structure pairs matched by match_key.

        Only pairs where both a description and a structure share the same
        match_key value are returned. Items with match_keys that have no
        counterpart are excluded.

        Returns:
            List of (MusicDescription, MusicStructure) pairs sharing a match_key.
        """
        rows = await self._pool.fetch(
            f"""
            SELECT
                d.id AS d_id, d.name AS d_name, d.content AS d_content,
                d.match_key AS d_match_key, d.created_at AS d_created_at,
                d.updated_at AS d_updated_at,
                s.id AS s_id, s.name AS s_name, s.content AS s_content,
                s.match_key AS s_match_key, s.created_at AS s_created_at,
                s.updated_at AS s_updated_at
            FROM music_descriptions d
            INNER JOIN music_structures s ON d.match_key = s.match_key
            ORDER BY d.name ASC
            """
        )
        pairs: list[tuple[MusicDescription, MusicStructure]] = []
        for row in rows:
            desc = MusicDescription(
                id=row["d_id"],
                name=row["d_name"],
                content=row["d_content"],
                match_key=row["d_match_key"],
                created_at=row["d_created_at"],
                updated_at=row["d_updated_at"],
            )
            struct = MusicStructure(
                id=row["s_id"],
                name=row["s_name"],
                content=row["s_content"],
                match_key=row["s_match_key"],
                created_at=row["s_created_at"],
                updated_at=row["s_updated_at"],
            )
            pairs.append((desc, struct))
        return pairs
