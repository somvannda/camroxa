"""Studio player — compact transport under the preview."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class StudioTimelineStub(QWidget):
    play_toggled = Signal(bool)
    stop_requested = Signal()
    seek_requested = Signal(float)  # seconds
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("studioPlayer")
        self.setFixedHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        self._track_name = QLabel("No track")
        self._track_name.setObjectName(SUBTITLE_LABEL_ID)
        self._track_name.setWordWrap(False)
        meta.addWidget(self._track_name, stretch=1)
        self._time = QLabel("0:00 / 0:00")
        self._time.setObjectName(SUBTITLE_LABEL_ID)
        self._time.setMinimumWidth(88)
        self._time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meta.addWidget(self._time)
        root.addLayout(meta)

        transport = QHBoxLayout()
        transport.setSpacing(6)

        self._prev = _transport_btn("Prev", "Previous track")
        self._prev.clicked.connect(self.previous_requested.emit)
        self._play = _transport_btn("Play", "Play / pause", checkable=True, width=64)
        self._play.toggled.connect(self._on_play)
        self._stop = _transport_btn("Stop", "Stop and return to start")
        self._stop.clicked.connect(self._on_stop)
        self._next = _transport_btn("Next", "Next track")
        self._next.clicked.connect(self.next_requested.emit)
        for btn in (self._prev, self._play, self._stop, self._next):
            transport.addWidget(btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setMinimumHeight(18)
        self._slider.setToolTip("Scrub preview playhead")
        self._slider.sliderMoved.connect(self._on_slide)
        self._slider.sliderReleased.connect(self._on_release)
        transport.addWidget(self._slider, stretch=1)
        root.addLayout(transport)

        self._duration = 0.0
        self._position = 0.0
        self._scrubbing = False

    def _on_play(self, playing: bool) -> None:
        self._play.setText("Pause" if playing else "Play")
        self.play_toggled.emit(playing)

    def _on_stop(self) -> None:
        blocked = self._play.blockSignals(True)
        self._play.setChecked(False)
        self._play.setText("Play")
        self._play.blockSignals(blocked)
        self.stop_requested.emit()

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

    def set_track_name(self, name: str) -> None:
        text = str(name or "").strip()
        if not text:
            self._track_name.setText("No track")
            self._track_name.setToolTip("")
            return
        try:
            display = Path(text).name or text
        except Exception:
            display = text
        self._track_name.setText(display)
        self._track_name.setToolTip(text)

    def set_duration(self, duration_sec: float) -> None:
        self._duration = max(0.0, float(duration_sec or 0.0))
        self._render_labels(self._position if not self._scrubbing else self._slider_time())

    def set_position(self, time_sec: float) -> None:
        if self._scrubbing:
            return
        self._position = max(0.0, float(time_sec or 0.0))
        if self._duration > 0:
            blocked = self._slider.blockSignals(True)
            self._slider.setValue(
                int(max(0, min(1000, round((self._position / self._duration) * 1000))))
            )
            self._slider.blockSignals(blocked)
        self._render_labels(self._position)

    def set_playing(self, playing: bool) -> None:
        blocked = self._play.blockSignals(True)
        self._play.setChecked(playing)
        self._play.setText("Pause" if playing else "Play")
        self._play.blockSignals(blocked)

    def _slider_time(self) -> float:
        if self._duration <= 0:
            return self._position
        return (self._slider.value() / 1000.0) * self._duration

    def _render_labels(self, t: float) -> None:
        shown = max(0.0, float(t or 0.0))
        if self._duration > 0:
            shown = min(shown, self._duration)
        self._time.setText(f"{_fmt(shown)} / {_fmt(self._duration)}")


def _transport_btn(
    label: str, tip: str, *, checkable: bool = False, width: int = 52
) -> QPushButton:
    btn = QPushButton(label)
    btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
    btn.setToolTip(tip)
    btn.setCheckable(checkable)
    btn.setFixedHeight(32)
    btn.setMinimumWidth(width)
    return btn


def _fmt(sec: float) -> str:
    s = int(max(0, sec))
    return f"{s // 60}:{s % 60:02d}"
