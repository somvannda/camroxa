"""Studio scene architecture tree."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from features.studio.lib.scene_document import SCENE_TREE_NODES


class StudioSceneTree(QWidget):
    node_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._list = QListWidget()
        for key, label in SCENE_TREE_NODES:
            item = QListWidgetItem(label)
            item.setData(int(Qt.ItemDataRole.UserRole), key)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._emit)
        layout.addWidget(self._list, stretch=1)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _emit(self, row: int) -> None:
        item = self._list.item(row)
        if item is None:
            return
        key = item.data(int(Qt.ItemDataRole.UserRole))
        if isinstance(key, str) and key:
            self.node_selected.emit(key)

    def select_node(self, key: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(int(Qt.ItemDataRole.UserRole)) == key:
                self._list.setCurrentRow(i)
                return

    def current_node(self) -> str:
        item = self._list.currentItem()
        if item is None:
            return SCENE_TREE_NODES[0][0]
        key = item.data(int(Qt.ItemDataRole.UserRole))
        return key if isinstance(key, str) else SCENE_TREE_NODES[0][0]
