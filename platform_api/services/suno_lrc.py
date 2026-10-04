"""Convert Suno aligned-word timestamps into LRC lyric text."""

from __future__ import annotations

import re
from typing import Any

_LRC_HIT = re.compile(r"^\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]", re.MULTILINE)
_LRC_LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$")


def parse_lrc_timestamp(minutes: str, seconds: str, millis: str | None) -> float:
    total = int(minutes) * 60 + int(seconds)
    if millis:
        if len(millis) == 1:
            total += int(millis) / 10.0
        elif len(millis) == 2:
            total += int(millis) / 100.0
        else:
            total += int(millis[:3]) / 1000.0
    return max(0.0, float(total))


def parse_lrc_lines(lrc: str) -> list[tuple[float, str]]:
    parsed: list[tuple[float, str]] = []
    for raw_line in str(lrc or "").splitlines():
        match = _LRC_LINE.match(raw_line.strip())
        if not match:
            continue
        minutes, seconds, millis, text = match.groups()
        cleaned = str(text or "").strip()
        if not cleaned:
            continue
        parsed.append((parse_lrc_timestamp(minutes, seconds, millis), cleaned))
    return parsed


def format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, millis = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def lrc_to_srt(lrc: str) -> str:
    """Convert line-level LRC into basic SRT cues for video editors."""
    entries = parse_lrc_lines(lrc)
    if not entries:
        return ""
    blocks: list[str] = []
    for index, (start, text) in enumerate(entries, start=1):
        if index < len(entries):
            end = max(start + 0.5, entries[index][0] - 0.05)
        else:
            end = start + 5.0
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_time(start)} --> {format_srt_time(end)}",
                    text,
                    "",
                ]
            )
        )
    return "\n".join(blocks)


def looks_like_lrc(text: str | None) -> bool:
    """True when text has at least two LRC timestamp tags."""
    if not text or not str(text).strip():
        return False
    return len(_LRC_HIT.findall(str(text))) >= 2


def format_lrc_time(seconds: float) -> str:
    total = max(0.0, float(seconds))
    minutes = int(total // 60)
    secs = total - minutes * 60
    return f"[{minutes:02d}:{secs:05.2f}]"


def _word_start(item: dict[str, Any]) -> float:
    for key in ("startS", "start_s", "start"):
        raw = item.get(key)
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def _word_text(item: dict[str, Any]) -> str:
    return str(item.get("word") or item.get("text") or "")


def aligned_words_to_lrc(aligned_words: list[dict[str, Any]] | None) -> str:
    """Group Suno word alignments into line-level LRC.

    Suno often embeds newlines in ``word`` to mark line / section breaks
    (e.g. ``"[Verse]\\nSnowflakes "``). We flush a line whenever a newline
    appears and stamp it with the first word's start time.
    """
    if not aligned_words:
        return ""

    lines: list[tuple[float, str]] = []
    buf: list[str] = []
    line_start: float | None = None

    def flush() -> None:
        nonlocal buf, line_start
        text = "".join(buf)
        # Normalize spaces but keep section markers intact.
        text = re.sub(r"[ \t]+", " ", text).strip()
        if text and line_start is not None:
            lines.append((line_start, text))
        buf = []
        line_start = None

    for item in aligned_words:
        if not isinstance(item, dict):
            continue
        word = _word_text(item)
        if not word:
            continue
        start = _word_start(item)
        parts = word.split("\n")
        for index, part in enumerate(parts):
            if index > 0:
                flush()
            if not part:
                continue
            if line_start is None:
                line_start = start
            buf.append(part)
    flush()

    if len(lines) < 2:
        return ""
    return "\n".join(f"{format_lrc_time(start)}{text}" for start, text in lines)


def _find_aligned_words(value: Any, depth: int = 0) -> list[dict[str, Any]] | None:
    """Recursively locate an ``alignedWords``/``aligned_words`` list.

    sunoapi.org returns it at the top of ``data``; Camxora's `musicapi` nests
    its job result (e.g. ``data.result`` / ``data.response.sunoData[0]``), so a
    fixed key lookup is not enough.
    """
    if depth > 6:
        return None
    if isinstance(value, dict):
        for key in ("alignedWords", "aligned_words"):
            words = value.get(key)
            if isinstance(words, list):
                return [item for item in words if isinstance(item, dict)]
        for child in value.values():
            found = _find_aligned_words(child, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_aligned_words(child, depth + 1)
            if found is not None:
                return found
    return None


def parse_aligned_words_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract alignedWords list from get-timestamped-lyrics response body."""
    if not isinstance(payload, dict):
        return []
    found = _find_aligned_words(payload)
    return found if found is not None else []
