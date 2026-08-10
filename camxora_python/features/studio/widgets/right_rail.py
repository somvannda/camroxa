"""Studio right rail — Inspector (scene axes) + Developer JSON."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from features.studio.widgets.developer_json import DeveloperJsonPanel
from features.studio.widgets.inspector_host import InspectorHost
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel, make_scrollable_tab_page


class StudioRightRail(SettingsPanel):
    patch_requested = Signal(dict)
    json_apply_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(
            "Inspector",
            subtitle="",
            fill_available_height=True,
            parent=parent,
        )
        if hasattr(self, "_root"):
            self._root.setContentsMargins(6, 8, 6, 8)
            self._root.setSpacing(6)
        if hasattr(self, "_body"):
            self._body.setSpacing(6)

        self._selection = QLabel("Select a scene node")
        self._selection.setObjectName(SUBTITLE_LABEL_ID)
        self._selection.setWordWrap(False)
        self._selection.setFixedHeight(18)
        self.add_widget(self._selection)

        self._tabs = QTabWidget()
        self._inspector = InspectorHost()
        self._inspector.patch_requested.connect(self.patch_requested.emit)
        # Tight side inset so axis cards use most of the rail width.
        inspector_page = QWidget()
        inspector_layout = QVBoxLayout(inspector_page)
        inspector_layout.setContentsMargins(4, 8, 4, 8)
        inspector_layout.setSpacing(0)
        inspector_layout.addWidget(self._inspector, stretch=1)
        self._tabs.addTab(inspector_page, "Inspector")

        self._dev = DeveloperJsonPanel()
        self._dev.apply_json_requested.connect(self.json_apply_requested.emit)
        self._tabs.addTab(make_scrollable_tab_page(self._dev), "Developer")
        self.add_widget(self._tabs, stretch=1)

    def show_node(self, key: str) -> None:
        self._inspector.show_node(key)
        self._tabs.setCurrentIndex(0)
        label = key.replace("_", " ").title() if key else "Scene"
        self._selection.setText(f"Selected: {label}")

    def bind_document(self, state: dict) -> None:
        self._inspector.bind_all(state)

    def set_document(self, doc: dict) -> None:
        self._dev.set_document(doc)

    def set_selection_label(self, text: str) -> None:
        self._selection.setText(text or "Select a scene node on the left")
