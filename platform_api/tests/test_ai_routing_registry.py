"""AI routing registry constant tests."""

from __future__ import annotations

from platform_api.ai.registry import PROVIDER_SUB_MODELS, SUB_MODEL_COST_TIERS
from platform_api.ai.types import IMAGE_OPERATIONS, IMAGE_PROVIDERS, PROVIDER_CAPABILITIES, TEXT_LLM_PROVIDERS, TEXT_OPERATIONS, ServiceType
from platform_api.services.model_cost_estimates import operation_types_for_model


def test_slai_text_models_include_mimo() -> None:
    slai_models = PROVIDER_SUB_MODELS["slai"]
    text_models = slai_models[ServiceType.TEXT_GENERATION]
    image_models = slai_models[ServiceType.IMAGE_GENERATION]

    assert "xiaomi/mimo-v2.5-pro" in text_models
    assert "gpt-5.6-sol" in text_models
    assert "gpt-5.6-terra" in text_models
    assert "gpt-5.6-luna" in text_models
    assert "cgpt-web/gpt-5.5-pro" not in text_models
    assert "slai/gpt-image-2" in image_models
    assert "xiaomi/mimo-v2.5-pro" not in image_models
    assert "gpt-5.6-sol" not in image_models
    assert SUB_MODEL_COST_TIERS["xiaomi/mimo-v2.5-pro"] == "~$0.00009/1K"
    assert SUB_MODEL_COST_TIERS["slai/gpt-image-2"] == "~$0.01/img"


def test_suno_supports_music_and_lyric_text() -> None:
    assert ServiceType.TEXT_GENERATION in PROVIDER_CAPABILITIES["suno"]
    assert ServiceType.MUSIC_GENERATION in PROVIDER_CAPABILITIES["suno"]
    assert "suno" in TEXT_LLM_PROVIDERS
    assert "suno" not in IMAGE_PROVIDERS
    assert "fal" in IMAGE_PROVIDERS

    suno_models = PROVIDER_SUB_MODELS["suno"]
    assert "lyrics" in suno_models[ServiceType.TEXT_GENERATION]
    assert "V5" in suno_models[ServiceType.MUSIC_GENERATION]
    assert SUB_MODEL_COST_TIERS["lyrics"] == "~0.4 credits (~$0.004)"
    assert SUB_MODEL_COST_TIERS["V5"] == "~12 Suno credits (~$0.06)"


def test_slai_gpt56_models_support_all_text_operations() -> None:
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        assert set(operation_types_for_model("slai", model)) == set(TEXT_OPERATIONS)
        assert set(operation_types_for_model("slai", model)).isdisjoint(set(IMAGE_OPERATIONS))
        assert "music" not in operation_types_for_model("slai", model)
