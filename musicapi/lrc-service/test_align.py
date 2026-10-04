#!/usr/bin/env python3
"""Pure-logic tests for the LRC microservice (no model required).

Run:  python test_align.py   (or: pytest test_align.py)
"""
from __future__ import annotations

from server import (
    build_lrc,
    format_lrc_time,
    interpolate_nones,
    normalize_token,
    snap_to_lyrics,
    split_lyric_lines,
    tokenize,
)


def test_tokenize_drops_punctuation_keeps_apostrophes() -> None:
    assert tokenize("Hello, world! Don't stop.") == ["Hello", "world", "Don't", "stop"]


def test_normalize_and_split_lines() -> None:
    assert normalize_token("Hello") == "hello"
    assert split_lyric_lines("[Verse]\n\nHello world\n  \nSecond line") == [
        "[Verse]",
        "Hello world",
        "Second line",
    ]


def test_interpolate_nones() -> None:
    result = interpolate_nones([None, 2.0, None, None, 6.0, None])
    expected = [2.0, 2.0, 10 / 3, 14 / 3, 6.0, 6.0]
    assert all(abs(a - b) < 1e-9 for a, b in zip(result, expected)), result
    assert interpolate_nones([]) == []


def test_format_lrc_time() -> None:
    assert format_lrc_time(0) == "[00:00.00]"
    assert format_lrc_time(65.2) == "[01:05.20]"


def test_snap_matches_lyric_lines() -> None:
    lyrics = "[Verse]\nHello world tonight\nWe sing along"
    recognized = [
        {"word": "hello", "start": 1.0, "end": 1.3},
        {"word": "world", "start": 1.4, "end": 1.7},
        {"word": "tonight", "start": 1.8, "end": 2.2},
        {"word": "we", "start": 3.0, "end": 3.2},
        {"word": "sing", "start": 3.3, "end": 3.5},
        {"word": "along", "start": 3.6, "end": 4.0},
    ]
    lines, words = snap_to_lyrics(recognized, lyrics)
    texts = [line["text"] for line in lines]
    assert texts == ["[Verse]", "Hello world tonight", "We sing along"]
    # Section marker has no ASR match; it borrows the next known start (1.0).
    assert lines[0]["startS"] == 1.0
    assert lines[1]["startS"] == 1.0
    assert lines[2]["startS"] == 3.0
    # Word-level output is monotonic non-decreasing.
    starts = [w["startS"] for w in words]
    assert starts == sorted(starts)
    lrc = build_lrc(lines)
    assert lrc.startswith("[00:01.00][Verse]")
    assert "We sing along" in lrc


def test_snap_without_matches_is_empty() -> None:
    lines, words = snap_to_lyrics([{"word": "zzz", "start": 1.0, "end": 2.0}], "Hello world\nSecond line")
    assert lines == []
    assert words == []


def test_snap_without_lyrics_is_empty() -> None:
    assert snap_to_lyrics([{"word": "hi", "start": 1.0, "end": 2.0}], "") == ([], [])


def test_build_lrc_needs_two_lines() -> None:
    assert build_lrc([{"text": "Only one", "startS": 1.0}]) == ""
    assert build_lrc([]) == ""


def test_snap_fills_missed_word_within_line() -> None:
    # ASR heard "hello" and "tonight" but missed "world"; the line still gets a
    # bounded, monotonic word/line timing.
    lyrics = "Hello world tonight\nWe sing along"
    recognized = [
        {"word": "hello", "start": 1.0, "end": 1.2},
        {"word": "tonight", "start": 2.0, "end": 2.4},
        {"word": "we", "start": 3.0, "end": 3.2},
        {"word": "sing", "start": 3.3, "end": 3.5},
        {"word": "along", "start": 3.6, "end": 4.0},
    ]
    lines, words = snap_to_lyrics(recognized, lyrics)
    assert lines[0]["text"] == "Hello world tonight"
    assert lines[0]["startS"] == 1.0
    middle = [w for w in words if normalize_token(w["word"]) == "world"]
    assert middle and middle[0]["startS"] >= 1.0


if __name__ == "__main__":
    import sys

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {exc}")
    if failures:
        sys.exit(1)
    print("align: all checks passed")
