"""Detect whether bundled ffmpeg can actually open h264_nvenc.

FFmpeg may stay alive after spawn while waiting for pipe frames, then fail
when NVENC opens (e.g. driver API too old). A tiny lavfi probe catches that
before export starts so we can fall back to libx264.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from shared.lib.subprocess_utils import run_hidden

# Process-lifetime cache keyed by resolved ffmpeg path.
_NVENC_PROBE_CACHE: dict[str, bool] = {}
_NVENC_DISABLED = False

_NVENC_UNAVAILABLE_MARKERS = (
    "nvenc api version",
    "minimum required nvidia driver",
    "driver does not support the required nvenc",
    "unknown encoder 'h264_nvenc'",
    "unknown encoder: h264_nvenc",
    "cannot load nvcuda",
    "no nvenc-capable devices",
    "no nvenc capable devices",
    "nvenc is not supported",
)


def mark_nvenc_unavailable(ffmpeg_path: str | None = None) -> None:
    """Remember that NVENC cannot be used for the rest of this process."""
    global _NVENC_DISABLED
    _NVENC_DISABLED = True
    if ffmpeg_path:
        _NVENC_PROBE_CACHE[_probe_cache_key(ffmpeg_path)] = False
    for key in list(_NVENC_PROBE_CACHE.keys()):
        _NVENC_PROBE_CACHE[key] = False


def clear_nvenc_probe_cache() -> None:
    """Test helper: drop cached probe results."""
    global _NVENC_DISABLED
    _NVENC_DISABLED = False
    _NVENC_PROBE_CACHE.clear()


def nvenc_error_indicates_unavailable(err_txt: str) -> bool:
    """Return True when ffmpeg stderr means NVENC cannot be used on this machine."""
    text = str(err_txt or "").lower()
    if not text:
        return False
    if any(marker in text for marker in _NVENC_UNAVAILABLE_MARKERS):
        return True
    if "h264_nvenc" in text or "nvenc" in text:
        if "error while opening encoder" in text or "function not implemented" in text:
            return True
    return False


def _force_software_encode() -> bool:
    raw = str(os.environ.get("CAMXORA_FORCE_X264", "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _probe_cache_key(ffmpeg_path: str) -> str:
    path = str(ffmpeg_path or "ffmpeg").strip() or "ffmpeg"
    try:
        return str(Path(path).resolve())
    except OSError:
        return path


def probe_h264_nvenc(ffmpeg_path: str, *, force: bool = False, timeout_sec: float = 20.0) -> bool:
    """Return True if ``ffmpeg_path`` can encode one frame with h264_nvenc.

    Results are cached per ffmpeg binary for the process lifetime. Set
    ``CAMXORA_FORCE_X264=1`` to skip NVENC entirely.
    """
    key = _probe_cache_key(ffmpeg_path)
    if _NVENC_DISABLED or _force_software_encode():
        _NVENC_PROBE_CACHE[key] = False
        return False
    if not force and key in _NVENC_PROBE_CACHE:
        return _NVENC_PROBE_CACHE[key]

    cmd = [
        str(ffmpeg_path or "ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=256x256:d=0.04",
        "-frames:v",
        "1",
        "-c:v",
        "h264_nvenc",
        "-f",
        "null",
        "-",
    ]
    ok = False
    try:
        completed = run_hidden(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1.0, float(timeout_sec)),
            check=False,
        )
        err = str(completed.stderr or "")
        ok = int(completed.returncode or 0) == 0 and not nvenc_error_indicates_unavailable(err)
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        ok = False

    _NVENC_PROBE_CACHE[key] = bool(ok)
    return bool(ok)


def rewrite_nvenc_cmd_to_x264(cmd: list[str], *, x264_preset: str, x264_crf: str) -> list[str]:
    """Swap h264_nvenc flags in an ffmpeg argv list for libx264 equivalents."""
    cmd2 = list(cmd)
    if "h264_nvenc" not in cmd2:
        return cmd2
    cmd2[cmd2.index("h264_nvenc")] = "libx264"
    for flag in ("-cq", "-rc", "-tune", "-zerolatency", "-bf"):
        while flag in cmd2:
            i = cmd2.index(flag)
            del cmd2[i : i + 2]
    if "-preset" in cmd2:
        i = cmd2.index("-preset")
        cmd2[i + 1] = x264_preset
    if "-crf" not in cmd2:
        pix = cmd2.index("-pix_fmt") if "-pix_fmt" in cmd2 else len(cmd2)
        cmd2.insert(pix, "-crf")
        cmd2.insert(pix + 1, x264_crf)
    return cmd2
