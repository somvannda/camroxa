"""Repository for desktop client log batches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4


class DatabaseProtocol(Protocol):
    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...


@dataclass(slots=True)
class ClientLogBatch:
    id: UUID
    user_id: UUID
    client_id: str | None
    client_label: str | None
    app_version: str | None
    line_count: int
    size_bytes: int
    content: str
    created_at: datetime


class ClientLogRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def insert(
        self,
        *,
        user_id: UUID,
        content: str,
        line_count: int,
        client_id: str | None = None,
        client_label: str | None = None,
        app_version: str | None = None,
    ) -> ClientLogBatch:
        batch_id = uuid4()
        size_bytes = len(content.encode("utf-8", errors="replace"))
        row = await self._db.fetchrow(
            """
            INSERT INTO client_log_batches (
                id, user_id, client_id, client_label, app_version,
                line_count, size_bytes, content
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, user_id, client_id, client_label, app_version,
                      line_count, size_bytes, content, created_at
            """,
            str(batch_id),
            str(user_id),
            client_id,
            client_label,
            app_version,
            int(line_count),
            int(size_bytes),
            content,
        )
        return self._row_to_batch(row)

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ClientLogBatch], int]:
        page = max(1, int(page))
        page_size = max(1, min(200, int(page_size)))
        offset = (page - 1) * page_size
        total = int(
            await self._db.fetchval(
                "SELECT COUNT(*) FROM client_log_batches WHERE user_id = $1",
                str(user_id),
            )
            or 0
        )
        rows = await self._db.fetch(
            """
            SELECT id, user_id, client_id, client_label, app_version,
                   line_count, size_bytes, content, created_at
            FROM client_log_batches
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            str(user_id),
            page_size,
            offset,
        )
        return [self._row_to_batch(row) for row in rows], total

    async def get_by_id(self, batch_id: UUID) -> ClientLogBatch | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, client_id, client_label, app_version,
                   line_count, size_bytes, content, created_at
            FROM client_log_batches
            WHERE id = $1
            """,
            str(batch_id),
        )
        if row is None:
            return None
        return self._row_to_batch(row)

    async def prune_user_batches(self, *, user_id: UUID, keep: int = 40) -> int:
        """Keep newest N batches per user; delete older ones."""
        keep = max(1, int(keep))
        result = await self._db.execute(
            """
            DELETE FROM client_log_batches
            WHERE user_id = $1
              AND id NOT IN (
                SELECT id FROM client_log_batches
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
              )
            """,
            str(user_id),
            keep,
        )
        # asyncpg returns e.g. "DELETE 3"
        try:
            return int(str(result).split()[-1])
        except Exception:
            return 0

    @staticmethod
    def _row_to_batch(row: Any) -> ClientLogBatch:
        return ClientLogBatch(
            id=UUID(str(row["id"])),
            user_id=UUID(str(row["user_id"])),
            client_id=row["client_id"],
            client_label=row["client_label"],
            app_version=row["app_version"],
            line_count=int(row["line_count"] or 0),
            size_bytes=int(row["size_bytes"] or 0),
            content=str(row["content"] or ""),
            created_at=row["created_at"],
        )
