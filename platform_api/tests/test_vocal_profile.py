"""Tests for structured vocal profiles and bilingual prompt helpers."""

from __future__ import annotations

import pytest

from platform_api.ai.purposes.vocal_profile import (
    build_suno_style_prompt,
    build_section_language_map_from_roles,
    lyric_vocal_profile_for_batch,
    parse_vocal_profile,
    resolve_batch_languages,
    resolve_header_language,
    resolve_workspace_batch_languages,
    sanitize_production_description,
    validate_vocal_profile_payload,
)
from platform_api.services.generation_service import (
    build_lyric_draft_system_prompt,
    build_lyric_shape_user_prompt,
)


EURODANCE_DESCRIPTION = (
    "Eurodance and Hands Up track featuring a blend of English vocals, "
    "The song is set in a minor key at a fast tempo of 142 BPM, "
    "It opens with a heavy, four-on-the-floor kick drum and a syncopated, buzzy synth bassline, "
    "The lead melody is a bright, saw-tooth synth hook with a distinct trance-gate effect, "
    "Male and Female vocal are processed with pitch correction and light reverb, "
    "delivering melodic verses in German, "
    "The chorus features a repetitive, catchy English hook with a slight vocal chop effect, "
    "The production is polished with side-chain compression on the synths to create a pumping feel."
)

BILINGUAL_PROFILE = {
    "mode": "bilingual",
    "primary_language": "en",
    "secondary_language": "de",
    "verse_role": "secondary",
    "chorus_role": "primary",
    "section_language_map": {
        "intro": "secondary",
        "verse": "secondary",
        "chorus": "primary",
        "drop": "primary",
        "bridge": "secondary",
    },
}


def test_sanitize_production_description_removes_language_clauses() -> None:
    cleaned = sanitize_production_description(EURODANCE_DESCRIPTION)
    assert "German" not in cleaned
    assert "English vocals" not in cleaned
    assert "142 BPM" in cleaned
    assert "four-on-the-floor kick" in cleaned


def test_build_section_language_map_from_roles() -> None:
    section_map = build_section_language_map_from_roles(
        verse_role="secondary",
        chorus_role="primary",
    )
    assert section_map["verse"] == "secondary"
    assert section_map["chorus"] == "primary"
    assert section_map["drop"] == "primary"
    assert section_map["bridge"] == "secondary"


def test_parse_and_validate_bilingual_profile() -> None:
    profile = parse_vocal_profile(BILINGUAL_PROFILE)
    assert profile is not None
    assert profile.is_bilingual
    validated = validate_vocal_profile_payload(BILINGUAL_PROFILE)
    assert validated is not None
    assert validated["secondary_language"] == "de"


def test_resolve_workspace_batch_languages_uses_secondary_when_different() -> None:
    assert resolve_workspace_batch_languages(language="en", secondary_language="de") == (
        "en",
        "de",
    )
    assert resolve_workspace_batch_languages(language="de", secondary_language=None) == (
        "de",
        None,
    )
    assert resolve_workspace_batch_languages(language="en", secondary_language="en") == (
        "en",
        None,
    )


def test_lyric_vocal_profile_for_batch_monolingual_when_no_secondary() -> None:
    profile = parse_vocal_profile(BILINGUAL_PROFILE)
    assert (
        lyric_vocal_profile_for_batch(
            description_profile=profile,
            primary="en",
            secondary=None,
        )
        is None
    )


def test_lyric_vocal_profile_for_batch_defaults_verse_secondary() -> None:
    profile = lyric_vocal_profile_for_batch(
        description_profile=None,
        primary="en",
        secondary="de",
    )
    assert profile is not None
    assert profile.is_bilingual
    assert profile.verse_role == "secondary"
    assert profile.chorus_role == "primary"


def test_lyric_vocal_profile_for_batch_keeps_description_section_map() -> None:
    desc_profile = parse_vocal_profile(BILINGUAL_PROFILE)
    profile = lyric_vocal_profile_for_batch(
        description_profile=desc_profile,
        primary="en",
        secondary="de",
    )
    assert profile is not None
    assert profile.section_language_map["verse"] == "secondary"
    assert profile.section_language_map["chorus"] == "primary"


def test_resolve_batch_languages_requires_secondary_for_bilingual() -> None:
    profile = parse_vocal_profile(BILINGUAL_PROFILE)
    primary, secondary = resolve_batch_languages(
        batch_language="en",
        secondary_language="de",
        profile=profile,
    )
    assert primary == "en"
    assert secondary == "de"


def test_resolve_batch_languages_rejects_same_language() -> None:
    profile = parse_vocal_profile(BILINGUAL_PROFILE)
    with pytest.raises(ValueError):
        resolve_batch_languages(
            batch_language="de",
            secondary_language="de",
            profile=profile,
        )


def test_resolve_header_language_uses_section_map() -> None:
    profile = parse_vocal_profile(BILINGUAL_PROFILE)
    assert (
        resolve_header_language(
            "[Verse]",
            profile=profile,
            primary="en",
            secondary="de",
        )
        == "de"
    )
    assert (
        resolve_header_language(
            "[Chorus]",
            profile=profile,
            primary="en",
            secondary="de",
        )
        == "en"
    )


def test_build_suno_style_prompt_includes_explicit_vocal_policy() -> None:
    profile = parse_vocal_profile(BILINGUAL_PROFILE)
    style = build_suno_style_prompt(
        production_description=EURODANCE_DESCRIPTION,
        profile=profile,
        primary="en",
        secondary="de",
        structure_headers=["[Verse]", "[Chorus]"],
    )
    assert "German" in style
    assert "English" in style
    assert "142 BPM" in style
    assert len(style) <= 255


def test_truncate_suno_style_limits_length() -> None:
    from platform_api.ai.purposes.vocal_profile import truncate_suno_style

    long_style = "A" * 400
    assert len(truncate_suno_style(long_style)) == 255


def test_bilingual_lyric_prompts_include_section_plan() -> None:
    headers = ["[Verse]", "[Chorus]"]
    system = build_lyric_draft_system_prompt(
        language="en",
        min_lines=8,
        profile=BILINGUAL_PROFILE,
        secondary_language="de",
        structure_headers=headers,
    )
    assert "Bilingual song" in system
    assert "[Verse]" in system
    assert "German" in system

    user_prompt = build_lyric_shape_user_prompt(
        draft_lyrics="Line one\nLine two",
        structure_guide="Dark atmospheric arc",
        structure_headers=headers,
        profile=BILINGUAL_PROFILE,
        primary_language="en",
        secondary_language="de",
    )
    assert "Section language plan" in user_prompt
    assert "[Chorus] → English" in user_prompt
