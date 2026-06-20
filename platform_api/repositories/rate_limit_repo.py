"""Rate limit configuration repository.

Manages CRUD operations for the rate_limit_config table.
Supports Admin live-update of rate limits (applied within 5 seconds via Redis cache TTL).

Requirements: 19.4
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from platform_api.middleware.rate_limit import RateLimitConfig


# ---------------------------------------------------------------------------
# Data model for rate limit config records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RateLimitConfigRecord:
    """Full rate limit config record from the database.

    Attributes:
        id: UUID primary key.
        endpoint_type: The endpoint type (e.g., 'suno', 'image', 'llm', 'default').
        max_requests: Maximum requests allowed in the window.
        window_seconds: Duration of the sliding window in seconds.
        updated_at: Last modification timestamp.
    """

    id: str
    endpoint_type: str
    max_requests: int
    window_seconds: int
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Database Protocol
# ---------------------------------------------------------------------------


class DatabaseProtocol(Protocol):
    """Minimal async database interface."""

    async def execute(self, query: str, *args: Any) -> None: ...
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...
    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class RateLimitConfigRepository:
    """Repository for rate_limit_config table operations.

    Provides:
        - get_all: Return all configured rate limit records.
        - get_config: Return config for a specific endpoint type (implements the Protocol).
        - upsert: Insert or update a rate limit config record.

    Args:
        db: Async database connection or pool.
    """

    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def get_all(self) -> list[RateLimitConfigRecord]:
        """Return all rate limit configuration records.

        Returns:
            List of all RateLimitConfigRecord entries, ordered by endpoint_type.
        """
        rows = await self._db.fetch(
            """
            SELECT id, endpoint_type, max_requests, window_seconds, updated_at
            FROM rate_limit_config
            ORDER BY endpoint_type
            """
        )
        return [self._row_to_record(row) for row in rows]

    async def get_config(self, endpoint_type: str) -> RateLimitConfig | None:
        """Return rate limit config for a specific endpoint type.

        This method satisfies the RateLimitConfigRepository Protocol from
        middleware/rate_limit.py.

        Args:
            endpoint_type: The endpoint type to look up.

        Returns:
            RateLimitConfig if found, None otherwise.
        """
        row = await self._db.fetchrow(
            """
            SELECT max_requests, window_seconds
            FROM rate_limit_config
            WHERE endpoint_type = $1
            """,
            endpoint_type,
        )
        if row is None:
            return None
        return RateLimitConfig(
            max_requests=row["max_requests"],
            window_seconds=row["window_seconds"],
        )

    async def upsert(
        self,
        endpoint_type: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitConfigRecord:
        """Insert or update a rate limit configuration record.

        Uses PostgreSQL's ON CONFLICT ... DO UPDATE (upsert) semantics.

        Args:
            endpoint_type: The endpoint type to configure.
            max_requests: Maximum requests allowed in the window.
            window_seconds: Duration of the sliding window in seconds.

        Returns:
            The upserted RateLimitConfigRecord.
        """
        row = await self._db.fetchrow(
            """
            INSERT INTO rate_limit_config (endpoint_type, max_requests, window_seconds, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (endpoint_type) DO UPDATE SET
                max_requests = EXCLUDED.max_requests,
                window_seconds = EXCLUDED.window_seconds,
                updated_at = NOW()
            RETURNING id, endpoint_type, max_requests, window_seconds, updated_at
            """,
            endpoint_type,
            max_requests,
            window_seconds,
        )
        if row is None:
            # Shouldn't happen with RETURNING, but be safe
            return RateLimitConfigRecord(
                id="",
                endpoint_type=endpoint_type,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
        return self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> RateLimitConfigRecord:
        """Convert a database row to a RateLimitConfigRecord."""
        return RateLimitConfigRecord(
            id=str(row["id"]) if row.get("id") else "",
            endpoint_type=row.get("endpoint_type", ""),
            max_requests=row.get("max_requests", 60),
            window_seconds=row.get("window_seconds", 60),
            updated_at=row.get("updated_at"),
        )
