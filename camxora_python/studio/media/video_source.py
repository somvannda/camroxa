"""Per-asset video frame decode/seek, backed by OpenCV.

Python analog of the reference app syncing a hidden `<video>` element's
`currentTime` — `VideoSource.get_frame_rgb(time)` seeks (or advances
sequentially during forward playback, which is much cheaper than seeking
every frame) and returns the decoded RGB frame as a numpy array.
"""

from __future__ import annotations

import logging
import threading

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_SEQUENTIAL_TOLERANCE_FRAMES = 2.0


class VideoSource:
    def __init__(self, path: str) -> None:
        self.path = path
        self._cap = cv2.VideoCapture(path)
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._last_time: float | None = None
        self._last_frame: np.ndarray | None = None
        self._lock = threading.Lock()

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def is_open(self) -> bool:
        return bool(self._cap.isOpened())

    def get_frame_rgb(self, time: float) -> np.ndarray | None:
        """Return the frame at `time` seconds as an HxWx3 RGB uint8 array."""
        if not self.is_open:
            return None
        time = max(0.0, time)
        with self._lock:
            frame_gap = None if self._last_time is None else time - self._last_time
            needs_seek = (
                frame_gap is None
                or frame_gap < 0
                or frame_gap > (_SEQUENTIAL_TOLERANCE_FRAMES / self._fps)
            )
            if needs_seek:
                self._cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000.0)
            ok, frame = self._cap.read()
            if not ok or frame is None:
                if self._last_frame is not None:
                    return self._last_frame
                return None
            self._last_time = time
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._last_frame = frame_rgb
            return frame_rgb

    def release(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()


class VideoSourceCache:
    """Keeps one VideoSource per media asset alive for the editing session."""

    def __init__(self) -> None:
        self._sources: dict[str, VideoSource] = {}

    def get(self, media_id: str, path: str) -> VideoSource:
        source = self._sources.get(media_id)
        if source is None or not source.is_open:
            source = VideoSource(path)
            self._sources[media_id] = source
        return source

    def release(self, media_id: str) -> None:
        source = self._sources.pop(media_id, None)
        if source is not None:
            source.release()

    def release_all(self) -> None:
        for source in self._sources.values():
            source.release()
        self._sources.clear()
