"""Music channel selection card."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from shared.models.auth import ProfileResponse
from shared.themes.deep_blue import PANEL_SCROLL_CONTENT_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import make_panel_scroll_area


class ChannelSelectionCard(QFrame):
    toggled = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title_label = QLabel(title.upper())
        title_label.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title_label)

        scroll = make_panel_scroll_area()
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_host = QWidget()
        self._list_host.setObjectName(PANEL_SCROLL_CONTENT_ID)
        self._list_host.setAutoFillBackground(False)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_host)
        root.addWidget(scroll, stretch=1)

        self._buttons: dict[str, QPushButton] = {}
        self._selected_ids: list[str] = []

    def set_profiles(self, profiles: list[ProfileResponse], selected_ids: list[str]) -> None:
        self._selected_ids = list(selected_ids)
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._buttons.clear()

        if not profiles:
            empty = QLabel("No profiles available yet.")
            empty.setObjectName(SUBTITLE_LABEL_ID)
            empty.setWordWrap(True)
            self._list_layout.addWidget(empty)
        else:
            for profile in profiles:
                button = QPushButton()
                button.setCheckable(True)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                button.clicked.connect(lambda checked=False, pid=profile.id: self.toggled.emit(pid))
                self._buttons[profile.id] = button
                self._list_layout.addWidget(button)
        self._refresh_buttons(profiles)

    def _refresh_buttons(self, profiles: list[ProfileResponse]) -> None:
        profile_map = {profile.id: profile for profile in profiles}
        for profile_id, button in self._buttons.items():
            profile = profile_map.get(profile_id)
            if profile is None:
                continue
            selected_index = self._selected_ids.index(profile_id) if profile_id in self._selected_ids else -1
            button.setChecked(selected_index >= 0)
            suffix = f" ({selected_index + 1})" if selected_index >= 0 else ""
            button.setText(f"{profile.name}{suffix}")
