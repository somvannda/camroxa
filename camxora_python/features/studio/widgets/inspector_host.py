"""Inspector host — one scrollable panel for the selected scene node."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from features.studio.lib.scene_document import SCENE_TREE_NODES
from features.studio.widgets.inspectors import _AxisPanel, build_studio_inspectors
from shared.widgets.settings_ui import make_scrollable_tab_page


class InspectorHost(QWidget):
    patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._inspectors = build_studio_inspectors()
        self._key_to_index: dict[str, int] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        for key, _label in SCENE_TREE_NODES:
            panel = self._inspectors[key]
            panel.patch_requested.connect(self.patch_requested.emit)
            wrapped = make_scrollable_tab_page(panel)
            idx = self._stack.addWidget(wrapped)
            self._key_to_index[key] = idx
        layout.addWidget(self._stack)

    def show_node(self, key: str) -> None:
        idx = self._key_to_index.get(key)
        if idx is not None:
            self._stack.setCurrentIndex(idx)

    def bind_all(self, state: dict) -> None:
        for panel in self._inspectors.values():
            panel.bind(state)

    def inspector(self, key: str) -> _AxisPanel | None:
        return self._inspectors.get(key)
