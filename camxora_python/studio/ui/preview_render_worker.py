"""Background compositor worker — keeps the UI thread free during scrubbing."""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QThread, Signal

from studio.core.project_state import ProjectState
from studio.media.audio_source import AudioSourceCache
from studio.media.video_source import VideoSourceCache
from studio.render.compositor import render_frame

logger = logging.getLogger(__name__)


class PreviewRenderWorker(QThread):
    """Renders one preview frame off the UI thread."""

    finished = Signal(int, object)  # generation, HxWx3 uint8 ndarray

    def __init__(
        self,
        generation: int,
        project_state: ProjectState,
        time: float,
        video_cache: VideoSourceCache,
        width: int,
        height: int,
        audio_cache: AudioSourceCache | None = None,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.project_state = project_state
        self.time = time
        self.video_cache = video_cache
        self.audio_cache = audio_cache
        self.width = width
        self.height = height

    def run(self) -> None:
        logger.debug(
            "worker render gen=%s time=%.3f size=%sx%s",
            self.generation,
            self.time,
            self.width,
            self.height,
        )
        try:
            frame = render_frame(
                self.project_state,
                self.time,
                self.video_cache,
                audio_cache=self.audio_cache,
                width=self.width,
                height=self.height,
            )
            logger.debug("worker done gen=%s frame=%s", self.generation, getattr(frame, "shape", None))
            self.finished.emit(self.generation, frame)
        except Exception:
            logger.exception("worker render failed gen=%s", self.generation)
            raise
