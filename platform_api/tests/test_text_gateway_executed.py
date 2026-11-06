"""Text gateway reports the provider/model that actually ran (W7)."""

from __future__ import annotations

import pytest

from platform_api.ai.providers.text.gateway import TextProviderGateway
from platform_api.exceptions import ExternalServiceError


class FakeLlmClient:
    def __init__(self, *, fail_models: set[str] | None = None) -> None:
        self.fail_models = fail_models or set()
        self.calls: list[str] = []

    async def chat_completion(
        self,
        *,
        messages,
        model: str = "x",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format=None,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_payload=None,
        timeout_seconds: float | None = None,
    ):
        self.calls.append(model)
        if model in self.fail_models:
            raise ExternalServiceError(
                f"{model} is down", is_retryable=True, details={"model": model}
            )
        return {"choices": [{"message": {"content": f"ok:{model}"}}]}


class FakePool:
    async def execute(self, fn):
        return await fn("test-key")


def _gateway(component: FakeLlmClient) -> TextProviderGateway:
    return TextProviderGateway(
        llm_client=component,
        openai_pool=FakePool(),
        deepseek_pool=FakePool(),
        slai_pool=FakePool(),
        slai_base_url="https://slai.test",
    )


@pytest.mark.asyncio
async def test_reports_first_provider_on_success() -> None:
    client = FakeLlmClient()
    gateway = _gateway(client)

    result = await gateway.generate_text_with_meta(
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="s",
        user_prompt="u",
        provider_chain=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-v4-flash")],
    )

    assert result.content == "ok:gpt-4o-mini"
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_reports_fallback_provider_when_first_fails() -> None:
    client = FakeLlmClient(fail_models={"gpt-4o-mini"})
    gateway = _gateway(client)

    result = await gateway.generate_text_with_meta(
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="s",
        user_prompt="u",
        provider_chain=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-v4-flash")],
    )

    assert result.content == "ok:deepseek-v4-flash"
    assert result.provider == "deepseek"
    assert result.model == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_generate_text_wrapper_returns_content_only() -> None:
    gateway = _gateway(FakeLlmClient())

    content = await gateway.generate_text(
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="s",
        user_prompt="u",
    )

    assert content == "ok:gpt-4o-mini"
