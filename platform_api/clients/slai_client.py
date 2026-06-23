"""Async HTTP client for the SLAI image generation API.

Handles image generation requests with submit + poll pattern.
SLAI returns a URL/cache_id on submit; we poll until the image is ready.
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
    """Convert an httpx exception or HTTP error response into an ExternalServiceError."""
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(
            f"SLAI timeout: {context}",
            is_retryable=True,
            details={"provider": "slai", "reason": "timeout"},
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        return ExternalServiceError(
            f"SLAI error {status}: {context}",
            is_retryable=is_retryable,
            details={
                "provider": "slai",
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        )

    return ExternalServiceError(
        f"SLAI connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "slai", "reason": "connection_error"},
    )


class SlaiClient:
    """Async client for the SLAI image generation API.

    Uses a submit → poll pattern:
    1. POST /v1/images/generations to start generation
    2. If SLAI responds with a URL immediately, return it
    3. If SLAI responds with a cache_id (pending), poll until ready
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.slai_api_base_url.rstrip("/")
        self._api_key = settings.slai_api_key
        self._timeout = httpx.Timeout(
            timeout=float(settings.image_timeout_seconds),
            connect=15.0,
        )

    async def close(self) -> None:
        """No persistent client to close (uses per-request clients)."""
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
        """Generate an image using SLAI.

        Submits a generation request and waits for the result. If the initial
        request returns a cache_id (async generation), polls until the image
        is ready (up to 3 minutes total).

        Returns:
            Response dict with 'data' containing image URL.

        Raises:
            ExternalServiceError: On permanent failure after retries.
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
            "model": "cgpt-web/gpt-5.5-pro",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": "url",
            "n": 1,
        }

        if reference_image_base64:
            payload["image_url"] = f"data:image/png;base64,{reference_image_base64}"

        if extra_params:
            payload.update(extra_params)

        url = f"{self._base_url}/v1/images/generations"

        # Submit with generous timeout (SLAI can be slow)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=15.0),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                # Got immediate result with URL
                if self._has_image_url(data):
                    return data

                # Got pending response — poll for result
                cache_id = self._extract_cache_id(data)
                if cache_id:
                    logger.info("SLAI returned cache_id=%s, polling for result...", cache_id)
                    return await self._poll_for_result(key, cache_id)

                # Unknown shape but 200 — return as-is
                return data

        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="generate_image") from exc

    async def _poll_for_result(
        self, api_key: str, cache_id: str, max_wait: int = 150
    ) -> dict[str, Any]:
        """Poll SLAI for a completed image result.

        Checks every 5 seconds for up to max_wait seconds.
        """
        poll_url = f"{self._base_url}/v1/images/generations/{cache_id}"
        elapsed = 0.0
        poll_interval = 5.0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                ) as client:
                    resp = await client.get(poll_url)

                    if resp.status_code == 200:
                        data = resp.json()
                        if self._has_image_url(data):
                            logger.info(
                                "SLAI image ready (cache_id=%s, %.0fs elapsed)",
                                cache_id, elapsed,
                            )
                            return data
                    # 202 = still processing, 404 = not ready yet
                    elif resp.status_code not in (202, 404):
                        logger.warning(
                            "SLAI poll returned %d for cache_id=%s",
                            resp.status_code, cache_id,
                        )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.debug("SLAI poll attempt failed: %s", exc)
                continue

        raise ExternalServiceError(
            f"SLAI image generation did not complete within {max_wait}s (cache_id={cache_id})",
            is_retryable=True,
            details={"provider": "slai", "cache_id": cache_id},
        )

    @staticmethod
    def _has_image_url(data: dict[str, Any]) -> bool:
        """Check if the response contains a usable image URL."""
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
        """Extract cache_id from a pending SLAI response."""
        if not isinstance(data, dict):
            return ""
        data_list = data.get("data")
        if isinstance(data_list, list) and data_list:
            first = data_list[0]
            if isinstance(first, dict):
                return str(first.get("cache_id", "") or "").strip()
        return str(data.get("cache_id", "") or "").strip()
