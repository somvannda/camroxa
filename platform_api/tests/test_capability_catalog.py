"""Tests for AI capability catalog and routing audit."""

from __future__ import annotations

from platform_api.ai.capability_catalog import audit_routing_configuration, build_capability_catalog
from platform_api.ai.types import IMAGE_OPERATIONS, TEXT_OPERATIONS


def test_catalog_includes_suno_for_lyrics() -> None:
    catalog = build_capability_catalog()
    assert "suno" in catalog["text_llm_providers"]
    suno = next(item for item in catalog["providers"] if item["provider"] == "suno")
    assert "music_generation" in suno["service_types"]
    assert "text_generation" in suno["service_types"]
    assert "lyrics" in suno["text_models"]
    assert "V6" in suno["music_models"]


def test_audit_flags_missing_pricing() -> None:
    result = audit_routing_configuration(
        assignments={
            "lyric": {"provider": "slai", "sub_model": "xiaomi/mimo-v2.5-pro"},
        },
        text_fallback_chain=[],
        image_fallback_chain=[],
        pricing_entries=[],
    )
    assert result["ready"] is False
    assert result["error_count"] >= 1
    assert any(issue["code"] == "missing_pricing" for issue in result["issues"])


def test_audit_passes_when_pricing_present() -> None:
    result = audit_routing_configuration(
        assignments={
            "lyric": {"provider": "deepseek", "sub_model": "deepseek-chat"},
        },
        text_fallback_chain=[],
        image_fallback_chain=[],
        pricing_entries=[
            {
                "ai_service": "deepseek",
                "operation_type": "lyric",
                "sub_model": "deepseek-chat",
                "credits_per_operation": 3,
            }
        ],
    )
    assert result["ready"] is True
    assert result["error_count"] == 0


def test_audit_accepts_suno_for_music_without_sub_model() -> None:
    result = audit_routing_configuration(
        assignments={
            "music": {"provider": "suno", "sub_model": None},
        },
        text_fallback_chain=[],
        image_fallback_chain=[],
        pricing_entries=[
            {
                "ai_service": "suno",
                "operation_type": "music",
                "sub_model": "V6_MINI",
                "credits_per_operation": 15,
            }
        ],
    )
    assert result["ready"] is True
    assert result["error_count"] == 0


def test_audit_accepts_suno_for_lyric_operation() -> None:
    result = audit_routing_configuration(
        assignments={
            "lyric": {"provider": "suno", "sub_model": "lyrics"},
        },
        text_fallback_chain=[],
        image_fallback_chain=[],
        pricing_entries=[
            {
                "ai_service": "suno",
                "operation_type": "lyric",
                "sub_model": "lyrics",
                "credits_per_operation": 5,
            }
        ],
    )
    assert result["ready"] is True
    assert result["error_count"] == 0


def test_audit_rejects_suno_for_text_operation() -> None:
    result = audit_routing_configuration(
        assignments={
            "channel_name": {"provider": "suno", "sub_model": None},
        },
        text_fallback_chain=[],
        image_fallback_chain=[],
        pricing_entries=[
            {
                "ai_service": "suno",
                "operation_type": "channel_name",
                "credits_per_operation": 3,
            }
        ],
    )
    assert result["ready"] is False
    assert any(issue["code"] == "invalid_capability" for issue in result["issues"])


def test_fallback_requires_pricing_for_all_text_operations() -> None:
    result = audit_routing_configuration(
        assignments={},
        text_fallback_chain=[{"provider": "deepseek", "sub_model": "deepseek-chat"}],
        pricing_entries=[
            {
                "ai_service": "deepseek",
                "operation_type": "lyric",
                "sub_model": "deepseek-chat",
                "credits_per_operation": 3,
            }
        ],
    )
    missing = [
        issue
        for issue in result["issues"]
        if issue["code"] == "missing_pricing" and issue["operation"] != "lyric"
    ]
    assert len(missing) == len(TEXT_OPERATIONS) - 1


def test_image_fallback_requires_pricing_for_all_image_operations() -> None:
    result = audit_routing_configuration(
        assignments={},
        text_fallback_chain=[],
        image_fallback_chain=[{"provider": "fal", "sub_model": "flux-pro"}],
        pricing_entries=[
            {
                "ai_service": "fal",
                "operation_type": "channel_logo",
                "sub_model": "flux-pro",
                "credits_per_operation": 3,
            }
        ],
    )
    missing = [
        issue
        for issue in result["issues"]
        if issue["code"] == "missing_pricing" and issue["operation"] != "channel_logo"
    ]
    assert len(missing) == len(IMAGE_OPERATIONS) - 1


def test_catalog_lists_all_text_operations() -> None:
    catalog = build_capability_catalog()
    assert set(catalog["text_operations"]) == set(TEXT_OPERATIONS)
