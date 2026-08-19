"""Tests for Suno aligned-words → LRC conversion."""

from __future__ import annotations

from platform_api.services.suno_lrc import (
    aligned_words_to_lrc,
    format_lrc_time,
    looks_like_lrc,
    lrc_to_srt,
    parse_aligned_words_payload,
)


def test_format_lrc_time() -> None:
    assert format_lrc_time(1.36) == "[00:01.36]"
    assert format_lrc_time(65.5) == "[01:05.50]"


def test_looks_like_lrc() -> None:
    assert looks_like_lrc("[00:01.00]One\n[00:04.00]Two")
    assert not looks_like_lrc("[Verse]\nHello world")
    assert not looks_like_lrc("[00:01.00]only one stamp")


def test_lrc_to_srt() -> None:
    lrc = "[00:01.00]Hello world\n[00:04.50]Second line"
    srt = lrc_to_srt(lrc)
    assert "1\n" in srt
    assert "00:00:01,000 --> 00:00:04,450" in srt
    assert "Hello world" in srt
    assert "Second line" in srt


def test_aligned_words_to_lrc_groups_lines_on_newlines() -> None:
    words = [
        {"word": "[Verse]\nSnowflakes ", "startS": 2.63, "success": True},
        {"word": "dance ", "startS": 3.43, "success": True},
        {"word": "on ", "startS": 3.91, "success": True},
        {"word": "rooftops ", "startS": 4.35, "success": True},
        {"word": "high\n", "startS": 5.11, "success": True},
        {"word": "Under ", "startS": 6.40, "success": True},
        {"word": "neon light", "startS": 6.90, "success": True},
    ]
    lrc = aligned_words_to_lrc(words)
    assert looks_like_lrc(lrc)
    assert "[00:02.63][Verse]" in lrc
    assert "Snowflakes dance on rooftops high" in lrc
    assert "[00:06.40]Under neon light" in lrc


def test_parse_aligned_words_payload() -> None:
    payload = {
        "code": 200,
        "data": {
            "alignedWords": [
                {"word": "Hello", "startS": 1.0, "endS": 1.2},
                {"word": "world", "startS": 1.3, "endS": 1.5},
            ]
        },
    }
    words = parse_aligned_words_payload(payload)
    assert len(words) == 2
    assert words[0]["word"] == "Hello"
