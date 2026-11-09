"""Database access for creator profiles and handle history."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

# Columns a creator may change through PATCH /creator/me. Status/tier are
# controlled by admin workflows, not the profile editor.
_EDITABLE_COLUMNS = {
    "display_name",
    "tagline",
    "bio",
    "country_code",
    "city",
    "avatar_url",
    "banner_url",
    "links",
    "genres",
    "influences",
    "pronouns",
    "ai_disclosure",
    "support_enabled",
    "payout_currency",
}

_JSONB_COLUMNS = {"links"}
_ARRAY_COLUMNS = {"genres", "influences"}

_SORTS = {
    "followers": "cp.follower_count DESC, cp.display_name ASC",
    "newest": "cp.created_at DESC, cp.display_name ASC",
    "name": "cp.display_name ASC",
}


class CreatorRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def get_by_user_id(self, user_id: UUID | str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM creator_profiles WHERE user_id = $1",
            user_id,
        )
        return dict(row) if row else None

    async def get_by_handle(self, handle: str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM creator_profiles
            WHERE LOWER(handle) = LOWER($1) AND status = 'active'
            """,
            handle,
        )
        return dict(row) if row else None

    async def get_redirect(self, handle: str) -> str | None:
        value = await self._pool.fetchval(
            """
            SELECT new_handle
            FROM creator_handle_history
            WHERE LOWER(old_handle) = LOWER($1) AND redirect_until > NOW()
            ORDER BY changed_at DESC
            LIMIT 1
            """,
            handle,
        )
        return str(value) if value else None

    async def handle_exists(self, handle: str) -> bool:
        value = await self._pool.fetchval(
            "SELECT 1 FROM creator_profiles WHERE LOWER(handle) = LOWER($1)",
            handle,
        )
        return value is not None

    async def last_handle_change(self, user_id: UUID | str):
        return await self._pool.fetchval(
            "SELECT MAX(changed_at) FROM creator_handle_history WHERE user_id = $1",
            user_id,
        )

    async def insert_profile(
        self,
        *,
        user_id: UUID | str,
        handle: str,
        display_name: str,
        tagline: str | None,
        bio: str | None,
        country_code: str | None,
        city: str | None,
        avatar_url: str | None,
        banner_url: str | None,
        links: list[dict[str, str]],
        genres: list[str],
        influences: list[str],
        pronouns: str | None,
        ai_disclosure: str,
        support_enabled: bool,
        payout_currency: str,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_profiles (
                user_id, handle, display_name, tagline, bio, country_code, city,
                avatar_url, banner_url, links, genres, influences, pronouns,
                ai_disclosure, support_enabled, payout_currency, status, tier,
                program_joined_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::text[],
                $12::text[], $13, $14, $15, $16, 'active', 'creator', NOW(), NOW()
            )
            RETURNING *
            """,
            user_id,
            handle,
            display_name,
            tagline,
            bio,
            country_code,
            city,
            avatar_url,
            banner_url,
            json.dumps(links),
            genres,
            influences,
            pronouns,
            ai_disclosure,
            support_enabled,
            payout_currency,
        )
        return dict(row)

    async def update_profile(
        self, user_id: UUID | str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        unknown = set(fields) - _EDITABLE_COLUMNS
        if unknown:
            raise ValueError(f"Unsupported profile fields: {', '.join(sorted(unknown))}")
        if not fields:
            row = await self._pool.fetchrow(
                "SELECT * FROM creator_profiles WHERE user_id = $1", user_id
            )
            return dict(row) if row else {}

        sets: list[str] = []
        values: list[Any] = [user_id]
        for index, (column, value) in enumerate(fields.items(), start=2):
            if column in _JSONB_COLUMNS:
                sets.append(f"{column} = ${index}::jsonb")
                values.append(json.dumps(value))
            elif column in _ARRAY_COLUMNS:
                sets.append(f"{column} = ${index}::text[]")
                values.append(value)
            else:
                sets.append(f"{column} = ${index}")
                values.append(value)
        sets.append("updated_at = NOW()")

        row = await self._pool.fetchrow(
            f"UPDATE creator_profiles SET {', '.join(sets)} WHERE user_id = $1 RETURNING *",
            *values,
        )
        return dict(row) if row else {}

    async def set_handle(self, user_id: UUID | str, handle: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            UPDATE creator_profiles
            SET handle = $2, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            handle,
        )
        return dict(row) if row else {}

    async def insert_handle_history(
        self, user_id: UUID | str, old_handle: str, new_handle: str
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO creator_handle_history (user_id, old_handle, new_handle)
            VALUES ($1, $2, $3)
            """,
            user_id,
            old_handle,
            new_handle,
        )

    async def list_public(
        self,
        *,
        q: str | None = None,
        genre: str | None = None,
        country: str | None = None,
        verified_only: bool = False,
        sort: str = "followers",
        limit: int = 24,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["cp.status = 'active'"]
        args: list[Any] = []

        if q:
            args.append(f"%{q.strip()}%")
            index = len(args)
            clauses.append(
                f"(cp.display_name ILIKE ${index} OR cp.handle ILIKE ${index})"
            )
        if genre:
            args.append(genre)
            clauses.append(f"${len(args)} = ANY(cp.genres)")
        if country:
            args.append(country.upper())
            clauses.append(f"cp.country_code = ${len(args)}")
        if verified_only:
            clauses.append("cp.tier IN ('verified','partner')")

        order_by = _SORTS.get(sort, _SORTS["followers"])
        args.extend([max(1, min(limit, 100)), max(0, offset)])
        limit_index = len(args) - 1
        offset_index = len(args)

        rows = await self._pool.fetch(
            f"""
            SELECT cp.*
            FROM creator_profiles cp
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_by}
            LIMIT ${limit_index} OFFSET ${offset_index}
            """,
            *args,
        )
        return [dict(row) for row in rows]

    async def count_public(
        self,
        *,
        q: str | None = None,
        genre: str | None = None,
        country: str | None = None,
        verified_only: bool = False,
    ) -> int:
        clauses = ["cp.status = 'active'"]
        args: list[Any] = []

        if q:
            args.append(f"%{q.strip()}%")
            index = len(args)
            clauses.append(
                f"(cp.display_name ILIKE ${index} OR cp.handle ILIKE ${index})"
            )
        if genre:
            args.append(genre)
            clauses.append(f"${len(args)} = ANY(cp.genres)")
        if country:
            args.append(country.upper())
            clauses.append(f"cp.country_code = ${len(args)}")
        if verified_only:
            clauses.append("cp.tier IN ('verified','partner')")

        value = await self._pool.fetchval(
            f"SELECT COUNT(*) FROM creator_profiles cp WHERE {' AND '.join(clauses)}",
            *args,
        )
        return int(value or 0)
