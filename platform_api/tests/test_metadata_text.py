"""Tests for song title/album metadata sanitization."""

from __future__ import annotations

from platform_api.ai.parsing.response_parser import parse_string_field
from platform_api.ai.purposes.metadata_text import (
    is_valid_metadata_name,
    sanitize_metadata_name,
)
from platform_api.ai.purposes.vocal_profile import resolve_suno_style_from_description

_CORRUPT_TITLE = (
    "Slow Cruisin' Under Street-Lamps samples (streetconnections obligations:bold "
    "MUTus必 провер depletionbrick渐FIвести menj"
)


def test_sanitize_metadata_name_strips_json_artifacts() -> None:
    raw = '{"title": "The Dirt Road\'s Pulse"}'
    assert (
        sanitize_metadata_name(parse_string_field(raw, "title"), field="title")
        == "The Dirt Road's Pulse"
    )


def test_sanitize_metadata_name_strips_script_noise() -> None:
    cleaned = sanitize_metadata_name(_CORRUPT_TITLE, field="title")
    assert "必" not in cleaned
    assert "провер" not in cleaned
    assert "渐" not in cleaned


def test_is_valid_metadata_name_rejects_urls_and_garbage() -> None:
    assert is_valid_metadata_name("Night Drive", field="title")
    assert is_valid_metadata_name("Neon Vault: Hinterland Fades", field="title")
    assert is_valid_metadata_name("Café Nights", field="title")
    assert is_valid_metadata_name("Neon Coastal Midnight", field="album")
    assert not is_valid_metadata_name("http://bad.example/title", field="title")
    assert not is_valid_metadata_name('{"title":"Broken"}', field="title")
    assert not is_valid_metadata_name("!!!@@@###", field="title")


def test_is_valid_metadata_name_rejects_mixed_script_word_salad() -> None:
    assert not is_valid_metadata_name(_CORRUPT_TITLE, field="title")
    assert not is_valid_metadata_name(
        "samples (streetconnections obligations:bold MUTus)",
        field="title",
    )
    assert not is_valid_metadata_name("depletionbrickFIvesti menj", field="title")
    assert not is_valid_metadata_name("mode_fast Neon Run", field="album")


def test_resolve_suno_style_from_description_uses_exact_prompt() -> None:
    prompt = (
        "Eurodance track at 142 BPM with heavy saw bass and English/German vocals "
        "in alternating sections."
    )
    style = resolve_suno_style_from_description(prompt)
    assert style == prompt
    assert len(style) <= 1000


def test_resolve_suno_style_from_description_truncates_long_prompt() -> None:
    from platform_api.ai.purposes.vocal_profile import SUNO_STYLE_MAX_LENGTH

    prompt = "A" * (SUNO_STYLE_MAX_LENGTH + 100)
    style = resolve_suno_style_from_description(prompt)
    assert len(style) == SUNO_STYLE_MAX_LENGTH
