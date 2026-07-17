"""Music history card."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import QDate, Qt, Signal, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from shared.lib.formatting import format_datetime_label, format_run_date_label, today_ymd
from shared.lib.music_history_labels import is_song_title_generating
from shared.models.platform import MusicHistoryBatch, MusicHistorySong
from shared.themes.deep_blue import SHELL_DATE_EDIT_ID, SUBTITLE_LABEL_ID
from shared.widgets.data_table import create_data_table

EMPTY_MESSAGE = "No history rows match the current filters."


def batch_retry_targets(batch: MusicHistoryBatch) -> tuple[list[str], list[str]]:
    """Return (draft_failed ids, suno_failed ids) for batch-level retry."""
    draft_ids: list[str] = []
    suno_ids: list[str] = []
    for song in batch.songs:
        song_status = str(song.status or "").strip().lower()
        suno_status = str(song.suno_status or "").strip().lower()
        if song_status == "draft_failed":
            draft_ids.append(song.song_id)
        if song_status == "suno_failed" or suno_status == "suno_failed":
            suno_ids.append(song.song_id)
    return draft_ids, suno_ids

# Default widths aligned with MusicWorkspacePage.tsx; stretch columns grow with the card.
_HISTORY_FIXED_COLUMN_WIDTHS = {
    0: 60,
    4: 170,
    5: 170,
    6: 170,
    7: 170,
    8: 110,
}
_HISTORY_STRETCH_COLUMNS = (1, 2, 3)  # album 1, album 2, Title — Run date uses stretchLastSection
_HISTORY_COL_ALBUM_1 = 1
_HISTORY_COL_ALBUM_2 = 2
_HISTORY_COL_TITLE = 3
_HISTORY_COL_PRIMARY = 6
_HISTORY_COL_SECONDARY = 7
_HISTORY_COLUMN_COUNT = 10
_HISTORY_SONG_ROW_HEIGHT = 36
_HISTORY_BATCH_SEPARATOR_ROW_HEIGHT = 26
_BATCH_SEPARATOR_BG = QColor(96, 165, 250, 36)
_BATCH_SEPARATOR_FG = QColor("#93c5fd")


@dataclass(frozen=True, slots=True)
class HistoryRow:
    batch: MusicHistoryBatch
    song: MusicHistorySong | None = None
    row_number: int | None = None
    is_batch_separator: bool = False


class GeneratingTitleCell(QWidget):
    """Animated Generating... label for in-progress draft rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._title = QLabel("Generating.")
        self._title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._title, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(450)

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 3
        self._title.setText("Generating" + "." * (self._phase + 1))


class HistoryCard(QFrame):
    filters_changed = Signal()
    row_selected = Signal(object)
    open_folder_requested = Signal(str, str)
    retry_draft_requested = Signal(object)
    retry_suno_requested = Signal(object)
    enqueue_images_requested = Signal(object)
    continue_video_requested = Signal(object)
    retry_batch_requested = Signal(str, list, list)
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("HISTORY")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        filters = QHBoxLayout()
        today = QDate.fromString(today_ymd(), "yyyy-MM-dd")
        self._date_filter_active = True
        self._from_date = QDateEdit()
        self._from_date.setObjectName(SHELL_DATE_EDIT_ID)
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(today)
        self._to_date = QDateEdit()
        self._to_date.setObjectName(SHELL_DATE_EDIT_ID)
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(today)
        self._last_batch = QCheckBox("Last batch")
        show_all = QPushButton("Show all")
        show_all.clicked.connect(self._clear_filters)
        filters.addWidget(QLabel("From"))
        filters.addWidget(self._from_date)
        filters.addWidget(QLabel("To"))
        filters.addWidget(self._to_date)
        filters.addWidget(self._last_batch)
        filters.addWidget(show_all)
        filters.addStretch()
        root.addLayout(filters)

        meta = QHBoxLayout()
        self._summary = QLabel("No history yet.")
        self._summary.setObjectName(SUBTITLE_LABEL_ID)
        self._updated = QLabel("Updated —")
        self._updated.setObjectName(SUBTITLE_LABEL_ID)
        meta.addWidget(self._summary, stretch=1)
        meta.addWidget(self._updated)
        root.addLayout(meta)

        self._table = create_data_table(
            [
                "No",
                "album 1",
                "album 2",
                "Title",
                "Description",
                "Structure",
                "Primary Channel",
                "Secondary Channel",
                "Suno",
                "Run date",
            ]
        )
        self._table.setObjectName("history_data_table")
        self._table.setAlternatingRowColors(False)
        self._table.setMinimumHeight(240)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vertical_header = self._table.verticalHeader()
        vertical_header.setDefaultSectionSize(_HISTORY_SONG_ROW_HEIGHT)
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(80)
        for index, width in _HISTORY_FIXED_COLUMN_WIDTHS.items():
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
            self._table.setColumnWidth(index, width)
        for index in _HISTORY_STRETCH_COLUMNS:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(_HISTORY_COL_ALBUM_1, 150)
        self._table.setColumnWidth(_HISTORY_COL_ALBUM_2, 150)
        self._table.setColumnWidth(_HISTORY_COL_TITLE, 220)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.setMouseTracking(True)
        self._table.viewport().setMouseTracking(True)
        root.addWidget(self._table, stretch=1)

        self._table_rows: list[HistoryRow] = []
        self._selected_song_id: str | None = None

        self._from_date.dateChanged.connect(self._on_date_filter_changed)
        self._to_date.dateChanged.connect(self._on_date_filter_changed)
        self._last_batch.stateChanged.connect(lambda *_: self.filters_changed.emit())

    def _on_date_filter_changed(self) -> None:
        self._date_filter_active = True
        self.filters_changed.emit()

    def _clear_filters(self) -> None:
        self._date_filter_active = False
        self._last_batch.setChecked(False)
        self.filters_changed.emit()

    def filter_values(self) -> dict[str, object]:
        if not self._date_filter_active:
            return {
                "from_date": "",
                "to_date": "",
                "last_batch_only": self._last_batch.isChecked(),
            }
        return {
            "from_date": self._from_date.date().toString("yyyy-MM-dd"),
            "to_date": self._to_date.date().toString("yyyy-MM-dd"),
            "last_batch_only": self._last_batch.isChecked(),
        }

    def set_summary(self, summary: str, updated_at: str | None) -> None:
        self._summary.setText(summary)
        self._updated.setText(f"Updated {format_datetime_label(updated_at)}")

    def set_rows(self, rows: list[HistoryRow], selected_song_id: str | None) -> None:
        self._table_rows = rows
        self._selected_song_id = selected_song_id
        self._table.clearSpans()
        self._table.clearContents()
        if not rows:
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, _HISTORY_COLUMN_COUNT)
            item = QTableWidgetItem(EMPTY_MESSAGE)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(0, 0, item)
            return

        self._table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            if entry.is_batch_separator:
                self._table.setItem(row_index, 0, self._make_batch_separator_item(entry.batch))
                self._table.setSpan(row_index, 0, 1, self._table.columnCount())
                self._table.setRowHeight(row_index, _HISTORY_BATCH_SEPARATOR_ROW_HEIGHT)
                continue

            if entry.song is None:
                continue

            album_1 = str(entry.batch.ok_album or entry.song.album or "").strip() or "—"
            album_2 = str(entry.batch.alt_album or "").strip() or "—"
            values = [
                str(entry.row_number or ""),
                album_1,
                album_2,
                entry.song.description_name or "—",
                entry.song.structure_name or "—",
                entry.song.suno_status or entry.song.status or "pending",
                format_run_date_label(entry.batch.from_date or entry.batch.to_date),
            ]
            column_indexes = (0, _HISTORY_COL_ALBUM_1, _HISTORY_COL_ALBUM_2, 4, 5, 8, 9)
            for col_index, value in zip(column_indexes, values, strict=True):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                )
                if value and value != "—":
                    item.setToolTip(value)
                self._table.setItem(row_index, col_index, item)

            self._set_title_cell(
                row_index,
                title=entry.song.title,
                status=entry.song.status,
            )

            self._table.setCellWidget(
                row_index,
                _HISTORY_COL_PRIMARY,
                self._channel_cell(entry.batch.ok_profile_name or "—", entry.song.output_dir_ok, "primary"),
            )
            self._table.setCellWidget(
                row_index,
                _HISTORY_COL_SECONDARY,
                self._channel_cell(entry.batch.alt_profile_name or "—", entry.song.output_dir_alt, "secondary"),
            )
            self._table.setRowHeight(row_index, _HISTORY_SONG_ROW_HEIGHT)

        self._apply_row_selection()

    def _set_title_cell(
        self,
        row_index: int,
        *,
        title: str | None,
        status: str | None,
    ) -> None:
        """Paint title column with either the animated placeholder or final title text."""
        self._table.removeCellWidget(row_index, _HISTORY_COL_TITLE)
        stale_item = self._table.takeItem(row_index, _HISTORY_COL_TITLE)
        if stale_item is not None:
            del stale_item

        if is_song_title_generating(status, title):
            self._table.setCellWidget(row_index, _HISTORY_COL_TITLE, GeneratingTitleCell())
            return

        display_title = title or "—"
        title_item = QTableWidgetItem(display_title)
        title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        title_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        if display_title != "—":
            title_item.setToolTip(display_title)
        self._table.setItem(row_index, _HISTORY_COL_TITLE, title_item)

    def _apply_row_selection(self) -> None:
        if not self._selected_song_id:
            self._table.clearSelection()
            return
        for row_index, entry in enumerate(self._table_rows):
            if entry.song is not None and entry.song.song_id == self._selected_song_id:
                self._table.selectRow(row_index)
                return
        self._table.clearSelection()

    def _batch_separator_label(self, batch: MusicHistoryBatch) -> str:
        run_date = format_run_date_label(batch.from_date or batch.to_date)
        generated = format_datetime_label(batch.created_at or batch.updated_at)
        ok_name = batch.ok_profile_name or "Primary"
        alt_name = batch.alt_profile_name or "Secondary"
        album_1 = str(batch.ok_album or "").strip()
        album_2 = str(batch.alt_album or "").strip()
        album_bits: list[str] = []
        if album_1:
            album_bits.append(f"album 1 {album_1}")
        if album_2:
            album_bits.append(f"album 2 {album_2}")
        album_part = f"{' · '.join(album_bits)} · " if album_bits else ""
        return (
            f"Batch {batch.batch_id[:8]} · {ok_name} → {alt_name} · "
            f"{album_part}"
            f"{batch.song_count} song{'s' if batch.song_count != 1 else ''} · "
            f"Run {run_date} · Generated {generated}"
        )

    def _make_batch_separator_item(self, batch: MusicHistoryBatch) -> QTableWidgetItem:
        item = QTableWidgetItem(self._batch_separator_label(batch))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setBackground(QBrush(_BATCH_SEPARATOR_BG))
        item.setForeground(QBrush(_BATCH_SEPARATOR_FG))
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        return item

    def _clear_cell_widgets(self) -> None:
        """Legacy helper; prefer QTableWidget.clearContents() before repainting rows."""
        for row_index in range(self._table.rowCount()):
            for col_index in range(self._table.columnCount()):
                widget = self._table.cellWidget(row_index, col_index)
                if widget is not None:
                    self._table.removeCellWidget(row_index, col_index)
                    widget.deleteLater()

    def _channel_cell(self, label: str, path: str | None, side: str) -> QWidget:
        host = QWidget()
        host.setMinimumHeight(28)
        layout = QHBoxLayout(host)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        name = QLabel(label)
        name.setObjectName(SUBTITLE_LABEL_ID)
        open_btn = QPushButton("Open")
        open_btn.setObjectName("history_open_button")
        open_btn.setFixedHeight(20)
        open_btn.setMaximumWidth(52)
        open_btn.setEnabled(bool(path))
        if path:
            open_btn.clicked.connect(
                lambda checked=False, folder=path: self.open_folder_requested.emit(
                    folder,
                    "primary" if side.lower() in {"ok", "primary"} else "secondary",
                )
            )
        layout.addWidget(name, stretch=1)
        layout.addWidget(open_btn)
        return host

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._table_rows):
            entry = self._table_rows[row]
            if entry.is_batch_separator or entry.song is None:
                return
            self._selected_song_id = entry.song.song_id
            self._table.selectRow(row)
            self.row_selected.emit(entry)

    def _emit_retry_batch(
        self,
        batch_id: str,
        draft_ids: list[str],
        suno_ids: list[str],
        _checked: bool = False,
    ) -> None:
        self.retry_batch_requested.emit(batch_id, draft_ids, suno_ids)

    def _show_context_menu(self, position) -> None:
        index = self._table.indexAt(position)
        menu = QMenu(self)

        if not index.isValid():
            refresh_action = menu.addAction("Refresh history")
            refresh_action.triggered.connect(self.refresh_requested.emit)
            if menu.actions():
                menu.exec(self._table.viewport().mapToGlobal(position))
            return

        row = index.row()
        if not (0 <= row < len(self._table_rows)):
            return
        entry = self._table_rows[row]

        refresh_action = menu.addAction("Refresh status")
        refresh_action.triggered.connect(self.refresh_requested.emit)

        draft_ids, suno_ids = batch_retry_targets(entry.batch)
        failed_count = len(draft_ids) + len(suno_ids)
        if failed_count > 0:
            suffix = "s" if failed_count != 1 else ""
            action = menu.addAction(f"Retry batch ({failed_count} song{suffix})")
            action.triggered.connect(
                partial(
                    self._emit_retry_batch,
                    entry.batch.batch_id,
                    draft_ids,
                    suno_ids,
                )
            )

        if entry.is_batch_separator or entry.song is None:
            if menu.actions():
                menu.exec(self._table.viewport().mapToGlobal(position))
            return

        song_status = str(entry.song.status or "pending").strip().lower()
        suno_status = str(entry.song.suno_status or "").strip().lower()

        if song_status in {"pending", "draft_failed"}:
            action = menu.addAction("Retry draft")
            action.triggered.connect(lambda: self.retry_draft_requested.emit(entry))

        if song_status == "draft_ready":
            action = menu.addAction("Suno")
            action.triggered.connect(lambda: self.retry_suno_requested.emit(entry))

        if song_status == "suno_failed" or suno_status == "suno_failed":
            action = menu.addAction("Retry Suno")
            action.triggered.connect(lambda: self.retry_suno_requested.emit(entry))

        image_total = int(entry.song.image_jobs_total or 0)
        image_done = int(entry.song.image_jobs_completed or 0)
        if song_status in {"suno_success", "completed", "complete"} or (
            image_total > 0 and image_done < image_total
        ):
            if image_total == 0 or image_done < image_total:
                action = menu.addAction("Image")
                action.triggered.connect(lambda: self.enqueue_images_requested.emit(entry))

        if image_total > 0 and image_done >= image_total:
            action = menu.addAction("Video")
            action.triggered.connect(lambda: self.continue_video_requested.emit(entry))

        menu.exec(self._table.viewport().mapToGlobal(position))
