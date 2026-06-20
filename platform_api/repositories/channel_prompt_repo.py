"""Channel prompt repository with asyncpg-based CRUD operations.

Provides CRUD for the channel_prompts table used by the onboarding wizard
to generate channel names, logos, covers, descriptions, keywords, and tags.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import ChannelPrompt

logger = logging.getLogger(__name__)


class AsyncPGPool(Protocol):
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def execute(self, query: str, *args: Any) -> str: ...


_SELECT_COLS = "id, name, content, category, genre, match_key, is_active, created_at, updated_at"


def _row_to_channel_prompt(row: Any) -> ChannelPrompt:
    return ChannelPrompt(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        category=row["category"],
        genre=row["genre"],
        match_key=row["match_key"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ChannelPromptRepository:
    """Repository for channel prompt CRUD operations."""

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def create(self, prompt: ChannelPrompt) -> ChannelPrompt:
        row = await self._pool.fetchrow(
            f"""INSERT INTO channel_prompts (name, content, category, genre, match_key, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                RETURNING {_SELECT_COLS}""",
            prompt.name,
            prompt.content,
            prompt.category,
            prompt.genre,
            prompt.match_key,
            prompt.is_active,
        )
        return _row_to_channel_prompt(row)

    async def get_by_id(self, prompt_id: UUID) -> ChannelPrompt | None:
        row = await self._pool.fetchrow(
            f"SELECT {_SELECT_COLS} FROM channel_prompts WHERE id = $1",
            prompt_id,
        )
        return _row_to_channel_prompt(row) if row else None

    async def list_all(self) -> list[ChannelPrompt]:
        rows = await self._pool.fetch(
            f"SELECT {_SELECT_COLS} FROM channel_prompts ORDER BY category, name ASC"
        )
        return [_row_to_channel_prompt(r) for r in rows]

    async def list_by_category(self, category: str) -> list[ChannelPrompt]:
        rows = await self._pool.fetch(
            f"SELECT {_SELECT_COLS} FROM channel_prompts WHERE category = $1 ORDER BY name ASC",
            category,
        )
        return [_row_to_channel_prompt(r) for r in rows]

    async def get_best_match(self, category: str, genre: str, match_key: str | None = None) -> ChannelPrompt | None:
        """Get the best matching prompt for a category.

        Priority: match_key > genre-specific > default (empty genre).
        """
        # Try match_key first (linked to music_descriptions)
        if match_key:
            row = await self._pool.fetchrow(
                f"""SELECT {_SELECT_COLS} FROM channel_prompts
                    WHERE category = $1 AND match_key = $2 AND is_active = true
                    ORDER BY name ASC LIMIT 1""",
                category,
                match_key,
            )
            if row:
                return _row_to_channel_prompt(row)

        # Try genre-specific
        if genre:
            row = await self._pool.fetchrow(
                f"""SELECT {_SELECT_COLS} FROM channel_prompts
                    WHERE category = $1 AND genre = $2 AND is_active = true
                    ORDER BY name ASC LIMIT 1""",
                category,
                genre,
            )
            if row:
                return _row_to_channel_prompt(row)

        # Fall back to default (empty genre)
        row = await self._pool.fetchrow(
            f"""SELECT {_SELECT_COLS} FROM channel_prompts
                WHERE category = $1 AND genre = '' AND is_active = true
                ORDER BY name ASC LIMIT 1""",
            category,
        )
        return _row_to_channel_prompt(row) if row else None

    async def update(self, prompt_id: UUID, **fields: Any) -> ChannelPrompt | None:
        if not fields:
            return await self.get_by_id(prompt_id)

        set_parts = []
        values: list[Any] = []
        idx = 1
        for key, val in fields.items():
            set_parts.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1
        set_parts.append(f"updated_at = NOW()")
        values.append(prompt_id)

        query = f"""UPDATE channel_prompts SET {', '.join(set_parts)}
                    WHERE id = ${idx} RETURNING {_SELECT_COLS}"""
        row = await self._pool.fetchrow(query, *values)
        return _row_to_channel_prompt(row) if row else None

    async def delete(self, prompt_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM channel_prompts WHERE id = $1", prompt_id
        )
        return result.endswith("1")
