"""AudioController — encapsulates pygame audio playback state.

Extracted from ``MainWindow`` as part of the *main-window-decomposition* spec
(Requirement 3). The controller owns all pygame audio state (play, pause, stop,
seek, duration tracking) and exposes a pure :meth:`tick` for the UI timer.

The controller does **not** hold a reference to ``MainWindow``. Instead it
receives two callables:

* ``preview_accessor`` — returns the visualizer preview widget (the object that
  owns ``current_time``, ``audio_path``, ``audio_ready`` and the playback marker
  helpers ``_mark_playback_*``).
* ``ui_update_fn`` — invoked with ``(current_time, duration)`` so the host can
  refresh the seek label and slider after a state change. The controller never
  touches widgets directly.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame


class AudioController:
    """Encapsulates pygame audio playback state (play, pause, stop, seek)."""

    def __init__(
        self,
        *,
        preview_accessor: Callable[[], object],
        ui_update_fn: Callable[[float, float], None],
    ) -> None:
        self._preview_accessor = preview_accessor
        self._ui_update_fn = ui_update_fn
        self._audio_paused: bool = False
        self._seek_dragging: bool = False

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------
    @property
    def audio_paused(self) -> bool:
        """Whether playback is currently paused (vs. stopped or playing)."""
        return self._audio_paused

    @property
    def seek_dragging(self) -> bool:
        """Whether the user is currently dragging the seek slider."""
        return self._seek_dragging

    @seek_dragging.setter
    def seek_dragging(self, value: bool) -> None:
        self._seek_dragging = bool(value)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------
    def play_audio(self) -> None:
        """Begin (or resume) playback of the selected MP3.

        Raises:
            RuntimeError: If the pygame mixer is not initialized, or if pygame
                raises while starting playback. A well-defined ``RuntimeError``
                is surfaced rather than an unhandled pygame exception.
        """
        if not pygame.mixer.get_init():
            raise RuntimeError("pygame mixer is not initialized")
        preview = self._preview_accessor()
        if not getattr(preview, "audio_path", ""):
            return
        if not getattr(preview, "audio_ready", False):
            return
        try:
            if self._audio_paused:
                pygame.mixer.music.unpause()
                preview._mark_playback_started(preview.current_time)
            else:
                start_t = max(0.0, float(preview.current_time))
                pygame.mixer.music.play(start=start_t)
                preview._mark_playback_started(start_t)
            preview.audio_playing = True
            self._audio_paused = False
        except Exception as exc:
            raise RuntimeError(f"Audio playback failed: {exc}") from exc
        self._push_ui_update()

    def toggle_playback(self) -> None:
        """Pause if currently playing, otherwise start/resume playback."""
        preview = self._preview_accessor()
        if getattr(preview, "audio_playing", False):
            self.pause_audio()
        else:
            self.play_audio()

    def pause_audio(self) -> None:
        """Pause playback if the mixer is active and currently busy."""
        preview = self._preview_accessor()
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            preview._mark_playback_paused()
            preview.audio_playing = False
            self._audio_paused = True
        self._push_ui_update()

    def stop_audio(self) -> None:
        """Stop playback and reset paused state."""
        preview = self._preview_accessor()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            preview._mark_playback_stopped()
            self._audio_paused = False
            preview.audio_playing = False
        self._push_ui_update()

    # ------------------------------------------------------------------
    # Seeking
    # ------------------------------------------------------------------
    def seek_relative(self, delta_sec: float) -> None:
        """Seek by ``delta_sec`` seconds relative to the current position."""
        preview = self._preview_accessor()
        self.seek_to(float(preview.current_time) + float(delta_sec))

    def seek_to(self, t_sec: float) -> None:
        """Seek to ``t_sec`` seconds, clamped to ``[0, duration]``.

        When the audio duration is unknown (``0.0``) only the lower bound is
        applied. If the mixer is active and the audio is ready, playback
        restarts from the clamped position.
        """
        preview = self._preview_accessor()
        duration = self.get_audio_duration()
        t = max(0.0, float(t_sec))
        if duration > 0.0:
            t = min(t, duration)
        preview.current_time = t
        if (
            getattr(preview, "audio_path", "")
            and pygame.mixer.get_init()
            and getattr(preview, "audio_ready", False)
        ):
            try:
                pygame.mixer.music.play(start=t)
                preview._mark_playback_started(t)
                preview.audio_playing = True
                self._audio_paused = False
            except Exception:
                return None
        self._push_ui_update()

    # ------------------------------------------------------------------
    # Duration / UI queries
    # ------------------------------------------------------------------
    def get_audio_duration(self) -> float:
        """Return the audio duration in seconds, or ``0.0`` if unknown."""
        preview = self._preview_accessor()
        try:
            cached = float(getattr(preview, "_audio_duration_sec", 0.0) or 0.0)
            if cached > 0.0:
                return cached
            analyzer = getattr(preview, "analyzer", None)
            if (
                analyzer
                and hasattr(analyzer, "info")
                and getattr(analyzer.info, "duration_sec", None) is not None
            ):
                return float(analyzer.info.duration_sec)
        except Exception:
            return 0.0
        return 0.0

    def sync_play_button_state(self) -> bool:
        """Return whether audio is currently playing (no widget mutation)."""
        preview = self._preview_accessor()
        return bool(getattr(preview, "audio_playing", False))

    def tick(self) -> tuple[float, float]:
        """Return ``(current_time, duration)`` without modifying any widget."""
        preview = self._preview_accessor()
        duration = self.get_audio_duration()
        current_time = float(getattr(preview, "current_time", 0.0))
        return (current_time, duration)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _push_ui_update(self) -> None:
        """Push the current ``(current_time, duration)`` to the host UI hook."""
        current_time, duration = self.tick()
        self._ui_update_fn(current_time, duration)
