"""Scene architecture tree — left-rail navigation for Composition Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID

# Architecture tree order (alignment doc). Palette is global at top.
SCENE_TREE_NODES: tuple[tuple[str, str], ...] = (
    ("palette", "Color Palette"),
    ("background", "Background"),
    ("spectrum", "Spectrum"),
    ("logo", "Logo"),
    ("text", "Text"),
    ("overlay", "Overlay"),
    ("particles", "Particles"),
    ("lighting", "Lighting"),
    ("camera", "Camera"),
    ("post", "Post"),
    ("audio_mapping", "Audio Mapping"),
)

SCENE_TREE_KEYS: tuple[str, ...] = tuple(key for key, _ in SCENE_TREE_NODES)


class SceneTree(QWidget):
    """Vertical scene-object list. Selecting a node shows its inspector."""

    node_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        caption = QLabel("Scene")
        caption.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(caption)

        self._list = QListWidget()
        self._list.setObjectName("compositionSceneTree")
        for key, label in SCENE_TREE_NODES:
            item = QListWidgetItem(label)
            item.setData(int(Qt.ItemDataRole.UserRole), key)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._emit_selection)
        root.addWidget(self._list, stretch=1)

        if self._list.count():
            self._list.setCurrentRow(0)

    def _emit_selection(self, row: int) -> None:
        item = self._list.item(row)
        if item is None:
            return
        key = item.data(int(Qt.ItemDataRole.UserRole))
        if isinstance(key, str) and key:
            self.node_selected.emit(key)

    def select_node(self, node_key: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(int(Qt.ItemDataRole.UserRole)) == node_key:
                self._list.setCurrentRow(i)
                return

    def current_node(self) -> str:
        item = self._list.currentItem()
        if item is None:
            return SCENE_TREE_KEYS[0]
        key = item.data(int(Qt.ItemDataRole.UserRole))
        return key if isinstance(key, str) else SCENE_TREE_KEYS[0]
