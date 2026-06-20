"""Key pool repository with asyncpg for API key entry management.

Provides CRUD operations for API key entries, provider configuration,
usage counter management, and status event log queries.

Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.3, 5.5
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import ApiKeyEntry, KeyPoolConfig, KeyStatusEvent
from platform_api.models.enums import KeyStatus, SelectionStrategy

logger = logging.getLogger(__name__)


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        ...

    async def execute(self, query: str, *args: Any) -> str:
        ...


class KeyPoolRepository:
    """Repository for API key pool operations using asyncpg.

    Implements CRUD for key entries, provider configuration management,
    usage counter increments, daily counter resets, and event log queries.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    # -----------------------------------------------------------------------
    # Key Entry CRUD
    # -----------------------------------------------------------------------

    async def list_by_provider(self, provider: str) -> list[ApiKeyEntry]:
        """Return all key entries for a provider, ordered by priority.

        Args:
            provider: The provider identifier (e.g. "suno", "fal", "openai").

        Returns:
            A list of ApiKeyEntry dataclasses for the provider.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, provider, label, encrypted_key_value, priority, status,
                   total_requests, daily_requests, success_count, failure_count,
                   rate_limit_hits, last_used_at, last_failure_at, rate_limited_at,
                   created_at, updated_at
            FROM api_key_entries
            WHERE provider = $1
            ORDER BY priority ASC, created_at ASC
            """,
            provider,
        )
        return [self._row_to_entry(row) for row in rows]

    async def get_active_by_provider(self, provider: str) -> list[ApiKeyEntry]:
        """Return only active key entries for a provider, ordered by priority.

        Args:
            provider: The provider identifier.

        Returns:
            A list of ApiKeyEntry dataclasses with status='active'.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, provider, label, encrypted_key_value, priority, status,
                   total_requests, daily_requests, success_count, failure_count,
                   rate_limit_hits, last_used_at, last_failure_at, rate_limited_at,
                   created_at, updated_at
            FROM api_key_entries
            WHERE provider = $1 AND status = 'active'
            ORDER BY priority ASC, created_at ASC
            """,
            provider,
        )
        return [self._row_to_entry(row) for row in rows]

    async def get_by_id(self, key_id: UUID) -> ApiKeyEntry | None:
        """Return a single key entry by ID, or None if not found.

        Args:
            key_id: The UUID of the key entry.

        Returns:
            An ApiKeyEntry dataclass or None.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, provider, label, encrypted_key_value, priority, status,
                   total_requests, daily_requests, success_count, failure_count,
                   rate_limit_hits, last_used_at, last_failure_at, rate_limited_at,
                   created_at, updated_at
            FROM api_key_entries
            WHERE id = $1
            """,
            key_id,
        )
        return self._row_to_entry(row) if row else None

    async def create(self, entry: ApiKeyEntry) -> ApiKeyEntry:
        """Insert a new key entry and return it with server-generated defaults.

        Args:
            entry: The ApiKeyEntry to insert. The id, created_at, and
                   updated_at fields will be set by the database if not
                   already populated.

        Returns:
            The inserted ApiKeyEntry with all fields populated.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO api_key_entries
                (id, provider, label, encrypted_key_value, priority, status,
                 total_requests, daily_requests, success_count, failure_count,
                 rate_limit_hits, last_used_at, last_failure_at, rate_limited_at,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                    COALESCE($15, NOW()), COALESCE($16, NOW()))
            RETURNING id, provider, label, encrypted_key_value, priority, status,
                      total_requests, daily_requests, success_count, failure_count,
                      rate_limit_hits, last_used_at, last_failure_at, rate_limited_at,
                      created_at, updated_at
            """,
            entry.id,
            entry.provider,
            entry.label,
            entry.encrypted_key_value,
            entry.priority,
            entry.status.value,
            entry.total_requests,
            entry.daily_requests,
            entry.success_count,
            entry.failure_count,
            entry.rate_limit_hits,
            entry.last_used_at,
            entry.last_failure_at,
            entry.rate_limited_at,
            entry.created_at,
            entry.updated_at,
        )
        return self._row_to_entry(row)

    async def update(self, entry: ApiKeyEntry) -> None:
        """Update an existing key entry (all mutable fields).

        Args:
            entry: The ApiKeyEntry with updated field values. The id field
                   identifies which row to update.
        """
        await self._pool.execute(
            """
            UPDATE api_key_entries
            SET provider = $2,
                label = $3,
                encrypted_key_value = $4,
                priority = $5,
                status = $6,
                total_requests = $7,
                daily_requests = $8,
                success_count = $9,
                failure_count = $10,
                rate_limit_hits = $11,
                last_used_at = $12,
                last_failure_at = $13,
                rate_limited_at = $14,
                updated_at = NOW()
            WHERE id = $1
            """,
            entry.id,
            entry.provider,
            entry.label,
            entry.encrypted_key_value,
            entry.priority,
            entry.status.value,
            entry.total_requests,
            entry.daily_requests,
            entry.success_count,
            entry.failure_count,
            entry.rate_limit_hits,
            entry.last_used_at,
            entry.last_failure_at,
            entry.rate_limited_at,
        )
        logger.debug("Updated key entry %s", entry.id)

    async def delete(self, key_id: UUID) -> None:
        """Delete a key entry by ID.

        Args:
            key_id: The UUID of the key entry to delete.
        """
        await self._pool.execute(
            "DELETE FROM api_key_entries WHERE id = $1",
            key_id,
        )
        logger.info("Deleted key entry %s", key_id)

    # -----------------------------------------------------------------------
    # Provider Configuration
    # -----------------------------------------------------------------------

    async def get_provider_config(self, provider: str) -> KeyPoolConfig | None:
        """Return the pool configuration for a provider, or None if not configured.

        Args:
            provider: The provider identifier.

        Returns:
            A KeyPoolConfig dataclass or None.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, provider, selection_strategy, cooldown_seconds,
                   created_at, updated_at
            FROM key_pool_configs
            WHERE provider = $1
            """,
            provider,
        )
        if row is None:
            return None
        return KeyPoolConfig(
            id=row["id"],
            provider=row["provider"],
            selection_strategy=SelectionStrategy(row["selection_strategy"]),
            cooldown_seconds=row["cooldown_seconds"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def upsert_provider_config(self, config: KeyPoolConfig) -> None:
        """Insert or update the pool configuration for a provider.

        Uses PostgreSQL's ON CONFLICT (provider) DO UPDATE to handle
        both insert and update in a single statement.

        Args:
            config: The KeyPoolConfig to upsert.
        """
        await self._pool.execute(
            """
            INSERT INTO key_pool_configs
                (id, provider, selection_strategy, cooldown_seconds, created_at, updated_at)
            VALUES ($1, $2, $3, $4, COALESCE($5, NOW()), NOW())
            ON CONFLICT (provider) DO UPDATE
            SET selection_strategy = EXCLUDED.selection_strategy,
                cooldown_seconds = EXCLUDED.cooldown_seconds,
                updated_at = NOW()
            """,
            config.id,
            config.provider,
            config.selection_strategy.value,
            config.cooldown_seconds,
            config.created_at,
        )
        logger.debug(
            "Upserted provider config for %s (strategy=%s, cooldown=%ds)",
            config.provider,
            config.selection_strategy.value,
            config.cooldown_seconds,
        )

    # -----------------------------------------------------------------------
    # Provider Listing
    # -----------------------------------------------------------------------

    async def get_all_providers(self) -> list[str]:
        """Return all distinct provider identifiers that have key entries.

        Returns:
            A list of unique provider strings.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT provider FROM api_key_entries ORDER BY provider"
        )
        return [row["provider"] for row in rows]

    # -----------------------------------------------------------------------
    # Usage Counters
    # -----------------------------------------------------------------------

    async def increment_counters(
        self, key_id: UUID, *, success: bool, rate_limited: bool = False
    ) -> None:
        """Increment usage counters for a key after a request.

        Increments total_requests and daily_requests unconditionally.
        Increments success_count if success=True, otherwise failure_count.
        Increments rate_limit_hits if rate_limited=True.
        Updates last_used_at to NOW(). If not a success, updates last_failure_at.

        Args:
            key_id: The UUID of the key entry.
            success: Whether the request succeeded.
            rate_limited: Whether the request received a 429 response.
        """
        success_inc = 1 if success else 0
        failure_inc = 0 if success else 1
        rate_limit_inc = 1 if rate_limited else 0

        await self._pool.execute(
            """
            UPDATE api_key_entries
            SET total_requests = total_requests + 1,
                daily_requests = daily_requests + 1,
                success_count = success_count + $2,
                failure_count = failure_count + $3,
                rate_limit_hits = rate_limit_hits + $4,
                last_used_at = NOW(),
                last_failure_at = CASE WHEN $5 THEN last_failure_at ELSE NOW() END,
                updated_at = NOW()
            WHERE id = $1
            """,
            key_id,
            success_inc,
            failure_inc,
            rate_limit_inc,
            success,
        )
        logger.debug(
            "Incremented counters for key %s (success=%s, rate_limited=%s)",
            key_id,
            success,
            rate_limited,
        )

    async def reset_daily_counters(self) -> None:
        """Reset daily_requests to 0 for all key entries.

        Called at midnight UTC. Preserves total counters (total_requests,
        success_count, failure_count, rate_limit_hits).
        """
        result = await self._pool.execute(
            """
            UPDATE api_key_entries
            SET daily_requests = 0,
                updated_at = NOW()
            WHERE daily_requests > 0
            """
        )
        logger.info("Reset daily counters: %s", result)

    # -----------------------------------------------------------------------
    # Status Events
    # -----------------------------------------------------------------------

    async def insert_status_event(self, event: KeyStatusEvent) -> None:
        """Insert a key status transition event into the database.

        Args:
            event: The KeyStatusEvent dataclass to persist.
        """
        await self._pool.execute(
            """
            INSERT INTO key_status_events
                (id, key_id, provider, key_label, previous_status, new_status,
                 trigger_reason, http_status_code, response_summary, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, COALESCE($10, NOW()))
            """,
            event.id,
            event.key_id,
            event.provider,
            event.key_label,
            event.previous_status.value,
            event.new_status.value,
            event.trigger_reason,
            event.http_status_code,
            event.response_summary,
            event.created_at,
        )
        logger.debug(
            "Inserted status event: key %s %s → %s (%s)",
            event.key_id,
            event.previous_status.value,
            event.new_status.value,
            event.trigger_reason,
        )

    # -----------------------------------------------------------------------
    # Usage Stats & Events
    # -----------------------------------------------------------------------

    async def get_usage_stats(self, key_id: UUID) -> dict[str, Any]:
        """Return usage statistics for a specific key entry.

        Args:
            key_id: The UUID of the key entry.

        Returns:
            A dict with total_requests, daily_requests, success_count,
            failure_count, rate_limit_hits, last_used_at, and success_rate.
        """
        row = await self._pool.fetchrow(
            """
            SELECT total_requests, daily_requests, success_count, failure_count,
                   rate_limit_hits, last_used_at, last_failure_at
            FROM api_key_entries
            WHERE id = $1
            """,
            key_id,
        )
        if row is None:
            return {}

        total = row["total_requests"]
        success_rate = (
            round(row["success_count"] / total * 100, 1) if total > 0 else 0.0
        )

        return {
            "total_requests": total,
            "daily_requests": row["daily_requests"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "rate_limit_hits": row["rate_limit_hits"],
            "last_used_at": row["last_used_at"],
            "last_failure_at": row["last_failure_at"],
            "success_rate": success_rate,
        }

    async def get_recent_events(self, provider: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent status transition events for a provider.

        Args:
            provider: The provider identifier.
            limit: Maximum number of events to return (default 50).

        Returns:
            A list of dicts with event details, ordered by created_at DESC.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, key_id, provider, key_label, previous_status, new_status,
                   trigger_reason, http_status_code, response_summary, created_at
            FROM key_status_events
            WHERE provider = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            provider,
            limit,
        )
        return [
            {
                "id": row["id"],
                "key_id": row["key_id"],
                "provider": row["provider"],
                "key_label": row["key_label"],
                "previous_status": row["previous_status"],
                "new_status": row["new_status"],
                "trigger_reason": row["trigger_reason"],
                "http_status_code": row["http_status_code"],
                "response_summary": row["response_summary"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _row_to_entry(row: Any) -> ApiKeyEntry:
        """Convert a database row (asyncpg Record) to an ApiKeyEntry dataclass."""
        return ApiKeyEntry(
            id=row["id"],
            provider=row["provider"],
            label=row["label"],
            encrypted_key_value=row["encrypted_key_value"],
            priority=row["priority"],
            status=KeyStatus(row["status"]),
            total_requests=row["total_requests"],
            daily_requests=row["daily_requests"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            rate_limit_hits=row["rate_limit_hits"],
            last_used_at=row["last_used_at"],
            last_failure_at=row["last_failure_at"],
            rate_limited_at=row["rate_limited_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
