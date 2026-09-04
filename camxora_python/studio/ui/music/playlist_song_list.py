"""Drag-and-drop reorderable playlist song list (track + duration columns)."""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QPoint, Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QDropEvent, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from studio.core.models import MediaAsset
from studio.core.time_utils import fmt_time_ruler

_ROW_HEIGHT = 34
_TABLE_PAD = 6
_MAX_VISIBLE_ROWS = 12
_MIME_ROW = "application/x-camxora-playlist-row"
_DROP_LINE_COLOR = "#7466F1"


def _viewport_pos(table: QTableWidget, event) -> QPoint:
    """Map a table-widget drop/drag event position to viewport coordinates."""
    return table.viewport().mapFrom(table, event.position().toPoint())


def insertion_index_at_pos(table: QTableWidget, viewport_pos: QPoint) -> int:
    """Insert index 0..rowCount snapped to the nearest row boundary."""
    row_count = table.rowCount()
    if row_count == 0:
        return 0

    index = table.indexAt(viewport_pos)
    if not index.isValid():
        last_rect = table.visualRect(table.model().index(row_count - 1, 0))
        if not last_rect.isNull() and viewport_pos.y() >= last_rect.center().y():
            return row_count
        return 0

    rect = table.visualRect(index)
    if viewport_pos.y() < rect.center().y():
        return index.row()
    return index.row() + 1


def move_table_row(table: QTableWidget, drag_row: int, insert_at: int) -> int:
    """Move a full table row. Returns the new row index, or -1 when unchanged."""
    row_count = table.rowCount()
    if drag_row < 0 or drag_row >= row_count:
        return -1

    insert_at = max(0, min(insert_at, row_count))
    if insert_at == drag_row or insert_at == drag_row + 1:
        return -1

    row_items = [table.takeItem(drag_row, col) for col in range(table.columnCount())]
    table.removeRow(drag_row)
    if insert_at > drag_row:
        insert_at -= 1
    insert_at = max(0, min(insert_at, table.rowCount()))
    table.insertRow(insert_at)
    for col, item in enumerate(row_items):
        if item is not None:
            table.setItem(insert_at, col, item)
    if table.rowCount() != row_count:
        return -1
    return insert_at


class _DropLineOverlay(QWidget):
    """Purple snap line — transparent to mouse events."""

    def __init__(self, viewport: QWidget) -> None:
        super().__init__(viewport)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._line_y: int | None = None
        self.hide()

    def set_line_y(self, line_y: int | None) -> None:
        self._line_y = line_y
        if line_y is None:
            self.hide()
            return
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._line_y is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(_DROP_LINE_COLOR), 2)
        painter.setPen(pen)
        margin = 8
        right = max(margin + 1, self.width() - margin)
        y = self._line_y
        painter.drawLine(margin, y, right, y)
        dot_r = 3
        painter.setBrush(QColor(_DROP_LINE_COLOR))
        painter.drawEllipse(margin - dot_r, y - dot_r, dot_r * 2, dot_r * 2)
        painter.drawEllipse(right - dot_r, y - dot_r, dot_r * 2, dot_r * 2)
        painter.end()


class _ReorderableSongTable(QTableWidget):
    """Custom row drag with snap line indicator."""

    order_changed = Signal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self._drop_insert_at: int | None = None
        self._line_overlay = _DropLineOverlay(self.viewport())
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.viewport() and event.type() == QEvent.Type.Resize:
            if self._drop_insert_at is not None:
                self._line_overlay.setGeometry(self.viewport().rect())
        return super().eventFilter(obj, event)

    def startDrag(self, supportedActions) -> None:  # noqa: N802
        rows = sorted({index.row() for index in self.selectedIndexes()})
        drag_row = rows[0] if rows else self.currentRow()
        if drag_row < 0 or drag_row >= self.rowCount():
            return

        mime = QMimeData()
        mime.setData(_MIME_ROW, str(drag_row).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)
        self._clear_drop_indicator()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(_MIME_ROW):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasFormat(_MIME_ROW):
            event.ignore()
            return

        pos = _viewport_pos(self, event)
        insert_at = insertion_index_at_pos(self, pos)
        if insert_at != self._drop_insert_at:
            self._drop_insert_at = insert_at
            self._line_overlay.set_line_y(self._drop_line_y())

        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._clear_drop_indicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if not event.mimeData().hasFormat(_MIME_ROW):
            event.ignore()
            return

        try:
            drag_row = int(bytes(event.mimeData().data(_MIME_ROW)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            event.ignore()
            return

        pos = _viewport_pos(self, event)
        insert_at = insertion_index_at_pos(self, pos)
        self._clear_drop_indicator()

        new_row = move_table_row(self, drag_row, insert_at)
        if new_row < 0:
            event.ignore()
            return

        self.selectRow(new_row)
        event.acceptProposedAction()
        self.order_changed.emit()

    def _clear_drop_indicator(self) -> None:
        self._drop_insert_at = None
        self._line_overlay.set_line_y(None)

    def _drop_line_y(self) -> int | None:
        if self._drop_insert_at is None:
            return None

        insert_at = self._drop_insert_at
        row_count = self.rowCount()
        if row_count == 0:
            return 0

        if insert_at <= 0:
            rect = self.visualRect(self.model().index(0, 0))
            return rect.top() if not rect.isNull() else 0

        if insert_at >= row_count:
            rect = self.visualRect(self.model().index(row_count - 1, 0))
            return rect.bottom() if not rect.isNull() else self.viewport().height()

        rect = self.visualRect(self.model().index(insert_at, 0))
        return rect.top() if not rect.isNull() else None


class PlaylistSongList(QWidget):
    """Two-column song rows; drag to reorder."""

    order_changed = Signal(list)  # list[str] media ids

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._media_by_id: dict[str, MediaAsset] = {}
        self._table = _ReorderableSongTable(0, 2, self)
        self._table.setObjectName("PlaylistSongList")
        # Widget-level item styles so the selected row always uses the brand
        # purple regardless of any app/theme default selection color.
        self._table.setStyleSheet(
            "QTableWidget::item { border: none; padding: 6px 10px; }"
            "QTableWidget::item:hover { background: rgba(116, 102, 241, 0.18); }"
            "QTableWidget::item:selected { background: #7466F1; color: #ffffff; }"
        )
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setDragEnabled(True)
        self._table.setAcceptDrops(True)
        self._table.viewport().setAcceptDrops(True)
        self._table.setDropIndicatorShown(False)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.order_changed.connect(self._emit_order)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)

    def set_songs(
        self,
        song_ids: list[str],
        media_by_id: dict[str, MediaAsset],
        *,
        current_index: int | None = None,
    ) -> None:
        self._media_by_id = media_by_id
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        display_index = 0
        for media_id in song_ids:
            media = media_by_id.get(media_id)
            if media is None:
                continue
            display_index += 1
            row = self._table.rowCount()
            self._table.insertRow(row)
            display_name = media.name
            stem, ext = os.path.splitext(display_name)
            if ext.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"):
                display_name = stem
            title = QTableWidgetItem(f"{display_index:02d}  {display_name}")
            title.setData(Qt.ItemDataRole.UserRole, media_id)
            title.setToolTip(media.name)
            drag_flags = (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            title.setFlags(drag_flags)
            duration = QTableWidgetItem(fmt_time_ruler(media.duration or 0))
            duration.setData(Qt.ItemDataRole.UserRole, media_id)
            duration.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            duration.setFlags(drag_flags & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, title)
            self._table.setItem(row, 1, duration)
        if current_index is not None and 0 <= current_index < self._table.rowCount():
            self._table.selectRow(current_index)
        self._table.blockSignals(False)
        self._update_height()

    def _update_height(self) -> None:
        rows = self._table.rowCount()
        if rows <= 0:
            self._table.setFixedHeight(0)
            self.setFixedHeight(0)
            return
        visible = min(rows, _MAX_VISIBLE_ROWS)
        height = visible * _ROW_HEIGHT + _TABLE_PAD
        self._table.setFixedHeight(height)
        self.setFixedHeight(height)

    def song_ids(self) -> list[str]:
        ids: list[str] = []
        for row in range(self._table.rowCount()):
            media_id = None
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is None:
                    continue
                media_id = item.data(Qt.ItemDataRole.UserRole)
                if media_id:
                    break
            if media_id:
                ids.append(str(media_id))
        return ids

    def renumber_rows(self) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            text = item.text()
            if "  " in text:
                _, name = text.split("  ", 1)
            else:
                name = text
            item.setText(f"{row + 1:02d}  {name}")

    def _emit_order(self, *args: object) -> None:
        ids = self.song_ids()
        if len(ids) != self._table.rowCount():
            return
        self.order_changed.emit(ids)

    def set_current_index(self, index: int | None) -> None:
        if index is None or index < 0 or index >= self._table.rowCount():
            return
        self._table.selectRow(index)
