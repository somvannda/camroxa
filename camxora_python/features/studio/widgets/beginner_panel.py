"""Beginner mode (doc 06 Level 1) — theme/mood shortcuts into AI generate."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID


_THEMES = (
    ("cyberpunk edm neon lightning", "Cyberpunk"),
    ("festival edm confetti shake", "Festival"),
    ("cinematic fog god rays dolly", "Cinematic"),
    ("lofi calm mist drift ocean", "LoFi"),
    ("dark trap aggressive strobe", "Dark Trap"),
)


class BeginnerPanel(QWidget):
    generate_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Beginner — pick a look, generate a scene")
        title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(title)
        self._theme = QComboBox()
        for prompt, label in _THEMES:
            self._theme.addItem(label, prompt)
        layout.addWidget(self._theme)
        btn = QPushButton("Generate scene")
        btn.clicked.connect(lambda: self.generate_requested.emit(str(self._theme.currentData() or "")))
        layout.addWidget(btn)
        layout.addStretch()
