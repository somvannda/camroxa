"""Async HTTP client for the Fal AI image generation API.

Handles image generation requests with 60-second timeout.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

# Timeout for Fal AI image requests (seconds)
_FAL_TIMEOUT = 60.0


def _classify_error(exc: Exception, *, context: str = "") -> ExternalServiceError:
    """Convert an httpx exception or HTTP error response into an ExternalServiceError.

    Retryable: timeouts, rate limits (429), 5xx server errors.
    Permanent: 4xx client errors (except 429).
    """
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(
            f"Fal AI timeout: {context}",
            is_retryable=True,
            details={"provider": "fal", "reason": "timeout"},
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        return ExternalServiceError(
            f"Fal AI error {status}: {context}",
            is_retryable=is_retryable,
            details={
                "provider": "fal",
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        )

    # Network-level failures are retryable
    return ExternalServiceError(
        f"Fal AI connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "fal", "reason": "connection_error"},
    )


class FalClient:
    """Async client for the Fal AI image generation API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.fal_api_base_url.rstrip("/")
        self._api_key = settings.fal_api_key
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
                    "Authorization": f"Key {self._api_key}",
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
        model_id: str = "fal-ai/flux/schnell",
        width: int = 1920,
        height: int = 1080,
        num_images: int = 1,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate an image using Fal AI.

        Args:
            prompt: Text prompt describing the desired image.
            model_id: Fal AI model identifier (path-based routing).
            width: Output image width in pixels.
            height: Output image height in pixels.
            num_images: Number of images to generate.
            extra_params: Additional model-specific parameters.

        Returns:
            Response dict containing image URLs/data from Fal AI.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "prompt": prompt,
            "image_size": {
                "width": width,
                "height": height,
            },
            "num_images": num_images,
        }
        if extra_params:
            payload.update(extra_params)

        try:
            response = await client.post(f"/{model_id}", json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context=f"generate_image({model_id})") from exc
