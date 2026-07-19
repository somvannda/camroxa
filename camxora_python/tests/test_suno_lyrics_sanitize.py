"""Desktop mirror tests for Suno lyrics risk detection."""

from __future__ import annotations

from shared.lib.suno_lyrics_sanitize import (
    find_suno_risk_terms_in_lyrics,
    find_suno_risk_terms_in_text,
    sanitize_text_for_suno_with_changes,
)


def test_find_suno_risk_terms_matches_api_blocklist() -> None:
    hits = find_suno_risk_terms_in_lyrics("Shadows in the lowlight fade")
    assert any(hit.severity == "block" for hit in hits)


def test_find_suno_risk_terms_in_text_scans_title() -> None:
    hits = find_suno_risk_terms_in_text("lowlight dreams")
    assert any(hit.severity == "block" for hit in hits)


def test_sanitize_text_for_suno_with_changes_matches_api() -> None:
    cleaned, replacements = sanitize_text_for_suno_with_changes("lowlight fade")
    assert "afterglow" in cleaned
    assert replacements[0].source.lower() == "lowlight"
