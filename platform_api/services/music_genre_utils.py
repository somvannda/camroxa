"""Validation and resolution helpers for music prompt / streaming genres."""

from __future__ import annotations

from typing import Any


MAX_DESCRIPTION_GENRES = 10
MAX_GENRE_LENGTH = 60


def parse_genre_list(value: Any) -> list[str]:
    """Coerce JSONB/list/string values into a list of genre strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            import json

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in text.split(",") if part.strip()]
    return []


def normalize_description_genres(raw: list[str] | None) -> list[str]:
    """Trim, dedupe case-insensitively, and enforce length/count limits."""
    if not raw:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        genre = str(item or "").strip()
        if not genre:
            continue
        if len(genre) > MAX_GENRE_LENGTH:
            raise ValueError(f"Each genre must be at most {MAX_GENRE_LENGTH} characters.")
        key = genre.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(genre)
        if len(normalized) > MAX_DESCRIPTION_GENRES:
            raise ValueError(f"At most {MAX_DESCRIPTION_GENRES} genres are allowed.")

    return normalized


def parse_suno_clip_tags(tags_text: str | None) -> list[str]:
    if not tags_text:
        return []
    return [part.strip() for part in str(tags_text).split(",") if part.strip()]


def resolve_stream_genres(
    *,
    description_genres: Any = None,
    suno_tags_text: str | None = None,
) -> tuple[str | None, list[str]]:
    """Resolve primary genre and full genre list for streaming catalog rows.

    Priority:
    1. music_descriptions.genres
    2. Suno clip tags (comma-split)
    3. None — never use suno_tasks.style / production prompt text
    """
    catalog_genres = parse_genre_list(description_genres)
    if catalog_genres:
        return catalog_genres[0], catalog_genres

    clip_tags = parse_suno_clip_tags(suno_tags_text)
    if clip_tags:
        return clip_tags[0], clip_tags

    return None, []
