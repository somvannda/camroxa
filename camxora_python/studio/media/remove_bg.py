"""Local background removal — optional AI (rembg) with OpenCV fallback."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_CACHE_ROOT = Path.home() / ".camxora" / "remove_bg"


def _cache_path(source_path: Path) -> Path:
    stat = source_path.stat()
    digest = hashlib.sha1(f"{source_path.resolve()}:{stat.st_mtime_ns}".encode()).hexdigest()
    return _CACHE_ROOT / f"{digest}.png"


def _remove_with_rembg(source_path: Path, output_path: Path) -> bool:
    try:
        from rembg import remove
        from PIL import Image
    except ImportError:
        return False

    try:
        with Image.open(source_path) as image:
            result = remove(image)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path)
        return output_path.is_file()
    except Exception:
        logger.exception("rembg failed for %s", source_path)
        return False


def _remove_with_opencv(source_path: Path, output_path: Path) -> bool:
    img = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if img is None:
        return False
    h, w = img.shape[:2]
    if h < 2 or w < 2:
        return False

    corners = np.array(
        [img[0, 0], img[0, w - 1], img[h - 1, 0], img[h - 1, w - 1]], dtype=np.float32
    )
    bg = np.median(corners, axis=0)
    diff = np.linalg.norm(img.astype(np.float32) - bg, axis=2)
    thresh = float(max(25.0, np.percentile(diff, 82)))
    mask = (diff > thresh).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.GaussianBlur(mask, (7, 7), 0)

    bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = mask
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(output_path), bgra))


def rembg_available() -> bool:
    try:
        import rembg  # noqa: F401

        return True
    except ImportError:
        return False


def process_remove_background(source_path: str) -> tuple[str | None, str]:
    """Return ``(output_png_path, status_message)``."""
    src = Path(source_path)
    if not src.is_file():
        return None, "Source file not found."

    cached = _cache_path(src)
    if cached.is_file():
        return str(cached), "Using cached background removal."

    if _remove_with_rembg(src, cached):
        return str(cached), "Background removed (local AI — rembg)."

    if _remove_with_opencv(src, cached):
        method = "OpenCV color key"
        if rembg_available():
            method = "OpenCV fallback"
        else:
            method += " — install rembg for higher quality: pip install rembg"
        return str(cached), f"Background removed ({method})."

    return None, "Background removal failed."
