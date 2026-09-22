"""Two-tier tab chrome for the clip inspector (CapCut-style)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from studio.app.selection_style import inspector_tab_style


class InspectorTabRow(QFrame):
    tab_changed = Signal(int)

    def __init__(self, labels: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorTabRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._buttons: list[QPushButton] = []
        for index, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setObjectName("InspectorTabButton")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.clicked.connect(lambda _checked, idx=index: self._select(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)
        layout.addStretch(1)
        if self._buttons:
            self._select(0)

    def _sync_tab_styles(self) -> None:
        for btn in self._buttons:
            btn.setStyleSheet(inspector_tab_style(checked=btn.isChecked()))

    def _select(self, index: int) -> None:
        for idx, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(idx == index)
            btn.blockSignals(False)
        self._sync_tab_styles()
        self.tab_changed.emit(index)

    def set_active_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._select(index)

    def active_index(self) -> int:
        try:
            import shiboken6

            for idx, btn in enumerate(self._buttons):
                if shiboken6.isValid(btn) and btn.isChecked():
                    return idx
        except RuntimeError:
            pass
        return 0

    def set_tab_tooltip(self, label: str, tooltip: str) -> None:
        for btn in self._buttons:
            if btn.text() == label:
                btn.setToolTip(tooltip)
                return

    def set_visible_tabs(self, labels: tuple[str, ...]) -> None:
        """Rebuild row when tier-2 tabs change."""
        parent_layout = self.layout()
        while parent_layout.count():
            item = parent_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._buttons.clear()
        for index, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setObjectName("InspectorTabButton")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.clicked.connect(lambda _checked, idx=index: self._select(idx))
            parent_layout.insertWidget(index, btn)
            self._buttons.append(btn)
        if self._buttons:
            self._select(0)


class PlaceholderInspectorPage(QWidget):
    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        label = QLabel(hint)
        label.setObjectName("EmptyHint")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
