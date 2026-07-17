"""Compact toggle — matches InlineToggle.tsx (h-8, dot + label, fuchsia when pressed)."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class InlineToggle(QWidget):
    pressed_changed = Signal(bool)

    def __init__(self, label: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._button = QPushButton()
        self._button.setCheckable(True)
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.setObjectName("workflow_inline_toggle")
        self._button.setFixedHeight(32)
        self._button.toggled.connect(self._on_toggled)
        self._sync_button_text(False)
        layout.addWidget(self._button)

    def _sync_button_text(self, pressed: bool) -> None:
        dot = "●" if pressed else "○"
        self._button.setText(f" {dot}  {self._label}")

    def _on_toggled(self, checked: bool) -> None:
        name = "workflow_inline_toggle_pressed" if checked else "workflow_inline_toggle"
        self._button.setObjectName(name)
        self._button.style().unpolish(self._button)
        self._button.style().polish(self._button)
        self._sync_button_text(checked)
        self.pressed_changed.emit(checked)

    def set_pressed(self, pressed: bool) -> None:
        self._button.setChecked(pressed)

    def is_pressed(self) -> bool:
        return self._button.isChecked()
