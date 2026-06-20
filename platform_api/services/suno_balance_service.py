"""External Suno balance monitoring service.

Queries the Suno API credit endpoint, caches the result in Redis (30s TTL),
and enforces a reserve threshold to protect the platform from over-spending.
When the balance falls below the threshold, new Suno generation requests are
rejected and a low-balance alert is pushed to Admin WebSocket clients.

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Redis key for the cached Suno external balance
_REDIS_KEY = "suno:external_balance"


# ---------------------------------------------------------------------------
# Protocol definitions for dependency injection
# ---------------------------------------------------------------------------


class RedisProtocol(Protocol):
    """Minimal async Redis interface used by SunoBalanceService."""

    async def get(self, key: str) -> str | bytes | None:
        """Get a value by key."""
        ...

    async def setex(self, key: str, seconds: int, value: str) -> Any:
        """Set a value with expiration in seconds."""
        ...


class SunoClientProtocol(Protocol):
    """Minimal Suno client interface for balance retrieval."""

    async def get_credit_balance(self) -> dict[str, Any]:
        """Retrieve the current Suno API credit balance."""
        ...


class NotificationServiceProtocol(Protocol):
    """Minimal notification service interface for pushing alerts."""

    async def push(self, user_id: str, event: str, payload: dict) -> None:
        """Push a notification to a user's connected WebSocket clients."""
        ...


class AdminUserProviderProtocol(Protocol):
    """Provides the list of Admin user IDs for broadcasting alerts."""

    async def get_admin_user_ids(self) -> list[str]:
        """Return all Admin user IDs."""
        ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SunoBalanceService:
    """Monitors the platform's external Suno API credit balance.

    Responsibilities:
        - Query the Suno credit endpoint and cache the result in Redis (30s TTL).
        - Check whether the balance meets the reserve threshold.
        - Push low-balance alerts to all connected Admin WebSocket clients.
        - Gracefully handle unreachable Suno endpoint by serving cached data.

    Args:
        redis: Async Redis client supporting get/setex.
        suno_client: Client for querying the Suno API balance endpoint.
        notification_service: Service for pushing WebSocket notifications.
        admin_provider: Provides Admin user IDs for alert broadcasting.
        reserve_threshold: Minimum balance required to accept Suno requests (default 100).
        cache_ttl_seconds: TTL for the cached balance in Redis (default 30).
    """

    def __init__(
        self,
        *,
        redis: RedisProtocol,
        suno_client: SunoClientProtocol,
        notification_service: NotificationServiceProtocol | None = None,
        admin_provider: AdminUserProviderProtocol | None = None,
        reserve_threshold: int = 100,
        cache_ttl_seconds: int = 30,
    ) -> None:
        self._redis = redis
        self._suno_client = suno_client
        self._notification_service = notification_service
        self._admin_provider = admin_provider
        self._reserve_threshold = reserve_threshold
        self._cache_ttl = cache_ttl_seconds

    @property
    def reserve_threshold(self) -> int:
        """The configured reserve threshold."""
        return self._reserve_threshold

    async def get_balance(self) -> dict[str, Any]:
        """Query Suno API credit endpoint and cache the result in Redis.

        If the Suno API is unreachable, returns the cached value (if available)
        or a response with ``{"status": "unknown"}`` without blocking.

        Returns:
            Dict with balance information. Guaranteed to have at least a
            "credits" key (int or None) and a "status" key ("ok", "cached",
            or "unknown").
        """
        try:
            raw_balance = await self._suno_client.get_credit_balance()
            # Normalize: ensure a "credits" key exists
            balance_data = self._normalize_balance(raw_balance)
            balance_data["status"] = "ok"

            # Cache in Redis
            await self._redis.setex(
                _REDIS_KEY,
                self._cache_ttl,
                json.dumps(balance_data),
            )

            # Check threshold and alert if needed
            await self._check_and_alert(balance_data)

            return balance_data

        except Exception as exc:
            logger.warning(
                "Failed to reach Suno credit endpoint: %s. Serving cached value.",
                str(exc)[:200],
            )
            return await self._get_cached_or_unknown()

    async def check_reserve(self, threshold: int | None = None) -> bool:
        """Check if the external Suno balance meets the reserve threshold.

        Args:
            threshold: Override the default reserve threshold. If None, uses
                the configured default.

        Returns:
            True if balance >= threshold, False otherwise.
            If the balance is unknown (unreachable and no cache), returns True
            to avoid blocking requests unnecessarily (per Requirement 15.5).
        """
        effective_threshold = threshold if threshold is not None else self._reserve_threshold
        balance_data = await self.get_balance()

        credits = balance_data.get("credits")
        if credits is None:
            # Unknown balance — don't block requests (Requirement 15.5)
            return True

        return credits >= effective_threshold

    async def _get_cached_or_unknown(self) -> dict[str, Any]:
        """Return cached balance from Redis, or unknown status if no cache."""
        try:
            cached = await self._redis.get(_REDIS_KEY)
            if cached is not None:
                raw = cached if isinstance(cached, str) else cached.decode("utf-8")
                data = json.loads(raw)
                data["status"] = "cached"
                return data
        except Exception as exc:
            logger.warning("Failed to read cached Suno balance from Redis: %s", exc)

        return {"credits": None, "status": "unknown"}

    async def _check_and_alert(self, balance_data: dict[str, Any]) -> None:
        """Push low-balance alert to Admin clients if below threshold."""
        credits = balance_data.get("credits")
        if credits is None:
            return

        if credits < self._reserve_threshold:
            await self._push_admin_alert(credits)

    async def _push_admin_alert(self, current_balance: int) -> None:
        """Push a low-balance alert to all connected Admin WebSocket clients."""
        if self._notification_service is None or self._admin_provider is None:
            logger.warning(
                "Suno balance below threshold (%d < %d) but notification "
                "service or admin provider not configured.",
                current_balance,
                self._reserve_threshold,
            )
            return

        try:
            admin_ids = await self._admin_provider.get_admin_user_ids()
        except Exception as exc:
            logger.error("Failed to fetch admin user IDs for alert: %s", exc)
            return

        payload = {
            "service": "suno",
            "current_balance": current_balance,
            "threshold": self._reserve_threshold,
            "message": (
                f"Suno external balance is critically low: {current_balance} credits "
                f"(threshold: {self._reserve_threshold})."
            ),
        }

        for admin_id in admin_ids:
            try:
                await self._notification_service.push(
                    admin_id, "admin:low_balance_alert", payload
                )
            except Exception as exc:
                logger.warning(
                    "Failed to push low-balance alert to admin %s: %s",
                    admin_id,
                    str(exc)[:100],
                )

    @staticmethod
    def _normalize_balance(raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw Suno balance response into a consistent format.

        Attempts to extract a numeric credit value from the response.
        """
        # The Suno API may return the balance under various keys
        credits = raw.get("credits") or raw.get("balance") or raw.get("credit_balance")

        if credits is not None:
            try:
                credits = int(credits)
            except (TypeError, ValueError):
                credits = None

        return {"credits": credits, "raw": raw}
