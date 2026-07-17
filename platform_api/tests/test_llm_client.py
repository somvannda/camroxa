"""LLM client SLAI model normalization."""

import pytest

from platform_api.clients.llm_client import (
    _aggregate_streaming_chat_response,
    _chat_completions_url,
    _normalize_slai_text_model,
)


def test_normalize_slai_text_model_maps_legacy_mimo_alias() -> None:
    assert _normalize_slai_text_model("mimo-v2.5-pro") == "xiaomi/mimo-v2.5-pro"
    assert _normalize_slai_text_model("xiaomi/mimo-v2.5-pro") == "xiaomi/mimo-v2.5-pro"


def test_chat_completions_url_slai_uses_non_v1_path() -> None:
    assert (
        _chat_completions_url("https://api.slai.shop")
        == "https://api.slai.shop/chat/completions"
    )


def test_chat_completions_url_openai_uses_v1_path() -> None:
    assert (
        _chat_completions_url("https://api.openai.com")
        == "https://api.openai.com/v1/chat/completions"
    )


@pytest.mark.asyncio
async def test_aggregate_streaming_chat_response_collects_deltas() -> None:
    import httpx

    class _FakeResponse:
        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield "data: [DONE]"

    result = await _aggregate_streaming_chat_response(_FakeResponse())  # type: ignore[arg-type]
    assert result["choices"][0]["message"]["content"] == "Hello"
