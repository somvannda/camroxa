"""Studio AI Designer panel (doc 05) — prompt → Scene JSON."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class AiDesignerPanel(QWidget):
    generate_requested = Signal(str)
    modify_requested = Signal(str)
    improve_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("AI Designer")
        title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(title)
        hint = QLabel("AI edits Scene JSON only — never pixels.")
        hint.setObjectName(SUBTITLE_LABEL_ID)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._prompt = QLineEdit()
        self._prompt.setPlaceholderText("Futuristic purple EDM visualizer with lightning…")
        layout.addWidget(self._prompt)
        row = QHBoxLayout()
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
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

    def set_explanation(self, text: str) -> None:
        self._log.setPlainText(text)
