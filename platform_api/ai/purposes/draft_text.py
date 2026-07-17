"""Song draft response parsing — tolerant of provider-specific JSON quirks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from platform_api.ai.parsing.response_parser import (
    clean_llm_text,
    normalize_slot_text,
    parse_json_object,
)

logger = logging.getLogger(__name__)

_TITLE_KEYS = ("title", "song_title", "songtitle", "name")
_ALBUM_KEYS = ("album", "album_name", "albumname")
_LYRICS_KEYS = ("lyrics", "lyric", "song_lyrics", "content", "text")


def _unescape_json_string(value: str) -> str:
    text = str(value or "")
    try:
        return json.loads(f'"{text}"')
    except json.JSONDecodeError:
        return (
            text.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )


def _pick_field(parsed: dict[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in parsed.items()}
    for name in names:
        if name in lowered and lowered[name] is not None:
            return lowered[name]
    return None


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_lyrics(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            header = str(key).strip()
            if header and not header.startswith("["):
                header = f"[{header}]"
            if header:
                lines.append(header)
            if isinstance(item, list):
                lines.extend(str(line) for line in item if str(line).strip())
            else:
                text = str(item).strip()
                if text:
                    lines.append(text)
        return "\n".join(lines)
    return str(value or "")


def _extract_quoted_field(text: str, field_name: str) -> str | None:
    pattern = rf'["\']?{re.escape(field_name)}["\']?\s*:\s*"((?:[^"\\]|\\.)*)"'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return _unescape_json_string(match.group(1)).strip()


def _extract_loose_lyrics_field(text: str) -> str | None:
    match = re.search(r'["\']?lyrics["\']?\s*:\s*', text, re.IGNORECASE)
    if not match:
        return None

    rest = text[match.end() :].lstrip()
    if rest.startswith('"""'):
        end = rest.find('"""', 3)
        if end >= 0:
            return rest[3:end].strip()
        return rest[3:].strip()

    if not rest.startswith('"'):
        return None

    body = rest[1:]
    closing = body.rfind('"')
    if closing < 0:
        trimmed = body.rstrip().rstrip("}").strip()
        return trimmed or None
    return _unescape_json_string(body[:closing]).strip() or None


def _parse_draft_json_loose(content: str) -> dict[str, Any] | None:
    """Parse draft JSON when lyrics contain raw newlines (invalid strict JSON)."""
    text = clean_llm_text(content)
    title_match = re.search(
        r'["\']?title["\']?\s*:\s*"(?P<title>(?:[^"\\]|\\.)*)"',
        text,
        re.IGNORECASE,
    )
    album_match = re.search(
        r'["\']?album["\']?\s*:\s*"(?P<album>(?:[^"\\]|\\.)*)"',
        text,
        re.IGNORECASE,
    )
    lyrics = _extract_loose_lyrics_field(text)
    if title_match and album_match and lyrics:
        return {
            "title": _unescape_json_string(title_match.group("title")),
            "album": _unescape_json_string(album_match.group("album")),
            "lyrics": lyrics,
        }
    return None


def parse_title_album_lyrics(content: str) -> dict[str, str] | None:
    """Parse a combined song draft from LLM text."""
    if not str(content or "").strip():
        return None

    parsed = parse_json_object(content) or _parse_draft_json_loose(content)
    if parsed is not None:
        title = normalize_slot_text(
            _coerce_text(_pick_field(parsed, _TITLE_KEYS)), "title"
        )
        album = normalize_slot_text(
            _coerce_text(_pick_field(parsed, _ALBUM_KEYS)), "album"
        )
        lyrics = _coerce_lyrics(_pick_field(parsed, _LYRICS_KEYS))
        if title and album and lyrics:
            return {"title": title, "album": album, "lyrics": lyrics}

    text = clean_llm_text(content)
    title = _extract_quoted_field(text, "title")
    album = _extract_quoted_field(text, "album")
    lyrics = _extract_quoted_field(text, "lyrics") or _extract_loose_lyrics_field(text)
    if title and album and lyrics:
        return {
            "title": normalize_slot_text(title, "title"),
            "album": normalize_slot_text(album, "album"),
            "lyrics": lyrics,
        }

    logger.debug("Draft parse could not recover title/album/lyrics from response.")
    return None
