"""Repository for image sample rotation history."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

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
        batch_id: UUID | None = None,
        previous_batch_id: UUID | None = None,
        lock_key: str | None = None,
    ) -> str:
        """Return the least-used candidate and increment its counter.

        ``batch_id`` records which batch consumed the value. ``previous_batch_id``
        lets callers avoid repeating the immediately previous batch when another
        candidate exists. When ``lock_key`` is set and the pool supports
        transactions, a PostgreSQL advisory lock serialises concurrent pickers.
        """
        kind_key = str(kind or "").strip()
        candidates = [str(value).strip() for value in values if str(value).strip()]
        excluded = {str(value).strip() for value in (exclude or []) if str(value).strip()}
        if excluded:
            candidates = [value for value in candidates if value not in excluded]
        if not kind_key or not candidates:
            return candidates[0] if candidates else (values[0] if values else "")

        acquire = getattr(self._pool, "acquire", None)
        if lock_key and callable(acquire):
            async with acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1))",
                        str(lock_key),
                    )
                    return await self._pick_on(
                        conn,
                        kind_key=kind_key,
                        candidates=candidates,
                        batch_id=batch_id,
                        previous_batch_id=previous_batch_id,
                    )
        return await self._pick_on(
            self._pool,
            kind_key=kind_key,
            candidates=candidates,
            batch_id=batch_id,
            previous_batch_id=previous_batch_id,
        )

    async def _pick_on(
        self,
        db: Any,
        *,
        kind_key: str,
        candidates: list[str],
        batch_id: UUID | None,
        previous_batch_id: UUID | None,
    ) -> str:
        rows = await db.fetch(
            """
            SELECT value, used_count, used_at, last_batch_id
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
                "batch": row.get("last_batch_id"),
            }
            for row in rows
        }

        if previous_batch_id is not None:
            previous_key = str(previous_batch_id)
            fresh = [
                candidate
                for candidate in candidates
                if str(stats.get(candidate, {}).get("batch") or "") != previous_key
            ]
            if fresh:
                candidates = fresh

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
        await db.execute(
            """
            INSERT INTO image_random_history
                (kind, value, used_count, used_at, last_batch_id)
            VALUES ($1, $2, 1, NOW(), $3)
            ON CONFLICT (kind, value) DO UPDATE SET
                used_count = image_random_history.used_count + 1,
                used_at = NOW(),
                last_batch_id = COALESCE($3, image_random_history.last_batch_id)
            """,
            kind_key,
            chosen,
            batch_id,
        )
        return chosen
