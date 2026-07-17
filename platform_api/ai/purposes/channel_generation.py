"""Channel setup text generation helpers."""

from __future__ import annotations

from typing import Any, Protocol


class TextGenerationService(Protocol):
    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        provider: str,
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 800,
        response_format: dict[str, str] | None = None,
        prefer_json: bool = False,
        provider_chain: list[tuple[str, str]] | None = None,
    ) -> str:
        ...


async def generate_channel_text(
    generation_service: TextGenerationService,
    *,
    provider: str,
    model: str | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int = 1200,
    provider_chain: list[tuple[str, str]] | None = None,
) -> str:
    """Run a channel-purpose LLM call with registry-driven JSON mode."""
    from platform_api.ai.registry import json_response_format

    return await generation_service.generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        provider=provider,
        model=model or "",
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=json_response_format(provider, model),
        prefer_json=True,
        provider_chain=provider_chain,
    )
