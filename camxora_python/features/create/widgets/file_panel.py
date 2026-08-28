"""Files table and search, matching the standalone Create screen."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from features.create.constants import SAMPLE_FILES
from features.create.widgets.audio_player import AudioPlayer
from features.create.widgets.icons import create_icon
from shared.lib.ui_font import content_font


class FilePanel(QFrame):
    track_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("FILES")
        title.setObjectName("SectionLabel")
        refresh = QToolButton()
        refresh.setObjectName("FilesRefresh")
        refresh.setAutoRaise(True)
        refresh.setIcon(create_icon("refresh-cw", size=14, color="#8FA4BB"))
        refresh.setIconSize(QSize(14, 14))
        refresh.setToolTip("Refresh")
        refresh.setStyleSheet("QToolButton { background: transparent; border: none; padding: 2px; }")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(refresh)
        root.addLayout(header)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search older songs...")
        self.search.addAction(create_icon("search", size=14, color="#60758C"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("FileTable")
        self.table.setHorizontalHeaderLabels(["File", "Version", "MP3", "WAV", "LRC", "SRT", "State"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            header_view.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 96)
        self.table.setFont(content_font(15))
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.itemSelectionChanged.connect(self._emit_selection)
        root.addWidget(self.table, 1)

        self.player = AudioPlayer()
        root.addWidget(self.player)
        self._fill_rows()

    def _fill_rows(self) -> None:
        self.table.setRowCount(len(SAMPLE_FILES))
        for row, (name, version) in enumerate(SAMPLE_FILES):
            values = (name, version, "No", "No", "No", "No")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFont(content_font(15))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(row, col, item)
            placeholder = QTableWidgetItem("")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 6, placeholder)
            badge = QLabel("Ready")
            badge.setObjectName("StatusBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedHeight(16)
            badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            badge.setStyleSheet(
                "QLabel#StatusBadge {"
                " background-color: #00C878; color: #ffffff; border: none;"
                " border-radius: 3px; padding: 0 7px;"
                " font-size: 10px; font-weight: 600;"
                "}"
            )
            wrap = QWidget()
            wrap.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            wrap.setStyleSheet("background: transparent;")
            cell = QHBoxLayout(wrap)
            cell.setContentsMargins(4, 0, 4, 0)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.addWidget(badge)
            self.table.setCellWidget(row, 6, wrap)

    def _filter(self, query: str) -> None:
        needle = query.strip().lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            visible = (not needle) or (item is not None and needle in item.text().lower())
            self.table.setRowHidden(row, not visible)

    def _emit_selection(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        name = self.table.item(items[0].row(), 0)
        version = self.table.item(items[0].row(), 1)
        title = f"{name.text()} · {version.text()}" if name and version else "No track selected"
        self.player.set_track(title)
        self.track_selected.emit(title)

    def select_relative(self, delta: int) -> None:
        row = self.table.currentRow()
        target = max(0, min(self.table.rowCount() - 1, row + delta))
        self.table.selectRow(target)
