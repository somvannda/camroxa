"""Async HTTP client for the CALA image generation API.

CALA provides image generation via an OpenAI-compatible endpoint.
Base URL: configurable (default http://localhost:3000)
Endpoint: POST /v1/images/generations
Model: cgpt-web/gpt-5.5
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


def _classify_error(exc: Exception, *, context: str = "") -> ExternalServiceError:
    """Convert an httpx exception into an ExternalServiceError."""
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(
            f"CALA timeout: {context}",
            is_retryable=True,
            details={"provider": "cala", "reason": "timeout"},
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        return ExternalServiceError(
            f"CALA error {status}: {context}",
            is_retryable=is_retryable,
            details={
                "provider": "cala",
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        )
    return ExternalServiceError(
        f"CALA connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "cala", "reason": "connection_error"},
    )


class CalaClient:
    """Async client for the CALA image generation API.

    Uses OpenAI-compatible /v1/images/generations endpoint with:
    - model: cgpt-web/gpt-5.5
    - prompt, n, aspect_ratio
    - Bearer token auth from Key Pool
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = (settings.cala_api_base_url or "http://localhost:3000").rstrip("/")
        self._api_key = getattr(settings, "cala_api_key", "") or ""
        # CALA image generation can take 3-5 minutes
        self._timeout = httpx.Timeout(
            timeout=300.0,
            connect=15.0,
        )

    async def close(self) -> None:
        """No persistent client to close."""
        pass

    async def generate_image(
        self,
        *,
        prompt: str,
        width: int = 1920,
        height: int = 1080,
        style_strength: float = 0.6,
        reference_image_base64: str | None = None,
        extra_params: dict[str, Any] | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Generate an image using CALA.

        Args:
            prompt: Text prompt describing the desired image.
            width: Output width (used to derive aspect_ratio).
            height: Output height (used to derive aspect_ratio).
            api_key: Optional API key override (from key pool).

        Returns:
            Response dict with 'data' containing image URL.
        """
        key = api_key or self._api_key

        # Determine aspect ratio
        if width == height:
            aspect_ratio = "1:1"
        elif height > width:
            aspect_ratio = "9:16"
        else:
            aspect_ratio = "16:9"

        payload: dict[str, Any] = {
            "model": "cgpt-web/gpt-5.5",
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": aspect_ratio,
        }

        if reference_image_base64:
            payload["image_url"] = f"data:image/png;base64,{reference_image_base64}"

        if extra_params:
            payload.update(extra_params)

        url = f"{self._base_url}/v1/images/generations"

        # Retry up to 3 times
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                ) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    # If response has a URL, return immediately
                    if self._has_image_url(data):
                        return data

                    # If pending with cache_id, poll for result
                    cache_id = self._extract_cache_id(data)
                    if cache_id:
                        logger.info("CALA returned cache_id=%s, polling...", cache_id)
                        return await self._poll_for_result(key, cache_id)

                    return data

            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                if attempt < max_retries:
                    is_retryable = False  # Don't retry timeouts — CALA is just slow
                    if isinstance(exc, httpx.HTTPStatusError):
                        is_retryable = exc.response.status_code in (429, 500, 502, 503, 504)
                    if is_retryable:
                        delay = 2.0 * attempt
                        logger.warning("CALA attempt %d/%d failed (%s), retrying in %.1fs...", attempt, max_retries, exc, delay)
                        await asyncio.sleep(delay)
                        continue
                raise _classify_error(exc, context="generate_image") from exc

        raise ExternalServiceError("CALA: all retries exhausted", is_retryable=True)

    async def _poll_for_result(self, api_key: str, cache_id: str, max_wait: int = 150) -> dict[str, Any]:
        """Poll CALA for a completed image result."""
        poll_url = f"{self._base_url}/v1/images/generations/{cache_id}"
        elapsed = 0.0
        poll_interval = 5.0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                ) as client:
                    resp = await client.get(poll_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if self._has_image_url(data):
                            logger.info("CALA image ready (cache_id=%s, %.0fs)", cache_id, elapsed)
                            return data
            except (httpx.TimeoutException, httpx.RequestError):
                continue

        raise ExternalServiceError(
            f"CALA image not ready after {max_wait}s (cache_id={cache_id})",
            is_retryable=True,
        )

    @staticmethod
    def _has_image_url(data: dict[str, Any]) -> bool:
        """Check if response contains a usable image URL."""
        if not isinstance(data, dict):
            return False
        data_list = data.get("data")
        if isinstance(data_list, list) and data_list:
            first = data_list[0]
            if isinstance(first, dict):
                url = first.get("url", "")
                return bool(url and url.startswith("http"))
        return False

    @staticmethod
    def _extract_cache_id(data: dict[str, Any]) -> str:
        """Extract cache_id from a pending response."""
        if not isinstance(data, dict):
            return ""
        data_list = data.get("data")
        if isinstance(data_list, list) and data_list:
            first = data_list[0]
            if isinstance(first, dict):
                return str(first.get("cache_id", "") or "").strip()
        return str(data.get("cache_id", "") or "").strip()
