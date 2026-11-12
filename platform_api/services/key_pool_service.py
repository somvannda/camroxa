"""Key pool service implementing key selection, management, and pool operations.

Provides round-robin and priority-based key selection strategies, key CRUD
operations, provider configuration, pool health status, Redis-backed
position tracking for deterministic round-robin cycling, automatic
failover with cooldown recovery, and cooldown-based key recovery.

Requirements: 2.1, 2.2, 2.3, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis

from platform_api.clients.suno_routing import (
    is_suno_compatible_provider,
    set_active_suno_base_url,
)
from platform_api.exceptions import DuplicateKeyLabelError, ExternalServiceError, NoAvailableKeysError
from platform_api.models.domain import ApiKeyEntry, KeyPoolConfig, KeyStatusEvent
from platform_api.models.enums import KeyStatus, SelectionStrategy
from platform_api.repositories.key_pool_repo import KeyPoolRepository
from platform_api.services.key_encryption import KeyEncryption

logger = logging.getLogger(__name__)

# musicapi remaps its 402 "Insufficient credits." to 429 on the public
# /api/v1 surface, so a 429 body can be a billing stop rather than throttling.
# Marking those keys rate_limited parks the whole pool and retrying cannot
# help — the account has no credits. Fail fast with the real reason instead.
_BILLING_EXHAUSTED_MARKERS = (
    "insufficient credits",
    "insufficient_credit",
    "insufficient balance",
    "credit_exhausted",
    "credits_exhausted",
    "out of credits",
)


def is_billing_exhausted_response(response_body: str | None) -> bool:
    """True when a 429 body means 'out of credits' instead of 'slow down'."""
    text = str(response_body or "").lower()
    if not text:
        return False
    return any(marker in text for marker in _BILLING_EXHAUSTED_MARKERS)


# 401 bodies are not uniform. ``invalid_key`` and ``missing_credentials`` will
# not heal with time (the key was revoked, or the upstream account has no
# credentials for the requested provider), so parking them for a cooldown only
# burns rotation slots. An account in arrears also answers 401, but a top-up
# does fix it, so that stays on the recoverable path.
_AUTH_MISSING_CREDENTIALS_MARKERS = (
    "no active credentials for provider",
    "no credentials for provider",
    "missing credentials",
)
_AUTH_INVALID_KEY_MARKERS = (
    "auth_002",
    "invalid api key",
    "invalid_api_key",
    "api key is invalid",
    "invalid key",
    "key is invalid",
    "revoked",
)

# How long execute_with_failover is willing to sleep for the soonest parked
# key to finish its cooldown before giving the request back to the job queue.
KEY_POOL_MAX_COOLDOWN_WAIT_SECONDS = 65.0

# Dedup window for "this provider has no selectable keys" ops alerts. One burst
# of parallel songs must not turn into dozens of Telegram messages.
KEY_POOL_ALERT_COOLDOWN_SECONDS = 900


def classify_auth_rejection(response_body: str | None) -> str:
    """Classify a 401 body so the pool can park, disable, or fail fast.

    Returns one of ``missing_credentials``, ``invalid_key``, ``billing`` or
    ``unknown``.
    """
    text = str(response_body or "").lower()
    if any(marker in text for marker in _AUTH_MISSING_CREDENTIALS_MARKERS):
        return "missing_credentials"
    if any(marker in text for marker in _AUTH_INVALID_KEY_MARKERS):
        return "invalid_key"
    if any(marker in text for marker in _BILLING_EXHAUSTED_MARKERS):
        return "billing"
    return "unknown"


def _schedule_ops_alert(message: str) -> None:
    """Best-effort ops alert; never blocks or fails the caller."""

    async def _send() -> None:
        try:
            from platform_api.services.telegram_ops_alert_service import (
                get_telegram_ops_service,
            )

            service = get_telegram_ops_service()
            if service is None:
                return
            await service.send_html(message)
        except Exception:
            logger.debug("Key-pool ops alert failed", exc_info=True)

    try:
        asyncio.get_running_loop().create_task(_send())
    except RuntimeError:
        logger.warning("No running loop for key-pool ops alert")


def _alert_provider_out_of_credits(provider: str, response_body: str | None) -> None:
    """Best-effort ops ping when a provider's upstream account is empty."""
    summary = (response_body or "Insufficient credits.")[:200]
    _schedule_ops_alert(
        f"⚠️ <b>{provider}</b> is out of credits.\n"
        f"<code>{summary}</code>\n"
        "Generation fails until the upstream account is topped up."
    )


def _effective_suno_base_url(configured: str | None) -> str:
    """The host the Suno client will actually use for this request.

    Key filtering still uses the *raw* configured base URL, but the routing
    context must publish the effective host so downstream checks (e.g.
    ``active_provider_is_musicapi``) agree with the client's fallback to the
    environment default.
    """
    text = str(configured or "").strip().rstrip("/")
    if text:
        return text
    try:
        from platform_api.config import get_settings

        return str(get_settings().suno_api_base_url or "").strip().rstrip("/")
    except Exception:
        return ""


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
        config = await self._get_provider_config(provider)
        if is_suno_compatible_provider(provider):
            set_active_suno_base_url(_effective_suno_base_url(config.base_url))
        active_keys = await self._get_active_keys(provider, base_url=config.base_url)

        if not active_keys:
            # Build status counts for the error
            all_keys = await self._repo.list_by_provider(provider)
            status_counts = self._compute_status_counts(all_keys)
            await self._alert_no_active_keys(provider, status_counts)
            raise NoAvailableKeysError(provider=provider, status_counts=status_counts)

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
        self,
        provider: str,
        key_value: str,
        label: str,
        priority: int,
        base_url: str | None = None,
    ) -> UUID:
        """Add a new key to a provider's pool.

        Encrypts the key value, validates uniqueness of the label within
        the provider, and stores with initial status of active.

        Args:
            provider: The provider identifier.
            key_value: The raw API key string (1–500 characters).
            label: User-friendly label (1–100 characters, unique per provider).
            priority: Selection priority (1–100, lower = higher priority).
            base_url: Upstream host this key belongs to (for provider
                switching). ``None`` = host-agnostic (legacy).

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
            base_url=(base_url or "").strip().rstrip("/") or None,
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
        base_url: str | None = None,
        clear_base_url: bool = False,
    ) -> None:
        """Update key metadata (label, priority, value, or host).

        Args:
            key_id: The UUID of the key entry to update.
            label: New label (optional).
            priority: New priority (optional).
            key_value: New key value to encrypt and store (optional).
            base_url: New upstream host for the key (optional).
            clear_base_url: When True, reset the key to host-agnostic.
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

        if clear_base_url:
            entry.base_url = None
        elif base_url is not None:
            entry.base_url = (base_url or "").strip().rstrip("/") or None

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

    async def get_decrypted_key_value(self, key_id: UUID) -> str:
        """Decrypt and return the raw API key for an entry (admin/ops only)."""
        entry = await self.get_key_entry(key_id)
        return self._encryption.decrypt(entry.encrypted_key_value)

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

    async def active_base_url(self, provider: str) -> str | None:
        """Return the configured active upstream host, or None for the default."""
        config = await self._get_provider_config(provider)
        return config.base_url

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
        base_url: str | None = None,
        clear_base_url: bool = False,
    ) -> None:
        """Configure selection strategy, cooldown and active host for a provider.

        Creates a new configuration if none exists, or updates the existing one.

        Args:
            provider: The provider identifier.
            strategy: Selection strategy ("round_robin" or "priority").
            cooldown_seconds: Cooldown duration in seconds (10–3600).
            base_url: Active upstream host. When set, only keys tagged with the
                same host are selected, enabling reversible provider switching.
            clear_base_url: When True, fall back to the environment default and
                accept every active key (legacy behaviour).
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

        if clear_base_url:
            config.base_url = None
        elif base_url is not None:
            config.base_url = (base_url or "").strip().rstrip("/") or None

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
        # Recover keys whose cooldown already expired before reporting. Selection
        # also recovers, but health/admin reads must not keep showing a stale
        # "critical" after the cooldown window has passed.
        await self._check_and_recover_keys(provider)
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

        The retry budget covers the whole pool — ``max(max_retries,
        len(active_keys))`` — so a 4-key pool always tries all 4 keys. When every
        key is parked for a short cooldown, the request waits for the soonest
        recovery (bounded by ``KEY_POOL_MAX_COOLDOWN_WAIT_SECONDS``) instead of
        failing immediately. If all attempts fail, the last exception is
        re-raised.

        Args:
            provider: The provider identifier (e.g. "suno", "fal").
            execute_fn: An async callable that takes an API key string and
                        performs the HTTP request. Should raise
                        httpx.HTTPStatusError on non-2xx responses.
            max_retries: Minimum total attempts (default 3). The pool size wins
                         when it is larger.

        Returns:
            The response from a successful execute_fn call.

        Raises:
            NoAvailableKeysError: If no active keys are available and none is
                about to finish its cooldown.
            httpx.HTTPStatusError: If all retry attempts fail (re-raises last).
        """
        tried_key_ids: set[UUID] = set()
        last_exception: BaseException | None = None
        attempt = 0
        max_attempts = max_retries
        waited_for_cooldown = False

        # Resolve the active host once per execution: only keys tagged with that
        # host are eligible, and the Suno client reads it to pick its base URL.
        config = await self._get_provider_config(provider)
        if is_suno_compatible_provider(provider):
            set_active_suno_base_url(_effective_suno_base_url(config.base_url))

        while attempt < max_attempts:
            # Get active keys excluding already-tried ones
            active_keys = await self._get_active_keys(provider, base_url=config.base_url)
            if not tried_key_ids:
                # Cover the whole pool: a retry budget smaller than the pool
                # leaves healthy keys untried when earlier keys reject.
                max_attempts = max(max_retries, len(active_keys))
            available_keys = [k for k in active_keys if k.id not in tried_key_ids]

            if not available_keys:
                if attempt == 0 and not waited_for_cooldown:
                    # Every key may be parked for a short cooldown. Waiting for
                    # the soonest recovery is better than failing a burst of
                    # parallel songs that all hit the same parked pool.
                    wait_seconds = await self._earliest_cooldown_wait(provider)
                    if wait_seconds is not None:
                        waited_for_cooldown = True
                        if wait_seconds > 0:
                            logger.info(
                                "All '%s' keys are cooling down; waiting %.1fs for "
                                "the soonest recovery instead of failing.",
                                provider,
                                wait_seconds,
                            )
                            await asyncio.sleep(wait_seconds + 0.1)
                        continue
                if attempt == 0:
                    # No active keys at all and none about to recover
                    all_keys = await self._repo.list_by_provider(provider)
                    status_counts = self._compute_status_counts(all_keys)
                    await self._alert_no_active_keys(provider, status_counts)
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
            attempt += 1
            decrypted_key = self._encryption.decrypt(selected.encrypted_key_value)

            try:
                response = await execute_fn(decrypted_key)
                # Success — report and return
                await self.report_key_success(provider, selected.id)
                return response

            except (httpx.HTTPStatusError, ExternalServiceError) as exc:
                last_exception = exc
                status_code, response_body = self._failover_status(exc)

                if status_code == 429 and is_billing_exhausted_response(response_body):
                    # Billing stop dressed as a rate limit: do not park the key
                    # (all keys share the account credits) and do not burn the
                    # remaining attempts — surface the real cause immediately.
                    await self._repo.increment_counters(selected.id, success=False)
                    logger.error(
                        "Provider '%s' is out of credits (429 billing body: %s). "
                        "Not marking keys; failing fast.",
                        provider,
                        (response_body or "")[:160],
                    )
                    _alert_provider_out_of_credits(provider, response_body)
                    raise ExternalServiceError(
                        f"Provider '{provider}' is out of credits. "
                        "Top up the upstream account to resume generation.",
                        is_retryable=False,
                        details={
                            "provider": provider,
                            "status_code": status_code,
                            "reason": "provider_credits_exhausted",
                            "response_summary": (response_body or "")[:200],
                        },
                    ) from exc

                if status_code == 429:
                    # Rate limited — mark key and retry
                    await self._handle_rate_limited(
                        provider, selected, exc, response_body
                    )
                    logger.warning(
                        "Failover [attempt %d/%d] key %s (%s) rate-limited (429) "
                        "for provider '%s'. Retrying with next key.",
                        attempt,
                        max_attempts,
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
                        attempt,
                        max_attempts,
                        selected.id,
                        selected.label,
                        status_code,
                        provider,
                    )
                elif status_code == 401:
                    # A 401 is key-specific in practice: the key was revoked, the
                    # account has no credentials for the requested provider, or it
                    # is in arrears until topped up. Park only the recoverable
                    # cases; disable keys that cannot heal on their own.
                    await self._handle_auth_failed(
                        provider, selected, status_code, response_body
                    )
                    logger.warning(
                        "Failover [attempt %d/%d] key %s (%s) rejected (401, %s) "
                        "for provider '%s'. Retrying with next key.",
                        attempt,
                        max_attempts,
                        selected.id,
                        selected.label,
                        classify_auth_rejection(response_body),
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

    @staticmethod
    def _failover_status(exc: BaseException) -> tuple[int, str]:
        """Extract ``(http_status, body)`` from a failover exception.

        Provider clients (Suno) wrap ``httpx.HTTPStatusError`` in
        ``ExternalServiceError``, so the status code must also be read from its
        ``details``; otherwise a 402/403 never rotates the key and failover is
        silently skipped. Returns ``(0, "")`` when no HTTP status is available.
        """
        if isinstance(exc, httpx.HTTPStatusError):
            body = exc.response.text[:500] if exc.response.text else ""
            return exc.response.status_code, body
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            try:
                status = int(details.get("status_code") or 0)
            except (TypeError, ValueError):
                status = 0
            return status, str(details.get("reason") or "")[:500]
        return 0, ""

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
        For HTTP 401: parked as rate_limited by ``_handle_auth_failed``.
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
        elif status_code in (401, 402, 403):
            # Handled by _handle_auth_failed / _handle_exhausted in
            # execute_with_failover
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
        response = getattr(exc, "response", None)
        retry_after = response.headers.get("Retry-After") if response is not None else None
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

    async def _handle_auth_failed(
        self,
        provider: str,
        key_entry: ApiKeyEntry,
        status_code: int,
        response_body: str,
    ) -> None:
        """Park or disable a key the provider rejected with 401.

        A 401 is key-specific in practice. The response body separates the
        cases:

        * ``invalid_key`` / ``missing_credentials`` — the key was revoked, or the
          upstream account has no credentials for the requested provider. These
          never heal on their own, so the key is disabled instead of parked;
          an admin re-enables it after fixing the key or account.
        * ``billing`` — the account is in arrears and rejects calls until it is
          topped up. Park it as ``rate_limited`` for one provider cooldown so it
          rejoins the pool automatically once credited (``exhausted`` never
          auto-recovers, so it must not be used here).
        * ``unknown`` — park as ``rate_limited`` and retry after the cooldown.
        """
        previous_status = key_entry.status
        reason = classify_auth_rejection(response_body)

        if reason in {"invalid_key", "missing_credentials"}:
            key_entry.status = KeyStatus.DISABLED
            await self._repo.update(key_entry)
            await self._repo.increment_counters(key_entry.id, success=False)
            await self._record_status_event(
                key_entry=key_entry,
                provider=provider,
                previous_status=previous_status,
                new_status=KeyStatus.DISABLED,
                trigger_reason=f"auth_rejected_{status_code}_{reason}",
                http_status_code=status_code,
                response_summary=response_body[:200] if response_body else None,
            )
            await self._invalidate_cache(provider)
            logger.error(
                "Disabled key %s (%s) for provider '%s': upstream rejected it "
                "with %d (%s). Fix the key/account and re-enable it in Key Pool.",
                key_entry.id,
                key_entry.label,
                provider,
                status_code,
                reason,
            )
            _schedule_ops_alert(
                f"🔑 <b>{provider}</b> key <code>{key_entry.label}</code> disabled: "
                f"upstream returned {status_code} ({reason}).\n"
                "Fix the key/account and re-enable it in Key Pool."
            )
            return

        config = await self._get_provider_config(provider)

        key_entry.status = KeyStatus.RATE_LIMITED
        key_entry.rate_limited_at = datetime.utcnow()
        await self._repo.update(key_entry)

        cooldown_key = f"key_pool:{provider}:cooldown:{key_entry.id}"
        await self._redis.set(cooldown_key, "1", ex=config.cooldown_seconds)

        await self._repo.increment_counters(key_entry.id, success=False)

        await self._record_status_event(
            key_entry=key_entry,
            provider=provider,
            previous_status=previous_status,
            new_status=KeyStatus.RATE_LIMITED,
            trigger_reason=f"auth_rejected_{status_code}_{reason}",
            http_status_code=status_code,
            response_summary=response_body[:200] if response_body else None,
        )

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

    async def _get_active_keys(
        self, provider: str, base_url: str | None = None
    ) -> list[ApiKeyEntry]:
        """Fetch active keys for a provider, using Redis cache when available.

        First checks for rate-limited keys whose cooldown has expired and
        recovers them. Then attempts to read from the Redis ZSET cache.
        Falls back to direct PostgreSQL queries if Redis is unavailable.

        Returns keys sorted by priority ASC, created_at ASC.

        Args:
            provider: The provider identifier.
            base_url: When set, only keys tagged with this upstream host are
                returned (provider switching). ``None`` returns every active key.

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
        keys = await self._repo.get_active_by_provider(provider)
        if base_url:
            tagged = [k for k in keys if (k.base_url or "") == base_url]
            if tagged:
                return tagged
            # No key is tagged for the active host. An untagged key is
            # host-agnostic, so keep a single-host provider pool usable instead
            # of failing every request with NoAvailableKeysError.
            untagged = [k for k in keys if not (k.base_url or "")]
            if untagged:
                logger.warning(
                    "No keys tagged for host %s (provider=%s); using %d "
                    "untagged host-agnostic key(s). Tag the key's upstream host "
                    "in Key Pool → Provider Settings to silence this.",
                    base_url,
                    provider,
                    len(untagged),
                )
                return untagged
            return tagged
        return keys

    async def _alert_no_active_keys(
        self, provider: str, status_counts: dict[str, int]
    ) -> None:
        """Ops alert when the pool has zero selectable keys.

        Deduped in Redis so a burst of parallel songs produces one alert per
        ``KEY_POOL_ALERT_COOLDOWN_SECONDS`` instead of a message storm.
        """
        dedup_key = f"key_pool:{provider}:alert:no_active"
        try:
            if await self._redis.exists(dedup_key):
                return
            await self._redis.set(dedup_key, "1", ex=KEY_POOL_ALERT_COOLDOWN_SECONDS)
        except Exception:
            logger.debug(
                "Could not dedupe no-active-keys alert (provider=%s)",
                provider,
                exc_info=True,
            )

        counts = ", ".join(
            f"{name}={count}" for name, count in status_counts.items() if count
        )
        _schedule_ops_alert(
            f"🚨 <b>{provider}</b> key pool has no active keys"
            + (f" ({counts})" if counts else "")
            + ".\nGeneration fails until a key is re-enabled or topped up."
        )

    async def _earliest_cooldown_wait(self, provider: str) -> float | None:
        """Seconds to wait for the soonest parked key to rejoin the pool.

        Returns ``None`` when waiting cannot help (no parked keys, no predictable
        expiry, or the soonest recovery is beyond
        ``KEY_POOL_MAX_COOLDOWN_WAIT_SECONDS``). Returns ``0.0`` when a parked
        key's cooldown has already elapsed and recovery is due immediately.
        """
        all_keys = await self._repo.list_by_provider(provider)
        rate_limited = [k for k in all_keys if k.status == KeyStatus.RATE_LIMITED]
        if not rate_limited:
            return None

        soonest: float | None = None
        for key in rate_limited:
            cooldown_key = f"key_pool:{provider}:cooldown:{key.id}"
            try:
                ttl = await self._redis.ttl(cooldown_key)
            except Exception:
                logger.debug(
                    "Could not read cooldown TTL for key %s (provider=%s)",
                    key.id,
                    provider,
                    exc_info=True,
                )
                return None
            if ttl is None:
                continue
            if ttl == -2:
                # Cooldown key is gone — _check_and_recover_keys can promote it now.
                return 0.0
            if ttl == -1:
                # Key exists with no expiry; recovery is not time-based.
                continue
            if ttl == 0:
                # Expired but not reaped yet: clear it so recovery can promote
                # the key on the next pass.
                await self._redis.delete(cooldown_key)
                return 0.0
            soonest = float(ttl) if soonest is None else min(soonest, float(ttl))

        if soonest is None or soonest > KEY_POOL_MAX_COOLDOWN_WAIT_SECONDS:
            return None
        return soonest

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
