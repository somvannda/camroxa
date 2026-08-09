"""Studio timeline stub — audio scrub / playhead (not a full NLE)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class StudioTimelineStub(QWidget):
    play_toggled = Signal(bool)
    seek_requested = Signal(float)  # seconds

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        caption = QLabel("Timeline")
        caption.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(caption)
        self._play = QPushButton("Play")
        self._play.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._play.setCheckable(True)
        self._play.toggled.connect(self._on_play)
        layout.addWidget(self._play)
        from PySide6.QtCore import Qt

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.sliderMoved.connect(self._on_slide)
        self._slider.sliderReleased.connect(self._on_release)
        layout.addWidget(self._slider, stretch=1)
        self._time = QLabel("0:00 / 0:00")
        self._time.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._time)
        self._duration = 0.0
        self._scrubbing = False

    def _on_play(self, playing: bool) -> None:
        self._play.setText("Pause" if playing else "Play")
        self.play_toggled.emit(playing)

    def _on_slide(self, value: int) -> None:
        self._scrubbing = True
        if self._duration <= 0:
            return
        self.seek_requested.emit((value / 1000.0) * self._duration)

    def _on_release(self) -> None:
        self._scrubbing = False
        if self._duration <= 0:
            return
        self.seek_requested.emit((self._slider.value() / 1000.0) * self._duration)

    def set_duration(self, duration_sec: float) -> None:
        self._duration = max(0.0, float(duration_sec or 0.0))
        self._render_labels(0.0)

    def set_position(self, time_sec: float) -> None:
        if self._scrubbing:
            return
        t = max(0.0, float(time_sec or 0.0))
        if self._duration > 0:
            blocked = self._slider.blockSignals(True)
            self._slider.setValue(int(max(0, min(1000, round((t / self._duration) * 1000)))))
            self._slider.blockSignals(blocked)
        self._render_labels(t)

    def set_playing(self, playing: bool) -> None:
        blocked = self._play.blockSignals(True)
        self._play.setChecked(playing)
        self._play.setText("Pause" if playing else "Play")
        self._play.blockSignals(blocked)

    def _render_labels(self, t: float) -> None:
        self._time.setText(f"{_fmt(t)} / {_fmt(self._duration)}")


def _fmt(sec: float) -> str:
    s = int(max(0, sec))
    return f"{s // 60}:{s % 60:02d}"
