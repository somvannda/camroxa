"""Async HTTP client for LLM services (DeepSeek / SLAI) used for song draft generation.

Handles chat completion requests with 30-second timeout.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

# Timeout for LLM requests (seconds)
_LLM_TIMEOUT = 30.0


def _classify_error(exc: Exception, *, context: str = "") -> ExternalServiceError:
    """Convert an httpx exception or HTTP error response into an ExternalServiceError.

    Retryable: timeouts, rate limits (429), 5xx server errors.
    Permanent: 4xx client errors (except 429).
    """
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(
            f"LLM timeout: {context}",
            is_retryable=True,
            details={"provider": "llm", "reason": "timeout"},
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        return ExternalServiceError(
            f"LLM error {status}: {context}",
            is_retryable=is_retryable,
            details={
                "provider": "llm",
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        )

    # Network-level failures are retryable
    return ExternalServiceError(
        f"LLM connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "llm", "reason": "connection_error"},
    )


class LlmClient:
    """Async client for LLM services (DeepSeek/SLAI) — OpenAI-compatible chat API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.deepseek_api_base_url.rstrip("/")
        self._api_key = settings.deepseek_api_key
        self._timeout = httpx.Timeout(
            timeout=float(settings.llm_timeout_seconds),
            connect=10.0,
        )
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: dict[str, str] | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request to the LLM provider.

        Uses the OpenAI-compatible chat completions endpoint.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            model: Model identifier (e.g. "deepseek-chat", "deepseek-coder").
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in the response.
            response_format: Optional response format spec (e.g. {"type": "json_object"}).
            api_key: Optional per-request API key (injected by the key pool).
                     When provided, overrides the client's default key for this
                     request so pooled keys with failover are actually used.
            base_url: Optional per-request base URL override. When provided, the
                      request is sent to this endpoint instead of the client's
                      default base URL. Used when SLAI pool keys are routed
                      through the LLM client (SLAI has its own OpenAI-compatible
                      chat endpoint).

        Returns:
            Response dict from the LLM containing choices with generated content.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        # Per-request base_url + key override (used when SLAI pool keys route
        # through this client). Falls back to the client's default otherwise.
        if base_url:
            # One-shot request to a different endpoint
            headers = {
                "Authorization": f"Bearer {api_key or self._api_key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as temp_client:
                    response = await temp_client.post(
                        f"{base_url.rstrip('/')}/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                raise _classify_error(exc, context=f"chat_completion({model})") from exc
        else:
            client = await self._get_client()
            request_headers = (
                {"Authorization": f"Bearer {api_key}"} if api_key else None
            )
            try:
                response = await client.post(
                    "/v1/chat/completions", json=payload, headers=request_headers
                )
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                raise _classify_error(exc, context=f"chat_completion({model})") from exc

    async def generate_song_draft(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Generate a song draft (title, album, lyrics) using the LLM.

        Convenience method that wraps chat_completion with JSON response format.

        Args:
            system_prompt: System-level instruction for draft generation.
            user_prompt: User-level prompt with description, structure, avoid lists, etc.
            model: Model identifier.
            temperature: Sampling temperature (maps from creativity level 0-100).
            api_key: Optional per-request API key (injected by the key pool).
            base_url: Optional per-request base URL override (for SLAI routing).

        Returns:
            Response dict from the LLM (caller is responsible for parsing/validating).

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=2048,
            response_format={"type": "json_object"},
            api_key=api_key,
            base_url=base_url,
        )
