"""Import media files: probe duration/dimensions and generate thumbnails.

Python analog of the reference app's `importFiles()` — but since there is no
browser `<video>`/`<audio>` element, probing uses OpenCV (video), soundfile
(audio), and Pillow (image) directly against the file on disk.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import soundfile as sf
from PIL import Image

from studio.core.models import MediaAsset, new_id
from studio.media.thumb_cache import load_cached_filmstrip, media_cache_key, persistent_cache_dir, save_cached_filmstrip

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

DEFAULT_IMAGE_DURATION = 5.0
THUMB_SIZE = (160, 90)
FILMSTRIP_SIZE = (60, 40)
FILMSTRIP_FRAMES = 5


def default_cache_dir() -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "camxora_studio_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def guess_media_type(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "image"
    return None


def _probe_video(path: Path) -> tuple[float, int | None, int | None]:
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        duration = (frame_count / fps) if fps > 0 else 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
        return duration, width, height
    finally:
        cap.release()


def _probe_audio(path: Path) -> tuple[float, int | None]:
    info = sf.info(str(path))
    duration = info.frames / info.samplerate if info.samplerate else 0.0
    return duration, info.samplerate


def _probe_image(path: Path) -> tuple[int | None, int | None]:
    with Image.open(path) as img:
        return img.width, img.height


def _make_video_thumbnail(path: Path, cache_dir: Path, duration: float) -> str | None:
    cap = cv2.VideoCapture(str(path))
    try:
        seek_time = min(0.3, duration / 2 if duration else 0.0)
        cap.set(cv2.CAP_PROP_POS_MSEC, seek_time * 1000)
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        frame = cv2.resize(frame, THUMB_SIZE, interpolation=cv2.INTER_AREA)
        out_path = cache_dir / f"thumb_{uuid.uuid4().hex[:9]}.jpg"
        cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return str(out_path)
    except Exception:
        logger.exception("Failed to build video thumbnail for %s", path)
        return None
    finally:
        cap.release()


def _make_image_thumbnail(path: Path, cache_dir: Path) -> str | None:
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail(THUMB_SIZE)
            out_path = cache_dir / f"thumb_{uuid.uuid4().hex[:9]}.jpg"
            img.save(out_path, "JPEG", quality=80)
            return str(out_path)
    except Exception:
        logger.exception("Failed to build image thumbnail for %s", path)
        return None


def build_video_filmstrip(
    path: Path,
    duration: float,
    cache_dir: Path,
    frames: int = FILMSTRIP_FRAMES,
    size: tuple[int, int] = FILMSTRIP_SIZE,
    *,
    use_persistent_cache: bool = True,
) -> list[str]:
    """Generate a small strip of evenly-spaced thumbnails for the clip's
    filmstrip on the timeline (port of `buildThumbCache`)."""
    if use_persistent_cache:
        cached = load_cached_filmstrip(path, frames=frames, size=size)
        if cached is not None:
            return cached

    cap = cv2.VideoCapture(str(path))
    out: list[str] = []
    strip_dir = persistent_cache_dir() / "filmstrips" / media_cache_key(path) if use_persistent_cache else cache_dir
    strip_dir.mkdir(parents=True, exist_ok=True)
    try:
        for i in range(frames):
            t = (duration or 1.0) * (i / frames)
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            out_path = strip_dir / f"frame_{i:02d}.jpg"
            cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
            out.append(str(out_path))
    except Exception:
        logger.exception("Failed to build filmstrip for %s", path)
    finally:
        cap.release()

    if use_persistent_cache and out:
        save_cached_filmstrip(path, frames=frames, size=size, thumb_paths=out)
    return out


def probe_and_import(path: str | Path, cache_dir: Path | None = None) -> MediaAsset | None:
    """Probe a single file on disk and return a populated MediaAsset, or
    None if the file type isn't supported."""
    path = Path(path)
    media_type = guess_media_type(path)
    if media_type is None:
        logger.warning("Unsupported media type for %s", path)
        return None
    cache_dir = cache_dir or default_cache_dir()

    duration = 0.0
    width: int | None = None
    height: int | None = None
    sample_rate: int | None = None
    thumb_path: str | None = None

    if media_type == "video":
        duration, width, height = _probe_video(path)
        thumb_path = _make_video_thumbnail(path, cache_dir, duration)
    elif media_type == "audio":
        duration, sample_rate = _probe_audio(path)
    else:  # image
        duration = DEFAULT_IMAGE_DURATION
        width, height = _probe_image(path)
        thumb_path = _make_image_thumbnail(path, cache_dir)

    return MediaAsset(
        id=new_id("med"),
        name=path.name,
        type=media_type,  # type: ignore[arg-type]
        path=str(path),
        duration=duration,
        width=width,
        height=height,
        sample_rate=sample_rate,
        thumb_path=thumb_path,
    )


def import_files(paths: list[str | Path], cache_dir: Path | None = None) -> list[MediaAsset]:
    cache_dir = cache_dir or default_cache_dir()
    if not paths:
        return []
    if len(paths) == 1:
        asset = probe_and_import(paths[0], cache_dir)
        return [asset] if asset is not None else []

    workers = min(8, len(paths))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(lambda p: probe_and_import(p, cache_dir), paths)
    return [asset for asset in results if asset is not None]
