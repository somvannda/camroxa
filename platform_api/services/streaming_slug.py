"""Slug helpers for streaming storage keys."""

from __future__ import annotations

import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, fallback: str = "item", max_length: int = 120) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip())
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = _SLUG_RE.sub("-", text).strip("-")
    if not text:
        text = fallback
    return text[:max_length].strip("-") or fallback
