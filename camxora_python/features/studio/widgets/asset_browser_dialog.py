"""Asset Library as a discovery drawer (not a second scene-tree picker)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from features.studio.widgets.asset_library import AssetLibraryPanel


class AssetBrowserDialog(QDialog):
    """Modal browse/search surface for catalog discovery (doc 08)."""

    apply_requested = Signal(dict)
    favorite_toggled = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Browse assets")
        self.setModal(False)
        self.resize(460, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self._panel = AssetLibraryPanel()
        self._panel.apply_requested.connect(self.apply_requested.emit)
        self._panel.favorite_toggled.connect(self.favorite_toggled.emit)
        layout.addWidget(self._panel, stretch=1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def set_favorites(self, ids: list[str] | set[str]) -> None:
        self._panel.set_favorites(ids)

    def set_context_node(self, node_key: str | None) -> None:
        self._panel.set_context_node(node_key)
