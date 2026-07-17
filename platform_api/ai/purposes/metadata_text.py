"""Sanitization and validation for song title/album metadata."""

from __future__ import annotations

import re
import unicodedata

TITLE_MAX_CHARS = 120
ALBUM_MAX_CHARS = 80
TITLE_MAX_WORDS = 12
ALBUM_MAX_WORDS = 6

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_JSON_LEAK_RE = re.compile(r'^\s*["\']?\w+["\']?\s*:', re.IGNORECASE)
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_FORBIDDEN_CHARS_RE = re.compile(r'[{}\[\]\\|<>/`@#$%^*+=~"]')
_EXCESS_PUNCT_RE = re.compile(r"[!?]{2,}|\.{3,}")
_REPEAT_CHAR_RE = re.compile(r"(.)\1{5,}")


def _field_limits(field: str) -> tuple[int, int]:
    if field == "album":
        return ALBUM_MAX_CHARS, ALBUM_MAX_WORDS
    return TITLE_MAX_CHARS, TITLE_MAX_WORDS


def sanitize_metadata_name(
    value: str,
    *,
    field: str = "title",
    max_length: int | None = None,
) -> str:
    """Normalize LLM title/album output for storage and Suno."""
    max_chars, _ = _field_limits(field)
    limit = max_length if max_length is not None else max_chars

    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", "").replace("\u201d", "")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = _FORBIDDEN_CHARS_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(".,;:*")

    if len(text) > limit:
        text = text[:limit].rstrip(" '-.")
    return text


def is_valid_metadata_name(
    value: str,
    *,
    field: str = "title",
    max_length: int | None = None,
) -> bool:
    """Return True when metadata is safe to store and submit."""
    max_chars, max_words = _field_limits(field)
    limit = max_length if max_length is not None else max_chars

    raw = str(value or "").strip()
    if not raw:
        return False
    if any(char in raw for char in "{}[]"):
        return False
    if _JSON_LEAK_RE.search(raw) or _URL_RE.search(raw):
        return False
    if _EXCESS_PUNCT_RE.search(raw):
        return False

    cleaned = sanitize_metadata_name(raw, field=field, max_length=limit)
    if not cleaned or len(cleaned) < 2:
        return False
    if cleaned != sanitize_metadata_name(cleaned, field=field, max_length=limit):
        return False
    if _REPEAT_CHAR_RE.search(cleaned):
        return False

    words = cleaned.split()
    if not words or len(words) > max_words or len(cleaned) > limit:
        return False

    letters = sum(1 for char in cleaned if char.isalpha())
    if letters < max(2, len(cleaned) // 4):
        return False
    return True
