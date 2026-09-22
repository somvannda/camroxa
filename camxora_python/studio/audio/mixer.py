"""Real-time playback audio mixer — sums active audio-bearing clips into the
default output device, the Python analog of the reference app's
`AudioContext` graph + `MediaStreamDestination`.

The audio callback owns the master playback clock: it advances `_audio_time`
by exactly one block per callback so playback stays at real-time speed even
when the UI thread is busy repainting the timeline or preview. The UI timer
only reads that clock back to move the playhead line and refresh visuals.
"""

from __future__ import annotations

import logging

import numpy as np

from studio.core.project_state import ProjectState
from studio.media.audio_source import AudioSourceCache

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 2
DEFAULT_BLOCK_SIZE = 1024


class AudioMixer:
    def __init__(
        self,
        project_state: ProjectState,
        audio_cache: AudioSourceCache | None = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        block_size: int = DEFAULT_BLOCK_SIZE,
    ) -> None:
        self.project_state = project_state
        self.audio_cache = audio_cache or AudioSourceCache()
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self._stream = None
        self._available = True
        self._audio_time = 0.0

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    @property
    def audio_time(self) -> float:
        return self._audio_time

    def sync_playhead(self, time: float) -> None:
        """Reset the audio master clock — call on play/resume/seek."""
        self._audio_time = max(0.0, time)

    def mix_block(self, start_time: float, frames: int) -> np.ndarray:
        """Pure mixing logic — also used (indirectly) by the export pipeline
        via `export/ffmpeg_export.py` for deterministic offline audio mix."""
        mix = np.zeros((frames, self.channels), dtype=np.float32)
        block_duration = frames / self.sample_rate
        active = self.project_state.active_clips_at(start_time)
        solo_ids = {t.id for t in self.project_state.project.tracks if t.solo}
        any_solo = bool(solo_ids)

        for bucket in (active.video, active.audio):
            for track, clip in bucket:
                if track.muted:
                    continue
                if any_solo and track.id not in solo_ids:
                    continue
                media = self.project_state.get_media(clip.media_id)
                if media is None:
                    continue
                source = self.audio_cache.get(media.id, media.path, media.type)
                if source is None:
                    continue
                local_start = (start_time - clip.start) + clip.trim_start
                block = source.slice_seconds_at_rate(local_start, block_duration, self.sample_rate)
                if len(block) < frames:
                    padded = np.zeros(frames, dtype=np.float32)
                    if len(block):
                        padded[: len(block)] = block
                    block = padded
                elif len(block) > frames:
                    block = block[:frames]
                volume = clip.volume if clip.volume is not None else 1.0
                mix[:, 0] += block * volume
                if self.channels > 1:
                    mix[:, 1] += block * volume

        np.clip(mix, -1.0, 1.0, out=mix)
        return mix

    def _callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:  # noqa: ANN001
        if status:
            logger.debug("Audio stream status: %s", status)
        if not self.project_state.is_playing:
            outdata.fill(0)
            return
        try:
            outdata[:] = self.mix_block(self._audio_time, frames)
            self._audio_time += frames / self.sample_rate
            # Best-effort publish for the UI thread — a float assign is
            # atomic enough for preview scrubber/playhead display.
            self.project_state.playhead = self._audio_time
        except Exception:
            logger.exception("Audio mix callback failed")
            outdata.fill(0)

    def start(self) -> bool:
        if self._stream is not None:
            return True
        try:
            import sounddevice as sd

            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._callback,
                latency="high",
            )
            self._stream.start()
            self._available = True
            return True
        except Exception:
            logger.warning("Audio output unavailable — playback preview will be silent.", exc_info=True)
            self._stream = None
            self._available = False
            return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                logger.debug("Error stopping audio stream", exc_info=True)
            self._stream = None
