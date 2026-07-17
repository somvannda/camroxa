"""Tests for tolerant song draft parsing."""

from __future__ import annotations

from platform_api.ai.parsing.response_parser import normalize_slot_text, parse_string_field
from platform_api.ai.purposes.draft_text import parse_title_album_lyrics


def test_parse_title_album_lyrics_standard_json() -> None:
    parsed = parse_title_album_lyrics(
        '{"title":"Song","album":"Album","lyrics":"[Verse]\\nHello"}'
    )
    assert parsed == {
        "title": "Song",
        "album": "Album",
        "lyrics": "[Verse]\nHello",
    }


def test_parse_title_album_lyrics_markdown_fence() -> None:
    content = '```json\n{"title":"T","album":"A","lyrics":"[Verse]\\nline"}\n```'
    parsed = parse_title_album_lyrics(content)
    assert parsed is not None
    assert parsed["title"] == "T"


def test_parse_title_album_lyrics_case_insensitive_keys() -> None:
    parsed = parse_title_album_lyrics(
        '{"Title":"Song","Album":"Album","Lyrics":"[Verse]\\nHi"}'
    )
    assert parsed is not None
    assert parsed["title"] == "Song"


def test_parse_title_album_lyrics_raw_newlines_in_lyrics() -> None:
    content = """{
  "title": "Analog Outsider",
  "album": "Night Circuits",
  "lyrics": "[Verse]
first line
[Chorus]
hook line"
}"""
    parsed = parse_title_album_lyrics(content)
    assert parsed is not None
    assert parsed["title"] == "Analog Outsider"
    assert "[Verse]" in parsed["lyrics"]
    assert "hook line" in parsed["lyrics"]


def test_parse_string_field_strips_wrapping_quotes() -> None:
    raw = '"We Rest Up For the Underworld\'s Final Dawn"'
    assert parse_string_field(raw, "title") == "We Rest Up For the Underworld's Final Dawn"


def test_parse_string_field_strips_json_key_leak() -> None:
    raw = '\n"title": "Departing Tides on the Final Dawn Rain"'
    assert (
        parse_string_field(raw, "title")
        == "Departing Tides on the Final Dawn Rain"
    )


def test_normalize_slot_text_json_object() -> None:
    raw = '{"title": "\\"Quoted Title\\""}'
    assert normalize_slot_text(raw, "title") == "Quoted Title"
