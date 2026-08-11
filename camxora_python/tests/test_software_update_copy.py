from __future__ import annotations

from shared.lib.software_update_copy import (
    SUMMARY_MANDATORY,
    format_download_progress,
    format_update_summary,
    format_version_row,
    format_whats_new,
)


def test_format_update_summary() -> None:
    text = format_update_summary(required_version="0.2.5", current_version="0.2.4")
    assert text == SUMMARY_MANDATORY
    assert "required update" in text.lower()
    assert "application will close" in text.lower()
    assert "save your work" not in text.lower()
    # Versions belong on the muted meta row, not duplicated in the body.
    assert "0.2.5" not in text
    assert "0.2.4" not in text
    assert "camxora" not in text.lower()
    assert "setup" not in text.lower()


def test_format_version_row() -> None:
    assert (
        format_version_row(
            required_version="1.2.5",
            current_version="1.2.4",
            mandatory=True,
        )
        == "Required 1.2.5  ·  Current 1.2.4"
    )


def test_format_download_progress() -> None:
    assert format_download_progress(percent=31) == "Downloading update… 31%"
    assert format_download_progress(megabytes=12.5) == "Downloading update… 12.5 MB"


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


def test_format_whats_new_skips_changelog_metadata() -> None:
    notes = """Camxora 1.2.4 — Lightning export timing (per-bolt) + visibility
August 11, 2026
What's new
- Restore per-bolt lightning export timing
- Keep multi-bolt visibility in encode windows
"""
    assert format_whats_new(notes) == [
        "Restore per-bolt lightning export timing",
        "Keep multi-bolt visibility in encode windows",
    ]


def test_format_whats_new_hides_metadata_only_notes() -> None:
    notes = """Camxora 1.2.4 — Lightning export timing
August 11, 2026
What's new
"""
    assert format_whats_new(notes) == []
