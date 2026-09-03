import pytest

from studio.ui.timeline.geometry import (
    CLIP_HEIGHT,
    CLIP_LABEL_HEIGHT,
    TRACK_HEIGHT,
    effective_timeline_width_px,
    timeline_width_px,
)


def test_effective_timeline_width_fills_wide_viewport():
    content = timeline_width_px(0.0, 70.0)
    assert effective_timeline_width_px(0.0, 70.0, 1920) == max(content, 1920)


def test_effective_timeline_width_shrinks_with_narrow_viewport():
    content = timeline_width_px(0.0, 70.0)
    assert effective_timeline_width_px(0.0, 70.0, 800) == content


def test_effective_timeline_width_content_wins_when_longer():
    wide = effective_timeline_width_px(120.0, 70.0, 800)
    assert wide == timeline_width_px(120.0, 70.0)
    assert wide > 800


def test_clip_body_taller_than_label_bar():
    """Phase-1 chrome: label strip is thin so filmstrip/waveform gets more height."""
    body_height = CLIP_HEIGHT - CLIP_LABEL_HEIGHT
    assert CLIP_LABEL_HEIGHT <= 12
    assert body_height >= CLIP_HEIGHT * 0.75


def test_track_height_unchanged_for_header_alignment():
    assert TRACK_HEIGHT == 56
