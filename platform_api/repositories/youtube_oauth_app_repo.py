"""Repository for admin-managed YouTube OAuth applications.

Stores Google OAuth client credentials for backend-mediated YouTube channel
connection flows. Client secrets are encrypted before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class YouTubeOAuthAppRecord:
    """Admin-managed YouTube OAuth app metadata."""

    id: str
    name: str
    client_id: str
    encrypted_client_secret: bytes
    is_default: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatabaseProtocol(Protocol):
    """Minimal async database interface for repository operations."""

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...

    async def execute(self, query: str, *args: Any) -> str: ...


class YouTubeOAuthAppRepository:
    """CRUD repository for admin-managed YouTube OAuth apps."""

    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def list_all(self) -> list[YouTubeOAuthAppRecord]:
        rows = await self._db.fetch(
            """
            SELECT id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            FROM youtube_oauth_apps
            ORDER BY is_default DESC, lower(name) ASC, created_at ASC
            """
        )
        return [self._row_to_record(row) for row in rows]

    async def create(
        self,
        *,
        name: str,
        client_id: str,
        encrypted_client_secret: bytes,
        is_default: bool,
    ) -> YouTubeOAuthAppRecord | None:
        row = await self._db.fetchrow(
            """
            WITH inserted AS (
                INSERT INTO youtube_oauth_apps (
                    name,
                    client_id,
                    encrypted_client_secret,
                    is_default,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                RETURNING id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            ),
            cleared AS (
                UPDATE youtube_oauth_apps
                SET is_default = FALSE,
                    updated_at = NOW()
                WHERE $4::boolean = TRUE
                  AND id <> (SELECT id FROM inserted)
                  AND is_default = TRUE
            )
            SELECT id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            FROM inserted
            """,
            name,
            client_id,
            encrypted_client_secret,
            is_default,
        )
        return self._row_to_record(row) if row else None

    async def update(
        self,
        app_id: str,
        *,
        name: str | None = None,
        client_id: str | None = None,
        encrypted_client_secret: bytes | None = None,
        is_default: bool | None = None,
    ) -> YouTubeOAuthAppRecord | None:
        row = await self._db.fetchrow(
            """
            WITH updated AS (
                UPDATE youtube_oauth_apps
                SET name = COALESCE($2, name),
                    client_id = COALESCE($3, client_id),
                    encrypted_client_secret = COALESCE($4, encrypted_client_secret),
                    is_default = COALESCE($5, is_default),
                    updated_at = NOW()
                WHERE id = $1::uuid
                RETURNING id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            ),
            cleared AS (
                UPDATE youtube_oauth_apps
                SET is_default = FALSE,
                    updated_at = NOW()
                WHERE COALESCE((SELECT is_default FROM updated), FALSE) = TRUE
                  AND id <> (SELECT id FROM updated)
                  AND is_default = TRUE
            )
            SELECT id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            FROM updated
            """,
            app_id,
            name,
            client_id,
            encrypted_client_secret,
            is_default,
        )
        return self._row_to_record(row) if row else None

    async def delete(self, app_id: str) -> bool:
        result = await self._db.execute(
            "DELETE FROM youtube_oauth_apps WHERE id = $1::uuid",
            app_id,
        )
        return result.upper() != "DELETE 0"

    async def get_by_id(self, app_id: str) -> YouTubeOAuthAppRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            FROM youtube_oauth_apps
            WHERE id = $1::uuid
            """,
            app_id,
        )
        return self._row_to_record(row) if row else None

    async def get_default(self) -> YouTubeOAuthAppRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, name, client_id, encrypted_client_secret, is_default, created_at, updated_at
            FROM youtube_oauth_apps
            WHERE is_default = TRUE
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """
        )
        return self._row_to_record(row) if row else None

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> YouTubeOAuthAppRecord:
        return YouTubeOAuthAppRecord(
            id=str(row["id"]),
            name=str(row["name"] or ""),
            client_id=str(row["client_id"] or ""),
            encrypted_client_secret=bytes(row["encrypted_client_secret"] or b""),
            is_default=bool(row["is_default"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
