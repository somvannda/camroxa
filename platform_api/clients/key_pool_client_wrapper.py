"""Client wrapper that integrates the Key Pool Service with existing provider clients.

Provides transparent key injection and automatic failover for each provider client
(Suno, Fal, LLM, Slai). The wrapper sits between the GenerationService and the
actual HTTP clients, replacing the single-key pattern with pool-based selection.

Requirements: 8.1, 8.2
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from platform_api.ports.key_pool_service_port import KeyPoolServicePort

logger = logging.getLogger(__name__)


class KeyPoolClientWrapper:
    """Wraps an existing client to inject API keys from the pool.

    Instead of each client holding a single API key from Settings,
    this wrapper intercepts requests and injects the key selected
    by the Key Pool Service. It delegates key selection, failover,
    and usage tracking entirely to the KeyPoolService.

    Each provider client (Suno, Fal, LLM, Slai) gets its own wrapper
    instance configured with the appropriate provider identifier.

    Args:
        key_pool_service: The key pool service implementing selection
                          and failover logic.
        provider: The provider identifier (e.g. "suno", "fal", "openai", "slai").

    Example usage::

        suno_wrapper = KeyPoolClientWrapper(key_pool_service, provider="suno")

        # In GenerationService, instead of calling suno_client directly:
        result = await suno_wrapper.execute(
            lambda api_key: suno_client.submit_task_with_key(api_key, ...)
        )
    """

    def __init__(self, key_pool_service: KeyPoolServicePort, provider: str) -> None:
        self._key_pool = key_pool_service
        self._provider = provider

    @property
    def provider(self) -> str:
        """The provider identifier this wrapper is configured for."""
        return self._provider

    async def execute(
        self, request_fn: Callable[[str], Awaitable[Any]]
    ) -> Any:
        """Execute request_fn with automatic key selection and failover.

        Delegates to the Key Pool Service's ``execute_with_failover`` method,
        which handles:
        - Selecting the next available key using the configured strategy
        - Calling ``request_fn`` with the decrypted API key
        - On HTTP 429: marking the key as rate_limited and retrying
        - On HTTP 402/403: marking the key as exhausted and retrying
        - Limiting retries to a maximum of 3 attempts
        - Tracking usage (success/failure counters)

        Args:
            request_fn: An async callable that receives an API key string
                        as its single argument and performs the HTTP request
                        to the external provider. Should raise
                        ``httpx.HTTPStatusError`` on non-2xx responses so
                        the failover logic can detect rate limits and
                        billing errors.

        Returns:
            The response from a successful ``request_fn`` call.

        Raises:
            NoAvailableKeysError: If no active keys exist for the provider
                                  or all keys fail during failover.
            httpx.HTTPStatusError: If all retry attempts fail with a
                                   non-recoverable error (re-raises last).
        """
        logger.debug(
            "Executing request with key pool failover for provider '%s'",
            self._provider,
        )
        return await self._key_pool.execute_with_failover(
            provider=self._provider,
            execute_fn=request_fn,
            max_retries=3,
        )

    async def get_key(self) -> str:
        """Get a single API key from the pool without executing a request.

        Useful for clients that need the key upfront (e.g., to set auth
        headers on a persistent HTTP client) rather than per-request
        injection.

        Returns:
            The decrypted API key value string.

        Raises:
            NoAvailableKeysError: If no active keys exist for the provider.
        """
        return await self._key_pool.get_key(self._provider)
