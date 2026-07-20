"""User-facing copy helpers for desktop software updates."""

from __future__ import annotations

import re

_HEADER_RE = re.compile(r"^#{1,6}\s+")
_BULLET_RE = re.compile(r"^[-*•]\s+")
_VERSION_BANNER_RE = re.compile(r"^\[?\d+\.\d+(?:\.\d+)?\]?\s*[-–—].*$")
_CODEY_RE = re.compile(
    r"(clearContents|removeCellWidget|app[_-]version\.txt|Meipass|_internal|pyinstaller)",
    re.IGNORECASE,
)
_PAREN_CODEY_RE = re.compile(r"\([^)]*(?:clearContents|removeCellWidget|app[_-]version\.txt)[^)]*\)", re.IGNORECASE)


def format_update_summary(*, required_version: str, current_version: str) -> str:
    required = str(required_version or "").strip() or "the latest version"
    current = str(current_version or "").strip() or "an older build"
    return (
        f"Camxora {required} is required to continue.\n"
        f"You’re on {current}. The update installs in the background, then Camxora restarts."
    )


def format_whats_new(release_notes: str, *, max_bullets: int = 3, max_chars: int = 110) -> list[str]:
    """Turn admin release notes into short, user-facing bullets."""
    text = str(release_notes or "").replace("\r\n", "\n").strip()
    if not text:
        return []

    bullets: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if _VERSION_BANNER_RE.match(line):
            continue
        if _HEADER_RE.match(line):
            continue
        line = _BULLET_RE.sub("", line).strip()
        line = _HEADER_RE.sub("", line).strip()
        line = _PAREN_CODEY_RE.sub("", line).strip(" -–—")
        if not line or _CODEY_RE.search(line):
            continue
        if len(line) > max_chars:
            line = line[: max_chars - 1].rstrip() + "…"
        if line not in bullets:
            bullets.append(line)
        if len(bullets) >= max_bullets:
            break

    if bullets:
        return bullets

    # Fallback: first non-empty paragraph, shortened.
    paragraph = " ".join(text.split())
    if _CODEY_RE.search(paragraph):
        return []
    if len(paragraph) > max_chars:
        paragraph = paragraph[: max_chars - 1].rstrip() + "…"
    return [paragraph] if paragraph else []
