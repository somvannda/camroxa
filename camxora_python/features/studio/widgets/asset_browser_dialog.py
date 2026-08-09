"""Asset Library as a discovery drawer (not a second scene-tree picker)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from features.studio.widgets.asset_library import AssetLibraryPanel


class AssetBrowserDialog(QDialog):
    """Modal browse/search surface for catalog discovery (doc 08)."""

    apply_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Browse assets")
        self.setModal(True)
        self.resize(420, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self._panel = AssetLibraryPanel()
        self._panel.apply_requested.connect(self._on_apply)
        layout.addWidget(self._panel, stretch=1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _on_apply(self, patch: dict) -> None:
        self.apply_requested.emit(patch)
        # Keep open so creators can apply several assets while searching.
