"""Prepare a smaller upload copy for very large merged videos.

Post for Me accepts a single presigned PUT (no multipart, no resume), so a 6 GB
merge cannot be uploaded reliably. Above the threshold we transcode a 1080p
~6 Mbps copy (roughly 0.9 GB/hour) and upload that; the original stays local.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

UPLOAD_COPY_THRESHOLD_BYTES = 2 * 1024**3  # 2 GiB
UPLOAD_COPY_HEIGHT = 1080
UPLOAD_COPY_MAXRATE = "6M"
UPLOAD_COPY_BUFSIZE = "12M"


@dataclass(frozen=True, slots=True)
class UploadCopyPlan:
    source: Path
    target: Path
    source_bytes: int


def should_make_upload_copy(size_bytes: int | None) -> bool:
    """True when the file is large enough that a single PUT is unreliable."""
    try:
        size = int(size_bytes or 0)
    except (TypeError, ValueError):
        return False
    return size >= UPLOAD_COPY_THRESHOLD_BYTES


def upload_copy_target(source: str | Path) -> Path:
    path = Path(source)
    return path.with_name(f"{path.stem}.uploadcopy.mp4")


def build_upload_copy_command(ffmpeg: str, source: str | Path, target: str | Path) -> list[str]:
    """H.264/AAC 1080p copy tuned for upload, web-safe and fast to decode."""
    return [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        f"scale=-2:'min({UPLOAD_COPY_HEIGHT},ih)'",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        UPLOAD_COPY_MAXRATE,
        "-maxrate",
        UPLOAD_COPY_MAXRATE,
        "-bufsize",
        UPLOAD_COPY_BUFSIZE,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(target),
    ]


def make_upload_copy_plan(source: str | Path, size_bytes: int | None = None) -> UploadCopyPlan | None:
    """Plan a copy only when the file exists and is over the threshold."""
    path = Path(source)
    try:
        source_size = int(size_bytes if size_bytes is not None else path.stat().st_size)
    except OSError:
        return None
    if not should_make_upload_copy(source_size):
        return None
    return UploadCopyPlan(source=path, target=upload_copy_target(path), source_bytes=source_size)
