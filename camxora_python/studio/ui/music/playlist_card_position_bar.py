"""Align preset buttons for the Minimal White playlist card on the preview."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from studio.core.playlist_layout import (
    _MINIMAL_WHITE_CARD_Y,
    _MINIMAL_WHITE_MARGIN_X,
    _minimal_white_card_size_norm,
)
from studio.core.playlist_settings import PlaylistSettings
from studio.render.compositor import DEFAULT_HEIGHT, DEFAULT_WIDTH
from studio.ui.icons.lucide_icons import ICON_COLOR, ICON_SZ_INSPECTOR_ALIGN, set_button_lucide_icon


class _AlignButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorAlignButton")
        self.setToolTip(tooltip)
        self.setFixedSize(28, 24)
        set_button_lucide_icon(self, icon_name, size=ICON_SZ_INSPECTOR_ALIGN, color=ICON_COLOR)


class PlaylistCardPositionBar(QWidget):
    position_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        align_row = QHBoxLayout()
        align_row.setContentsMargins(0, 0, 0, 0)
        align_row.setSpacing(2)

        specs = (
            ("align-left", "left", "Align left"),
            ("align-h-center", "center_h", "Align center"),
            ("align-right", "right", "Align right"),
            ("align-top", "top", "Align top"),
            ("align-v-center", "center_v", "Align middle"),
            ("align-bottom", "bottom", "Align bottom"),
        )
        for icon_name, key, tip in specs:
            btn = _AlignButton(icon_name, tip, self)
            btn.clicked.connect(lambda _=False, mode=key: self._align(mode))
            align_row.addWidget(btn)
        align_row.addStretch(1)
        root.addLayout(align_row)

        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset = QPushButton("Reset position")
        reset.setObjectName("GhostButton")
        reset.clicked.connect(self._reset)
        reset_row.addWidget(reset)
        reset_row.addStretch(1)
        root.addLayout(reset_row)

        self._settings: PlaylistSettings | None = None

    def bind_settings(self, settings: PlaylistSettings) -> None:
        self._settings = settings

    def _align(self, mode: str) -> None:
        if self._settings is None:
            return
        norm_w, norm_h = _minimal_white_card_size_norm(
            DEFAULT_WIDTH,
            DEFAULT_HEIGHT,
            self._settings,
        )
        layout = self._settings.component_layout.setdefault("song_list", {})
        margin_x = _MINIMAL_WHITE_MARGIN_X
        margin_y = _MINIMAL_WHITE_CARD_Y

        if mode == "left":
            layout["x"] = margin_x
            self._settings.list_side = "left"
        elif mode == "right":
            layout["x"] = round(1.0 - margin_x - norm_w, 4)
            self._settings.list_side = "right"
        elif mode == "center_h":
            layout["x"] = round(max(0.0, (1.0 - norm_w) / 2), 4)
        elif mode == "top":
            layout["y"] = margin_y
        elif mode == "center_v":
            layout["y"] = round(max(0.0, (1.0 - norm_h) / 2), 4)
        elif mode == "bottom":
            layout["y"] = round(max(0.0, 1.0 - margin_y - norm_h), 4)

        self.position_changed.emit()

    def _reset(self) -> None:
        if self._settings is None:
            return
        self._settings.component_layout.pop("song_list", None)
        self._settings.list_side = "right"
        self.position_changed.emit()
