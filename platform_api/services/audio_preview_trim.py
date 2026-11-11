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


async def trim_audio_range_bytes(
    data: bytes, *, start_s: float, end_s: float, fmt: str
) -> bytes:
    """Return ``data`` between ``start_s`` and ``end_s`` in the same container.

    Used by Sample: the slice a user picked on the waveform becomes the seed for
    a new song. Seeking happens after the input is opened because the bytes come
    over a pipe, which cannot be seeked.
    """
    if not data:
        raise PreviewTrimError("empty audio buffer")
    start = max(0.0, float(start_s or 0.0))
    end = max(start, float(end_s or 0.0))
    duration = max(0.5, end - start)
    container = "mp3" if str(fmt).lower() == "mp3" else "wav"
    args = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
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
        raise PreviewTrimError(f"ffmpeg sample trim failed: {exc}") from exc
    if proc.returncode != 0 or len(out) < 400:
        detail = (err or b"").decode("utf-8", "replace")[-300:]
        raise PreviewTrimError(f"ffmpeg sample trim failed ({proc.returncode}): {detail}")
    logger.debug(
        "Trimmed %s sample %.2fs-%.2fs (%d -> %d bytes)",
        container,
        start,
        end,
        len(data),
        len(out),
    )
    return out


async def _run_ffmpeg(args: list[str], data: bytes) -> bytes:
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
        raise PreviewTrimError(f"ffmpeg edit failed: {exc}") from exc
    if proc.returncode != 0 or len(out) < 400:
        detail = (err or b"").decode("utf-8", "replace")[-300:]
        raise PreviewTrimError(f"ffmpeg edit failed ({proc.returncode}): {detail}")
    return out


async def probe_audio_duration_bytes(data: bytes) -> float:
    """Length of an audio buffer in seconds (used by fade/remove edits).

    ffprobe cannot read a pipe reliably for container metadata, so the bytes go
    to a temporary file first.
    """
    import os
    import tempfile

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise PreviewTrimError("ffprobe is not installed on this host.")
    if not data:
        raise PreviewTrimError("empty audio buffer")
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        proc = await asyncio.create_subprocess_exec(
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise PreviewTrimError(
            "ffprobe failed: " + (err or b"").decode("utf-8", "replace")[-200:]
        )
    try:
        return float(out.decode().strip())
    except ValueError as exc:
        raise PreviewTrimError("ffprobe returned no duration") from exc


async def transform_audio_bytes(
    data: bytes, *, audio_filter: str, fmt: str = "mp3"
) -> bytes:
    """Apply an ffmpeg audio filter and re-encode (reverse, speed, fades)."""
    if not data:
        raise PreviewTrimError("empty audio buffer")
    if not str(audio_filter or "").strip():
        raise PreviewTrimError("no audio filter given")
    container = "mp3" if str(fmt).lower() == "mp3" else "wav"
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if container == "mp3" else []
    args = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-af",
        audio_filter,
        *codec,
        "-f",
        container,
        "pipe:1",
    ]
    return await _run_ffmpeg(args, data)


async def remove_audio_range_bytes(
    data: bytes, *, start_s: float, end_s: float, fmt: str = "mp3"
) -> bytes:
    """Cut [start_s, end_s) out of the middle and join the remaining halves."""
    start = max(0.0, float(start_s or 0.0))
    end = max(start, float(end_s or 0.0))
    if end <= start:
        return data
    container = "mp3" if str(fmt).lower() == "mp3" else "wav"
    codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if container == "mp3" else []
    filter_complex = (
        f"[0:a]atrim=0:{start:.3f},asetpts=PTS-STARTPTS[a];"
        f"[0:a]atrim={end:.3f},asetpts=PTS-STARTPTS[b];"
        "[a][b]concat=n=2:v=0:a=1[out]"
    )
    args = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        *codec,
        "-f",
        container,
        "pipe:1",
    ]
    return await _run_ffmpeg(args, data)
