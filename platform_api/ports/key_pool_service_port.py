"""Key pool service protocol interface.

Defines the contract for the key pool service layer — key selection,
failover, usage tracking, and provider configuration management.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class KeyPoolServicePort(Protocol):
    """Port for key pool service operations.

    Implementations handle key selection using configured strategies,
    automatic failover on key failure, usage tracking, and provider
    configuration management.
    """

    async def get_key(self, provider: str) -> str:
        """Select the next available API key for a provider.

        Applies the configured selection strategy (round_robin or priority)
        to choose an active key from the provider's pool.

        Args:
            provider: The provider identifier (e.g. "suno", "fal", "openai").

        Returns:
            The decrypted API key value string.

        Raises:
            NoAvailableKeysError: If all keys for the provider are non-active.
        """
        ...

    async def execute_with_failover(
        self,
        provider: str,
        execute_fn: Any,
        max_retries: int = 3,
    ) -> Any:
        """Execute a request with automatic key failover on failure.

        Args:
            provider: The provider identifier.
            execute_fn: An async callable that receives an API key string
                        and returns the response from the external service.
            max_retries: Maximum number of retry attempts (default 3).

        Returns:
            The response from a successful execution.

        Raises:
            NoAvailableKeysError: If no active keys remain after retries.
        """
        ...

    async def report_key_success(self, provider: str, key_id: UUID) -> None:
        """Report a successful API call for usage tracking.

        Args:
            provider: The provider identifier.
            key_id: The UUID of the key entry used.
        """
        ...

    async def report_key_failure(
        self, provider: str, key_id: UUID, status_code: int, response_body: str
    ) -> None:
        """Report a failed API call — triggers status transitions and failover.

        Args:
            provider: The provider identifier.
            key_id: The UUID of the key entry used.
            status_code: The HTTP status code from the external API.
            response_body: Summary of the response body.
        """
        ...

    async def add_key(
        self, provider: str, key_value: str, label: str, priority: int
    ) -> UUID:
        """Add a new key to a provider's pool.

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
        ...

    async def remove_key(self, key_id: UUID) -> None:
        """Remove a key from the pool.

        Args:
            key_id: The UUID of the key entry to remove.
        """
        ...

    async def update_key(
        self,
        key_id: UUID,
        *,
        label: str | None = None,
        priority: int | None = None,
        key_value: str | None = None,
    ) -> None:
        """Update key metadata.

        Args:
            key_id: The UUID of the key entry to update.
            label: New label (optional).
            priority: New priority (optional).
            key_value: New key value to encrypt and store (optional).
        """
        ...

    async def set_key_status(self, key_id: UUID, status: str) -> None:
        """Manually set key status (enable/disable).

        Args:
            key_id: The UUID of the key entry.
            status: The new status string ("active" or "disabled").
        """
        ...

    async def get_pool_status(self, provider: str) -> dict[str, Any]:
        """Get pool health summary for a provider.

        Args:
            provider: The provider identifier.

        Returns:
            A dict with total_keys, active_keys, rate_limited_keys,
            exhausted_keys, disabled_keys, and health_indicator.
        """
        ...

    async def configure_provider(
        self,
        provider: str,
        *,
        strategy: str | None = None,
        cooldown_seconds: int | None = None,
    ) -> None:
        """Configure selection strategy and cooldown for a provider.

        Args:
            provider: The provider identifier.
            strategy: Selection strategy ("round_robin" or "priority").
            cooldown_seconds: Cooldown duration in seconds (10–3600).
        """
        ...
