"""Resolve a portable ffmpeg binary — shared by audio extraction and export.

Self-contained via the `imageio-ffmpeg` dependency (per the confirmed
architecture decision), falling back to a system PATH `ffmpeg` if present.
"""

from __future__ import annotations

import functools
import shutil


@functools.lru_cache(maxsize=1)
def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        raise RuntimeError(
            "No ffmpeg binary available (imageio-ffmpeg failed and none found on PATH)."
        )
