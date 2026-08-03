from __future__ import annotations

from shared.lib.software_update_copy import format_update_summary, format_whats_new


def test_format_update_summary() -> None:
    text = format_update_summary(required_version="0.2.5", current_version="0.2.4")
    assert "0.2.5" in text
    assert "0.2.4" in text
    assert "setup" in text.lower()


def test_format_whats_new_keeps_user_bullets() -> None:
    notes = """[0.2.5] - 2026-07-19
## Fixed
- Progress table no longer flashes empty rows
- Faster startup on cold launch
"""
    bullets = format_whats_new(notes)
    assert bullets == [
        "Progress table no longer flashes empty rows",
        "Faster startup on cold launch",
    ]


def test_format_whats_new_skips_engineer_noise() -> None:
    notes = (
        "- Progress table no longer shows stale text "
        "(clearContents + removeCellWidget in operational rows card)\n"
        "- Packaged builds read resources/app_version.txt when frozen"
    )
    assert format_whats_new(notes) == [
        "Progress table no longer shows stale text",
    ]
