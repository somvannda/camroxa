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


def mp3_has_duration_header(path: str | Path) -> bool:
    """True when the MP3 carries a Xing/Info header (players report the true length)."""
    try:
        with Path(path).open("rb") as handle:
            head = handle.read(8192)
    except OSError:
        return False
    return b"Xing" in head or b"Info" in head


def ensure_mp3_duration_header(path: str | Path, *, ffmpeg_path: str = "") -> bool:
    """Re-mux an MP3 to add a Xing/Info header so its reported duration is accurate.

    Suno's MP3s often lack the header, so ffprobe/players estimate the length from
    file size and over-report by several seconds (the exported MP4 is correct, but
    the MP3 label looks longer). ``ffmpeg -c copy -write_xing 1`` writes the header
    without re-encoding. Best-effort: on any failure the original file is kept.
    """
    target = Path(str(path or "").strip())
    if not target.is_file() or not file_looks_like_mpeg_audio(target):
        return False
    if mp3_has_duration_header(target):
        return True
    try:
        from shared.lib.ffmpeg_paths import resolve_ffmpeg_path
        from shared.lib.subprocess_utils import run_hidden

        ffmpeg = resolve_ffmpeg_path(ffmpeg_path or "")
        if not ffmpeg:
            return False
        tmp = target.parent / f"{target.name}.xing.tmp"
        try:
            proc = run_hidden(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(target),
                    "-c",
                    "copy",
                    "-write_xing",
                    "1",
                    "-f",
                    "mp3",
                    str(tmp),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size <= 0:
                return False
            if not mp3_has_duration_header(tmp):
                return False
            tmp.replace(target)
            return True
        finally:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
    except Exception:
        return False
