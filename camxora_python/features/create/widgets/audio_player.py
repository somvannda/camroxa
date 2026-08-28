"""Compact files-panel transport."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from features.create.constants import PLAYER_HEIGHT
from features.create.widgets.icons import create_icon
from shared.lib.ui_font import content_font


def _format_ms(value: int) -> str:
    seconds = max(0, int(value / 1000))
    return f"{seconds // 60}:{seconds % 60:02d}"


class AudioPlayer(QFrame):
    play_clicked = Signal()
    stop_clicked = Signal()
    back_clicked = Signal()
    next_clicked = Signal()
    seeked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Player")
        self.setFixedHeight(PLAYER_HEIGHT)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        meta = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(create_icon("music-4", size=16, color="#7C3AED").pixmap(16, 16))
        self.track = QLabel("No track selected")
        self.track.setObjectName("TrackTitle")
        self.track.setFont(content_font(12))
        self.time = QLabel("0:00 / 0:00")
        self.time.setObjectName("FieldLabel")
        self.time.setAlignment(Qt.AlignmentFlag.AlignRight)
        meta.addWidget(icon)
        meta.addWidget(self.track, 1)
        meta.addWidget(self.time)
        root.addLayout(meta)

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderReleased.connect(lambda: self.seeked.emit(self.progress.value()))
        root.addWidget(self.progress)

        transport = QHBoxLayout()
        transport.setSpacing(6)
        volume = QLabel()
        volume.setPixmap(create_icon("volume-2", size=14, color="#8FA4BB").pixmap(14, 14))
        transport.addWidget(volume)
        transport.addStretch(1)
        self.back = self._button("Back")
        self.play = self._button("Play", primary=True)
        self.stop = self._button("Stop")
        self.next = self._button("Next")
        self.back.clicked.connect(self.back_clicked.emit)
        self.play.clicked.connect(self.play_clicked.emit)
        self.stop.clicked.connect(self.stop_clicked.emit)
        self.next.clicked.connect(self.next_clicked.emit)
        transport.addWidget(self.back)
        transport.addWidget(self.play)
        transport.addWidget(self.stop)
        transport.addWidget(self.next)
        root.addLayout(transport)

    def _button(self, text: str, *, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("TransportPrimary" if primary else "Transport")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def set_track(self, title: str) -> None:
        self.track.setText(title or "No track selected")

    def set_playing(self, playing: bool) -> None:
        self.play.setText("Pause" if playing else "Play")

    def set_position(self, position: int, duration: int) -> None:
        self.time.setText(f"{_format_ms(position)} / {_format_ms(duration)}")
        if duration > 0 and not self.progress.isSliderDown():
            self.progress.setRange(0, duration)
            self.progress.setValue(position)
