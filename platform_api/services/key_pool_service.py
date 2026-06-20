"""Key pool service implementing key selection, management, and pool operations.

Provides round-robin and priority-based key selection strategies, key CRUD
operations, provider configuration, pool health status, Redis-backed
position tracking for deterministic round-robin cycling, automatic
failover with cooldown recovery, and cooldown-based key recovery.

Requirements: 2.1, 2.2, 2.3, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis

from platform_api.exceptions import DuplicateKeyLabelError, NoAvailableKeysError
from platform_api.models.domain import ApiKeyEntry, KeyPoolConfig, KeyStatusEvent
from platform_api.models.enums import KeyStatus, SelectionStrategy
from platform_api.repositories.key_pool_repo import KeyPoolRepository
from platform_api.services.key_encryption import KeyEncryption

logger = logging.getLogger(__name__)


class KeyPoolService:
    """Core key pool service for managing API keys across providers.

    Implements key selection using configurable strategies (round_robin or
    priority), key CRUD operations with encryption, and pool health monitoring.

    Args:
        repository: The key pool database repository.
        encryption: The encryption utility for key values.
        redis: An async Redis client for caching and round-robin tracking.
    """

    def __init__(
        self,
        repository: KeyPoolRepository,
        encryption: KeyEncryption,
        redis: Redis,
    ) -> None:
        self._repo = repository
        self._encryption = encryption
        self._redis = redis

    # -----------------------------------------------------------------------
    # Key Selection
    # -----------------------------------------------------------------------

    async def get_key(self, provider: str) -> str:
        """Select the next available API key for a provider.

        Applies the configured selection strategy to choose an active key.
        Filters out keys with non-active status (rate_limited, exhausted,
        disabled) from the candidate pool.

        Args:
            provider: The provider identifier (e.g. "suno", "fal").

        Returns:
            The decrypted API key value string.

        Raises:
            NoAvailableKeysError: If no active keys exist for the provider.
        """
        active_keys = await self._get_active_keys(provider)

        if not active_keys:
            # Build status counts for the error
            all_keys = await self._repo.list_by_provider(provider)
            status_counts = self._compute_status_counts(all_keys)
            raise NoAvailableKeysError(provider=provider, status_counts=status_counts)

        config = await self._get_provider_config(provider)
        strategy = config.selection_strategy

        if strategy == SelectionStrategy.ROUND_ROBIN:
            selected = await self._select_round_robin(provider, active_keys)
        else:
            selected = await self._select_priority(provider, active_keys)

        return self._encryption.decrypt(selected.encrypted_key_value)

    async def _select_round_robin(
        self, provider: str, active_keys: list[ApiKeyEntry]
    ) -> ApiKeyEntry:
        """Select the next key using round-robin cycling.

        Uses a Redis counter `key_pool:{provider}:rr_position` to track
        the current position. The counter is incremented atomically and
        the position wraps around the number of active keys.

        Args:
            provider: The provider identifier.
            active_keys: List of active keys to cycle through (sorted by
                         priority then created_at for deterministic ordering).

        Returns:
            The selected ApiKeyEntry.
        """
        rr_key = f"key_pool:{provider}:rr_position"
        # INCR returns the value after increment (starts at 1 for new keys)
        position: int = await self._redis.incr(rr_key)
        # Use modulo to cycle; position starts at 1, so subtract 1 for 0-based index
        index = (position - 1) % len(active_keys)
        selected: ApiKeyEntry = active_keys[index]
        logger.debug(
            "Round-robin selected key %s (position=%d, index=%d) for %s",
            selected.id,
            position,
            index,
            provider,
        )
        return selected

    async def _select_priority(
        self, provider: str, active_keys: list[ApiKeyEntry]
    ) -> ApiKeyEntry:
        """Select the key with the lowest priority number.

        When multiple keys share the same lowest priority, uses round-robin
        among the tied keys via a separate Redis counter.

        Args:
            provider: The provider identifier.
            active_keys: List of active keys sorted by priority ASC.

        Returns:
            The selected ApiKeyEntry.
        """
        # active_keys is already sorted by priority ASC, created_at ASC
        lowest_priority = active_keys[0].priority
        tied_keys = [k for k in active_keys if k.priority == lowest_priority]

        if len(tied_keys) == 1:
            return tied_keys[0]

        # Round-robin among tied keys
        rr_key = f"key_pool:{provider}:priority_rr:{lowest_priority}"
        position: int = await self._redis.incr(rr_key)
        index = (position - 1) % len(tied_keys)
        selected: ApiKeyEntry = tied_keys[index]
        logger.debug(
            "Priority selected key %s (priority=%d, tie_index=%d) for %s",
            selected.id,
            lowest_priority,
            index,
            provider,
        )
        return selected

    # -----------------------------------------------------------------------
    # Key Management (CRUD)
    # -----------------------------------------------------------------------

    async def add_key(
        self, provider: str, key_value: str, label: str, priority: int
    ) -> UUID:
        """Add a new key to a provider's pool.

        Encrypts the key value, validates uniqueness of the label within
        the provider, and stores with initial status of active.

        Args:
            provider: The provider identifier.
            key_value: The raw API key string (1–500 characters).
            label: User-friendly label (1–100 characters, unique per provider).
            priority: Selection priority (1–100, lower = higher priority).

        Returns:
            The UUID of the newly created key entry.

        Raises:
            DuplicateKeyLabelError: If label already exists for this provider.
        """
        # Check for duplicate label
        existing_keys = await self._repo.list_by_provider(provider)
        for key in existing_keys:
            if key.label == label:
                raise DuplicateKeyLabelError(provider=provider, label=label)

        encrypted_value = self._encryption.encrypt(key_value)
        entry = ApiKeyEntry(
            id=uuid4(),
            provider=provider,
            label=label,
            encrypted_key_value=encrypted_value,
            priority=priority,
            status=KeyStatus.ACTIVE,
        )
        created = await self._repo.create(entry)

        # Invalidate cache
        await self._invalidate_cache(provider)

        logger.info("Added key '%s' (id=%s) to provider '%s'", label, created.id, provider)
        return created.id

    async def remove_key(self, key_id: UUID) -> None:
        """Remove a key from the pool.

        Args:
            key_id: The UUID of the key entry to remove.
        """
        entry = await self._repo.get_by_id(key_id)
        if entry is None:
            logger.warning("Attempted to remove non-existent key %s", key_id)
            return

        await self._repo.delete(key_id)
        await self._invalidate_cache(entry.provider)
        logger.info("Removed key %s from provider '%s'", key_id, entry.provider)

    async def update_key(
        self,
        key_id: UUID,
        *,
        label: str | None = None,
        priority: int | None = None,
        key_value: str | None = None,
    ) -> None:
        """Update key metadata (label, priority, or key value).

        Args:
            key_id: The UUID of the key entry to update.
            label: New label (optional).
            priority: New priority (optional).
            key_value: New key value to encrypt and store (optional).
        """
        entry = await self._repo.get_by_id(key_id)
        if entry is None:
            logger.warning("Attempted to update non-existent key %s", key_id)
            return

        if label is not None:
            # Check for duplicate label within the same provider
            existing_keys = await self._repo.list_by_provider(entry.provider)
            for key in existing_keys:
                if key.label == label and key.id != key_id:
                    raise DuplicateKeyLabelError(provider=entry.provider, label=label)
            entry.label = label

        if priority is not None:
            entry.priority = priority

        if key_value is not None:
            entry.encrypted_key_value = self._encryption.encrypt(key_value)

        await self._repo.update(entry)
        await self._invalidate_cache(entry.provider)
        logger.info("Updated key %s", key_id)

    async def set_key_status(self, key_id: UUID, status: str) -> None:
        """Manually set key status (enable/disable).

        Args:
            key_id: The UUID of the key entry.
            status: The new status string ("active" or "disabled").
        """
        entry = await self._repo.get_by_id(key_id)
        if entry is None:
            logger.warning("Attempted to set status on non-existent key %s", key_id)
            return

        entry.status = KeyStatus(status)
        await self._repo.update(entry)
        await self._invalidate_cache(entry.provider)
        logger.info("Set key %s status to '%s'", key_id, status)

    # -----------------------------------------------------------------------
    # Key Queries (for admin router)
    # -----------------------------------------------------------------------

    async def list_keys(self, provider: str) -> list[ApiKeyEntry]:
        """List all keys for a provider (all statuses).

        Args:
            provider: The provider identifier.

        Returns:
            List of all ApiKeyEntry records for the provider.
        """
        return await self._repo.list_by_provider(provider)

    async def get_key_entry(self, key_id: UUID) -> ApiKeyEntry:
        """Get a single key entry by ID.

        Args:
            key_id: The UUID of the key entry.

        Returns:
            The ApiKeyEntry if found.

        Raises:
            ValueError: If the key does not exist.
        """
        entry = await self._repo.get_by_id(key_id)
        if entry is None:
            raise ValueError(f"Key entry not found: {key_id}")
        return entry

    async def get_provider_config(self, provider: str) -> KeyPoolConfig:
        """Get provider pool configuration (public interface).

        Returns the existing configuration or a default one.

        Args:
            provider: The provider identifier.

        Returns:
            The provider's KeyPoolConfig.
        """
        return await self._get_provider_config(provider)

    async def get_recent_events(self, provider: str, limit: int = 50) -> list[dict]:
        """Get recent status transition events for a provider.

        Args:
            provider: The provider identifier.
            limit: Maximum number of events to return.

        Returns:
            List of event dicts suitable for KeyStatusEventResponse.
        """
        return await self._repo.get_recent_events(provider, limit=limit)

    async def get_all_providers_health(self) -> list[dict]:
        """Get health summary for all providers with key entries.

        Returns:
            List of health dicts suitable for ProviderHealthResponse.
        """
        providers = await self._repo.get_all_providers()
        results = []
        for provider in providers:
            status = await self.get_pool_status(provider)
            results.append(status)
        return results

    async def get_cooldown_remaining(self, provider: str, key_id: UUID) -> int | None:
        """Get remaining cooldown seconds for a rate-limited key.

        Args:
            provider: The provider identifier.
            key_id: The UUID of the key entry.

        Returns:
            Remaining seconds, or None if no cooldown is active.
        """
        cooldown_key = f"key_pool:{provider}:cooldown:{key_id}"
        try:
            ttl = await self._redis.ttl(cooldown_key)
            if ttl > 0:
                return ttl
        except Exception:
            pass
        return None

    # -----------------------------------------------------------------------
    # Provider Configuration
    # -----------------------------------------------------------------------

    async def configure_provider(
        self,
        provider: str,
        *,
        strategy: str | None = None,
        cooldown_seconds: int | None = None,
    ) -> None:
        """Configure selection strategy and cooldown for a provider.

        Creates a new configuration if none exists, or updates the existing one.

        Args:
            provider: The provider identifier.
            strategy: Selection strategy ("round_robin" or "priority").
            cooldown_seconds: Cooldown duration in seconds (10–3600).
        """
        config = await self._repo.get_provider_config(provider)
        if config is None:
            config = KeyPoolConfig(
                id=uuid4(),
                provider=provider,
            )

        if strategy is not None:
            config.selection_strategy = SelectionStrategy(strategy)

        if cooldown_seconds is not None:
            config.cooldown_seconds = cooldown_seconds

        await self._repo.upsert_provider_config(config)

        # Reset round-robin position when strategy changes
        if strategy is not None:
            await self._redis.delete(f"key_pool:{provider}:rr_position")

        logger.info(
            "Configured provider '%s': strategy=%s, cooldown=%ds",
            provider,
            config.selection_strategy.value,
            config.cooldown_seconds,
        )

    # -----------------------------------------------------------------------
    # Pool Health Status
    # -----------------------------------------------------------------------

    async def get_pool_status(self, provider: str) -> dict[str, Any]:
        """Get pool health summary for a provider.

        Returns counts of keys in each status and an overall health indicator:
        - "healthy": at least half of keys are active (and at least 1 active)
        - "degraded": some active keys but less than half
        - "critical": no active keys

        Args:
            provider: The provider identifier.

        Returns:
            A dict with total_keys, active_keys, rate_limited_keys,
            exhausted_keys, disabled_keys, and health_indicator.
        """
        all_keys = await self._repo.list_by_provider(provider)
        status_counts = self._compute_status_counts(all_keys)

        total = len(all_keys)
        active = status_counts.get("active", 0)

        if total == 0:
            health_indicator = "critical"
        elif active == 0:
            health_indicator = "critical"
        elif active >= total / 2:
            health_indicator = "healthy"
        else:
            health_indicator = "degraded"

        return {
            "provider": provider,
            "total_keys": total,
            "active_keys": active,
            "rate_limited_keys": status_counts.get("rate_limited", 0),
            "exhausted_keys": status_counts.get("exhausted", 0),
            "disabled_keys": status_counts.get("disabled", 0),
            "health_indicator": health_indicator,
        }

    # -----------------------------------------------------------------------
    # Failover and Cooldown
    # -----------------------------------------------------------------------

    async def execute_with_failover(
        self,
        provider: str,
        execute_fn: Callable[[str], Awaitable[Any]],
        max_retries: int = 3,
    ) -> Any:
        """Execute a request with automatic key failover on failure.

        Selects an API key from the provider's pool and calls `execute_fn`
        with the decrypted key value. On HTTP 429 or 402/403 billing errors,
        marks the key appropriately and retries with the next available key.

        Max 3 total attempts (initial + 2 retries). If all attempts fail,
        the last exception is re-raised.

        Args:
            provider: The provider identifier (e.g. "suno", "fal").
            execute_fn: An async callable that takes an API key string and
                        performs the HTTP request. Should raise
                        httpx.HTTPStatusError on non-2xx responses.
            max_retries: Maximum total attempts (default 3).

        Returns:
            The response from a successful execute_fn call.

        Raises:
            NoAvailableKeysError: If no active keys are available.
            httpx.HTTPStatusError: If all retry attempts fail (re-raises last).
        """
        tried_key_ids: set[UUID] = set()
        last_exception: BaseException | None = None

        for attempt in range(max_retries):
            # Get active keys excluding already-tried ones
            active_keys = await self._get_active_keys(provider)
            available_keys = [k for k in active_keys if k.id not in tried_key_ids]

            if not available_keys:
                # No more keys to try
                if attempt == 0:
                    # No active keys at all
                    all_keys = await self._repo.list_by_provider(provider)
                    status_counts = self._compute_status_counts(all_keys)
                    raise NoAvailableKeysError(
                        provider=provider, status_counts=status_counts
                    )
                # All keys exhausted during retries — re-raise last error
                break

            # Select key using configured strategy (from available subset)
            config = await self._get_provider_config(provider)
            if config.selection_strategy == SelectionStrategy.ROUND_ROBIN:
                selected = await self._select_round_robin(provider, available_keys)
            else:
                selected = await self._select_priority(provider, available_keys)

            tried_key_ids.add(selected.id)
            decrypted_key = self._encryption.decrypt(selected.encrypted_key_value)

            try:
                response = await execute_fn(decrypted_key)
                # Success — report and return
                await self.report_key_success(provider, selected.id)
                return response

            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status_code = exc.response.status_code
                response_body = exc.response.text[:500] if exc.response.text else ""

                if status_code == 429:
                    # Rate limited — mark key and retry
                    await self._handle_rate_limited(
                        provider, selected, exc, response_body
                    )
                    logger.warning(
                        "Failover [attempt %d/%d] key %s (%s) rate-limited (429) "
                        "for provider '%s'. Retrying with next key.",
                        attempt + 1,
                        max_retries,
                        selected.id,
                        selected.label,
                        provider,
                    )
                elif status_code in (402, 403):
                    # Billing exhausted — mark key and retry
                    await self._handle_exhausted(
                        provider, selected, status_code, response_body
                    )
                    logger.warning(
                        "Failover [attempt %d/%d] key %s (%s) exhausted (%d) "
                        "for provider '%s'. Retrying with next key.",
                        attempt + 1,
                        max_retries,
                        selected.id,
                        selected.label,
                        status_code,
                        provider,
                    )
                else:
                    # Other HTTP errors — report failure and re-raise immediately
                    await self.report_key_failure(
                        provider, selected.id, status_code, response_body
                    )
                    raise

        # All retries exhausted — re-raise last error
        if last_exception is not None:
            raise last_exception
        # Shouldn't reach here, but guard against it
        all_keys = await self._repo.list_by_provider(provider)
        status_counts = self._compute_status_counts(all_keys)
        raise NoAvailableKeysError(provider=provider, status_counts=status_counts)

    async def report_key_success(self, provider: str, key_id: UUID) -> None:
        """Report a successful API call for usage tracking.

        Increments counters in both PostgreSQL (durability) and Redis (fast path).
        Redis counters provide low-latency reads for the dashboard; PostgreSQL
        ensures counters survive Redis eviction or restarts.

        Args:
            provider: The provider identifier.
            key_id: The UUID of the key that succeeded.
        """
        # PostgreSQL (durable store)
        await self._repo.increment_counters(key_id, success=True)

        # Redis fast-path counters for low-latency dashboard reads
        await self._increment_redis_counters(provider, key_id, success=True)

        logger.debug("Reported success for key %s (provider=%s)", key_id, provider)

    async def report_key_failure(
        self, provider: str, key_id: UUID, status_code: int, response_body: str
    ) -> None:
        """Report a failed API call — triggers status transitions and logging.

        For HTTP 429: marks key as rate_limited and sets cooldown.
        For HTTP 402/403: marks key as exhausted.
        For other errors: increments failure counter without status change.

        Increments counters in both PostgreSQL (durability) and Redis (fast path).

        Args:
            provider: The provider identifier.
            key_id: The UUID of the key that failed.
            status_code: The HTTP status code received.
            response_body: A summary of the response body (truncated).
        """
        is_rate_limited = status_code == 429

        if is_rate_limited:
            # Handled by _handle_rate_limited in execute_with_failover
            await self._repo.increment_counters(
                key_id, success=False, rate_limited=True
            )
        elif status_code in (402, 403):
            # Handled by _handle_exhausted in execute_with_failover
            await self._repo.increment_counters(key_id, success=False)
        else:
            # General failure — just increment counters
            await self._repo.increment_counters(key_id, success=False)

        # Redis fast-path counters
        await self._increment_redis_counters(
            provider, key_id, success=False, rate_limited=is_rate_limited
        )

        logger.debug(
            "Reported failure for key %s (provider=%s, status=%d)",
            key_id,
            provider,
            status_code,
        )

    # -----------------------------------------------------------------------
    # Failover Helpers
    # -----------------------------------------------------------------------

    async def _handle_rate_limited(
        self,
        provider: str,
        key_entry: ApiKeyEntry,
        exc: httpx.HTTPStatusError,
        response_body: str,
    ) -> None:
        """Handle a 429 rate-limited response for a key.

        Marks the key as rate_limited, sets a cooldown TTL in Redis,
        records a status event, and increments counters.

        Args:
            provider: The provider identifier.
            key_entry: The key entry that was rate-limited.
            exc: The httpx exception with response details.
            response_body: Truncated response body for logging.
        """
        previous_status = key_entry.status

        # Determine cooldown duration
        config = await self._get_provider_config(provider)
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            cooldown_seconds = min(int(retry_after), 3600)
        else:
            cooldown_seconds = config.cooldown_seconds

        # Update key status in database
        key_entry.status = KeyStatus.RATE_LIMITED
        key_entry.rate_limited_at = datetime.utcnow()
        await self._repo.update(key_entry)

        # Set cooldown TTL in Redis
        cooldown_key = f"key_pool:{provider}:cooldown:{key_entry.id}"
        await self._redis.set(cooldown_key, "1", ex=cooldown_seconds)

        # Increment counters (rate-limited)
        await self._repo.increment_counters(
            key_entry.id, success=False, rate_limited=True
        )

        # Record status event
        await self._record_status_event(
            key_entry=key_entry,
            provider=provider,
            previous_status=previous_status,
            new_status=KeyStatus.RATE_LIMITED,
            trigger_reason="rate_limit_429",
            http_status_code=429,
            response_summary=response_body[:200] if response_body else None,
        )

        # Invalidate cache
        await self._invalidate_cache(provider)

    async def _handle_exhausted(
        self,
        provider: str,
        key_entry: ApiKeyEntry,
        status_code: int,
        response_body: str,
    ) -> None:
        """Handle a 402/403 billing-exhausted response for a key.

        Marks the key as exhausted, records a status event, and increments
        counters. Exhausted keys never auto-recover.

        Args:
            provider: The provider identifier.
            key_entry: The key entry that was exhausted.
            status_code: The HTTP status code (402 or 403).
            response_body: Truncated response body for logging.
        """
        previous_status = key_entry.status

        # Update key status in database
        key_entry.status = KeyStatus.EXHAUSTED
        await self._repo.update(key_entry)

        # Increment counters
        await self._repo.increment_counters(key_entry.id, success=False)

        # Record status event
        trigger = f"exhausted_{status_code}"
        await self._record_status_event(
            key_entry=key_entry,
            provider=provider,
            previous_status=previous_status,
            new_status=KeyStatus.EXHAUSTED,
            trigger_reason=trigger,
            http_status_code=status_code,
            response_summary=response_body[:200] if response_body else None,
        )

        # Invalidate cache
        await self._invalidate_cache(provider)

    async def _record_status_event(
        self,
        *,
        key_entry: ApiKeyEntry,
        provider: str,
        previous_status: KeyStatus,
        new_status: KeyStatus,
        trigger_reason: str,
        http_status_code: int | None = None,
        response_summary: str | None = None,
    ) -> None:
        """Record a key status transition event in the database.

        Creates a KeyStatusEvent and inserts it into the key_status_events
        table for audit and dashboard display.

        Args:
            key_entry: The key whose status changed.
            provider: The provider identifier.
            previous_status: The status before the transition.
            new_status: The status after the transition.
            trigger_reason: Why the transition occurred.
            http_status_code: The HTTP status code that triggered it (optional).
            response_summary: A summary of the response (optional).
        """
        event = KeyStatusEvent(
            id=uuid4(),
            key_id=key_entry.id,
            provider=provider,
            key_label=key_entry.label,
            previous_status=previous_status,
            new_status=new_status,
            trigger_reason=trigger_reason,
            http_status_code=http_status_code,
            response_summary=response_summary,
        )
        await self._insert_status_event(event)

    async def _insert_status_event(self, event: KeyStatusEvent) -> None:
        """Insert a KeyStatusEvent record into the database.

        Args:
            event: The KeyStatusEvent to persist.
        """
        await self._repo.insert_status_event(event)

    # -----------------------------------------------------------------------
    # Cooldown Recovery (Requirements 4.1, 4.2, 4.3, 4.4, 4.5)
    # -----------------------------------------------------------------------

    async def _check_and_recover_keys(self, provider: str) -> None:
        """Check rate-limited keys for expired cooldowns and recover them.

        For each rate-limited key in the provider's pool, checks if the
        Redis cooldown TTL key has expired (key no longer exists). If expired,
        transitions the key back to active status and records the recovery event.

        Exhausted keys are NEVER auto-recovered regardless of time elapsed.
        Configuration changes to cooldown_seconds do NOT affect keys already
        in cooldown — the original TTL set at rate-limit time is honored.

        This method is called before key selection to ensure recovered keys
        are included in the active pool.

        Args:
            provider: The provider identifier.
        """
        all_keys = await self._repo.list_by_provider(provider)
        rate_limited_keys = [
            k for k in all_keys if k.status == KeyStatus.RATE_LIMITED
        ]

        if not rate_limited_keys:
            return

        for key in rate_limited_keys:
            cooldown_key = f"key_pool:{provider}:cooldown:{key.id}"
            exists = await self._redis.exists(cooldown_key)

            if not exists:
                # Cooldown has expired — recover key to active
                previous_status = key.status
                key.status = KeyStatus.ACTIVE
                key.rate_limited_at = None
                await self._repo.update(key)

                # Record recovery event
                await self._record_status_event(
                    key_entry=key,
                    provider=provider,
                    previous_status=previous_status,
                    new_status=KeyStatus.ACTIVE,
                    trigger_reason="cooldown_recovery",
                )

                logger.info(
                    "Recovered key %s (label='%s') from rate_limited to active "
                    "(provider='%s', cooldown expired)",
                    key.id,
                    key.label,
                    provider,
                )

        # Invalidate cache if any keys were recovered
        recovered = [
            k for k in rate_limited_keys if k.status == KeyStatus.ACTIVE
        ]
        if recovered:
            await self._invalidate_cache(provider)

    # -----------------------------------------------------------------------
    # Usage Tracking (Requirements 5.1, 5.2, 5.3, 5.4, 5.5)
    # -----------------------------------------------------------------------

    async def reset_daily_counters(self) -> None:
        """Reset daily request counters for all keys at midnight UTC.

        Resets daily_requests to 0 in PostgreSQL (durable store) and deletes
        all daily Redis counter keys. Preserves total counters (total_requests,
        success_count, failure_count, rate_limit_hits).

        This method should be called by a scheduled task at midnight UTC.
        """
        # Reset in PostgreSQL (durable store)
        await self._repo.reset_daily_counters()

        # Reset Redis daily counters by scanning and deleting matching keys
        # Use pattern matching to find all daily counter keys
        pattern = "key_pool:*:daily_*"
        try:
            cursor: int | bytes = 0
            deleted_count = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break
            logger.info(
                "Reset daily counters: deleted %d Redis keys", deleted_count
            )
        except Exception:
            # Redis failure is non-fatal — PostgreSQL is the source of truth
            logger.warning(
                "Failed to reset Redis daily counters (non-fatal, "
                "PostgreSQL counters were reset successfully)"
            )

    async def _increment_redis_counters(
        self,
        provider: str,
        key_id: UUID,
        *,
        success: bool,
        rate_limited: bool = False,
    ) -> None:
        """Increment usage counters in Redis for fast dashboard reads.

        Stores daily counters at keys like:
        - key_pool:{provider}:{key_id}:daily_requests
        - key_pool:{provider}:{key_id}:daily_success
        - key_pool:{provider}:{key_id}:daily_failures
        - key_pool:{provider}:{key_id}:daily_rate_limits

        These are reset at midnight UTC by reset_daily_counters.

        Args:
            provider: The provider identifier.
            key_id: The UUID of the key.
            success: Whether the request succeeded.
            rate_limited: Whether the request received a 429 response.
        """
        prefix = f"key_pool:{provider}:{key_id}"
        try:
            await self._redis.incr(f"{prefix}:daily_requests")
            if success:
                await self._redis.incr(f"{prefix}:daily_success")
            else:
                await self._redis.incr(f"{prefix}:daily_failures")
            if rate_limited:
                await self._redis.incr(f"{prefix}:daily_rate_limits")
        except Exception:
            # Redis failure for counters is non-fatal — PostgreSQL has the
            # durable copy. Log and continue.
            logger.warning(
                "Failed to increment Redis counters for key %s (non-fatal)",
                key_id,
            )

    # -----------------------------------------------------------------------
    # Redis Cache Layer (Requirements 8.4, 8.5)
    # -----------------------------------------------------------------------

    async def populate_cache(self, provider: str) -> None:
        """Populate the Redis active keys ZSET and rate_limited SET for a provider.

        Loads active keys from PostgreSQL and stores them in a sorted set
        scored by priority. Also rebuilds the rate_limited set.

        Called on startup and after cache invalidation.

        Args:
            provider: The provider identifier.
        """
        try:
            active_keys = await self._repo.get_active_by_provider(provider)
            all_keys = await self._repo.list_by_provider(provider)

            active_zset_key = f"key_pool:{provider}:active"
            rate_limited_set_key = f"key_pool:{provider}:rate_limited"

            # Clear and rebuild the active ZSET
            await self._redis.delete(active_zset_key)
            if active_keys:
                # zadd expects mapping {member: score}
                mapping: dict[str, float] = {
                    str(key.id): float(key.priority) for key in active_keys
                }
                await self._redis.zadd(active_zset_key, mapping)

            # Clear and rebuild the rate_limited SET
            await self._redis.delete(rate_limited_set_key)
            rate_limited_keys = [
                k for k in all_keys if k.status == KeyStatus.RATE_LIMITED
            ]
            if rate_limited_keys:
                members = [str(k.id) for k in rate_limited_keys]
                await self._redis.sadd(rate_limited_set_key, *members)

            logger.debug(
                "Populated cache for provider '%s': %d active keys, %d rate-limited",
                provider,
                len(active_keys),
                len(rate_limited_keys),
            )
        except Exception:
            logger.warning(
                "Failed to populate Redis cache for provider '%s' (non-fatal)",
                provider,
            )

    async def load_all_caches(self) -> None:
        """Load Redis caches for all providers with key entries.

        Called on application startup to warm the cache. Iterates through
        all distinct providers that have at least one key entry.
        """
        try:
            providers = await self._repo.get_all_providers()
            for provider in providers:
                await self.populate_cache(provider)
            logger.info(
                "Loaded Redis caches for %d providers on startup", len(providers)
            )
        except Exception:
            logger.warning(
                "Failed to load Redis caches on startup (non-fatal, "
                "falling back to direct DB queries)"
            )

    async def _get_cached_active_key_ids(self, provider: str) -> list[str] | None:
        """Try to get active key IDs from Redis ZSET cache.

        Returns a list of key ID strings ordered by priority (score), or
        None if Redis is unavailable or cache is empty.

        Args:
            provider: The provider identifier.

        Returns:
            List of key ID strings or None on cache miss/error.
        """
        try:
            active_zset_key = f"key_pool:{provider}:active"
            # ZRANGE returns members ordered by score (priority) ascending
            members = await self._redis.zrange(active_zset_key, 0, -1)
            if members:
                return [m.decode() if isinstance(m, bytes) else m for m in members]
            return None
        except Exception:
            logger.warning(
                "Redis unavailable for active keys cache (provider='%s'), "
                "falling back to PostgreSQL",
                provider,
            )
            return None

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    async def _get_active_keys(self, provider: str) -> list[ApiKeyEntry]:
        """Fetch active keys for a provider, using Redis cache when available.

        First checks for rate-limited keys whose cooldown has expired and
        recovers them. Then attempts to read from the Redis ZSET cache.
        Falls back to direct PostgreSQL queries if Redis is unavailable.

        Returns keys sorted by priority ASC, created_at ASC.

        Args:
            provider: The provider identifier.

        Returns:
            List of active ApiKeyEntry records.
        """
        # Check and recover any rate-limited keys whose cooldown has expired
        await self._check_and_recover_keys(provider)

        # Try Redis cache first
        cached_ids = await self._get_cached_active_key_ids(provider)
        if cached_ids is not None:
            # We have cached IDs — still need to fetch full entries from DB
            # but this validates which keys are active without a filtered query
            # For simplicity and correctness, use the DB filtered query since
            # the cache may be slightly stale after recovery. The cache primarily
            # serves as a fast-path validation layer.
            pass

        # Fall back to (or confirm with) PostgreSQL
        return await self._repo.get_active_by_provider(provider)

    async def _get_provider_config(self, provider: str) -> KeyPoolConfig:
        """Get provider configuration, returning defaults if not configured.

        Default strategy is PRIORITY with 60-second cooldown.

        Args:
            provider: The provider identifier.

        Returns:
            The provider's KeyPoolConfig (existing or default).
        """
        config = await self._repo.get_provider_config(provider)
        if config is None:
            # Return default config (priority strategy, 60s cooldown)
            config = KeyPoolConfig(provider=provider)
        return config

    async def _invalidate_cache(self, provider: str) -> None:
        """Invalidate the Redis cache for a provider.

        Increments the version counter so any cached data is considered stale,
        and deletes the active ZSET so it will be lazily rebuilt on next access.
        Also updates the rate_limited SET.

        Args:
            provider: The provider identifier.
        """
        try:
            version_key = f"key_pool:{provider}:version"
            active_zset_key = f"key_pool:{provider}:active"
            rate_limited_set_key = f"key_pool:{provider}:rate_limited"

            await self._redis.incr(version_key)
            # Delete the active cache — it will be lazily rebuilt
            await self._redis.delete(active_zset_key)
            # Delete rate_limited set — rebuild on next populate
            await self._redis.delete(rate_limited_set_key)
        except Exception:
            logger.warning(
                "Failed to invalidate Redis cache for provider '%s' (non-fatal)",
                provider,
            )

    @staticmethod
    def _compute_status_counts(keys: list[ApiKeyEntry]) -> dict[str, int]:
        """Compute a count of keys in each status.

        Args:
            keys: List of ApiKeyEntry records.

        Returns:
            Dict mapping status name to count.
        """
        counts: dict[str, int] = {
            "active": 0,
            "rate_limited": 0,
            "exhausted": 0,
            "disabled": 0,
        }
        for key in keys:
            status_name = key.status.value
            if status_name in counts:
                counts[status_name] += 1
        return counts
