"""Purpose-specific helpers built on shared parsing."""

from __future__ import annotations

import re

from platform_api.ai.parsing.response_parser import (
    clean_llm_text,
    parse_json_array,
    parse_json_object,
    parse_string_field,
    parse_string_list,
)
from platform_api.ai.purposes.draft_text import parse_title_album_lyrics
__all__ = [
    "parse_channel_description",
    "parse_description_text",
    "parse_keywords",
    "parse_string_list",
    "parse_tags",
    "parse_title_album_lyrics",
]


_ACRONYMS = frozenset({"edm", "hiit", "dj", "uk", "us", "bpm", "4k"})
_SHORT_WORDS = _ACRONYMS | frozenset({"gym", "mix", "pop", "rap", "hop"})


def _split_loose_list(content: str, *, limit: int) -> list[str]:
    raw = clean_llm_text(content).strip().strip("{}").strip()
    parts = [
        part.strip().strip('"').strip("'")
        for part in re.split(r"[,;\n]", raw)
        if part.strip()
    ]
    return parts[:limit]


def _flatten_raw_terms(raw: list[str]) -> list[str]:
    """Expand comma-joined blobs the model sometimes returns as one array item."""
    terms: list[str] = []
    for item in raw:
        text = str(item).strip()
        if not text:
            continue
        if "," in text:
            terms.extend(part.strip() for part in text.split(",") if part.strip())
        else:
            terms.append(text)
    return terms


def _clean_single_term(term: str, *, max_words: int, max_len: int) -> str | None:
    term = re.sub(r"\s+", " ", term.strip().strip("\"'"))
    if not term:
        return None

    words = [word for word in term.split() if not (len(word) == 1 and word.isalpha())]
    if not words:
        return None

    kept: list[str] = []
    for word in words[:max_words]:
        lowered = word.lower()
        if len(word) < 3:
            continue
        if len(word) == 3 and lowered not in _SHORT_WORDS:
            continue
        kept.append(word)
    if not kept:
        return None

    cleaned = " ".join(kept[:max_words])
    if len(cleaned) < 3 and cleaned.lower() not in _ACRONYMS:
        return None
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rsplit(" ", 1)[0].strip()
        if len(cleaned) < 3:
            return None
    return cleaned


def normalize_youtube_keywords(items: list[str]) -> list[str]:
    """Normalize LLM keywords for YouTube Studio comma-separated keyword field."""
    seen: set[str] = set()
    normalized: list[str] = []
    for term in _flatten_raw_terms(items):
        cleaned = _clean_single_term(term, max_words=3, max_len=35)
        if cleaned is None:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
        if len(normalized) >= 30:
            break
    return normalized


def normalize_youtube_tags(items: list[str]) -> list[str]:
    """Normalize LLM tags for YouTube Studio tag field (500-char combined limit)."""
    seen: set[str] = set()
    normalized: list[str] = []
    total_chars = 0
    for term in _flatten_raw_terms(items):
        cleaned = _clean_single_term(term, max_words=3, max_len=30)
        if cleaned is None:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        extra = len(cleaned) + (2 if normalized else 0)
        if total_chars + extra > 500:
            break
        seen.add(key)
        normalized.append(cleaned)
        total_chars += extra
        if len(normalized) >= 40:
            break
    return normalized


def format_youtube_comma_field(items: list[str], *, max_chars: int | None = None) -> str:
    """Join terms for paste into YouTube Studio comma-separated fields."""
    text = ", ".join(item.strip() for item in items if item.strip())
    if max_chars is None or len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    last_comma = trimmed.rfind(", ")
    if last_comma > 0:
        return trimmed[:last_comma]
    return trimmed


def parse_channel_description(content: str) -> dict[str, object]:
    parsed = parse_json_object(content)
    if parsed is None:
        raise ValueError("Cannot parse LLM response as JSON object.")
    return {
        "description": str(parsed.get("description", "")),
        "keywords": normalize_youtube_keywords(
            [str(k) for k in parsed.get("keywords", []) if str(k).strip()]
        ),
        "tags": normalize_youtube_tags(
            [str(t) for t in parsed.get("tags", []) if str(t).strip()]
        ),
    }


def parse_description_text(content: str) -> str:
    """Parse a description-only JSON object or plain text."""
    parsed = parse_json_object(content)
    if parsed is not None and parsed.get("description") is not None:
        return str(parsed.get("description", "")).strip()
    return clean_llm_text(content)


def parse_keywords(content: str) -> list[str]:
    parsed = parse_json_object(content)
    if parsed is not None:
        keywords_raw = parsed.get("keywords", [])
        if isinstance(keywords_raw, list):
            keywords = [str(k).strip() for k in keywords_raw if str(k).strip()]
            if keywords:
                return normalize_youtube_keywords(keywords)
    parsed_array = parse_json_array(content)
    if parsed_array is not None:
        keywords = [str(k).strip() for k in parsed_array if str(k).strip()]
        if keywords:
            return normalize_youtube_keywords(keywords)
    loose = _split_loose_list(content, limit=50)
    if loose:
        return normalize_youtube_keywords(loose)
    return normalize_youtube_keywords(parse_string_list(content))


def parse_tags(content: str) -> list[str]:
    parsed = parse_json_object(content)
    if parsed is not None:
        tags_raw = parsed.get("tags", [])
        if isinstance(tags_raw, list):
            tags = [str(t).strip() for t in tags_raw if str(t).strip()]
            if tags:
                return normalize_youtube_tags(tags)
    parsed_array = parse_json_array(content)
    if parsed_array is not None:
        tags = [str(t).strip() for t in parsed_array if str(t).strip()]
        if tags:
            return normalize_youtube_tags(tags)
    loose = _split_loose_list(content, limit=60)
    if loose:
        return normalize_youtube_tags(loose)
    return normalize_youtube_tags(parse_string_list(content))


def parse_single_text_field(content: str, *field_names: str) -> str:
    return parse_string_field(content, *field_names)
