"""Sanitization and validation for song title/album metadata."""

from __future__ import annotations

import re
import unicodedata

TITLE_MAX_CHARS = 120
ALBUM_MAX_CHARS = 80
TITLE_MAX_WORDS = 12
ALBUM_MAX_WORDS = 6

# Glued LLM tokens like "streetconnections" / "depletionbrick".
_MAX_UNHYPHENATED_TOKEN_LEN = 16

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_JSON_LEAK_RE = re.compile(r'^\s*["\']?\w+["\']?\s*:', re.IGNORECASE)
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_FORBIDDEN_CHARS_RE = re.compile(r'[{}\[\]\\|<>/`@#$%^*+=~"]')
_EXCESS_PUNCT_RE = re.compile(r"[!?]{2,}|\.{3,}")
_REPEAT_CHAR_RE = re.compile(r"(.)\1{5,}")
# Colon/underscore glued keywords: "obligations:bold", "mode_fast"
_GLUED_SEPARATOR_RE = re.compile(r"[A-Za-z0-9]:[A-Za-z0-9]|[A-Za-z0-9]_[A-Za-z0-9]")
# camelCase / CapMixed glue inside a token
_CAMEL_GLUE_RE = re.compile(r"[a-z]{2,}[A-Z][a-z]|[A-Z]{2,}[a-z]{2,}[A-Z]")
# Non-Latin letter scripts that show up in title/album word-salad
_SCRIPT_NOISE_RE = re.compile(
    "["
    "\u0370-\u03FF"  # Greek
    "\u0400-\u04FF"  # Cyrillic
    "\u0500-\u052F"  # Cyrillic supplement
    "\u0600-\u06FF"  # Arabic
    "\u0900-\u097F"  # Devanagari
    "\u3040-\u30FF"  # Hiragana / Katakana
    "\u3400-\u9FFF"  # CJK
    "\uAC00-\uD7AF"  # Hangul
    "\uF900-\uFAFF"  # CJK compatibility
    "]"
)


def _field_limits(field: str) -> tuple[int, int]:
    if field == "album":
        return ALBUM_MAX_CHARS, ALBUM_MAX_WORDS
    return TITLE_MAX_CHARS, TITLE_MAX_WORDS


def _is_latin_letter(char: str) -> bool:
    if not char.isalpha():
        return False
    name = unicodedata.name(char, "")
    return name.startswith("LATIN ")


def _is_allowed_metadata_char(char: str) -> bool:
    """ASCII word chars + common title punctuation, or Latin letters (é, ñ, ü)."""
    if char in " '-&().,!?:":
        return True
    if char.isascii() and char.isalnum():
        return True
    return _is_latin_letter(char)


def _token_core(token: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", token)


def _has_glued_garbage_token(text: str) -> bool:
    if _GLUED_SEPARATOR_RE.search(text) or _CAMEL_GLUE_RE.search(text):
        return True
    for raw in text.split():
        core = _token_core(raw)
        if not core:
            continue
        # Hyphenated titles are fine ("Street-Lamps"); check each segment.
        for part in core.split("-"):
            if len(part) > _MAX_UNHYPHENATED_TOKEN_LEN:
                return True
            letters = sum(1 for ch in part if ch.isalpha())
            digits = sum(1 for ch in part if ch.isdigit())
            # Digit-letter soup like "FI123vesti" / "boldMUTus2"
            if digits and letters and not part.isdigit():
                if letters >= 4 and digits >= 1 and not re.fullmatch(r"\d+[A-Za-z]+|[A-Za-z]+\d+", part):
                    return True
                if re.search(r"[A-Za-z]\d+[A-Za-z]|\d+[A-Za-z]+\d+", part):
                    return True
    return False


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
    # Drop non-Latin script noise; validation still rejects leftover word-salad.
    text = _SCRIPT_NOISE_RE.sub("", text)
    text = "".join(ch for ch in text if _is_allowed_metadata_char(ch) or ch.isspace())
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
    if _SCRIPT_NOISE_RE.search(raw):
        return False
    if any(not (_is_allowed_metadata_char(ch) or ch.isspace()) for ch in raw):
        return False

    cleaned = sanitize_metadata_name(raw, field=field, max_length=limit)
    if not cleaned or len(cleaned) < 2:
        return False
    if cleaned != sanitize_metadata_name(cleaned, field=field, max_length=limit):
        return False
    if _REPEAT_CHAR_RE.search(cleaned):
        return False
    if _has_glued_garbage_token(cleaned):
        return False

    words = cleaned.split()
    if not words or len(words) > max_words or len(cleaned) > limit:
        return False

    letters = sum(1 for char in cleaned if char.isalpha())
    if letters < max(2, len(cleaned) // 4):
        return False
    # Require mostly real Latin letters (rejects punctuation-heavy leftovers).
    latin_letters = sum(1 for char in cleaned if _is_latin_letter(char))
    if latin_letters < max(2, letters * 3 // 4):
        return False
    return True
