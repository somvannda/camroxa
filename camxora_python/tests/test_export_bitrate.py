"""Tests for CapCut-inspired Recommended export bitrate."""

from __future__ import annotations

from shared.lib.export_bitrate import (
    format_bitrate_mbps,
    recommended_export_bitrate_kbps,
    recommended_vbr_ladder_kbps,
)


def test_recommended_bitrate_1440p_30_quality_matches_capcut_anchor() -> None:
    # Observed CapCut 2K@30 Recommended ≈ 12 Mbps
    assert recommended_export_bitrate_kbps(2560, 1440, 30, "quality") == 12000


def test_recommended_bitrate_1080p_30_quality() -> None:
    assert recommended_export_bitrate_kbps(1920, 1080, 30, "quality") == 8000


def test_recommended_bitrate_scales_with_fps() -> None:
    base = recommended_export_bitrate_kbps(2560, 1440, 30, "quality")
    assert recommended_export_bitrate_kbps(2560, 1440, 60, "quality") == base * 2
    assert recommended_export_bitrate_kbps(2560, 1440, 24, "quality") == int(round(base * 24 / 30))
    assert recommended_export_bitrate_kbps(2560, 1440, 48, "quality") == int(round(base * 48 / 30))


def test_recommended_bitrate_scales_with_speed() -> None:
    quality = recommended_export_bitrate_kbps(1920, 1080, 30, "quality")
    best = recommended_export_bitrate_kbps(1920, 1080, 30, "best_quality")
    very_fast = recommended_export_bitrate_kbps(1920, 1080, 30, "very_fast")
    assert best > quality > very_fast
    assert best == int(round(quality * 1.25))
    assert very_fast == int(round(quality * 0.55))


def test_vbr_ladder_peaks() -> None:
    target, maxrate, bufsize = recommended_vbr_ladder_kbps(1920, 1080, 30, "quality")
    assert target == 8000
    assert maxrate == 12000
    assert bufsize == 16000


def test_format_bitrate_mbps() -> None:
    assert format_bitrate_mbps(12000) == "12 Mbps"
    assert format_bitrate_mbps(8500) == "8.5 Mbps"
