"""Async HTTP client for the Suno music generation API.

Handles task submission, status polling, and credit balance retrieval.
Timeout: 30 seconds per request.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

# Timeout for Suno API requests (seconds)
_SUNO_TIMEOUT = 30.0


def _classify_error(exc: Exception, *, context: str = "") -> ExternalServiceError:
    """Convert an httpx exception or HTTP error response into an ExternalServiceError.

    Retryable: timeouts, rate limits (429), 5xx server errors.
    Permanent: 4xx client errors (except 429).
    """
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(
            f"Suno API timeout: {context}",
            is_retryable=True,
            details={"provider": "suno", "reason": "timeout"},
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        return ExternalServiceError(
            f"Suno API error {status}: {context}",
            is_retryable=is_retryable,
            details={
                "provider": "suno",
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        )

    # Network-level failures (DNS, connection reset, etc.) are retryable
    return ExternalServiceError(
        f"Suno API connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "suno", "reason": "connection_error"},
    )


class SunoClient:
    """Async client for the Suno music generation API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.suno_api_base_url.rstrip("/")
        self._api_key = settings.suno_api_key
        self._callback_base_url = settings.suno_callback_base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            timeout=float(settings.suno_timeout_seconds),
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

    async def submit_task(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool = False,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """Submit a music generation task to Suno.

        Args:
            model: Suno model version (e.g. "V5", "V5_5").
            title: Song title.
            lyrics: Song lyrics.
            style: Music style/genre descriptor.
            instrumental: Whether to generate an instrumental track.
            callback_url: URL for Suno to notify on completion.

        Returns:
            Response dict from Suno containing the task ID and status.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "title": title,
            "lyrics": lyrics,
            "style": style,
            "instrumental": instrumental,
        }
        if callback_url:
            payload["callbackUrl"] = callback_url
        elif self._callback_base_url:
            payload["callbackUrl"] = f"{self._callback_base_url}/api/v1/callbacks/suno"

        try:
            response = await client.post("/api/v1/generate", json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="submit_task") from exc

    async def check_status(self, task_id: str) -> dict[str, Any]:
        """Check the status of a previously submitted Suno task.

        Args:
            task_id: The Suno-assigned task identifier.

        Returns:
            Response dict with task status, audio URLs (if complete), etc.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"/api/v1/generate/record", params={"taskId": task_id})
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context=f"check_status({task_id})") from exc

    async def get_credit_balance(self) -> dict[str, Any]:
        """Retrieve the current Suno API credit balance.

        Returns:
            Response dict containing the credit balance information.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        client = await self._get_client()
        try:
            response = await client.get("/api/v1/generate/credit")
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="get_credit_balance") from exc
