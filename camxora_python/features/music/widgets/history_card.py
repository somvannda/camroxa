"""Music history card."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import QDate, QItemSelectionModel, Qt, Signal, QTimer
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
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
from shared.lib.music_composer import normalize_history_date_range
from shared.lib.music_history_labels import is_song_title_generating
from shared.lib.music_status import format_song_pipeline_status, song_pipeline_status_tooltip
from shared.models.platform import MusicHistoryBatch, MusicHistorySong
from features.create.widgets.icons import apply_button_icon, section_heading
from features.create.widgets.studio_controls import StudioCheckBox, StudioComboBox, StudioDateEdit
from features.create.widgets.studio_panel import StudioPanel
from shared.widgets.data_table import create_data_table

EMPTY_MESSAGE = "No history rows match the current filters. Try Show all or widen the history dates."

_STATUS_FILTER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("success", "Success"),
    ("failed", "Failed"),
    ("pending", "Pending"),
)
_STATUS_FILTER_ALL_LABEL = "All statuses"


def batch_retry_targets(batch: MusicHistoryBatch) -> tuple[list[str], list[str]]:
    """Return (draft_failed ids, suno_failed ids) for batch-level retry."""
    from shared.lib.music_status import is_song_suno_batch_retry_target

    draft_ids: list[str] = []
    suno_ids: list[str] = []
    for song in batch.songs:
        song_status = str(song.status or "").strip().lower()
        if song_status == "draft_failed":
            draft_ids.append(song.song_id)
        if is_song_suno_batch_retry_target(song.status, song.suno_status):
            suno_ids.append(song.song_id)
    return draft_ids, suno_ids


_USER_DELETABLE_SONG_STATUSES = frozenset(
    {"pending", "draft_failed", "draft_ready", "suno_failed"}
)


def batch_is_user_deletable(batch: MusicHistoryBatch) -> bool:
    """True when every song is failed/pending-draft and none have Suno success/pending."""
    songs = list(batch.songs or [])
    if not songs:
        # Empty shell batches should still be removable from History.
        status = str(batch.status or "").strip().lower()
        return status in {"failed", "pending", "partial", ""}
    return all(
        str(song.status or "").strip().lower() in _USER_DELETABLE_SONG_STATUSES
        for song in songs
    )

# Default widths aligned with MusicWorkspacePage.tsx; stretch columns grow with the card.
_HISTORY_FIXED_COLUMN_WIDTHS = {
    0: 60,
    4: 150,
    5: 150,
    6: 140,
    7: 160,
    8: 160,
    9: 110,
}
_HISTORY_STRETCH_COLUMNS = (1, 2, 3)  # album 1, album 2, Title — Run date uses stretchLastSection
_HISTORY_COL_ALBUM_1 = 1
_HISTORY_COL_ALBUM_2 = 2
_HISTORY_COL_TITLE = 3
_HISTORY_COL_DESCRIPTION = 4
_HISTORY_COL_STRUCTURE = 5
_HISTORY_COL_MOOD = 6
_HISTORY_COL_PRIMARY = 7
_HISTORY_COL_SECONDARY = 8
_HISTORY_COL_SUNO = 9
_HISTORY_COL_RUN_DATE = 10
_HISTORY_COLUMN_COUNT = 11
_HISTORY_SONG_ROW_HEIGHT = 36
_HISTORY_BATCH_SEPARATOR_ROW_HEIGHT = 26
_BATCH_SEPARATOR_BG = QColor(99, 53, 217, 36)
_BATCH_SEPARATOR_FG = QColor("#C4B5FD")


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
        self._title.setObjectName("PageSubtitle")
        layout.addWidget(self._title, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(450)

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 3
        self._title.setText("Generating" + "." * (self._phase + 1))


class HistoryCard(StudioPanel):
    filters_changed = Signal()
    row_selected = Signal(object)
    open_folder_requested = Signal(str, str)
    retry_draft_requested = Signal(object)
    retry_suno_requested = Signal(object)
    rewrite_album_requested = Signal(object, str)  # HistoryRow/batch entry, role ok|alt
    rewrite_title_requested = Signal(object)
    enqueue_images_requested = Signal(object)
    continue_video_requested = Signal(object)
    retry_batch_requested = Signal(str, list, list)
    rewrite_batch_requested = Signal(object)
    delete_batch_requested = Signal(str)
    refresh_requested = Signal()
    recover_failed_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        root.addWidget(section_heading("HISTORY", "scroll-text"))

        filters = QHBoxLayout()
        today = QDate.fromString(today_ymd(), "yyyy-MM-dd")
        self._date_filter_active = True
        self._from_date = StudioDateEdit()
        self._from_date.setDate(today)
        self._from_date.setFixedWidth(132)
        self._from_date.setToolTip("Filters the History table by planned run date.")
        self._to_date = StudioDateEdit()
        self._to_date.setDate(today)
        self._to_date.setFixedWidth(132)
        self._to_date.setToolTip("Filters the History table by planned run date.")
        self._last_batch = StudioCheckBox("Last batch")
        self._status_filter = QPushButton(_STATUS_FILTER_ALL_LABEL)
        self._status_filter.setObjectName("SecondaryButton")
        self._status_filter.setMinimumWidth(140)
        status_menu = QMenu(self._status_filter)
        self._status_actions: dict[str, QAction] = {}
        for value, label in _STATUS_FILTER_OPTIONS:
            action = QAction(label, status_menu)
            action.setCheckable(True)
            action.setData(value)
            action.toggled.connect(self._on_status_filter_toggled)
            status_menu.addAction(action)
            self._status_actions[value] = action
        self._status_filter.setMenu(status_menu)
        self._batch_filter = StudioComboBox()
        self._batch_filter.setMinimumWidth(220)
        self._batch_filter.addItem("All batches", "")
        self._show_all_btn = QPushButton("Show all")
        self._show_all_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._show_all_btn, "list")
        self._show_all_btn.clicked.connect(self._clear_filters)
        self._recover_btn = QPushButton("Recover failed")
        self._recover_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._recover_btn, "refresh-cw")
        self._recover_btn.setToolTip(
            "Scan loaded history and recover failures: retry drafts, "
            "rewrite+Suno on content-policy rejects, retry other Suno fails."
        )
        self._recover_btn.clicked.connect(self.recover_failed_requested.emit)
        from_label = QLabel("History from")
        from_label.setObjectName("FieldLabel")
        to_label = QLabel("History to")
        to_label.setObjectName("FieldLabel")
        status_label = QLabel("Status")
        status_label.setObjectName("FieldLabel")
        batch_label = QLabel("Batch")
        batch_label.setObjectName("FieldLabel")
        filters.addWidget(from_label)
        filters.addWidget(self._from_date)
        filters.addWidget(to_label)
        filters.addWidget(self._to_date)
        filters.addWidget(status_label)
        filters.addWidget(self._status_filter)
        filters.addWidget(batch_label)
        filters.addWidget(self._batch_filter)
        filters.addWidget(self._last_batch)
        filters.addWidget(self._show_all_btn)
        filters.addWidget(self._recover_btn)
        filters.addStretch()
        root.addLayout(filters)

        self._filter_hint = QLabel("")
        self._filter_hint.setObjectName("PageSubtitle")
        self._filter_hint.setWordWrap(True)
        root.addWidget(self._filter_hint)
        meta = QHBoxLayout()
        self._summary = QLabel("No history yet.")
        self._summary.setObjectName("PageSubtitle")
        self._updated = QLabel("Updated —")
        self._updated.setObjectName("FieldLabel")
        meta.addWidget(self._summary, stretch=1)
        meta.addWidget(self._updated)
        root.addLayout(meta)

        self._table = create_data_table(
            [
                "No",
                "Album 1",
                "Album 2",
                "Title",
                "Description",
                "Structure",
                "Mood",
                "Primary Channel",
                "Secondary Channel",
                "Suno",
                "Run date",
            ]
        )
        self._table.setObjectName("history_data_table")
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
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
        self._batch_filter.currentIndexChanged.connect(lambda *_: self.filters_changed.emit())
        self._update_filter_hint()

    def _selected_statuses(self) -> list[str]:
        return [
            value
            for value, action in self._status_actions.items()
            if action.isChecked()
        ]

    def _sync_status_filter_label(self) -> None:
        selected = self._selected_statuses()
        if not selected:
            self._status_filter.setText(_STATUS_FILTER_ALL_LABEL)
            return
        labels = [label for value, label in _STATUS_FILTER_OPTIONS if value in selected]
        self._status_filter.setText(", ".join(labels))

    def _on_status_filter_toggled(self, *_args: object) -> None:
        self._sync_status_filter_label()
        self.filters_changed.emit()

    def _clear_status_filter(self) -> None:
        for action in self._status_actions.values():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)
        self._sync_status_filter_label()

    def _on_date_filter_changed(self) -> None:
        self._date_filter_active = True
        self._from_date.setEnabled(True)
        self._to_date.setEnabled(True)
        self._normalize_date_edits()
        self._update_filter_hint()
        self.filters_changed.emit()

    def _normalize_date_edits(self) -> None:
        """Keep From ≤ To in the widgets (swap when the range is inverted)."""
        raw_from = self._from_date.date().toString("yyyy-MM-dd")
        raw_to = self._to_date.date().toString("yyyy-MM-dd")
        norm_from, norm_to = normalize_history_date_range(raw_from, raw_to)
        if not norm_from or not norm_to:
            return
        if norm_from == raw_from and norm_to == raw_to:
            return
        from_qd = QDate.fromString(norm_from, "yyyy-MM-dd")
        to_qd = QDate.fromString(norm_to, "yyyy-MM-dd")
        if not from_qd.isValid() or not to_qd.isValid():
            return
        self._from_date.blockSignals(True)
        self._to_date.blockSignals(True)
        self._from_date.setDate(from_qd)
        self._to_date.setDate(to_qd)
        self._from_date.blockSignals(False)
        self._to_date.blockSignals(False)

    def _clear_filters(self) -> None:
        self._date_filter_active = False
        self._last_batch.setChecked(False)
        self._clear_status_filter()
        self._batch_filter.blockSignals(True)
        self._batch_filter.setCurrentIndex(0)
        self._batch_filter.blockSignals(False)
        self._update_filter_hint()
        self.filters_changed.emit()

    def _empty_table_message(self) -> str:
        if not self._date_filter_active:
            return EMPTY_MESSAGE
        start = self._from_date.date().toString("MMM d")
        end = self._to_date.date().toString("MMM d")
        window = start if start == end else f"{start}–{end}"
        return f"No rows for {window}. Try Show all or widen the history dates."

    def _update_filter_hint(self) -> None:
        if self._date_filter_active:
            self._filter_hint.setText(
                "History dates filter this table only. Shows batches whose "
                "planned run date falls in History from–to (or created that day). "
                "Last batch ignores the date range."
            )
        else:
            self._filter_hint.setText(
                "Showing all loaded batches (date filter off). Change From/To to filter by date."
            )

    def filter_values(self) -> dict[str, object]:
        status = self._selected_statuses()
        batch_id = str(self._batch_filter.currentData() or "")
        if not self._date_filter_active:
            return {
                "from_date": "",
                "to_date": "",
                "last_batch_only": self._last_batch.isChecked(),
                "status": status,
                "batch_id": batch_id,
            }
        self._normalize_date_edits()
        from_date, to_date = normalize_history_date_range(
            self._from_date.date().toString("yyyy-MM-dd"),
            self._to_date.date().toString("yyyy-MM-dd"),
        )
        return {
            "from_date": from_date,
            "to_date": to_date,
            "last_batch_only": self._last_batch.isChecked(),
            "status": status,
            "batch_id": batch_id,
        }

    def set_batch_filter_options(self, batches: list[MusicHistoryBatch]) -> None:
        """Refresh Batch dropdown from currently loaded history (preserve selection)."""
        current = str(self._batch_filter.currentData() or "")
        self._batch_filter.blockSignals(True)
        self._batch_filter.clear()
        self._batch_filter.addItem("All batches", "")
        seen: set[str] = set()
        for batch in batches:
            batch_id = str(batch.batch_id or "").strip()
            if not batch_id or batch_id in seen:
                continue
            seen.add(batch_id)
            run_date = format_run_date_label(batch.from_date or batch.to_date)
            ok_name = batch.ok_profile_name or "Primary"
            alt_name = batch.alt_profile_name or "Secondary"
            label = f"{batch_id[:8]} · {ok_name} → {alt_name} · {run_date}"
            self._batch_filter.addItem(label, batch_id)
        index = self._batch_filter.findData(current)
        self._batch_filter.setCurrentIndex(index if index >= 0 else 0)
        self._batch_filter.blockSignals(False)
        self._batch_filter.sync_item_tooltips()

    def set_summary(self, summary: str, updated_at: str | None) -> None:
        self._summary.setText(summary)
        self._updated.setText(f"Updated {format_datetime_label(updated_at)}")

    def set_rows(self, rows: list[HistoryRow], selected_song_id: str | None) -> None:
        # History refreshes often (batch poll). Rebuilding the table + selectRow()
        # was yanking scroll back to the selected row / top — preserve position.
        vbar = self._table.verticalScrollBar()
        hbar = self._table.horizontalScrollBar()
        saved_v = vbar.value()
        saved_h = hbar.value()

        self._table_rows = rows
        self._selected_song_id = selected_song_id
        self._table.clearSpans()
        self._table.clearContents()
        if not rows:
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, _HISTORY_COLUMN_COUNT)
            item = QTableWidgetItem(self._empty_table_message())
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(0, 0, item)
            vbar.setValue(0)
            hbar.setValue(0)
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
            suno_label = format_song_pipeline_status(
                entry.song.status,
                entry.song.suno_status,
                entry.song.suno_error_message,
            )
            suno_tooltip = song_pipeline_status_tooltip(
                entry.song.status,
                entry.song.suno_status,
                entry.song.suno_error_message,
            )
            values = [
                str(entry.row_number or ""),
                album_1,
                album_2,
                entry.song.description_name or "—",
                entry.song.structure_name or "—",
                entry.song.mood_name or "—",
                suno_label,
                format_run_date_label(entry.batch.from_date or entry.batch.to_date),
            ]
            column_indexes = (
                0,
                _HISTORY_COL_ALBUM_1,
                _HISTORY_COL_ALBUM_2,
                _HISTORY_COL_DESCRIPTION,
                _HISTORY_COL_STRUCTURE,
                _HISTORY_COL_MOOD,
                _HISTORY_COL_SUNO,
                _HISTORY_COL_RUN_DATE,
            )
            for col_index, value in zip(column_indexes, values, strict=True):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                )
                tooltip = suno_tooltip if col_index == _HISTORY_COL_SUNO and suno_tooltip else value
                if tooltip and tooltip != "—":
                    item.setToolTip(tooltip)
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

        self._apply_row_selection(scroll_into_view=False)
        vbar.setValue(min(saved_v, vbar.maximum()))
        hbar.setValue(min(saved_h, hbar.maximum()))

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

    def _apply_row_selection(self, *, scroll_into_view: bool = False) -> None:
        if not self._selected_song_id:
            self._table.clearSelection()
            return
        for row_index, entry in enumerate(self._table_rows):
            if entry.song is not None and entry.song.song_id == self._selected_song_id:
                if scroll_into_view:
                    self._table.selectRow(row_index)
                else:
                    model = self._table.model()
                    selection = self._table.selectionModel()
                    if model is None or selection is None:
                        return
                    index = model.index(row_index, 0)
                    selection.select(
                        index,
                        QItemSelectionModel.SelectionFlag.ClearAndSelect
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
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
        name.setObjectName("PageSubtitle")
        open_btn = QPushButton("Open")
        open_btn.setObjectName("SecondaryButton")
        apply_button_icon(open_btn, "folder-open", size=12)
        open_btn.setFixedHeight(22)
        open_btn.setMaximumWidth(64)
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

    def _emit_rewrite_batch(self, targets: list, _checked: bool = False) -> None:
        self.rewrite_batch_requested.emit(targets)

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

        from features.music.lib.pipeline_recovery import collect_batch_rewrite_targets

        rewrite_targets = collect_batch_rewrite_targets(entry.batch)
        if rewrite_targets:
            suffix = "s" if len(rewrite_targets) != 1 else ""
            rewrite_action = menu.addAction(
                f"Rewrite lyrics ({len(rewrite_targets)} song{suffix})"
            )
            rewrite_action.setToolTip(
                "Rewrite lyrics then queue Suno for failed songs with usable lyrics. "
                "Corrupt/empty lyrics are skipped."
            )
            rewrite_action.triggered.connect(
                partial(self._emit_rewrite_batch, rewrite_targets)
            )

        if batch_is_user_deletable(entry.batch):
            delete_action = menu.addAction("Delete failed batch")
            delete_action.triggered.connect(
                partial(self.delete_batch_requested.emit, entry.batch.batch_id)
            )

        # Metadata rewrite — available even when Suno already succeeded.
        album_1_action = menu.addAction("Rewrite album 1")
        album_1_action.setToolTip(
            "Regenerate Primary channel album name (bills one album draft slot)."
        )
        album_1_action.triggered.connect(
            partial(self.rewrite_album_requested.emit, entry, "ok")
        )
        if str(getattr(entry.batch, "alt_profile_id", "") or "").strip() or str(
            getattr(entry.batch, "alt_album", "") or ""
        ).strip():
            album_2_action = menu.addAction("Rewrite album 2")
            album_2_action.setToolTip(
                "Regenerate Secondary channel album name (bills one album draft slot)."
            )
            album_2_action.triggered.connect(
                partial(self.rewrite_album_requested.emit, entry, "alt")
            )

        if entry.is_batch_separator or entry.song is None:
            if menu.actions():
                menu.exec(self._table.viewport().mapToGlobal(position))
            return

        title_action = menu.addAction("Rewrite title")
        title_action.setToolTip(
            "Regenerate this song's title without changing lyrics (bills one title draft slot)."
        )
        title_action.triggered.connect(
            lambda: self.rewrite_title_requested.emit(entry)
        )

        song_status = str(entry.song.status or "pending").strip().lower()
        suno_status = str(entry.song.suno_status or "").strip().lower()

        if song_status in {"pending", "draft_failed"}:
            action = menu.addAction("Retry draft")
            action.triggered.connect(lambda: self.retry_draft_requested.emit(entry))

        if song_status == "draft_ready":
            action = menu.addAction("Suno")
            action.triggered.connect(lambda: self.retry_suno_requested.emit(entry))

        from shared.lib.music_status import is_song_suno_retry_eligible

        if is_song_suno_retry_eligible(entry.song.status, entry.song.suno_status):
            if song_status != "draft_ready":
                action = menu.addAction("Retry Suno")
                action.triggered.connect(lambda: self.retry_suno_requested.emit(entry))

        # Single-song rewrite when this row is a rewrite-eligible failure.
        single_rewrite = [
            target
            for target in rewrite_targets
            if target.song_id == entry.song.song_id
        ]
        if single_rewrite and len(rewrite_targets) > 1:
            action = menu.addAction("Rewrite this song")
            action.triggered.connect(partial(self._emit_rewrite_batch, single_rewrite))

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
