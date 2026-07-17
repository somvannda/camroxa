"""LLM client SLAI model normalization."""

from platform_api.clients.llm_client import _normalize_slai_text_model


def test_normalize_slai_text_model_maps_legacy_mimo_alias() -> None:
    assert _normalize_slai_text_model("mimo-v2.5-pro") == "xiaomi/mimo-v2.5-pro"
    assert _normalize_slai_text_model("xiaomi/mimo-v2.5-pro") == "xiaomi/mimo-v2.5-pro"
