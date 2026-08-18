"""Pre-submit Suno guards for web music: titles, blocklist reject, sanitize."""

from __future__ import annotations

import re
from typing import Any

from platform_api.exceptions import ValidationError
from platform_api.services.suno_lyrics_sanitize import (
    SunoRuntimeBlocklist,
    find_suno_risk_terms_in_text,
    sanitize_text_for_suno,
)

_BRACKET_RE = re.compile(r"[\[\]{}]")
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_SECTION_ONLY_RE = re.compile(
    r"^(intro|verse|chorus|bridge|outro|hook|pre-?chorus|instrumental|inst|"
    r"break|drop|refrain|solo|interlude)(\s*\d+)?$",
    re.IGNORECASE,
)
_WEB_MUSIC_TITLE_MAX = 120


def prepare_web_music_title(*, title: str, lyrics: str = "") -> str:
    """Build a submit-safe title; strip lyric section tags like ``[Intro music]``."""
    raw = str(title or "").strip()
    if not raw:
        for line in str(lyrics or "").splitlines():
            candidate = _title_from_lyrics_line(line)
            if candidate:
                raw = candidate
                break
    return _clean_title_text(raw)


def _title_from_lyrics_line(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    if text.startswith("[") and text.endswith("]") and len(text) >= 3:
        inner = _clean_title_text(text[1:-1])
        if not inner or _SECTION_ONLY_RE.match(inner):
            return ""
        return inner
    return _clean_title_text(text)


def _clean_title_text(value: str) -> str:
    text = _BRACKET_RE.sub(" ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_WEB_MUSIC_TITLE_MAX]


def is_valid_web_music_title(title: str) -> bool:
    """Allow Unicode letters (Khmer, etc.); reject empty, URLs, and control chars."""
    text = str(title or "").strip()
    if len(text) < 2 or len(text) > _WEB_MUSIC_TITLE_MAX:
        return False
    if _URL_RE.search(text):
        return False
    if _BRACKET_RE.search(text):
        return False
    if any(ord(char) < 32 for char in text):
        return False
    return any(char.isalpha() for char in text)


def collect_suno_block_hits(
    runtime_config: SunoRuntimeBlocklist | None,
    **fields: str,
) -> list[dict[str, Any]]:
    """Return block-severity hits across named text fields."""
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int]] = set()
    for field, value in fields.items():
        text = str(value or "")
        if not text.strip():
            continue
        for hit in find_suno_risk_terms_in_text(text, runtime_config=runtime_config):
            if hit.severity != "block":
                continue
            key = (field, hit.term.lower(), hit.start, hit.end)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "field": field,
                    "term": hit.term,
                    "suggestion": hit.suggestion,
                }
            )
    return hits


def raise_if_suno_blocklisted(
    runtime_config: SunoRuntimeBlocklist | None,
    *,
    title: str = "",
    lyrics: str = "",
    style: str = "",
    negative_tags: str = "",
) -> None:
    """Reject the request when admin Suno blocklist wording is still present."""
    hits = collect_suno_block_hits(
        runtime_config,
        title=title,
        lyrics=lyrics,
        style=style,
        negative_tags=negative_tags,
    )
    if not hits:
        return
    terms: list[str] = []
    for hit in hits:
        term = str(hit["term"]).strip()
        if term and term.lower() not in {item.lower() for item in terms}:
            terms.append(term)
    listed = ", ".join(terms[:8])
    raise ValidationError(
        f"Remove Suno-blocked wording before creating: {listed}.",
        details={
            "field": str(hits[0]["field"]),
            "blocked_terms": terms,
            "hits": hits[:20],
            "code": "suno_blocklist",
        },
    )


def sanitize_web_music_suno_fields(
    runtime_config: SunoRuntimeBlocklist | None,
    *,
    title: str,
    lyrics: str,
    style: str,
    negative_tags: str = "",
) -> tuple[str, str, str, str]:
    """Replace any remaining blocked tokens so they never reach Suno."""
    return (
        sanitize_text_for_suno(title, runtime_config=runtime_config),
        sanitize_text_for_suno(lyrics, runtime_config=runtime_config),
        sanitize_text_for_suno(style, runtime_config=runtime_config),
        sanitize_text_for_suno(negative_tags, runtime_config=runtime_config)
        if str(negative_tags or "").strip()
        else "",
    )
