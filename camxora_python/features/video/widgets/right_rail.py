"""Video workspace right rail — Album and Playlist text domains."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from features.video.widgets.asset_summary import WorkspaceAssetSummary
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel, make_scrollable_tab_page


class VideoRightRail(SettingsPanel):
    side_tab_changed = Signal(str)

    _SIDE_TABS = (
        ("album", "Album"),
        ("title", "Playlist"),
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        tab_pages: dict[str, QWidget] | None = None,
    ) -> None:
        super().__init__(
            "Inspector",
            subtitle="Album and Playlist text domains",
            fill_available_height=True,
            parent=parent,
        )
        if hasattr(self, "_root"):
            self._root.setContentsMargins(10, 10, 10, 10)
            self._root.setSpacing(8)
        self._selection_badge = QLabel("No selection")
        self._selection_badge.setObjectName(SUBTITLE_LABEL_ID)
        self.add_action(self._selection_badge)

        self._asset_summary = WorkspaceAssetSummary()
        self.add_widget(self._asset_summary)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._emit_side_tab)
        self._tabs.tabBarClicked.connect(self._on_tab_bar_clicked)
        tab_pages = tab_pages or {}
        for key, label in self._SIDE_TABS:
            custom_page = tab_pages.get(key)
            if custom_page is not None:
                page = make_scrollable_tab_page(custom_page)
            else:
                page = QWidget()
                layout = QVBoxLayout(page)
                layout.setContentsMargins(8, 8, 8, 8)
                phase = "9f" if key == "export" else "9b"
                placeholder = QLabel(f"{label} panel — Phase {phase}")
                placeholder.setObjectName(SUBTITLE_LABEL_ID)
                placeholder.setWordWrap(True)
                layout.addWidget(placeholder)
                layout.addStretch()
            self._tabs.addTab(page, label)
        self.add_widget(self._tabs, stretch=1)

    def _emit_side_tab(self, index: int) -> None:
        if 0 <= index < len(self._SIDE_TABS):
            self.side_tab_changed.emit(self._SIDE_TABS[index][0])

    def _on_tab_bar_clicked(self, index: int) -> None:
        # Re-clicking the active Album/Playlist tab still enables preview drag focus.
        if 0 <= index < len(self._SIDE_TABS):
            self.side_tab_changed.emit(self._SIDE_TABS[index][0])

    def set_selection_label(self, label: str) -> None:
        self._selection_badge.setText(label)

    def bind_asset_summary(self, **kwargs) -> None:
        self._asset_summary.bind_asset_summary(**kwargs)

    def select_side_tab(self, tab_key: str) -> None:
        for index, (key, _label) in enumerate(self._SIDE_TABS):
            if key == tab_key:
                self._tabs.setCurrentIndex(index)
                return
