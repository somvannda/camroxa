"""Text generation gateway — routes chat calls through provider adapters."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from platform_api.ai.parsing.response_parser import extract_chat_content
from platform_api.ai.registry import (
    get_text_model_spec,
    json_response_format,
    resolve_text_model_id,
    resolve_text_request_timeout,
    text_model_extra_payload,
)
from platform_api.exceptions import ExternalServiceError, NoAvailableKeysError, ValidationError

logger = logging.getLogger(__name__)

_OPENAI_BASE_URL = "https://api.openai.com"

ProviderChain = list[tuple[str, str]]


class LlmChatClient(Protocol):
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
        ...


class PoolWrapper(Protocol):
    async def execute(self, fn: Any) -> Any:
        ...


class TextProviderGateway:
    """Provider-aware text generation without purpose-specific logic."""

    def __init__(
        self,
        *,
        llm_client: LlmChatClient,
        openai_pool: PoolWrapper | None,
        deepseek_pool: PoolWrapper | None,
        slai_pool: PoolWrapper | None,
        slai_base_url: str,
        default_llm_timeout_seconds: float = 120.0,
    ) -> None:
        self._llm_client = llm_client
        self._openai_pool = openai_pool
        self._deepseek_pool = deepseek_pool
        self._slai_pool = slai_pool
        self._slai_base_url = slai_base_url.rstrip("/")
        self._default_llm_timeout_seconds = float(default_llm_timeout_seconds)

    async def chat_completion(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: dict[str, str] | None = None,
        prefer_json: bool = False,
        draft: bool = False,
    ) -> dict[str, Any]:
        canonical_model = resolve_text_model_id(provider, model)
        spec = get_text_model_spec(provider, canonical_model)
        api_model = spec.api_id if spec is not None else canonical_model
        fmt = response_format
        if fmt is None and prefer_json:
            fmt = json_response_format(provider, canonical_model)

        extra_payload = text_model_extra_payload(provider, canonical_model)
        timeout_seconds = resolve_text_request_timeout(
            provider,
            canonical_model,
            fallback=self._default_llm_timeout_seconds,
            draft=draft,
        )

        async def _call(api_key: str, *, base_url: str | None = None) -> dict[str, Any]:
            try:
                return await self._llm_client.chat_completion(
                    messages=messages,
                    model=api_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=fmt,
                    api_key=api_key,
                    base_url=base_url,
                    extra_payload=extra_payload or None,
                    timeout_seconds=timeout_seconds,
                )
            except ExternalServiceError as exc:
                status_code = (exc.details or {}).get("status_code")
                if fmt and status_code == 400:
                    return await self._llm_client.chat_completion(
                        messages=messages,
                        model=api_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=None,
                        api_key=api_key,
                        base_url=base_url,
                        extra_payload=extra_payload or None,
                        timeout_seconds=timeout_seconds,
                    )
                raise

        if provider == "openai":
            wrapper = self._require_pool(self._openai_pool, provider)
            return await wrapper.execute(
                lambda api_key: _call(api_key, base_url=_OPENAI_BASE_URL)
            )
        if provider == "deepseek":
            wrapper = self._require_pool(self._deepseek_pool, provider)
            return await wrapper.execute(lambda api_key: _call(api_key))
        if provider == "slai":
            wrapper = self._require_pool(self._slai_pool, provider)
            return await wrapper.execute(
                lambda api_key: _call(api_key, base_url=self._slai_base_url)
            )

        raise ValidationError(
            "Unsupported LLM provider.",
            details={"provider": provider, "model": canonical_model},
        )

    async def chat_completion_with_fallback(
        self,
        *,
        provider_chain: ProviderChain,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: dict[str, str] | None = None,
        prefer_json: bool = False,
        draft: bool = False,
    ) -> dict[str, Any]:
        """Try models/providers in order; advance on any provider failure.

        Chain order is expected to already expand sibling models within a
        provider before switching providers (see ``resolve_text_chain``).
        Invalid-model 400s and other permanent errors still advance so a
        retired model cannot block SLAI/OpenAI fallback.
        """
        if not provider_chain:
            raise ValidationError(
                "No text providers configured for fallback chain.",
                details={"reason": "empty_chain"},
            )

        last_error: ExternalServiceError | None = None
        for index, (provider, model) in enumerate(provider_chain):
            try:
                return await self.chat_completion(
                    provider=provider,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    prefer_json=prefer_json,
                    draft=draft,
                )
            except ExternalServiceError as exc:
                last_error = exc
                if index >= len(provider_chain) - 1:
                    raise
                logger.warning(
                    "Text provider %s/%s failed (%s); trying next fallback model/provider.",
                    provider,
                    model,
                    exc,
                )
        if last_error is not None:
            raise last_error
        raise ExternalServiceError(
            "All text providers in the fallback chain failed.",
            is_retryable=False,
            details={"providers": [p for p, _ in provider_chain]},
        )

    async def generate_text(
        self,
        *,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 800,
        response_format: dict[str, str] | None = None,
        prefer_json: bool = False,
        draft: bool = False,
        provider_chain: ProviderChain | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        chain: ProviderChain = list(provider_chain) if provider_chain else [(provider, model)]
        if not chain:
            chain = [(provider, model)]

        last_error: ExternalServiceError | None = None
        for index, (chain_provider, chain_model) in enumerate(chain):
            try:
                response = await self.chat_completion(
                    provider=chain_provider,
                    model=chain_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    prefer_json=prefer_json,
                    draft=draft or max_tokens >= 2048,
                )
            except ExternalServiceError as exc:
                last_error = exc
                if index >= len(chain) - 1:
                    raise
                logger.warning(
                    "Text provider %s/%s failed (%s); trying next fallback.",
                    chain_provider,
                    chain_model,
                    exc,
                )
                continue

            content = extract_chat_content(response)
            if content:
                return content

            empty_error = ExternalServiceError(
                "LLM returned an unexpected response shape.",
                is_retryable=True,
                details={
                    "provider": chain_provider,
                    "model": chain_model,
                    "choice_keys": list((response.get("choices") or [{}])[0].keys())
                    if isinstance(response.get("choices"), list) and response.get("choices")
                    else [],
                    "message_keys": list(
                        (
                            ((response.get("choices") or [{}])[0] or {}).get("message")
                            or {}
                        ).keys()
                    )
                    if isinstance(
                        ((response.get("choices") or [{}])[0] or {}).get("message"),
                        dict,
                    )
                    else [],
                },
            )
            last_error = empty_error
            if index >= len(chain) - 1:
                raise empty_error
            logger.warning(
                "Text provider %s/%s returned empty content; trying next fallback.",
                chain_provider,
                chain_model,
            )

        if last_error is not None:
            raise last_error
        raise ExternalServiceError(
            "LLM returned an unexpected response shape.",
            is_retryable=True,
            details={"provider": provider, "model": model},
        )

    async def generate_json_draft(
        self,
        *,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        provider_chain: ProviderChain | None = None,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if provider_chain:
            return await self.chat_completion_with_fallback(
                provider_chain=provider_chain,
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
                prefer_json=True,
                draft=True,
            )
        return await self.chat_completion(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            prefer_json=True,
            draft=True,
        )

    @staticmethod
    def _require_pool(wrapper: PoolWrapper | None, provider: str) -> PoolWrapper:
        if wrapper is None:
            raise NoAvailableKeysError(provider, {})
        return wrapper
