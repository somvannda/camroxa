"""Studio track list — Video-style TRACK LIST card."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class StudioTrackList(QFrame):
    """Shows composition audio tracks; selecting one loads it for preview/export."""

    track_selected = Signal(str)
    add_tracks_requested = Signal()
    remove_track_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("TRACK LIST")
        title.setObjectName(SUBTITLE_LABEL_ID)
        header.addWidget(title)
        header.addStretch(1)
        self._add_btn = QPushButton("Add")
        self._add_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._add_btn.clicked.connect(self.add_tracks_requested.emit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._remove_btn.clicked.connect(self._emit_remove)
        header.addWidget(self._add_btn)
        header.addWidget(self._remove_btn)
        root.addLayout(header)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_activated)
        self._list.itemActivated.connect(self._on_activated)
        self._list.currentRowChanged.connect(self._on_row)
        root.addWidget(self._list, stretch=1)

        self._empty = QLabel("No preview music is attached yet.")
        self._empty.setObjectName(SUBTITLE_LABEL_ID)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)
        self._paths: list[str] = []

    def set_tracks(self, tracks: list[str], active_path: str = "") -> None:
        active = str(active_path or "").strip()
        paths = [str(p).strip() for p in tracks if str(p).strip()]
        if active and active not in paths:
            paths.insert(0, active)
        self._paths = paths
        blocked = self._list.blockSignals(True)
        self._list.clear()
        select_row = -1
        for i, path in enumerate(paths):
            item = QListWidgetItem(_display_name(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._list.addItem(item)
            if active and (_same_file(path, active) or path == active):
                select_row = i
        if select_row >= 0:
            self._list.setCurrentRow(select_row)
        self._list.blockSignals(blocked)
        empty = len(paths) == 0
        self._empty.setVisible(empty)
        self._list.setVisible(not empty)

    def _on_row(self, row: int) -> None:
        item = self._list.item(row)
        if item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if path:
            self.track_selected.emit(path)

    def _on_activated(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if path:
            self.track_selected.emit(path)

    def _emit_remove(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if path:
            self.remove_track_requested.emit(path)


def _display_name(path: str) -> str:
    try:
        return Path(path).name or path
    except Exception:
        return path


def _same_file(a: str, b: str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b
