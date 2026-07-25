"""Text provider fallback advances on permanent model errors."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from platform_api.ai.providers.text.gateway import TextProviderGateway
from platform_api.ai.parsing.response_parser import extract_chat_content
from platform_api.exceptions import ExternalServiceError
from platform_api.services.ai_routing_service import (
    RoutingResult,
    expand_text_chain_with_sibling_models,
)


def test_expand_text_chain_tries_sibling_models_before_next_provider() -> None:
    chain = expand_text_chain_with_sibling_models(
        [
            RoutingResult("deepseek", "deepseek-chat", "text_generation"),
            RoutingResult("slai", "xiaomi/mimo-v2.5-pro", "text_generation"),
            RoutingResult("openai", "gpt-4o-mini", "text_generation"),
        ]
    )
    providers = [item.provider for item in chain]
    assert list(dict.fromkeys(providers)) == ["deepseek", "slai", "openai"]
    deepseek = [item.sub_model for item in chain if item.provider == "deepseek"]
    assert deepseek == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert chain[2].provider == "slai"


def test_extract_chat_content_falls_back_to_reasoning_content() -> None:
    text = extract_chat_content(
        {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "reasoning_content": "Final answer: OK",
                    }
                }
            ]
        }
    )
    assert text == "Final answer: OK"


def test_extract_chat_content_joins_multipart_content() -> None:
    text = extract_chat_content(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": '{"title": "Coastal Pulse"}'},
                        ]
                    }
                }
            ]
        }
    )
    assert "Coastal Pulse" in text


@pytest.mark.asyncio
async def test_chat_completion_with_fallback_advances_on_non_retryable_400() -> None:
    class _FailThenOkClient:
        def __init__(self) -> None:
            self.models: list[str] = []

        async def chat_completion(self, **kwargs: Any) -> dict[str, Any]:
            model = str(kwargs.get("model") or "")
            self.models.append(model)
            if model == "deepseek-v4-flash":
                raise ExternalServiceError(
                    "invalid model",
                    is_retryable=False,
                    details={"status_code": 400},
                )
            return {
                "choices": [{"message": {"content": f"ok:{model}"}}],
            }

    class _Pool:
        async def execute(self, fn: Any) -> Any:
            return await fn("sk-test")

    client = _FailThenOkClient()
    gateway = TextProviderGateway(
        llm_client=client,
        openai_pool=_Pool(),
        deepseek_pool=_Pool(),
        slai_pool=_Pool(),
        slai_base_url="https://example.invalid",
    )
    response = await gateway.chat_completion_with_fallback(
        provider_chain=[
            ("deepseek", "deepseek-v4-flash"),
            ("deepseek", "deepseek-v4-pro"),
            ("slai", "xiaomi/mimo-v2.5-pro"),
        ],
        messages=[{"role": "user", "content": "hi"}],
    )
    assert response["choices"][0]["message"]["content"] == "ok:deepseek-v4-pro"
    assert client.models == ["deepseek-v4-flash", "deepseek-v4-pro"]
