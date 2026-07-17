"""Operational progress rows table — compact scan view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shared.lib.formatting import format_progress_updated_time
from shared.lib.manual_asset_paths import ManualAssetInspection
from shared.lib.progress_presentation import (
    compute_stage_progress_percent,
    format_album_label,
    format_channel_label,
    format_export_compact,
    format_images_compact,
    format_merge_compact,
    format_music_compact,
    format_run_date_label,
    format_stage_label,
    format_youtube_compact,
)
from shared.models.platform import ProgressRow, ProgressRowMeta
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.data_table import create_data_table

TABLE_HEADERS = [
    "Run",
    "Channel",
    "Album",
    "Stage",
    "Progress",
    "Music",
    "Images",
    "Export",
    "Merge",
    "YouTube",
    "Updated",
]

LOADING_MESSAGE = "Loading progress rows..."
EMPTY_MESSAGE = "No runs found for the selected operational filters."
SUBTITLE = (
    "Scan view for active runs. Progress shows the current stage percent. "
    "Select a row for full export, merge, error, and YouTube details on the right."
)

_COL_RUN = 0
_COL_CHANNEL = 1
_COL_ALBUM = 2
_COL_STAGE = 3
_COL_PROGRESS = 4
_COL_MUSIC = 5
_COL_IMAGES = 6
_COL_EXPORT = 7
_COL_MERGE = 8
_COL_YOUTUBE = 9
_COL_UPDATED = 10

_CENTER_ALIGNED_COLUMNS = {
    _COL_STAGE,
    _COL_PROGRESS,
    _COL_MUSIC,
    _COL_IMAGES,
    _COL_EXPORT,
    _COL_MERGE,
    _COL_YOUTUBE,
    _COL_UPDATED,
}


@dataclass(frozen=True, slots=True)
class EffectiveProgressRow:
    row: ProgressRow
    effective_status: str
    effective_converter: str
    effective_merge: str
    effective_stage: str
    effective_notes: str
    effective_converter_percent: int | None = None
    effective_merge_percent: int | None = None


class OperationalRowsCard(QFrame):
    open_folder_requested = Signal(str)
    open_run_folder_requested = Signal(str)
    sync_manual_requested = Signal(str)
    retry_images_requested = Signal(str)
    enqueue_images_requested = Signal(str)
    retry_drafts_requested = Signal(str, list)
    retry_suno_requested = Signal(str, list)
    row_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self._manual_mode = False
        self._inspections: dict[str, ManualAssetInspection] = {}
        self._syncing_batch_id = ""
        self._selected_row_index = -1
        self._rows: list[EffectiveProgressRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("OPERATIONAL ROWS")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        subtitle = QLabel(SUBTITLE)
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._table = create_data_table(TABLE_HEADERS)
        self._configure_table_columns()
        self._table.setSelectionBehavior(self._table.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(self._table.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self._table, 1)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _configure_table_columns(self) -> None:
        self._table.setAlternatingRowColors(False)
        self._table.setWordWrap(False)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(48)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_column_widths()

    def _apply_column_widths(self) -> None:
        header = self._table.horizontalHeader()
        compact_columns = {
            _COL_RUN,
            _COL_STAGE,
            _COL_PROGRESS,
            _COL_MUSIC,
            _COL_MERGE,
            _COL_YOUTUBE,
        }
        stretch_columns = (_COL_CHANNEL, _COL_ALBUM, _COL_IMAGES, _COL_EXPORT)

        for index in compact_columns:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
            if self._table.rowCount() > 0:
                self._table.resizeColumnToContents(index)

        header.setSectionResizeMode(_COL_UPDATED, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_UPDATED, 132)

        for index in stretch_columns:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = enabled

    def set_manual_inspections(self, inspections: dict[str, ManualAssetInspection]) -> None:
        self._inspections = inspections

    def set_syncing_batch_id(self, batch_id: str) -> None:
        self._syncing_batch_id = batch_id

    def show_loading(self) -> None:
        self._selected_row_index = -1
        self.row_selected.emit(None)
        self._set_message(LOADING_MESSAGE)

    def show_empty(self) -> None:
        self._selected_row_index = -1
        self.row_selected.emit(None)
        self._set_message(EMPTY_MESSAGE)

    def set_rows(self, rows: list[EffectiveProgressRow]) -> None:
        self._rows = rows
        if not rows:
            self.show_empty()
            return

        previous_key = ""
        if 0 <= self._selected_row_index < len(self._rows):
            previous = self._rows[self._selected_row_index].row.meta
            previous_key = f"{previous.batch_id}:{previous.profile_id}:{previous.role}"

        self._table.blockSignals(True)
        self._table.clearSpans()
        self._table.setRowCount(len(rows))
        for row_index, entry in enumerate(rows):
            row = entry.row
            export_full = str(entry.effective_converter or "").strip() or "—"
            merge_full = str(entry.effective_merge or "").strip() or "—"
            values = [
                format_run_date_label(row.run_date),
                format_channel_label(row.channel, row.meta.role),
                format_album_label(row.album),
                format_stage_label(entry.effective_stage),
                compute_stage_progress_percent(
                    row,
                    effective_stage=entry.effective_stage,
                    effective_status=entry.effective_status,
                    converter_percent=entry.effective_converter_percent,
                    merge_percent=entry.effective_merge_percent,
                ),
                format_music_compact(row),
                format_images_compact(row.meta),
                format_export_compact(export_full),
                format_merge_compact(merge_full),
                format_youtube_compact(row),
                self._format_updated_cell(row),
            ]
            tooltips = list(values)
            tooltips[_COL_EXPORT] = export_full
            tooltips[_COL_MERGE] = merge_full
            if row.album:
                tooltips[_COL_ALBUM] = str(row.album).strip()
            for col_index, value in enumerate(values):
                item = self._make_cell_item(value, center=col_index in _CENTER_ALIGNED_COLUMNS)
                item.setToolTip(tooltips[col_index].replace("\n", " · "))
                self._table.setItem(row_index, col_index, item)

        self._table.resizeRowsToContents()
        self._apply_column_widths()
        self._table.blockSignals(False)

        restore_index = -1
        if previous_key:
            for index, entry in enumerate(rows):
                meta = entry.row.meta
                key = f"{meta.batch_id}:{meta.profile_id}:{meta.role}"
                if key == previous_key:
                    restore_index = index
                    break
        if restore_index >= 0:
            self._table.selectRow(restore_index)
        elif rows:
            self._table.selectRow(0)
        else:
            self.row_selected.emit(None)

    @staticmethod
    def _make_cell_item(value: str, *, center: bool) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        else:
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _on_selection_changed(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            self._selected_row_index = -1
            self.row_selected.emit(None)
            return
        row_index = indexes[0].row()
        self._selected_row_index = row_index
        entry = self._row_at(row_index)
        self.row_selected.emit(entry)

    def _format_updated_cell(self, row: ProgressRow) -> str:
        updated_at = self._resolve_row_updated_at(row.meta)
        return format_progress_updated_time(updated_at, fallback=row.updated)

    @staticmethod
    def _resolve_row_updated_at(meta: ProgressRowMeta) -> datetime | None:
        if meta.updated_at is not None:
            return meta.updated_at
        candidates = [
            meta.music_updated_at,
            meta.image_updated_at,
            meta.youtube_updated_at,
        ]
        timestamps = [value for value in candidates if value is not None]
        return max(timestamps) if timestamps else None

    @staticmethod
    def _can_retry_images(entry: EffectiveProgressRow) -> bool:
        meta = entry.row.meta
        stage = entry.effective_stage.strip().lower()
        if meta.bg_status.upper() == "FAILED" or meta.th_status.upper() == "FAILED":
            return True
        if stage == "image":
            return True
        if stage == "error" and "FAILED" in str(entry.row.image or "").upper():
            return True
        return False

    def _row_at(self, row_index: int) -> EffectiveProgressRow | None:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def _emit_retry_drafts(self, batch_id: str, song_ids: list[str], _checked: bool = False) -> None:
        self.retry_drafts_requested.emit(batch_id, song_ids)

    def _emit_retry_suno(self, batch_id: str, song_ids: list[str], _checked: bool = False) -> None:
        self.retry_suno_requested.emit(batch_id, song_ids)

    def _emit_retry_images(self, batch_id: str, _checked: bool = False) -> None:
        self.retry_images_requested.emit(batch_id)

    def _emit_enqueue_images(self, batch_id: str, _checked: bool = False) -> None:
        self.enqueue_images_requested.emit(batch_id)

    def _emit_sync_manual(self, batch_id: str, _checked: bool = False) -> None:
        self.sync_manual_requested.emit(batch_id)

    def _emit_open_run_folder(self, path: str, _checked: bool = False) -> None:
        self.open_run_folder_requested.emit(path)

    def _emit_open_folder(self, path: str, _checked: bool = False) -> None:
        self.open_folder_requested.emit(path)

    @staticmethod
    def _copy_batch_id(batch_id: str, _checked: bool = False) -> None:
        text = str(batch_id or "").strip()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)

    @staticmethod
    def _open_youtube_url(url: str, _checked: bool = False) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        target = str(url or "").strip()
        if target:
            QDesktopServices.openUrl(QUrl(target))

    def _show_context_menu(self, position) -> None:
        from shared.lib.manual_asset_paths import manual_inspection_key

        index = self._table.indexAt(position)
        if not index.isValid():
            return
        entry = self._row_at(index.row())
        if entry is None:
            return

        menu = QMenu(self)
        meta = entry.row.meta
        recovery_added = False

        copy_action = menu.addAction("Copy Batch ID")
        copy_action.setEnabled(bool(str(meta.batch_id or "").strip()))
        copy_action.triggered.connect(partial(self._copy_batch_id, meta.batch_id))
        menu.addSeparator()

        draft_ids = list(meta.draft_failed_song_ids or [])
        if draft_ids:
            count = len(draft_ids)
            suffix = "s" if count != 1 else ""
            action = menu.addAction(f"Retry Failed Drafts ({count} song{suffix})")
            action.triggered.connect(partial(self._emit_retry_drafts, meta.batch_id, draft_ids))
            recovery_added = True

        suno_ids = list(meta.suno_failed_song_ids or [])
        if suno_ids:
            count = len(suno_ids)
            suffix = "s" if count != 1 else ""
            action = menu.addAction(f"Retry Failed Suno ({count} song{suffix})")
            action.triggered.connect(partial(self._emit_retry_suno, meta.batch_id, suno_ids))
            recovery_added = True

        if not self._manual_mode and self._can_retry_images(entry):
            action = menu.addAction("Retry Images")
            action.triggered.connect(partial(self._emit_retry_images, meta.batch_id))
            recovery_added = True

        if not self._manual_mode and int(meta.bg_total or 0) == 0 and int(meta.th_total or 0) == 0:
            # First-fire image continue when music is done and no jobs exist yet.
            music = str(entry.row.music or "").upper()
            if "READY" in music or "SUCCESS" in music or "DONE" in music or "COMPLETE" in music:
                action = menu.addAction("Image")
                action.triggered.connect(partial(self._emit_enqueue_images, meta.batch_id))
                recovery_added = True

        if self._manual_mode:
            key = manual_inspection_key(meta.batch_id, meta.profile_id, meta.role)
            inspection = self._inspections.get(key)
            if (
                inspection
                and inspection.ready
                and entry.effective_stage.lower() == "image"
            ):
                action = menu.addAction("Continue Pipeline")
                action.triggered.connect(partial(self._emit_sync_manual, meta.batch_id))
                recovery_added = True

        if recovery_added and (meta.run_dir or self._manual_mode):
            menu.addSeparator()

        if meta.run_dir:
            run_dir = meta.run_dir
            action = menu.addAction("Open Run Folder")
            action.triggered.connect(partial(self._emit_open_run_folder, run_dir))

        if meta.youtube_url:
            youtube_url = meta.youtube_url
            action = menu.addAction("Open YouTube URL")
            action.triggered.connect(partial(self._open_youtube_url, youtube_url))

        if self._manual_mode:
            key = manual_inspection_key(meta.batch_id, meta.profile_id, meta.role)
            inspection = self._inspections.get(key)
            if inspection and inspection.directory:
                directory = inspection.directory
                action = menu.addAction("Open Manual Folder")
                action.triggered.connect(partial(self._emit_open_folder, directory))

        if menu.actions():
            menu.exec(self._table.viewport().mapToGlobal(position))

    def _set_message(self, message: str) -> None:
        self._rows = []
        self._table.clearSpans()
        self._table.setRowCount(1)
        self._table.setSpan(0, 0, 1, len(TABLE_HEADERS))
        for col in range(len(TABLE_HEADERS)):
            self._table.setCellWidget(0, col, None)
        item = QTableWidgetItem(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 0, item)
