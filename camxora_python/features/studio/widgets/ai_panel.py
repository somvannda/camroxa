"""Studio AI Designer panel (doc 05) — prompt → Scene JSON."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID


class AiDesignerPanel(QWidget):
    generate_requested = Signal(str)
    modify_requested = Signal(str)
    improve_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._prompt = QLineEdit()
        self._prompt.setPlaceholderText("Futuristic purple EDM visualizer with lightning…")
        layout.addWidget(self._prompt)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        gen = QPushButton("Generate")
        gen.clicked.connect(lambda: self.generate_requested.emit(self._prompt.text()))
        mod = QPushButton("Modify")
        mod.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        mod.clicked.connect(lambda: self.modify_requested.emit(self._prompt.text()))
        imp = QPushButton("Improve")
        imp.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        imp.clicked.connect(self.improve_requested.emit)
        row.addWidget(gen)
        row.addWidget(mod)
        row.addWidget(imp)
        layout.addLayout(row)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        self._log.setPlaceholderText("AI result…")
        layout.addWidget(self._log)

    def set_explanation(self, text: str) -> None:
        self._log.setPlainText(text)
