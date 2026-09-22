"""Tests for track row chrome model and layout."""

from __future__ import annotations

from studio.core.playlist_row_chrome import (
    PlaylistRowChrome,
    default_row_chrome_for_layout,
    format_track_number,
    row_chrome_from_legacy,
    sync_legacy_row_flags,
)
from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_sub_template_styles import apply_style_dict, capture_style_dict, default_style_dict


def test_format_track_number():
    assert format_track_number(0, "padded2") == "01"
    assert format_track_number(9, "plain") == "10"


def test_default_row_chrome_differs_by_template():
    fm = default_row_chrome_for_layout("forest_mist")
    mw = default_row_chrome_for_layout("minimal_white")
    assert fm.play.show_on_inactive is False
    assert mw.play.show_on_inactive is True
    assert fm.play.when_playing == "play_icon"
    assert mw.play.when_playing == "animation"
    assert fm.animation.placement == "trailing"
    assert mw.animation.placement == "leading"


def test_row_chrome_legacy_migration():
    data = {"show_track_numbers": False, "show_durations": True}
    from core.playlist_sub_template_styles import _resolve_row_chrome

    chrome = _resolve_row_chrome(data, "minimal-white")
    assert chrome.numbers.enabled is False
    assert chrome.duration.enabled is True


def test_row_chrome_round_trip_in_style_dict():
    settings = PlaylistSettings(sub_template_id="minimal-white")
    settings.row_chrome = default_row_chrome_for_layout("minimal_white")
    settings.row_chrome.numbers.enabled = False
    sync_legacy_row_flags(settings)
    blob = capture_style_dict(settings)
    restored = PlaylistSettings(sub_template_id="minimal-white")
    apply_style_dict(restored, blob)
    assert restored.row_chrome.numbers.enabled is False
    assert restored.show_track_numbers is False


def test_default_style_dict_includes_row_chrome():
    blob = default_style_dict("forest-mist")
    assert "row_chrome" in blob
    assert blob["row_chrome"]["play"]["when_playing"] == "play_icon"


def test_row_chrome_serialization():
    chrome = PlaylistRowChrome.from_dict(
        {
            "numbers": {"enabled": True, "format": "plain"},
            "play": {"when_playing": "both", "size_scale_pct": 120},
            "duration": {"enabled": False},
            "animation": {"bar_count": 6, "placement": "trailing"},
        }
    )
    assert chrome.numbers.format == "plain"
    assert chrome.play.when_playing == "both"
    assert chrome.play.size_scale_pct == 120
    assert chrome.duration.enabled is False
    assert chrome.animation.bar_count == 6
