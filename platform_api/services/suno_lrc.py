"""Convert Suno aligned-word timestamps into LRC lyric text."""

from __future__ import annotations

import re
from typing import Any

_LRC_HIT = re.compile(r"^\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]", re.MULTILINE)


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


def parse_aligned_words_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract alignedWords list from get-timestamped-lyrics response body."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return []
    for key in ("alignedWords", "aligned_words"):
        words = data.get(key)
        if isinstance(words, list):
            return [item for item in words if isinstance(item, dict)]
    return []
