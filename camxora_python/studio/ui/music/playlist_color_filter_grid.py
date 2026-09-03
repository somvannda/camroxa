"""Solid color-set chips for the Playlist Settings tab."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QVBoxLayout, QWidget

from studio.core.playlist_color_filters import COLOR_FILTERS_BY_ID, PLAYLIST_COLOR_FILTERS
from studio.core.playlist_palette import palette_chip_stylesheet
from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_style import apply_style_to_settings
from studio.ui.inspector_layout import FIELD_GAP

_COLS = 6
_MIN_CHIP = 30
_MAX_CHIP = 44
_GRID_SPACING = 8


class PlaylistColorFilterGrid(QWidget):
    style_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = PlaylistSettings()
        self._filter_buttons: dict[str, QPushButton] = {}
        self._chip_size = _MIN_CHIP

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(FIELD_GAP)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(_GRID_SPACING)
        self._grid.setVerticalSpacing(_GRID_SPACING)
        for index, filt in enumerate(PLAYLIST_COLOR_FILTERS):
            btn = QPushButton()
            btn.setFixedSize(_MIN_CHIP, _MIN_CHIP)
            btn.setToolTip(filt.name)
            btn.setObjectName("PlaylistColorFilterChip")
            btn.clicked.connect(lambda _=False, fid=filt.id: self._on_filter_clicked(fid))
            self._filter_buttons[filt.id] = btn
            self._grid.addWidget(btn, index // _COLS, index % _COLS)
        layout.addLayout(self._grid)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_chip_size()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_chip_size()

    def _apply_chip_size(self) -> None:
        available = max(0, self.width())
        chip = (available - _GRID_SPACING * (_COLS - 1)) // _COLS
        chip = max(_MIN_CHIP, min(_MAX_CHIP, chip))
        if chip == self._chip_size:
            return
        self._chip_size = chip
        for btn in self._filter_buttons.values():
            btn.setFixedSize(chip, chip)

    def load_settings(self, settings: PlaylistSettings) -> None:
        self._settings = settings
        filt_id = settings.color_filter_id or "original"
        is_custom = filt_id == "custom"
        for fid, btn in self._filter_buttons.items():
            filt = COLOR_FILTERS_BY_ID[fid]
            btn.setStyleSheet(
                palette_chip_stylesheet(filt.palette, selected=(not is_custom and fid == filt_id))
            )

    def settings(self) -> PlaylistSettings:
        return self._settings

    def _on_filter_clicked(self, filter_id: str) -> None:
        if filter_id not in COLOR_FILTERS_BY_ID:
            return
        self._settings.color_filter_id = filter_id
        apply_style_to_settings(self._settings)
        self.load_settings(self._settings)
        self.style_changed.emit()
