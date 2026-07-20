"""Tests for export quality tier presets."""

from __future__ import annotations

from shared.lib.export_tiers import (
    DEFAULT_MANUAL_EXPORT_TIER,
    DEFAULT_PIPELINE_EXPORT_TIER,
    resolve_export_tier_settings,
)


def test_pipeline_defaults_to_draft_tier() -> None:
    tier = resolve_export_tier_settings({}, pipeline=True)
    assert tier.tier == DEFAULT_PIPELINE_EXPORT_TIER
    assert tier.resolution == "1280x720"
    assert tier.fps == 24
    assert tier.speed_mode == "very_fast"


def test_manual_defaults_to_standard_tier() -> None:
    tier = resolve_export_tier_settings({}, pipeline=False)
    assert tier.tier == DEFAULT_MANUAL_EXPORT_TIER
    assert tier.speed_mode == "fast"


def test_master_tier_uses_user_settings() -> None:
    tier = resolve_export_tier_settings(
        {
            "videoExportTier": "master",
            "outputResolution": "2560x1440",
            "videoExportFps": 48,
            "videoExportSpeedMode": "balanced",
        },
        pipeline=False,
    )
    assert tier.tier == "master"
    assert tier.resolution == "2560x1440"
    assert tier.fps == 48
    assert tier.speed_mode == "balanced"
