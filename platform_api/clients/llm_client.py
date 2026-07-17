"""Async HTTP client for LLM services (DeepSeek / SLAI) used for song draft generation.

Handles chat completion requests with configurable per-model timeouts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

# Legacy module constant — prefer settings.llm_timeout_seconds.
_LLM_TIMEOUT = 120.0

_SLAI_TEXT_MODEL_ALIASES = {
    "mimo-v2.5-pro": "xiaomi/mimo-v2.5-pro",
}


def _normalize_slai_text_model(model: str) -> str:
    from platform_api.ai.registry import resolve_text_model_id

    return resolve_text_model_id("slai", model)


def _chat_completions_url(base_url: str) -> str:
    """Build OpenAI-compatible chat URL for a provider base URL."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    # SLAI text chat is served at /chat/completions (images use /v1/images/...).
    if "slai" in normalized.lower():
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


async def _aggregate_streaming_chat_response(response: httpx.Response) -> dict[str, Any]:
    """Collect SSE chat completion chunks into a non-streaming response shape."""
    content_parts: list[str] = []
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta") or {}
            if not isinstance(delta, dict):
                continue
            piece = delta.get("content")
            if piece:
                content_parts.append(str(piece))
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "".join(content_parts),
                }
            }
        ]
    }


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
        self._default_timeout_seconds = float(settings.llm_timeout_seconds)
        self._timeout = httpx.Timeout(
            timeout=self._default_timeout_seconds,
            connect=10.0,
        )
        self._client: httpx.AsyncClient | None = None

    def _request_timeout(self, timeout_seconds: float | None) -> httpx.Timeout:
        read_timeout = float(timeout_seconds or self._default_timeout_seconds)
        return httpx.Timeout(timeout=read_timeout, connect=10.0)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
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
        extra_payload: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
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
        if extra_payload:
            payload.update(extra_payload)

        if base_url:
            from platform_api.ai.registry import resolve_text_model_id

            payload["model"] = resolve_text_model_id("slai", model)

        if not api_key:
            raise ExternalServiceError(
                "LLM API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "llm"},
            )

        # Per-request base_url + key override (used when SLAI pool keys route
        # through this client). Falls back to the client's default otherwise.
        if base_url:
            # One-shot request to a different endpoint
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(
                    timeout=self._request_timeout(timeout_seconds),
                ) as temp_client:
                    if payload.get("stream"):
                        async with temp_client.stream(
                            "POST",
                            _chat_completions_url(base_url),
                            json=payload,
                            headers=headers,
                        ) as response:
                            if response.is_error:
                                await response.aread()
                            response.raise_for_status()
                            return await _aggregate_streaming_chat_response(response)
                    response = await temp_client.post(
                        _chat_completions_url(base_url),
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                raise _classify_error(exc, context=f"chat_completion({model})") from exc
        else:
            client = await self._get_client()
            request_headers = {"Authorization": f"Bearer {api_key}"}
            request_timeout = self._request_timeout(timeout_seconds)
            try:
                response = await client.post(
                    "/v1/chat/completions",
                    json=payload,
                    headers=request_headers,
                    timeout=request_timeout,
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
