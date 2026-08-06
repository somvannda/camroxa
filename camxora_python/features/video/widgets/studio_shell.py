"""Composition Studio shell — scene tree + single inspector host."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from features.video.widgets.scene_tree import SCENE_TREE_KEYS, SceneTree
from shared.widgets.settings_ui import make_scrollable_tab_page


class VideoStudioShell(QWidget):
    """Left composition chrome: architecture tree + one inspector at a time.

    Template name / save / new live on the outer VideoLeftRail; this shell owns
    scene navigation and the inspector stack only.
    """

    node_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        inspectors: dict[str, QWidget] | None = None,
    ) -> None:
        super().__init__(parent)
        self._node_keys: list[str] = []
        self._key_to_index: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._tree = SceneTree()
        self._tree.node_selected.connect(self._on_node_selected)
        layout.addWidget(self._tree)

        self._stack = QStackedWidget()
        pages = inspectors or {}
        for key in SCENE_TREE_KEYS:
            page = pages.get(key)
            if page is None:
                page = QWidget()
            wrapped = make_scrollable_tab_page(page)
            idx = self._stack.addWidget(wrapped)
            self._node_keys.append(key)
            self._key_to_index[key] = idx

        layout.addWidget(self._stack, stretch=1)
        self.select_node("spectrum")

    def _on_node_selected(self, key: str) -> None:
        self._show_node(key)
        self.node_changed.emit(key)

    def _show_node(self, key: str) -> None:
        idx = self._key_to_index.get(key)
        if idx is not None:
            self._stack.setCurrentIndex(idx)

    def select_node(self, key: str) -> None:
        self._tree.select_node(key)
        self._show_node(key)

    def current_node(self) -> str:
        return self._tree.current_node()
