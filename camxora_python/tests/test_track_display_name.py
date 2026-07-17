"""Tests for Suno track display-name cleaning and title expansion."""

from __future__ import annotations

from features.video.lib.text_domain_runtime import expand_text_domains_to_overlays
from features.video.lib.track_display_name import clean_track_display_name, format_title_marker


def test_clean_track_display_name_strips_design_suffixes() -> None:
    assert clean_track_display_name(r"D:/x/10. Weaving Phantoms_OK.mp3") == "Weaving Phantoms"
    assert clean_track_display_name(r"D:/x/1. Dark Trap_Primary.mp3") == "Dark Trap"
    assert clean_track_display_name(r"D:/x/2. Song_Secondary.mp3") == "Song"
    assert clean_track_display_name(r"D:/x/3. Song_Alt.mp3") == "Song"
    assert clean_track_display_name(r"D:/x/4. Song_ATL.mp3") == "Song"


def test_format_title_marker() -> None:
    assert format_title_marker(0, "number") == "1. "
    assert format_title_marker(9, "number_pad") == "10. "
    assert format_title_marker(0, "bullet").startswith("•")
    assert format_title_marker(0, "plain") == ""


def test_format_title_marker_aligned_indent() -> None:
    # With 10 items, aligned uses 01..10 so title text shares one column.
    one = format_title_marker(0, "number", total=10, indent="aligned")
    ten = format_title_marker(9, "number", total=10, indent="aligned")
    assert one == "01. "
    assert ten == "10. "
    assert len(one) == len(ten)
    flush_one = format_title_marker(0, "number", total=10, indent="flush")
    assert flush_one == "1. "
    assert len(flush_one) < len(one)


def test_expand_title_grid_from_track_list() -> None:
    template = {
        "titleText": {
            "enabled": True,
            "contentMode": "pipeline",
            "listStyle": "number",
            "layout": "grid2_td",
            "style": {"fontSize": 28, "anchor": "left", "x": 40, "y": 80},
        }
    }
    paths = [
        r"D:/x/1. Alpha_OK.mp3",
        r"D:/x/2. Beta_Primary.mp3",
        r"D:/x/3. Gamma_Secondary.mp3",
    ]
    overlays = expand_text_domains_to_overlays(template, track_paths=paths)
    assert [item["text"] for item in overlays] == ["1. Alpha", "2. Beta", "3. Gamma"]
    assert all(item.get("source") == "titleText" for item in overlays)
