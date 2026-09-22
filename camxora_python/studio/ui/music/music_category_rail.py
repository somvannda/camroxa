"""Vertical category rail for the Music library (Kcut-style text tabs)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from studio.app.theme import PALETTE

MUSIC_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("all", "All"),
    ("ring", "Ring"),
    ("bars", "Bars"),
    ("wave", "Wave"),
    ("vinyl", "Vinyl"),
    ("lyric", "Lyric"),
    ("playlist", "Playlist"),
)


class MusicCategoryRail(QFrame):
    category_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MusicCategoryRail")
        self.setFixedWidth(72)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 10)
        layout.setSpacing(2)
        self._buttons: list[QPushButton] = []
        self._keys: list[str] = []
        for key, label in MUSIC_CATEGORIES:
            btn = QPushButton(label)
            btn.setObjectName("MusicCategoryButton")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c, k=key: self._select(k))
            layout.addWidget(btn)
            self._buttons.append(btn)
            self._keys.append(key)
        layout.addStretch(1)
        self._select("all")

    def _style_btn(self, btn: QPushButton, active: bool) -> None:
        if active:
            btn.setStyleSheet(
                f"QPushButton#MusicCategoryButton {{ background: {PALETTE.accent};"
                f" color: #ffffff; border: none; border-radius: 8px;"
                f" padding: 8px 4px; font-size: 11px; font-weight: 600; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton#MusicCategoryButton {{ background: transparent;"
                f" color: {PALETTE.text_dimmer}; border: none; border-radius: 8px;"
                f" padding: 8px 4px; font-size: 11px; font-weight: 600; }}"
                f"QPushButton#MusicCategoryButton:hover {{ color: {PALETTE.text};"
                f" background: {PALETTE.panel2}; }}"
            )

    def _select(self, key: str) -> None:
        for btn, k in zip(self._buttons, self._keys, strict=True):
            self._style_btn(btn, k == key)
        self.category_changed.emit(key)

    def set_active(self, key: str) -> None:
        if key in self._keys:
            self._select(key)
