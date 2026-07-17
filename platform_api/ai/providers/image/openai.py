"""OpenAI image generation helpers."""

from __future__ import annotations

from typing import Any

import httpx

from platform_api.ai.registry import resolve_image_model_id
from platform_api.exceptions import ExternalServiceError

_OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"


def openai_image_size(model: str, width: int, height: int) -> str:
    """Map requested dimensions to an OpenAI images API size string."""
    if model.startswith("gpt-image"):
        if width == height:
            return "1024x1024"
        if width > height:
            return "1536x1024"
        return "1024x1536"
    if width == height:
        return "1024x1024"
    if width > height:
        return "1792x1024"
    return "1024x1792"


def build_openai_image_payload(
    *,
    prompt: str,
    model: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    canonical = resolve_image_model_id("openai", model, default="gpt-image-1")
    payload: dict[str, Any] = {
        "model": canonical,
        "prompt": prompt,
        "n": 1,
        "size": openai_image_size(canonical, width, height),
    }
    if canonical.startswith("gpt-image"):
        payload["quality"] = "low"
    else:
        payload["response_format"] = "b64_json"
    return payload


async def request_openai_image(
    *,
    prompt: str,
    model: str,
    width: int,
    height: int,
    api_key: str,
) -> dict[str, Any]:
    """Call OpenAI /v1/images/generations and return the JSON response."""
    payload = build_openai_image_payload(
        prompt=prompt,
        model=model,
        width=width,
        height=height,
    )
    canonical = str(payload["model"])

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=15.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = await client.post(_OPENAI_IMAGES_URL, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(
            f"OpenAI image generation timeout (model={canonical})",
            is_retryable=True,
            details={"provider": "openai", "model": canonical},
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        raise ExternalServiceError(
            f"OpenAI image generation error {status} (model={canonical})",
            is_retryable=is_retryable,
            details={
                "provider": "openai",
                "model": canonical,
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        ) from exc
    except httpx.RequestError as exc:
        raise ExternalServiceError(
            f"OpenAI image connection error: {exc}",
            is_retryable=True,
            details={"provider": "openai", "model": canonical},
        ) from exc
