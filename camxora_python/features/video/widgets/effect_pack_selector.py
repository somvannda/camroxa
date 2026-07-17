"""Effect pack selector card — port of EffectPackSelectorCard.tsx."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID

class EffectPackSelector(QWidget):
    apply_requested = Signal(str)
    clear_requested = Signal()
    install_requested = Signal()
    reload_requested = Signal()
    toggle_enabled_requested = Signal()
    activate_requested = Signal()
    remove_requested = Signal()

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        show_apply_combo: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._binding = False
        self._status: dict | None = None
        self._show_apply_combo = show_apply_combo

        card = QFrame()
        card.setObjectName("account_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName(SUBTITLE_LABEL_ID)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName(SUBTITLE_LABEL_ID)
        subtitle_label.setWordWrap(True)
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        self._status_badge = QLabel("none")
        self._status_badge.setObjectName(SUBTITLE_LABEL_ID)
        header.addLayout(title_col, stretch=1)
        header.addWidget(self._status_badge)
        layout.addLayout(header)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._combo.setVisible(show_apply_combo)
        layout.addWidget(self._combo)

        self._message = QLabel("")
        self._message.setObjectName(SUBTITLE_LABEL_ID)
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        self._install_btn = QPushButton("Install ZIP")
        self._install_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._install_btn.clicked.connect(self.install_requested.emit)
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._reload_btn.clicked.connect(self.reload_requested.emit)
        self._clear_btn = QPushButton("Clear Pack")
        self._clear_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._clear_btn.clicked.connect(self.clear_requested.emit)
        self._toggle_btn = QPushButton("Enable")
        self._toggle_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._toggle_btn.clicked.connect(self.toggle_enabled_requested.emit)
        self._activate_btn = QPushButton("Activate")
        self._activate_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._activate_btn.clicked.connect(self.activate_requested.emit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._remove_btn.clicked.connect(self.remove_requested.emit)
        for button in (
            self._install_btn,
            self._reload_btn,
            self._clear_btn,
            self._toggle_btn,
            self._activate_btn,
            self._remove_btn,
        ):
            actions.addWidget(button)
        action_host = QWidget()
        action_host.setAutoFillBackground(False)
        action_host.setLayout(actions)
        layout.addWidget(action_host)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card)

    def _on_combo_changed(self, _index: int) -> None:
        if self._binding:
            return
        value = self._combo.currentData()
        if isinstance(value, str) and value:
            self.apply_requested.emit(value)

    def bind_state(
        self,
        *,
        options: list[dict[str, str]],
        selected_value: str,
        status: dict,
        busy: bool,
    ) -> None:
        self._binding = True
        try:
            self._status = status
            selection = status.get("selection")
            badge = str(status.get("status") or ("none" if not selection else "missing"))
            self._status_badge.setText(badge)
            self._message.setText(str(status.get("message") or ""))

            self._combo.blockSignals(True)
            self._combo.clear()
            self._combo.addItem("Select an installed pack", "")
            for option in options:
                self._combo.addItem(option["label"], option["value"])
            if selected_value:
                index = self._combo.findData(selected_value)
                if index >= 0:
                    self._combo.setCurrentIndex(index)
            self._combo.blockSignals(False)

            item = status.get("item") if isinstance(status.get("item"), dict) else None
            has_selection = bool(selection)
            self._clear_btn.setEnabled(has_selection and not busy)
            self._install_btn.setEnabled(not busy)
            self._reload_btn.setEnabled(not busy)

            has_item = item is not None
            self._toggle_btn.setVisible(has_item)
            self._remove_btn.setVisible(has_item)
            self._activate_btn.setVisible(bool(has_item and not item.get("active")))
            if has_item:
                self._toggle_btn.setText("Disable" if item.get("enabled") else "Enable")
                self._toggle_btn.setEnabled(not busy)
                self._remove_btn.setEnabled(not busy)
                self._activate_btn.setEnabled(not busy)
            self._combo.setEnabled(not busy)
        finally:
            self._binding = False
