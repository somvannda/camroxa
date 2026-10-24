"""Server-side audio truncation for free-tier previews.

Previews must never expose the full generated track, regardless of whether the
audio is streamed from B2, downloaded, or served through the Suno fallback.
The caller trims before storing, and trims again on any on-demand fallback, so a
storage miss cannot leak the full song.
"""

from __future__ import annotations

import asyncio
import logging
import shutil

logger = logging.getLogger(__name__)


class PreviewTrimError(RuntimeError):
    """Raised when a preview cannot be cut, so the full audio is never served."""


def _ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise PreviewTrimError("ffmpeg is not installed on this host.")
    return path


async def trim_audio_bytes(data: bytes, *, seconds: int, fmt: str) -> bytes:
    """Return the first ``seconds`` of ``data`` in the same container.

    ``fmt`` is ``mp3`` or ``wav``. MP3 frames and PCM WAV are copied without a
    re-encode, so this is fast and lossless. Any failure raises
    :class:`PreviewTrimError`; callers must not fall back to the original bytes.
    """
    if not data:
        raise PreviewTrimError("empty audio buffer")
    limit = max(1, int(seconds or 0))
    container = "mp3" if str(fmt).lower() == "mp3" else "wav"
    args = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-t",
        str(limit),
        "-c",
        "copy",
        "-f",
        container,
        "pipe:1",
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await proc.communicate(data)
    except Exception as exc:  # pragma: no cover - subprocess guard
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise PreviewTrimError(f"ffmpeg trim failed: {exc}") from exc
    if proc.returncode != 0 or len(out) < 400:
        detail = (err or b"").decode("utf-8", "replace")[-300:]
        raise PreviewTrimError(f"ffmpeg trim failed ({proc.returncode}): {detail}")
    logger.debug("Trimmed %s preview to %ss (%d -> %d bytes)", container, limit, len(data), len(out))
    return out
