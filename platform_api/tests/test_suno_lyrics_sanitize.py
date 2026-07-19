"""Tests for Suno lyrics sanitization helpers."""

from __future__ import annotations

from platform_api.services.suno_lyrics_sanitize import (
    SunoSanitizeReplacement,
    SunoRuntimeBlocklist,
    extract_blocked_terms_from_suno_error,
    find_suno_risk_terms_in_lyrics,
    find_suno_risk_terms_in_text,
    format_suno_replacements,
    infer_suno_replacements_from_learned_terms,
    sanitize_lyrics_for_suno,
    sanitize_text_for_suno_with_changes,
)


def test_extract_blocked_terms_from_producer_tag_message() -> None:
    message = (
        "Suno flagged sensitive content. "
        "(Your lyrics contain producer tag lowlight - we don't reference specific artists)"
    )
    assert extract_blocked_terms_from_suno_error(message) == ["lowlight"]


def test_sanitize_lyrics_replaces_lowlight_word() -> None:
    lyrics = "[Build-up]\nPressure in the bleeding lowlight\nYour breathing won't still"
    cleaned = sanitize_lyrics_for_suno(lyrics)
    assert "lowlight" not in cleaned.lower()
    assert "afterglow" in cleaned.lower()


def test_sanitize_lyrics_uses_extra_blocked_terms() -> None:
    lyrics = "We ride the midnight skyline"
    cleaned = sanitize_lyrics_for_suno(lyrics, blocked_terms=["skyline"], replacements={"skyline": "horizon"})
    assert "skyline" not in cleaned.lower()
    assert "horizon" in cleaned.lower()


def test_find_suno_risk_terms_flags_lowlight_as_block() -> None:
    lyrics = "Pressure in the bleeding lowlight tonight"
    hits = find_suno_risk_terms_in_lyrics(lyrics)
    assert any(hit.severity == "block" and hit.term.lower() == "lowlight" for hit in hits)


def test_find_suno_risk_terms_flags_feat_as_warn() -> None:
    lyrics = "City lights feat. someone unknown"
    hits = find_suno_risk_terms_in_lyrics(lyrics)
    assert any(hit.severity == "warn" for hit in hits)


def test_find_suno_risk_terms_uses_learned_terms() -> None:
    lyrics = "Echoes on the skyline"
    hits = find_suno_risk_terms_in_lyrics(lyrics, learned_terms=["skyline"])
    assert any(hit.severity == "block" and hit.term.lower() == "skyline" for hit in hits)


def test_find_suno_risk_terms_in_text_scans_title() -> None:
    hits = find_suno_risk_terms_in_text("Neon lowlight title")
    assert any(hit.severity == "block" for hit in hits)


def test_sanitize_text_for_suno_with_changes_returns_replacements() -> None:
    cleaned, replacements = sanitize_text_for_suno_with_changes(
        "Shadows in the lowlight fade",
        field="lyrics",
    )
    assert "afterglow" in cleaned.lower()
    assert replacements == [
        SunoSanitizeReplacement(field="lyrics", source="lowlight", target="afterglow")
    ]


def test_format_suno_replacements() -> None:
    text = format_suno_replacements(
        [SunoSanitizeReplacement(field="lyrics", source="lowlight", target="afterglow")]
    )
    assert text == "lowlight → afterglow"


def test_infer_suno_replacements_from_learned_terms() -> None:
    inferred = infer_suno_replacements_from_learned_terms(
        title="Afterglow nights",
        lyrics="We glow",
        learned_terms=["lowlight"],
    )
    assert inferred == [
        SunoSanitizeReplacement(field="text", source="lowlight", target="afterglow")
    ]


def test_runtime_config_warn_term_flags_without_default_replacement() -> None:
    runtime_config = SunoRuntimeBlocklist(
        replacements={"lowlight": "afterglow"},
        block_terms=frozenset(),
        warn_terms=frozenset({"vendor"}),
    )
    hits = find_suno_risk_terms_in_text("Signed by vendor only", runtime_config=runtime_config)
    assert any(hit.severity == "warn" and hit.term.lower() == "vendor" for hit in hits)


def test_runtime_config_block_term_sanitizes_with_replacement() -> None:
    runtime_config = SunoRuntimeBlocklist(
        replacements={"skyline": "horizon"},
        block_terms=frozenset({"skyline"}),
        warn_terms=frozenset(),
    )
    cleaned, replacements = sanitize_text_for_suno_with_changes(
        "Ride the skyline",
        runtime_config=runtime_config,
    )
    assert "horizon" in cleaned.lower()
    assert replacements[0].target == "horizon"
