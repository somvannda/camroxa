"""Database access for the curated music genre catalog."""

from __future__ import annotations

import json
from typing import Any


class MusicGenreCatalogRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def list_categories(self) -> list[str]:
        rows = await self._pool.fetch(
            """
            SELECT category, COUNT(*)::int AS genre_count
            FROM music_genre_catalog
            WHERE is_active = TRUE
            GROUP BY category
            ORDER BY category ASC
            """
        )
        return [str(row["category"]) for row in rows]

    async def search(
        self,
        *,
        query: str | None = None,
        category: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        rows = await self._pool.fetch(
            """
            SELECT id, name, slug, category, aliases
            FROM music_genre_catalog
            WHERE is_active = TRUE
              AND ($1::text IS NULL OR category = $1)
              AND (
                $2::text IS NULL
                OR name ILIKE $2
                OR slug ILIKE $2
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(COALESCE(aliases, '[]'::jsonb)) alias
                    WHERE alias ILIKE $2
                )
              )
            ORDER BY
              CASE WHEN $2 IS NULL THEN sort_order ELSE 0 END ASC,
              CASE WHEN $2 IS NOT NULL AND name ILIKE $2 THEN 0 ELSE 1 END,
              name ASC
            LIMIT $3
            """,
            category.strip() if category and category.strip() else None,
            pattern,
            max(1, min(limit, 100)),
        )
        return [dict(row) for row in rows]

    async def fetch_all_active(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT name, slug, category, aliases
            FROM music_genre_catalog
            WHERE is_active = TRUE
            ORDER BY sort_order ASC, name ASC
            """
        )
        return [dict(row) for row in rows]
