"""Repository for image sample rotation history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg


class ImageSampleRepository:
    """Persists least-used counters for image sample paths."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def pick_least_used_value(
        self,
        *,
        kind: str,
        values: list[str],
        exclude: list[str] | None = None,
    ) -> str:
        """Return the least-used candidate and increment its counter."""
        kind_key = str(kind or "").strip()
        candidates = [str(value).strip() for value in values if str(value).strip()]
        excluded = {str(value).strip() for value in (exclude or []) if str(value).strip()}
        if excluded:
            candidates = [value for value in candidates if value not in excluded]
        if not kind_key or not candidates:
            return candidates[0] if candidates else (values[0] if values else "")

        rows = await self._pool.fetch(
            """
            SELECT value, used_count, used_at
            FROM image_random_history
            WHERE kind = $1
              AND value = ANY($2::text[])
            """,
            kind_key,
            candidates,
        )
        stats: dict[str, dict[str, Any]] = {
            str(row["value"]): {
                "used": int(row["used_count"] or 0),
                "at": row["used_at"],
            }
            for row in rows
        }

        best: str | None = None
        best_used: int | None = None
        best_at: datetime | None = None
        for candidate in candidates:
            row = stats.get(candidate)
            used = int(row["used"]) if row else 0
            used_at = row["at"] if row else None
            if (
                best is None
                or used < int(best_used or 0)
                or (
                    used == int(best_used or 0)
                    and (
                        best_at is None
                        or (used_at is not None and used_at < best_at)
                    )
                )
            ):
                best = candidate
                best_used = used
                best_at = used_at

        chosen = str(best or candidates[0]).strip()
        await self._pool.execute(
            """
            INSERT INTO image_random_history (kind, value, used_count, used_at)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (kind, value) DO UPDATE SET
                used_count = image_random_history.used_count + 1,
                used_at = NOW()
            """,
            kind_key,
            chosen,
        )
        return chosen
