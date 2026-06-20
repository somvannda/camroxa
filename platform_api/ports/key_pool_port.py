"""Key pool repository protocol interface.

Defines the contract for API key pool database operations including
CRUD operations for key entries, provider configuration, usage counters,
and event log queries.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import ApiKeyEntry, KeyPoolConfig


class KeyPoolRepositoryPort(Protocol):
    """Port for API key pool database operations.

    Implementations handle storage and retrieval of API key entries,
    per-provider configuration, usage counter management, and
    status transition event queries.
    """

    async def list_by_provider(self, provider: str) -> list[ApiKeyEntry]:
        """Return all key entries for a provider, regardless of status."""
        ...

    async def get_active_by_provider(self, provider: str) -> list[ApiKeyEntry]:
        """Return only active key entries for a provider, ordered by priority."""
        ...

    async def get_by_id(self, key_id: UUID) -> ApiKeyEntry | None:
        """Return a single key entry by ID, or None if not found."""
        ...

    async def create(self, entry: ApiKeyEntry) -> ApiKeyEntry:
        """Insert a new key entry and return it with generated defaults."""
        ...

    async def update(self, entry: ApiKeyEntry) -> None:
        """Update an existing key entry (all mutable fields)."""
        ...

    async def delete(self, key_id: UUID) -> None:
        """Delete a key entry by ID."""
        ...

    async def get_provider_config(self, provider: str) -> KeyPoolConfig | None:
        """Return the pool configuration for a provider, or None if not configured."""
        ...

    async def upsert_provider_config(self, config: KeyPoolConfig) -> None:
        """Insert or update the pool configuration for a provider."""
        ...

    async def increment_counters(
        self, key_id: UUID, *, success: bool, rate_limited: bool = False
    ) -> None:
        """Increment usage counters for a key after a request.

        Increments total_requests and daily_requests unconditionally.
        Increments success_count if success=True, otherwise failure_count.
        Increments rate_limit_hits if rate_limited=True.
        Updates last_used_at to NOW().
        """
        ...

    async def reset_daily_counters(self) -> None:
        """Reset daily_requests to 0 for all key entries (midnight UTC reset)."""
        ...

    async def get_usage_stats(self, key_id: UUID) -> dict[str, Any]:
        """Return usage statistics for a specific key entry."""
        ...

    async def get_recent_events(self, provider: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent status transition events for a provider."""
        ...
