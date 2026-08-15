"""Prefer Suno MPEG CDN files and reject Opus-in-MP4 saved as .mp3."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_SUNO_CDN_HOST_MARKERS = ("cdn1.suno.ai", "cdn2.suno.ai", "cdn.suno.ai")
_NON_MPEG_CDN_SUFFIXES = (".m4a", ".mp4", ".webm", ".opus", ".aac")
_MIN_AUDIO_BYTES = 256


def prefer_suno_mpeg_cdn_url(url: str) -> str:
    """Rewrite ``cdn1.suno.ai/{id}.m4a`` to ``{id}.mp3`` (same clip, real MPEG)."""
    text = str(url or "").strip()
    if not text.startswith(("http://", "https://")):
        return text
    lower = text.lower()
    if lower.endswith(".mp3") or ".mp3?" in lower:
        return text
    parts = urlsplit(text)
    host = (parts.netloc or "").lower()
    if not any(marker in host for marker in _SUNO_CDN_HOST_MARKERS):
        return text
    path = parts.path or ""
    path_lower = path.lower()
    for suffix in _NON_MPEG_CDN_SUFFIXES:
        if path_lower.endswith(suffix):
            new_path = path[: -len(suffix)] + ".mp3"
            return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))
    return text


def payload_is_mpeg_audio(content: bytes) -> bool:
    """True when bytes look like MP3 (ID3 or MPEG frame), not MP4/M4A/Opus."""
    if not content or len(content) < _MIN_AUDIO_BYTES:
        return False
    if content[4:8] == b"ftyp":
        return False
    if content[:3] == b"ID3":
        return True
    if content[0] == 0xFF and (content[1] & 0xE0) == 0xE0 and (content[1] & 0xF6) != 0xF0:
        return True
    return False


def file_looks_like_mpeg_audio(path: str | Path) -> bool:
    """Sniff the start of a file without loading the whole track."""
    try:
        with Path(path).open("rb") as handle:
            return payload_is_mpeg_audio(handle.read(4096))
    except OSError:
        return False
