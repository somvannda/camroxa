"""CC Lyric and Layout tabs — lightweight scene-graph component list."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from studio.core.playlist_settings import COMPONENT_LABELS, PLAYLIST_COMPONENTS, PlaylistSettings
from studio.ui.inspector_layout import FIELD_GAP, SECTION_GAP


class PlaylistSceneComponentsPanel(QWidget):
    """Select playlist scene components (shared with preview overlay)."""

    component_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = PlaylistSettings()
        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SECTION_GAP)

        hint = QLabel(
            "Scene components rendered on the timeline and in preview. "
            "Select a block to highlight it in the position editor (Settings → Position)."
        )
        hint.setWordWrap(True)
        hint.setObjectName("InspectorHint")
        layout.addWidget(hint)

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(FIELD_GAP)
        layout.addWidget(self._list_host)
        layout.addStretch(1)

    def bind_settings(self, settings: PlaylistSettings) -> None:
        self._settings = settings
        self._rebuild()

    def _rebuild(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._buttons.clear()

        order = self._settings.component_order or list(PLAYLIST_COMPONENTS)
        selected = self._settings.selected_component
        for comp_id in order:
            if comp_id not in PLAYLIST_COMPONENTS:
                continue
            label = COMPONENT_LABELS.get(comp_id, comp_id)
            btn = QPushButton(label)
            btn.setObjectName("GhostButton")
            btn.setCheckable(True)
            btn.setChecked(comp_id == selected)
            btn.clicked.connect(lambda _checked=False, cid=comp_id: self._on_pick(cid))
            self._list_layout.addWidget(btn)
            self._buttons[comp_id] = btn

    def _on_pick(self, component_id: str) -> None:
        for cid, btn in self._buttons.items():
            btn.blockSignals(True)
            btn.setChecked(cid == component_id)
            btn.blockSignals(False)
        self.component_selected.emit(component_id)
