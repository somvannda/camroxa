"""Decode video-background frames for Studio / GPU preview (OpenCV)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}


def is_video_path(path: str | None) -> bool:
    text = str(path or "").strip()
    if not text:
        return False
    try:
        return Path(text).suffix.lower() in _VIDEO_SUFFIXES
    except OSError:
        return False


class VideoBackgroundSource:
    """Seekable plate decoder — one open capture, frames as RGBA uint8."""

    def __init__(self) -> None:
        self._path = ""
        self._cap: Any = None
        self._fps = 30.0
        self._frame_count = 0
        self._duration = 0.0
        self._last_index = -1
        self._last_rgba: np.ndarray | None = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def duration_sec(self) -> float:
        return self._duration

    def open(self, path: str) -> bool:
        p = str(path or "").strip()
        if not p or not Path(p).is_file() or not is_video_path(p):
            self.close()
            return False
        if p == self._path and self._cap is not None:
            return True
        self.close()
        try:
            import cv2
        except ImportError:
            return False
        cap = cv2.VideoCapture(p)
        if not cap.isOpened():
            cap.release()
            return False
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._cap = cap
        self._path = p
        self._fps = max(1.0, fps)
        self._frame_count = max(0, count)
        self._duration = (self._frame_count / self._fps) if self._frame_count else 0.0
        self._last_index = -1
        self._last_rgba = None
        return True

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None
        self._path = ""
        self._fps = 30.0
        self._frame_count = 0
        self._duration = 0.0
        self._last_index = -1
        self._last_rgba = None

    def frame_rgba_at(self, time_sec: float) -> np.ndarray | None:
        if self._cap is None:
            return None
        try:
            import cv2
        except ImportError:
            return None
        t = max(0.0, float(time_sec or 0.0))
        if self._duration > 0:
            t = min(t, max(0.0, self._duration - 1.0 / self._fps))
        index = int(t * self._fps)
        if self._frame_count > 0:
            index = max(0, min(self._frame_count - 1, index))
        if index == self._last_index and self._last_rgba is not None:
            return self._last_rgba
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(index))
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return self._last_rgba
        rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        self._last_index = index
        self._last_rgba = rgba
        return rgba
