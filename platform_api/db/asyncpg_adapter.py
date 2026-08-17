"""Thin asyncpg pool helpers used by v2 subscription/credit services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


class AsyncpgPoolAdapter:
    """Wrap asyncpg pool with fetch_one/fetch_all helpers and transactions."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def fetch_one(self, query: str, *args: Any) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(query, *args)
        return dict(row) if row is not None else None

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(query, *args)
        return [dict(row) for row in rows]

    async def fetch_val(self, query: str, *args: Any) -> Any:
        return await self._pool.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        return await self._pool.execute(query, *args)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["AsyncpgPoolAdapter"]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield AsyncpgConnectionAdapter(conn)


class AsyncpgConnectionAdapter:
    """Connection-scoped adapter for use inside a transaction block."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def fetch_one(self, query: str, *args: Any) -> dict[str, Any] | None:
        row = await self._conn.fetchrow(query, *args)
        return dict(row) if row is not None else None

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        rows = await self._conn.fetch(query, *args)
        return [dict(row) for row in rows]

    async def fetch_val(self, query: str, *args: Any) -> Any:
        return await self._conn.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        return await self._conn.execute(query, *args)


def wrap_pool(pool: Any) -> AsyncpgPoolAdapter:
    if isinstance(pool, AsyncpgPoolAdapter):
        return pool
    return AsyncpgPoolAdapter(pool)
