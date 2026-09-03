"""Compact transport row above the timeline edit toolbar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from studio.ui.icons.lucide_icons import (
    BTN_SZ_ICON,
    BTN_SZ_PLAY,
    ICON_COLOR,
    ICON_COLOR_ON_ACCENT,
    ICON_SZ_PLAY,
    ICON_SZ_TRANSPORT,
    set_button_lucide_icon,
)


class TimelineTransportBar(QFrame):
    play_toggled = Signal(bool)
    step_back_requested = Signal()
    step_forward_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TimelineTransportBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(8)

        self.step_back_btn = QPushButton()
        self.step_back_btn.setObjectName("IconButton")
        self.step_back_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.step_back_btn.setToolTip("Previous frame")
        set_button_lucide_icon(self.step_back_btn, "skip-back", size=ICON_SZ_TRANSPORT, color=ICON_COLOR)
        layout.addWidget(self.step_back_btn)

        self.play_btn = QPushButton()
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setFixedSize(BTN_SZ_PLAY, BTN_SZ_PLAY)
        self.play_btn.setToolTip("Play / Pause (Space)")
        set_button_lucide_icon(self.play_btn, "play", size=ICON_SZ_PLAY, color=ICON_COLOR_ON_ACCENT)
        layout.addWidget(self.play_btn)

        self.step_fwd_btn = QPushButton()
        self.step_fwd_btn.setObjectName("IconButton")
        self.step_fwd_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.step_fwd_btn.setToolTip("Next frame")
        set_button_lucide_icon(self.step_fwd_btn, "skip-forward", size=ICON_SZ_TRANSPORT, color=ICON_COLOR)
        layout.addWidget(self.step_fwd_btn)

        self.time_label = QLabel("00:00.00 / 00:00.00")
        self.time_label.setObjectName("TimeLabel")
        layout.addWidget(self.time_label)

        layout.addStretch(1)

        self.play_btn.clicked.connect(self._on_play_clicked)
        self.step_back_btn.clicked.connect(self.step_back_requested.emit)
        self.step_fwd_btn.clicked.connect(self.step_forward_requested.emit)
        self._playing = False

    def _on_play_clicked(self) -> None:
        self.set_playing(not self._playing)
        self.play_toggled.emit(self._playing)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        set_button_lucide_icon(
            self.play_btn,
            "pause" if playing else "play",
            size=ICON_SZ_PLAY,
            color=ICON_COLOR_ON_ACCENT,
        )

    def set_time_text(self, text: str) -> None:
        self.time_label.setText(text)
