"""Async HTTP client for the SLAI image generation API.

Handles image generation requests with 60-second timeout.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

# Timeout for SLAI image requests (seconds)
_SLAI_TIMEOUT = 60.0


def _classify_error(exc: Exception, *, context: str = "") -> ExternalServiceError:
    """Convert an httpx exception or HTTP error response into an ExternalServiceError.

    Retryable: timeouts, rate limits (429), 5xx server errors.
    Permanent: 4xx client errors (except 429).
    """
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

    # Network-level failures are retryable
    return ExternalServiceError(
        f"SLAI connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "slai", "reason": "connection_error"},
    )


class SlaiClient:
    """Async client for the SLAI image generation API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.slai_api_base_url.rstrip("/")
        self._api_key = settings.slai_api_key
        self._timeout = httpx.Timeout(
            timeout=float(settings.image_timeout_seconds),
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

    async def generate_image(
        self,
        *,
        prompt: str,
        width: int = 1920,
        height: int = 1080,
        style_strength: float = 0.6,
        reference_image_base64: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate an image using SLAI.

        Args:
            prompt: Text prompt describing the desired image.
            width: Output image width in pixels.
            height: Output image height in pixels.
            style_strength: Strength of style application (0.0-1.0).
            reference_image_base64: Optional base64-encoded reference image.
            extra_params: Additional model-specific parameters.

        Returns:
            Response dict containing image data/URLs from SLAI.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "style_strength": style_strength,
        }
        if reference_image_base64:
            payload["reference_image"] = reference_image_base64
        if extra_params:
            payload.update(extra_params)

        try:
            response = await client.post("/v1/generate/image", json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="generate_image") from exc
