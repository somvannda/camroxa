"""Normalize MP3 duration headers so players and ffprobe report the true length.

Suno's CDN MP3s (and the B2 copies we archive from them) frequently omit the
Xing/Info header. Without it, ffprobe and most players estimate the duration
from the file size and over-report by several seconds, so an exported MP4 that
carries the real audio length looks shorter than the MP3. Re-muxing with
``ffmpeg -c copy -write_xing 1`` writes the header losslessly (no re-encode).

Every function here is best-effort: on any failure the original bytes are
returned so callers can upload/serve the file unchanged.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

HEADER_SCAN_BYTES = 8192
_FFMPEG_TIMEOUT_SEC = 60


def mp3_has_duration_header(data: bytes) -> bool:
    """True when the MP3 carries a Xing/Info header (players report true length)."""
    head = data[:HEADER_SCAN_BYTES]
    return b"Xing" in head or b"Info" in head


def looks_like_mpeg_audio(data: bytes) -> bool:
    """True for MPEG audio (ID3 tag or MPEG frame sync); False for MP4/M4A/Opus."""
    if len(data) < 4:
        return False
    if data[:3] == b"ID3":
        return True
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    return False


def resolve_ffmpeg_path() -> str:
    override = str(os.environ.get("CAMXORA_FFMPEG_PATH") or "").strip()
    if override and Path(override).is_file():
        return override
    return shutil.which("ffmpeg") or ""


def ensure_mp3_duration_header(data: bytes) -> bytes:
    """Return MP3 bytes carrying a Xing/Info header, or the original on failure.

    Only MPEG audio without a header is touched; everything else (already-headed
    MP3s, Opus-in-MP4, WAV, empty bodies) is returned unchanged.
    """
    if not data or not looks_like_mpeg_audio(data):
        return data
    if mp3_has_duration_header(data):
        return data
    ffmpeg = resolve_ffmpeg_path()
    if not ffmpeg:
        logger.info("ffmpeg unavailable; skipping MP3 duration-header normalization.")
        return data
    try:
        with tempfile.TemporaryDirectory(prefix="camxora-mp3xing-") as tmp:
            work = Path(tmp)
            source = work / "in.mp3"
            target = work / "out.mp3"
            source.write_bytes(data)
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-c",
                    "copy",
                    "-write_xing",
                    "1",
                    "-f",
                    "mp3",
                    str(target),
                ],
                capture_output=True,
                check=False,
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
            if proc.returncode != 0 or not target.is_file() or target.stat().st_size <= 0:
                logger.warning(
                    "MP3 duration-header remux failed (rc=%s): %s",
                    proc.returncode,
                    (proc.stderr or b"")[:200],
                )
                return data
            normalized = target.read_bytes()
    except Exception as exc:  # noqa: BLE001 - best-effort, never break an upload
        logger.warning("MP3 duration-header normalization error: %s", exc)
        return data
    if not mp3_has_duration_header(normalized):
        return data
    return normalized


async def ensure_mp3_duration_header_async(data: bytes) -> bytes:
    """Threaded wrapper so ffmpeg never blocks the event loop."""
    import asyncio

    if not data or not looks_like_mpeg_audio(data) or mp3_has_duration_header(data):
        return data
    return await asyncio.to_thread(ensure_mp3_duration_header, data)
