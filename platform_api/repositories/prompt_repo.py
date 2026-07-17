"""Music prompt repository with asyncpg-based CRUD operations.

Provides CRUD for music_descriptions and music_structures tables,
matchKey-based pairing lookup for batch generation, user ownership,
and usage analytics from the songs table.

Requirements: 9.1, 9.2, 9.3, 9.6
"""

from __future__ import annotations

import json
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

_DESC_SELECT_COLS = (
    "id, name, content, match_key, vocal_profile, is_active, user_id, created_at, updated_at"
)
_STRUCT_SELECT_COLS = "id, name, content, match_key, is_active, user_id, created_at, updated_at"


def _serialize_jsonb_value(value: Any) -> str | None:
    """Serialize JSONB payloads for asyncpg parameters."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _row_to_description(row: Any) -> MusicDescription:
    """Convert an asyncpg Record to a MusicDescription domain object."""
    vocal_profile = row.get("vocal_profile") if hasattr(row, "get") else None
    if isinstance(vocal_profile, str):
        import json

        try:
            vocal_profile = json.loads(vocal_profile)
        except json.JSONDecodeError:
            vocal_profile = None
    return MusicDescription(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        match_key=row["match_key"],
        vocal_profile=vocal_profile if isinstance(vocal_profile, dict) else None,
        is_active=bool(row["is_active"]),
        user_id=row.get("user_id"),
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
        is_active=bool(row["is_active"]),
        user_id=row.get("user_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Prompt Repository
# ---------------------------------------------------------------------------


class PromptRepository:
    """Repository for music description and structure CRUD operations."""

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    # -----------------------------------------------------------------------
    # Music Descriptions
    # -----------------------------------------------------------------------

    async def create_description(self, desc: MusicDescription) -> MusicDescription:
        """Insert a new music description."""
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO music_descriptions (
                id, name, content, match_key, vocal_profile, is_active, user_id, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, NOW(), NOW())
            RETURNING {_DESC_SELECT_COLS}
            """,
            desc.id,
            desc.name,
            desc.content,
            desc.match_key,
            _serialize_jsonb_value(desc.vocal_profile),
            desc.is_active,
            desc.user_id,
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

    async def get_description_by_name(
        self, name: str, *, user_id: UUID | None = None
    ) -> MusicDescription | None:
        """Return the description matching the given name within an ownership scope."""
        if user_id is None:
            row = await self._pool.fetchrow(
                f"""
                SELECT {_DESC_SELECT_COLS}
                FROM music_descriptions
                WHERE name = $1 AND user_id IS NULL
                """,
                name,
            )
        else:
            row = await self._pool.fetchrow(
                f"""
                SELECT {_DESC_SELECT_COLS}
                FROM music_descriptions
                WHERE name = $1 AND user_id = $2 AND is_active = TRUE
                """,
                name,
                user_id,
            )
        if row is None:
            return None
        return _row_to_description(row)

    async def list_descriptions(self) -> list[MusicDescription]:
        """Return global (camxora) descriptions ordered by name ascending."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_DESC_SELECT_COLS}
            FROM music_descriptions
            WHERE user_id IS NULL
            ORDER BY name ASC
            """
        )
        return [_row_to_description(row) for row in rows]

    async def list_descriptions_for_user(self, user_id: UUID) -> list[MusicDescription]:
        """Return descriptions owned by the given user."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_DESC_SELECT_COLS}
            FROM music_descriptions
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY name ASC
            """,
            user_id,
        )
        return [_row_to_description(row) for row in rows]

    async def list_descriptions_workspace(self, user_id: UUID) -> list[MusicDescription]:
        """Return global descriptions plus the user's own descriptions."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_DESC_SELECT_COLS}
            FROM music_descriptions
            WHERE (user_id IS NULL AND is_active = TRUE) OR (user_id = $1 AND is_active = TRUE)
            ORDER BY name ASC
            """,
            user_id,
        )
        return [_row_to_description(row) for row in rows]

    async def update_description(
        self, desc_id: UUID, **fields: Any
    ) -> MusicDescription | None:
        """Update specified fields on a music description."""
        if not fields:
            return await self.get_description_by_id(desc_id)

        set_parts: list[str] = []
        values: list[Any] = []
        param_idx = 1

        for col, val in fields.items():
            if col == "vocal_profile":
                set_parts.append(f"{col} = ${param_idx}::jsonb")
                values.append(_serialize_jsonb_value(val))
            else:
                set_parts.append(f"{col} = ${param_idx}")
                values.append(val)
            param_idx += 1

        set_parts.append(f"updated_at = ${param_idx}")
        values.append(datetime.now(timezone.utc))
        param_idx += 1

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

    async def archive_description(self, desc_id: UUID) -> bool:
        """Soft-delete a music description while preserving song usage links."""
        result = await self._pool.execute(
            """
            UPDATE music_descriptions
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1 AND is_active = TRUE
            """,
            desc_id,
        )
        return result == "UPDATE 1"

    async def delete_description(self, desc_id: UUID) -> bool:
        """Hard-delete a music description (admin/global catalog only)."""
        await self._pool.execute(
            "UPDATE songs SET description_id = NULL WHERE description_id = $1",
            desc_id,
        )
        result = await self._pool.execute(
            "DELETE FROM music_descriptions WHERE id = $1",
            desc_id,
        )
        return result == "DELETE 1"

    async def count_description_usage(self, desc_id: UUID) -> int:
        """Return total song count referencing a description."""
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM songs WHERE description_id = $1",
            desc_id,
        )
        return int(count or 0)

    async def list_description_usage_by_user(
        self, desc_id: UUID
    ) -> list[dict[str, Any]]:
        """Return per-user usage counts for a description."""
        rows = await self._pool.fetch(
            """
            SELECT
                s.user_id,
                u.email,
                u.display_name,
                COUNT(*)::int AS usage_count,
                MAX(s.created_at) AS last_used_at
            FROM songs s
            JOIN users u ON u.id = s.user_id
            WHERE s.description_id = $1
            GROUP BY s.user_id, u.email, u.display_name
            ORDER BY usage_count DESC, u.email ASC
            """,
            desc_id,
        )
        return [dict(row) for row in rows]

    async def list_description_usage_by_profile(
        self, desc_id: UUID
    ) -> list[dict[str, Any]]:
        """Return per-channel-profile usage counts for a description."""
        rows = await self._pool.fetch(
            """
            WITH profile_uses AS (
                SELECT s.created_at, b.ok_profile_id AS profile_id
                FROM songs s
                JOIN batches b ON b.id = s.batch_id
                WHERE s.description_id = $1 AND b.ok_profile_id IS NOT NULL

                UNION ALL

                SELECT s.created_at, b.alt_profile_id AS profile_id
                FROM songs s
                JOIN batches b ON b.id = s.batch_id
                WHERE s.description_id = $1 AND b.alt_profile_id IS NOT NULL
            )
            SELECT
                pu.profile_id,
                cp.name AS profile_name,
                owner.email AS user_email,
                owner.display_name AS user_display_name,
                COUNT(*)::int AS usage_count,
                MAX(pu.created_at) AS last_used_at
            FROM profile_uses pu
            JOIN channel_profiles cp ON cp.id = pu.profile_id
            JOIN users owner ON owner.id = cp.user_id
            GROUP BY pu.profile_id, cp.name, owner.email, owner.display_name
            ORDER BY usage_count DESC, cp.name ASC
            """,
            desc_id,
        )
        return [dict(row) for row in rows]

    async def list_description_usage_by_day(
        self, desc_id: UUID
    ) -> list[dict[str, Any]]:
        """Return daily usage counts for a description."""
        rows = await self._pool.fetch(
            """
            SELECT
                DATE(s.created_at AT TIME ZONE 'UTC') AS usage_date,
                COUNT(*)::int AS usage_count
            FROM songs s
            WHERE s.description_id = $1
            GROUP BY DATE(s.created_at AT TIME ZONE 'UTC')
            ORDER BY usage_date ASC
            """,
            desc_id,
        )
        return [dict(row) for row in rows]

    async def map_description_usage_counts(self) -> dict[UUID, int]:
        """Return total usage counts keyed by description ID."""
        rows = await self._pool.fetch(
            """
            SELECT description_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE description_id IS NOT NULL
            GROUP BY description_id
            """
        )
        return {row["description_id"]: int(row["usage_count"]) for row in rows}

    # -----------------------------------------------------------------------
    # Music Structures
    # -----------------------------------------------------------------------

    async def create_structure(self, struct: MusicStructure) -> MusicStructure:
        """Insert a new music structure."""
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO music_structures (id, name, content, match_key, is_active, user_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING {_STRUCT_SELECT_COLS}
            """,
            struct.id,
            struct.name,
            struct.content,
            struct.match_key,
            struct.is_active,
            struct.user_id,
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

    async def get_structure_by_name(
        self, name: str, *, user_id: UUID | None = None
    ) -> MusicStructure | None:
        """Return the structure matching the given name within an ownership scope."""
        if user_id is None:
            row = await self._pool.fetchrow(
                f"""
                SELECT {_STRUCT_SELECT_COLS}
                FROM music_structures
                WHERE name = $1 AND user_id IS NULL
                """,
                name,
            )
        else:
            row = await self._pool.fetchrow(
                f"""
                SELECT {_STRUCT_SELECT_COLS}
                FROM music_structures
                WHERE name = $1 AND user_id = $2 AND is_active = TRUE
                """,
                name,
                user_id,
            )
        if row is None:
            return None
        return _row_to_structure(row)

    async def list_structures(self) -> list[MusicStructure]:
        """Return global (camxora) structures ordered by name ascending."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_STRUCT_SELECT_COLS}
            FROM music_structures
            WHERE user_id IS NULL
            ORDER BY name ASC
            """
        )
        return [_row_to_structure(row) for row in rows]

    async def list_structures_for_user(self, user_id: UUID) -> list[MusicStructure]:
        """Return structures owned by the given user."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_STRUCT_SELECT_COLS}
            FROM music_structures
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY name ASC
            """,
            user_id,
        )
        return [_row_to_structure(row) for row in rows]

    async def list_structures_workspace(self, user_id: UUID) -> list[MusicStructure]:
        """Return global structures plus the user's own structures."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_STRUCT_SELECT_COLS}
            FROM music_structures
            WHERE (user_id IS NULL AND is_active = TRUE) OR (user_id = $1 AND is_active = TRUE)
            ORDER BY name ASC
            """,
            user_id,
        )
        return [_row_to_structure(row) for row in rows]

    async def update_structure(
        self, struct_id: UUID, **fields: Any
    ) -> MusicStructure | None:
        """Update specified fields on a music structure."""
        if not fields:
            return await self.get_structure_by_id(struct_id)

        set_parts: list[str] = []
        values: list[Any] = []
        param_idx = 1

        for col, val in fields.items():
            set_parts.append(f"{col} = ${param_idx}")
            values.append(val)
            param_idx += 1

        set_parts.append(f"updated_at = ${param_idx}")
        values.append(datetime.now(timezone.utc))
        param_idx += 1

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

    async def archive_structure(self, struct_id: UUID) -> bool:
        """Soft-delete a music structure while preserving song usage links."""
        result = await self._pool.execute(
            """
            UPDATE music_structures
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1 AND is_active = TRUE
            """,
            struct_id,
        )
        return result == "UPDATE 1"

    async def delete_structure(self, struct_id: UUID) -> bool:
        """Hard-delete a music structure (admin/global catalog only)."""
        await self._pool.execute(
            "UPDATE songs SET structure_id = NULL WHERE structure_id = $1",
            struct_id,
        )
        result = await self._pool.execute(
            "DELETE FROM music_structures WHERE id = $1",
            struct_id,
        )
        return result == "DELETE 1"

    async def count_structure_usage(self, struct_id: UUID) -> int:
        """Return total song count referencing a structure."""
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM songs WHERE structure_id = $1",
            struct_id,
        )
        return int(count or 0)

    async def list_structure_usage_by_user(
        self, struct_id: UUID
    ) -> list[dict[str, Any]]:
        """Return per-user usage counts for a structure."""
        rows = await self._pool.fetch(
            """
            SELECT
                s.user_id,
                u.email,
                u.display_name,
                COUNT(*)::int AS usage_count,
                MAX(s.created_at) AS last_used_at
            FROM songs s
            JOIN users u ON u.id = s.user_id
            WHERE s.structure_id = $1
            GROUP BY s.user_id, u.email, u.display_name
            ORDER BY usage_count DESC, u.email ASC
            """,
            struct_id,
        )
        return [dict(row) for row in rows]

    async def list_structure_usage_by_profile(
        self, struct_id: UUID
    ) -> list[dict[str, Any]]:
        """Return per-channel-profile usage counts for a structure."""
        rows = await self._pool.fetch(
            """
            WITH profile_uses AS (
                SELECT s.created_at, b.ok_profile_id AS profile_id
                FROM songs s
                JOIN batches b ON b.id = s.batch_id
                WHERE s.structure_id = $1 AND b.ok_profile_id IS NOT NULL

                UNION ALL

                SELECT s.created_at, b.alt_profile_id AS profile_id
                FROM songs s
                JOIN batches b ON b.id = s.batch_id
                WHERE s.structure_id = $1 AND b.alt_profile_id IS NOT NULL
            )
            SELECT
                pu.profile_id,
                cp.name AS profile_name,
                owner.email AS user_email,
                owner.display_name AS user_display_name,
                COUNT(*)::int AS usage_count,
                MAX(pu.created_at) AS last_used_at
            FROM profile_uses pu
            JOIN channel_profiles cp ON cp.id = pu.profile_id
            JOIN users owner ON owner.id = cp.user_id
            GROUP BY pu.profile_id, cp.name, owner.email, owner.display_name
            ORDER BY usage_count DESC, cp.name ASC
            """,
            struct_id,
        )
        return [dict(row) for row in rows]

    async def list_structure_usage_by_day(
        self, struct_id: UUID
    ) -> list[dict[str, Any]]:
        """Return daily usage counts for a structure."""
        rows = await self._pool.fetch(
            """
            SELECT
                DATE(s.created_at AT TIME ZONE 'UTC') AS usage_date,
                COUNT(*)::int AS usage_count
            FROM songs s
            WHERE s.structure_id = $1
            GROUP BY DATE(s.created_at AT TIME ZONE 'UTC')
            ORDER BY usage_date ASC
            """,
            struct_id,
        )
        return [dict(row) for row in rows]

    async def map_structure_usage_counts(self) -> dict[UUID, int]:
        """Return total usage counts keyed by structure ID."""
        rows = await self._pool.fetch(
            """
            SELECT structure_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE structure_id IS NOT NULL
            GROUP BY structure_id
            """
        )
        return {row["structure_id"]: int(row["usage_count"]) for row in rows}

    # -----------------------------------------------------------------------
    # matchKey Pairing Lookups
    # -----------------------------------------------------------------------

    async def get_descriptions_with_match_key(self) -> list[MusicDescription]:
        """Return global descriptions that have a non-null match_key."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_DESC_SELECT_COLS}
            FROM music_descriptions
            WHERE match_key IS NOT NULL AND user_id IS NULL
            ORDER BY name ASC
            """
        )
        return [_row_to_description(row) for row in rows]

    async def get_structures_with_match_key(self) -> list[MusicStructure]:
        """Return global structures that have a non-null match_key."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_STRUCT_SELECT_COLS}
            FROM music_structures
            WHERE match_key IS NOT NULL AND user_id IS NULL
            ORDER BY name ASC
            """
        )
        return [_row_to_structure(row) for row in rows]

    async def get_matched_pairs(
        self,
    ) -> list[tuple[MusicDescription, MusicStructure]]:
        """Return global description-structure pairs matched by match_key."""
        rows = await self._pool.fetch(
            f"""
            SELECT
                d.id AS d_id, d.name AS d_name, d.content AS d_content,
                d.match_key AS d_match_key, d.is_active AS d_is_active, d.user_id AS d_user_id,
                d.created_at AS d_created_at, d.updated_at AS d_updated_at,
                s.id AS s_id, s.name AS s_name, s.content AS s_content,
                s.match_key AS s_match_key, s.is_active AS s_is_active, s.user_id AS s_user_id,
                s.created_at AS s_created_at, s.updated_at AS s_updated_at
            FROM music_descriptions d
            INNER JOIN music_structures s ON d.match_key = s.match_key
            WHERE d.user_id IS NULL AND s.user_id IS NULL
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
                is_active=bool(row["d_is_active"]),
                user_id=row["d_user_id"],
                created_at=row["d_created_at"],
                updated_at=row["d_updated_at"],
            )
            struct = MusicStructure(
                id=row["s_id"],
                name=row["s_name"],
                content=row["s_content"],
                match_key=row["s_match_key"],
                is_active=bool(row["s_is_active"]),
                user_id=row["s_user_id"],
                created_at=row["s_created_at"],
                updated_at=row["s_updated_at"],
            )
            pairs.append((desc, struct))
        return pairs
