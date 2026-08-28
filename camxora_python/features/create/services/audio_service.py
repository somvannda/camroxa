"""Thin QMediaPlayer wrapper for the Files panel transport."""

from __future__ import annotations

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioService(QObject):
    position_changed = Signal(int, int)
    playing_changed = Signal(bool)
    track_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self._emit_position)
        self.player.durationChanged.connect(self._emit_position)
        self.player.playbackStateChanged.connect(
            lambda state: self.playing_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)
        )

    def set_track(self, title: str, path: str = "") -> None:
        self.track_changed.emit(title or "No track selected")
        if path:
            self.player.setSource(QUrl.fromLocalFile(path))
        else:
            self.player.setSource(QUrl())

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.player.source().isEmpty():
            self.playing_changed.emit(True)
            self.playing_changed.emit(False)
        else:
            self.player.play()

    def stop(self) -> None:
        self.player.stop()

    def seek(self, position: int) -> None:
        self.player.setPosition(position)

    def _emit_position(self, *_args) -> None:
        self.position_changed.emit(int(self.player.position()), int(self.player.duration()))
