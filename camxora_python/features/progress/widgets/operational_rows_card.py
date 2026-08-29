"""Operational progress rows table — compact scan view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.icons import apply_button_icon, section_heading
from features.create.widgets.studio_panel import StudioPanel
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
)
from shared.models.platform import ProgressRow, ProgressRowMeta
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
    "Updated",
]

LOADING_MESSAGE = "Loading progress rows..."
EMPTY_MESSAGE = (
    "No operational rows found. Try changing the date range, stage filter, or Active only filter."
)
SUBTITLE = (
    "Scan view for active runs. Progress shows the current stage percent. "
    "Select a row for full export, merge, and error details on the right."
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
_COL_UPDATED = 9

_CENTER_ALIGNED_COLUMNS = {
    _COL_STAGE,
    _COL_PROGRESS,
    _COL_MUSIC,
    _COL_IMAGES,
    _COL_EXPORT,
    _COL_MERGE,
    _COL_UPDATED,
}

_ROW_HEIGHT = 28
_STAGE_COLUMN_WIDTH = 108
_CHANNEL_COLUMN_WIDTH = 200
_ALBUM_COLUMN_WIDTH = 200
_EXPORT_COLUMN_WIDTH = 88
_MERGE_COLUMN_WIDTH = 88
_COMPACT_COLUMN_PAD = 10
_STAGE_BADGE_COLORS = {
    "completed": "#00C878",
    "done": "#00C878",
    "music": "#38BDF8",
    "image": "#7C3AED",
    "export": "#6335D9",
    "converter": "#6335D9",
    "merge": "#14B8A6",
    "merger": "#14B8A6",
    "youtube": "#EC4899",
    "waiting": "#F59E0B",
    "pending": "#F59E0B",
    "failed": "#F43F5E",
    "error": "#F43F5E",
    "blocked": "#F43F5E",
}
_STATUS_COLORS = {
    "completed": "#00C878",
    "pending": "#F59E0B",
    "not started": "#60758C",
    "failed": "#F43F5E",
    "—": "#60758C",
}


def _parse_percent(label: str) -> int | None:
    text = str(label or "").strip().rstrip("%")
    if not text or text in {"—", "-"}:
        return None
    try:
        return max(0, min(100, int(text)))
    except ValueError:
        return None


def _progress_tone(percent: int | None, stage: str) -> str:
    key = str(stage or "").strip().lower()
    if key in {"error", "failed", "blocked"} or percent is None:
        return "danger" if key in {"error", "failed", "blocked"} else "muted"
    if percent >= 100 or key in {"done", "completed"}:
        return "success"
    if key in {"waiting", "pending"}:
        return "warning"
    return "active"


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


class OperationalRowsCard(StudioPanel):
    open_folder_requested = Signal(str)
    open_run_folder_requested = Signal(str)
    sync_manual_requested = Signal(str)
    retry_images_requested = Signal(str)
    enqueue_images_requested = Signal(str)
    retry_drafts_requested = Signal(str, list)
    retry_suno_requested = Signal(str, list)
    force_export_regenerate_requested = Signal(object)
    rebuild_export_requested = Signal(object)
    repair_export_requested = Signal(object)
    regenerate_track_requested = Signal(object, str)
    start_export_requested = Signal(object)
    start_merge_requested = Signal(object)
    change_run_folder_requested = Signal(object)
    download_missing_mp3s_requested = Signal(object)
    cancel_job_requested = Signal(object)
    stop_exporting_requested = Signal(object)
    continue_progress_requested = Signal(object)
    row_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manual_mode = False
        self._inspections: dict[str, ManualAssetInspection] = {}
        self._video_inspections: dict = {}
        self._syncing_batch_id = ""
        self._selected_row_index = -1
        self._rows: list[EffectiveProgressRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        root.addWidget(section_heading("OPERATIONAL ROWS", "list"))

        subtitle = QLabel(SUBTITLE)
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._table = create_data_table(TABLE_HEADERS)
        self._table.setObjectName("ProgressTable")
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        vertical = self._table.verticalHeader()
        vertical.setDefaultSectionSize(_ROW_HEIGHT)
        vertical.setMinimumSectionSize(_ROW_HEIGHT)
        vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
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
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(48)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_column_widths()

    def _apply_column_widths(self) -> None:
        header = self._table.horizontalHeader()
        for index in (_COL_RUN, _COL_PROGRESS, _COL_MUSIC, _COL_IMAGES):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
            if self._table.rowCount() > 0:
                self._table.resizeColumnToContents(index)
            if index != _COL_RUN:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(index, self._table.columnWidth(index) + _COMPACT_COLUMN_PAD)

        header.setSectionResizeMode(_COL_STAGE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_STAGE, _STAGE_COLUMN_WIDTH)
        header.setSectionResizeMode(_COL_EXPORT, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_EXPORT, _EXPORT_COLUMN_WIDTH)
        header.setSectionResizeMode(_COL_MERGE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_MERGE, _MERGE_COLUMN_WIDTH)
        header.setSectionResizeMode(_COL_UPDATED, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_UPDATED, 132)

        header.setSectionResizeMode(_COL_CHANNEL, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(_COL_CHANNEL, _CHANNEL_COLUMN_WIDTH)
        header.setSectionResizeMode(_COL_ALBUM, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(_COL_ALBUM, _ALBUM_COLUMN_WIDTH)

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = enabled

    def set_manual_inspections(self, inspections: dict[str, ManualAssetInspection]) -> None:
        self._inspections = inspections

    def set_video_inspections(self, inspections: dict) -> None:
        self._video_inspections = dict(inspections or {})

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
        self._table.clearContents()
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
                self._format_updated_cell(entry),
            ]
            tooltips = list(values)
            tooltips[_COL_EXPORT] = export_full
            tooltips[_COL_MERGE] = merge_full
            if row.album:
                tooltips[_COL_ALBUM] = str(row.album).strip()
            show_start_export = self._can_show_start_export(entry)
            for col_index, value in enumerate(values):
                if col_index == _COL_EXPORT and show_start_export:
                    continue
                self._table.removeCellWidget(row_index, col_index)
                item = self._make_cell_item(value, center=col_index in _CENTER_ALIGNED_COLUMNS)
                item.setToolTip(tooltips[col_index].replace("\n", " · "))
                if col_index in (_COL_EXPORT, _COL_MERGE):
                    color = _STATUS_COLORS.get(str(value).strip().lower(), "#E5EDF7")
                    item.setForeground(QColor(color))
                self._table.setItem(row_index, col_index, item)
                if col_index == _COL_STAGE:
                    self._set_stage_badge(row_index, str(value))
                if col_index == _COL_PROGRESS:
                    self._set_progress_cell(row_index, str(value), entry.effective_stage)
            if show_start_export:
                self._set_start_export_button(row_index, entry.row)
            self._table.setRowHeight(row_index, _ROW_HEIGHT)

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

    def _format_updated_cell(self, entry: EffectiveProgressRow | ProgressRow) -> str:
        if isinstance(entry, EffectiveProgressRow):
            row = entry.row
            stage = str(entry.effective_stage or row.stage or "").strip().lower()
        else:
            row = entry
            stage = str(row.stage or "").strip().lower()
        updated_at = self._resolve_row_updated_at(row.meta, stage=stage)
        return format_progress_updated_time(updated_at, fallback=row.updated)

    @staticmethod
    def _resolve_row_updated_at(
        meta: ProgressRowMeta,
        *,
        stage: str = "",
    ) -> datetime | None:
        # Freeze completion time once the pipeline is terminal so heartbeats
        # (batch sync / local overlay) do not keep rewriting the Update column.
        stage_key = str(stage or "").strip().lower()
        if stage_key == "done" and meta.youtube_updated_at is not None:
            return meta.youtube_updated_at
        if stage_key in {"done", "completed", "error"}:
            candidates = [
                meta.youtube_updated_at,
                meta.image_updated_at,
                meta.music_updated_at,
                meta.updated_at,
            ]
        elif meta.updated_at is not None:
            return meta.updated_at
        else:
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

    @staticmethod
    def _is_pipeline_finished(entry: EffectiveProgressRow) -> bool:
        """Done / Completed / YouTube rows are archival — no Continue/Stop/export."""
        stage = entry.effective_stage.strip().lower()
        return stage in {"done", "completed", "youtube"}

    @staticmethod
    def _can_start_video_export(entry: EffectiveProgressRow) -> bool:
        """Force Regenerate / Rebuild — allowed even on finished rows (explicit re-run)."""
        meta = entry.row.meta
        if not str(meta.run_dir or "").strip():
            return False
        if entry.effective_stage.strip().lower() == "error":
            return False
        if OperationalRowsCard._is_pipeline_finished(entry):
            return True
        return bool(meta.long_ready or meta.reel_ready)

    @staticmethod
    def _can_show_start_export(entry: EffectiveProgressRow) -> bool:
        if OperationalRowsCard._is_pipeline_finished(entry):
            return False
        stage = entry.effective_stage.strip().lower()
        if stage not in {"export", "converter"}:
            return False
        status = entry.effective_status.strip().lower()
        converter_text = str(entry.effective_converter or entry.row.converter or "").lower()
        if status in {"pending", "queued", "waiting"}:
            return True
        if "pending" in converter_text or "no exports yet" in converter_text:
            return True
        return False

    @staticmethod
    def _can_start_video_merge(entry: EffectiveProgressRow) -> bool:
        meta = entry.row.meta
        if not str(meta.run_dir or "").strip():
            return False
        if OperationalRowsCard._is_pipeline_finished(entry):
            return False
        stage = entry.effective_stage.strip().lower()
        if stage == "error":
            return False
        export_text = str(entry.effective_converter or entry.row.converter or "").lower()
        if "long " in export_text or "reel " in export_text or "merged" in export_text or "completed" in export_text:
            return True
        return bool(meta.long_ready or meta.reel_ready)

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
        finished = self._is_pipeline_finished(entry)

        if not finished:
            # Hard stop: cancel live work and keep auto-video / helper agents paused
            # until the user explicitly Start Export / Continue / Merge on a row.
            stop_action = menu.addAction("Stop Exporting")
            stop_action.triggered.connect(partial(self.stop_exporting_requested.emit, entry.row))

            # Soft cancel only (auto may resume later unless Stop Exporting was used).
            cancel_action = menu.addAction("Cancel Active Export/Merge")
            cancel_action.triggered.connect(partial(self.cancel_job_requested.emit, entry.row))

            continue_action = menu.addAction("Continue Progress")
            continue_action.triggered.connect(
                partial(self.continue_progress_requested.emit, entry)
            )
            menu.addSeparator()

            if self._can_show_start_export(entry):
                action = menu.addAction("Start Export")
                action.triggered.connect(partial(self.start_export_requested.emit, entry.row))
                menu.addSeparator()

            if self._can_start_video_merge(entry):
                action = menu.addAction("Start Merging Video")
                action.triggered.connect(partial(self.start_merge_requested.emit, entry.row))
                menu.addSeparator()

        # Explicit rebuild — allowed on finished rows; Continue/Stop stay hidden above.
        if self._can_start_video_export(entry):
            action = menu.addAction("Force Regenerate MP4")
            action.setToolTip(
                "Delete every exported MP4 for this branch and re-export all tracks."
            )
            action.triggered.connect(
                partial(self.force_export_regenerate_requested.emit, entry.row)
            )
            action = menu.addAction("Regenerate missing/broken MP4s")
            action.setToolTip(
                "Re-export only tracks whose MP4 is missing, tiny, corrupt, or truncated."
            )
            action.triggered.connect(partial(self.repair_export_requested.emit, entry.row))
            self._add_regenerate_one_track_menu(menu, entry)
            menu.addSeparator()

        copy_action = menu.addAction("Copy Batch ID")
        copy_action.setEnabled(bool(str(meta.batch_id or "").strip()))
        copy_action.triggered.connect(partial(self._copy_batch_id, meta.batch_id))
        menu.addSeparator()

        if not finished:
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

            from shared.lib.missing_mp3 import count_missing_role_mp3s_from_meta

            missing_n = count_missing_role_mp3s_from_meta(entry.row)
            if missing_n > 0:
                suffix = "s" if missing_n != 1 else ""
                action = menu.addAction(f"Download missing MP3{suffix} ({missing_n})")
                action.setToolTip(
                    "Download only the missing track(s) for this channel from Suno "
                    "(or Backblaze fallback) into this PC's run folder — without "
                    "re-drafting or re-requesting Suno generation."
                )
                action.triggered.connect(
                    partial(self.download_missing_mp3s_requested.emit, entry.row)
                )

            action = menu.addAction("Change Run Folder && Resume…")
            action.setToolTip(
                "Move this run to a different folder (e.g. a bad/full drive) and "
                "re-download already-successful MP3s/images there — without "
                "re-drafting or re-requesting Suno."
            )
            action.triggered.connect(partial(self.change_run_folder_requested.emit, entry.row))

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

    def _add_regenerate_one_track_menu(self, menu: QMenu, entry: EffectiveProgressRow) -> None:
        from shared.lib.video_runtime_inspection import progress_runtime_key

        meta = entry.row.meta
        key = progress_runtime_key(meta.batch_id, meta.profile_id, meta.role)
        inspection = self._video_inspections.get(key)
        mp3_paths = tuple(getattr(inspection, "mp3_paths", ()) or ())
        if not mp3_paths:
            return
        track_menu = menu.addMenu("Regenerate one track")
        track_menu.setToolTip("Delete and re-export a specific track from its MP3.")
        for mp3_path in mp3_paths[:40]:
            from pathlib import Path

            action = track_menu.addAction(Path(mp3_path).name)
            action.triggered.connect(
                partial(self.regenerate_track_requested.emit, entry.row, mp3_path)
            )

    def _set_start_export_button(self, row_index: int, row: ProgressRow) -> None:
        self._table.removeCellWidget(row_index, _COL_EXPORT)
        stale_item = self._table.takeItem(row_index, _COL_EXPORT)
        if stale_item is not None:
            del stale_item

        button = QPushButton("Start Export")
        button.setObjectName("SecondaryButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(22)
        apply_button_icon(button, "play")
        button.clicked.connect(partial(self.start_export_requested.emit, row))
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.addWidget(button)
        self._table.setCellWidget(row_index, _COL_EXPORT, wrap)

    def _set_stage_badge(self, row_index: int, label: str) -> None:
        color = _STAGE_BADGE_COLORS.get(str(label or "").strip().lower(), "#60758C")
        pill = QLabel(label)
        pill.setObjectName("StatusBadge")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setFixedHeight(16)
        pill.setStyleSheet(
            "QLabel#StatusBadge {"
            f" background-color: {color}; color: #ffffff; border: none;"
            " border-radius: 3px; padding: 0 7px;"
            " font-size: 10px; font-weight: 600;"
            "}"
        )
        wrap = QWidget()
        wrap.setObjectName("TransparentBlock")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(pill)
        self._table.setCellWidget(row_index, _COL_STAGE, wrap)

    def _set_progress_cell(self, row_index: int, label: str, stage: str) -> None:
        host = QWidget()
        host.setObjectName("TransparentBlock")
        column = QVBoxLayout(host)
        column.setContentsMargins(4, 2, 4, 2)
        column.setSpacing(1)
        text = QLabel(label)
        text.setObjectName("ProgressCellValue")
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        bar = QProgressBar()
        bar.setObjectName("ProgressCellBar")
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        parsed = _parse_percent(label)
        bar.setValue(0 if parsed is None else parsed)
        tone = _progress_tone(parsed, stage)
        bar.setProperty("tone", tone)
        column.addWidget(text)
        column.addWidget(bar)
        self._table.setCellWidget(row_index, _COL_PROGRESS, host)

    def _set_message(self, message: str) -> None:
        self._rows = []
        self._table.clearSpans()
        self._table.clearContents()
        self._table.setRowCount(1)
        self._table.setSpan(0, 0, 1, len(TABLE_HEADERS))
        for col in range(len(TABLE_HEADERS)):
            self._table.setCellWidget(0, col, None)
        item = QTableWidgetItem(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 0, item)
