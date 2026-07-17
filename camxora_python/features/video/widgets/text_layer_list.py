"""Text layer list controls — port of TextLayerListPanel."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.text_settings import TEXT_PRESET_OPTIONS
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import note_box


class TextLayerListPanel(QWidget):
    add_requested = Signal()
    duplicate_requested = Signal()
    delete_requested = Signal()
    move_up_requested = Signal()
    move_down_requested = Signal()
    preset_apply_requested = Signal(str)
    preset_restore_requested = Signal()
    overlay_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._overlay_count = 0
        self._selected_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_requested.emit)
        toolbar.addWidget(add_btn)

        self._preset_combo = QComboBox()
        self._preset_combo.addItem("Presets", "")
        for value, label in TEXT_PRESET_OPTIONS:
            self._preset_combo.addItem(label, value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        toolbar.addWidget(self._preset_combo)

        restore_btn = QPushButton("Restore")
        restore_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        restore_btn.setToolTip("Reset the last applied text preset to factory defaults.")
        restore_btn.clicked.connect(self.preset_restore_requested.emit)
        toolbar.addWidget(restore_btn)

        for label, signal in (
            ("Duplicate", self.duplicate_requested),
            ("Delete", self.delete_requested),
            ("Up", self.move_up_requested),
            ("Down", self.move_down_requested),
        ):
            button = QPushButton(label)
            button.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            button.clicked.connect(signal.emit)
            toolbar.addWidget(button)
            if label == "Duplicate":
                self._duplicate_btn = button
            elif label == "Delete":
                self._delete_btn = button
            elif label == "Up":
                self._up_btn = button
            else:
                self._down_btn = button

        toolbar_host = QWidget()
        toolbar_host.setLayout(toolbar)
        root.addWidget(toolbar_host)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self._list)

        self._empty_state = note_box("No text layers yet. Use Add or Presets to create one.")
        root.addWidget(self._empty_state)

    def _on_preset_changed(self, _index: int) -> None:
        if self._binding:
            return
        preset = self._preset_combo.currentData()
        if isinstance(preset, str) and preset:
            self.preset_apply_requested.emit(preset)
            self._binding = True
            self._preset_combo.setCurrentIndex(0)
            self._binding = False

    def _on_row_changed(self, row: int) -> None:
        if self._binding or row < 0:
            return
        self.overlay_selected.emit(row)

    def bind_overlays(self, overlays: list[dict], *, selected_index: int) -> None:
        self._binding = True
        try:
            self._overlay_count = len(overlays)
            self._selected_index = selected_index
            has_layers = bool(overlays)
            self._list.setVisible(has_layers)
            self._empty_state.setVisible(not has_layers)
            self._list.clear()

            for index, overlay in enumerate(overlays):
                title = str(overlay.get("text") or "").strip().split("\n", maxsplit=1)[0].strip()
                if not title:
                    title = f"Text {index + 1}"
                start = round(float(overlay.get("startSec") or 0))
                duration = round(float(overlay.get("durationSec") or 0))
                font_size = round(float(overlay.get("fontSize") or 0))
                enabled = "●" if overlay.get("enabled") else "○"
                item = QListWidgetItem(
                    f"{enabled} {title}\n{start}s · {duration}s · {font_size}px"
                )
                self._list.addItem(item)

            if has_layers and 0 <= selected_index < len(overlays):
                self._list.setCurrentRow(selected_index)

            has_selection = has_layers and 0 <= selected_index < len(overlays)
            self._duplicate_btn.setEnabled(has_selection)
            self._delete_btn.setEnabled(has_selection)
            self._up_btn.setEnabled(has_selection and selected_index > 0)
            self._down_btn.setEnabled(has_selection and selected_index < len(overlays) - 1)
        finally:
            self._binding = False
