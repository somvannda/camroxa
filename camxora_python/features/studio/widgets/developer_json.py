"""Developer mode — raw JSON synced with the composition document."""

from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class DeveloperJsonPanel(QWidget):
    apply_json_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        caption = QLabel("Developer — Scene JSON")
        caption.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(caption)
        self._editor = QTextEdit()
        self._editor.setAcceptRichText(False)
        layout.addWidget(self._editor, stretch=1)
        self._status = QLabel("")
        self._status.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._status)
        apply_btn = QPushButton("Apply JSON")
        apply_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        apply_btn.clicked.connect(self._emit_apply)
        layout.addWidget(apply_btn)

    def set_document(self, doc: dict) -> None:
        self._editor.setPlainText(json.dumps(doc, indent=2))
        self._status.setText("Synced")

    def _emit_apply(self) -> None:
        try:
            data = json.loads(self._editor.toPlainText())
        except json.JSONDecodeError as exc:
            self._status.setText(f"Invalid JSON: {exc}")
            return
        if not isinstance(data, dict):
            self._status.setText("Root must be an object")
            return
        self.apply_json_requested.emit(data)
        self._status.setText("Applied")
