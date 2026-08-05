"""Image controls + queue card."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from shared.lib.formatting import today_ymd
from shared.lib.formatting import format_channel_role_label
from shared.lib.image_workspace import QueueRow, format_queue_role_status
from shared.themes.deep_blue import SHELL_TEXT_EDIT_ID, SUBTITLE_LABEL_ID
from shared.widgets.data_table import create_data_table
from shared.widgets.shell_date_edit import make_shell_date_edit

_COL_DATE = 0
_COL_ALBUM = 1
_COL_CHANNEL = 2
_COL_ROLE = 3
_COL_BG = 4
_COL_TH = 5
_COL_BG_FILE = 6
_COL_TH_FILE = 7

_QUEUE_FIXED_COLUMN_WIDTHS: dict[int, int] = {
    _COL_DATE: 108,
    _COL_ROLE: 56,
    _COL_BG: 82,
    _COL_TH: 82,
}

_QUEUE_INTERACTIVE_COLUMN_WIDTHS: dict[int, int] = {
    _COL_ALBUM: 180,
    _COL_CHANNEL: 150,
}

_QUEUE_STRETCH_COLUMNS = (_COL_BG_FILE, _COL_TH_FILE)


def _status_colors(status: str) -> tuple[QBrush, QBrush]:
    normalized = status.lower()
    if "success" in normalized:
        return QBrush(QColor(16, 64, 48)), QBrush(QColor(167, 243, 208))
    if "running" in normalized:
        return QBrush(QColor(96, 64, 16)), QBrush(QColor(253, 230, 138))
    if "fail" in normalized:
        return QBrush(QColor(80, 24, 32)), QBrush(QColor(254, 205, 211))
    return QBrush(QColor(30, 41, 59)), QBrush(QColor(203, 213, 225))


class ControlsQueueCard(QFrame):
    filters_changed = Signal()
    reload_requested = Signal()
    row_selected = Signal(str)
    selection_cleared = Signal()
    prompts_changed = Signal()
    clear_queue_requested = Signal()
    job_retry_requested = Signal(str, str)
    jobs_retry_requested = Signal(list, str)
    jobs_regenerate_requested = Signal(list, str)
    manual_generation_requested = Signal(str)
    job_open_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Image Controls + Queue")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        helper = QLabel("Filter by date and use the queue to review background and thumbnail output together.")
        helper.setObjectName(SUBTITLE_LABEL_ID)
        helper.setWordWrap(True)
        root.addWidget(helper)

        toolbar = QHBoxLayout()
        self._from_date = self._make_date_edit()
        self._to_date = self._make_date_edit()
        reload = QPushButton("Reload")
        reload.clicked.connect(self.reload_requested.emit)
        deselect = QPushButton("Deselect")
        deselect.setToolTip(
            "Clear the selected queue row. Manual Generation then creates a Not available "
            "queue row for today."
        )
        deselect.clicked.connect(self.clear_selection)
        toolbar.addWidget(QLabel("From"))
        toolbar.addWidget(self._from_date)
        toolbar.addWidget(QLabel("To"))
        toolbar.addWidget(self._to_date)
        toolbar.addWidget(reload)
        toolbar.addWidget(deselect)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self._filter_banner = QLabel("")
        self._filter_banner.setObjectName(SUBTITLE_LABEL_ID)
        self._filter_banner.setWordWrap(True)
        self._filter_banner.hide()
        root.addWidget(self._filter_banner)

        stats = QGridLayout()
        self._date_range_value = QLabel("")
        self._matched_batches_value = QLabel("0")
        self._queue_status_value = QLabel("Ready")
        for col, (label, value) in enumerate(
            (
                ("Date Range", self._date_range_value),
                ("Matched Batches", self._matched_batches_value),
                ("Queue Status", self._queue_status_value),
            )
        ):
            tile = QVBoxLayout()
            heading = QLabel(label.upper())
            heading.setObjectName(SUBTITLE_LABEL_ID)
            tile.addWidget(heading)
            tile.addWidget(value)
            host = QFrame()
            host.setObjectName("music_section")
            host.setLayout(tile)
            stats.addWidget(host, 0, col)
        root.addLayout(stats)

        queue_header = QHBoxLayout()
        queue_title = QLabel("Job Queue")
        queue_title.setObjectName(SUBTITLE_LABEL_ID)
        self._queue_summary = QLabel("")
        self._queue_summary.setObjectName(SUBTITLE_LABEL_ID)
        queue_header.addWidget(queue_title)
        queue_header.addStretch()
        queue_header.addWidget(self._queue_summary)
        root.addLayout(queue_header)

        queue_hint = QLabel(
            "One row per album and channel. Each album gets one shared background and thumbnail "
            "(not per song). Click a row to preview. Right-click to Retry failed jobs or Regenerate "
            "(uses Preferences + prompts; charges credits/quota)."
        )
        queue_hint.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(queue_hint)

        self._table = create_data_table(
            ["Date", "Album", "Channel", "Role", "BG", "TH", "BG File", "TH File"]
        )
        self._configure_queue_table_columns()
        self._table.setMinimumHeight(320)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self._table, stretch=1)

        self._footer_detail = QLabel("")
        self._footer_detail.setObjectName(SUBTITLE_LABEL_ID)
        self._footer_detail.setWordWrap(True)
        self._footer_detail.hide()
        root.addWidget(self._footer_detail)

        prompts = QGridLayout()
        self._background_prompt = self._make_prompt_edit(
            "Guide how the background should evolve from the chosen sample image."
        )
        self._thumbnail_prompt = self._make_prompt_edit(
            "Guide how the thumbnail should build on the generated background plus text style."
        )
        self._bg_manual_btn = QPushButton("Manual Generation")
        self._bg_manual_btn.setToolTip(
            "With a row selected: regenerate that album background (credits/quota). "
            "With no row selected: create a Not available queue row for today and generate Background."
        )
        self._bg_manual_btn.clicked.connect(
            lambda: self.manual_generation_requested.emit("background")
        )
        self._th_manual_btn = QPushButton("Manual Generation")
        self._th_manual_btn.setToolTip(
            "With a row selected: regenerate that album thumbnail (credits/quota). "
            "With no row selected: create a Not available queue row for today and generate Thumbnail."
        )
        self._th_manual_btn.clicked.connect(
            lambda: self.manual_generation_requested.emit("thumbnail")
        )
        prompts.addWidget(self._prompt_label("Background Prompt"), 0, 0)
        prompts.addWidget(self._background_prompt, 1, 0)
        prompts.addWidget(self._bg_manual_btn, 2, 0)
        prompts.addWidget(self._prompt_label("Thumbnail Prompt"), 0, 1)
        prompts.addWidget(self._thumbnail_prompt, 1, 1)
        prompts.addWidget(self._th_manual_btn, 2, 1)
        prompts.setColumnStretch(0, 1)
        prompts.setColumnStretch(1, 1)
        root.addLayout(prompts)

        self._clear_btn = QPushButton("Clear Queue")
        self._clear_btn.clicked.connect(self.clear_queue_requested.emit)
        root.addWidget(self._clear_btn)

        self._rows: list[QueueRow] = []
        self._selected_key = ""

        self._from_date.dateChanged.connect(lambda *_: self.filters_changed.emit())
        self._to_date.dateChanged.connect(lambda *_: self.filters_changed.emit())
        self._background_prompt.textChanged.connect(lambda *_: self.prompts_changed.emit())
        self._thumbnail_prompt.textChanged.connect(lambda *_: self.prompts_changed.emit())

    def _configure_queue_table_columns(self) -> None:
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(56)
        for index, width in _QUEUE_FIXED_COLUMN_WIDTHS.items():
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
            self._table.setColumnWidth(index, width)
        for index, width in _QUEUE_INTERACTIVE_COLUMN_WIDTHS.items():
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(index, width)
        for index in _QUEUE_STRETCH_COLUMNS:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)

    @staticmethod
    def _make_date_edit():
        return make_shell_date_edit(initial=QDate.fromString(today_ymd(), "yyyy-MM-dd"))

    @staticmethod
    def _make_prompt_edit(placeholder: str) -> QTextEdit:
        edit = QTextEdit()
        edit.setObjectName(SHELL_TEXT_EDIT_ID)
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(112)
        return edit

    @staticmethod
    def _prompt_label(text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName(SUBTITLE_LABEL_ID)
        return label

    def from_date(self) -> str:
        return self._from_date.date().toString("yyyy-MM-dd")

    def to_date(self) -> str:
        return self._to_date.date().toString("yyyy-MM-dd")

    def set_date_range(self, from_date: str, to_date: str) -> None:
        self._from_date.blockSignals(True)
        self._to_date.blockSignals(True)
        if from_date.strip():
            parsed = QDate.fromString(from_date.strip(), "yyyy-MM-dd")
            if parsed.isValid():
                self._from_date.setDate(parsed)
        if to_date.strip():
            parsed = QDate.fromString(to_date.strip(), "yyyy-MM-dd")
            if parsed.isValid():
                self._to_date.setDate(parsed)
        self._from_date.blockSignals(False)
        self._to_date.blockSignals(False)

    def background_prompt(self) -> str:
        return self._background_prompt.toPlainText()

    def thumbnail_prompt(self) -> str:
        return self._thumbnail_prompt.toPlainText()

    def set_prompts(self, background: str, thumbnail: str) -> None:
        self._background_prompt.blockSignals(True)
        self._thumbnail_prompt.blockSignals(True)
        self._background_prompt.setPlainText(background)
        self._thumbnail_prompt.setPlainText(thumbnail)
        self._background_prompt.blockSignals(False)
        self._thumbnail_prompt.blockSignals(False)

    def set_stat_values(self, *, date_range: str, matched_batches: int, queue_status: str) -> None:
        self._date_range_value.setText(date_range)
        self._matched_batches_value.setText(str(matched_batches))
        self._queue_status_value.setText(queue_status)

    def set_queue_summary(self, summary: str) -> None:
        self._queue_summary.setText(summary)

    def set_footer_detail(self, detail: str) -> None:
        if detail:
            self._footer_detail.setText(detail)
            self._footer_detail.show()
        else:
            self._footer_detail.hide()

    def set_filter_banner(self, message: str | None) -> None:
        text = str(message or "").strip()
        if text:
            self._filter_banner.setText(text)
            self._filter_banner.show()
        else:
            self._filter_banner.hide()

    def set_clear_enabled(self, enabled: bool) -> None:
        self._clear_btn.setEnabled(enabled)

    def set_reload_enabled(self, enabled: bool) -> None:
        for child in self.findChildren(QPushButton):
            if child.text() == "Reload":
                child.setEnabled(enabled)

    def set_rows(self, rows: list[QueueRow], selected_key: str | None) -> None:
        self._rows = rows
        # None = caller wants default first row; "" = explicit deselection.
        if selected_key is None:
            self._selected_key = rows[0].key if rows else ""
        else:
            self._selected_key = selected_key
        if not rows:
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, 8)
            item = QTableWidgetItem("No jobs yet for the selected date range.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(0, 0, item)
            return

        self._table.clearSpans()
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.date_label,
                row.album_label,
                row.profile_name,
                format_channel_role_label(row.role),
                format_queue_role_status(row.bg_jobs),
                format_queue_role_status(row.th_jobs),
                (row.bg_job.output_image_path or "—").split("\\")[-1].split("/")[-1] if row.bg_job else "—",
                (row.th_job.output_image_path or "—").split("\\")[-1].split("/")[-1] if row.th_job else "—",
            ]
            tooltips = list(values)
            if row.track_count > 1:
                tooltips[_COL_ALBUM] = f"{row.album_label} · {row.track_count} tracks"
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col_index in (_COL_BG, _COL_TH):
                    background, foreground = _status_colors(
                        row.bg_job.status if row.bg_job and col_index == _COL_BG else (
                            row.th_job.status if row.th_job else value
                        )
                    )
                    item.setBackground(background)
                    item.setForeground(foreground)
                item.setToolTip(tooltips[col_index])
                self._table.setItem(row_index, col_index, item)

        self._table.blockSignals(True)
        self._table.clearSelection()
        if self._selected_key:
            for row_index, row in enumerate(rows):
                if row.key == self._selected_key:
                    self._table.selectRow(row_index)
                    break
        self._table.blockSignals(False)

    def clear_selection(self) -> None:
        self._selected_key = ""
        self._table.clearSelection()
        self.selection_cleared.emit()

    def selected_row(self) -> QueueRow | None:
        for row in self._rows:
            if row.key == self._selected_key:
                return row
        return None

    def _on_selection_changed(self) -> None:
        selected_items = self._table.selectedItems()
        if not selected_items:
            if self._selected_key:
                self._selected_key = ""
                self.selection_cleared.emit()
            return
        row_index = selected_items[0].row()
        if 0 <= row_index < len(self._rows):
            key = self._rows[row_index].key
            if key != self._selected_key:
                self._selected_key = key
                self.row_selected.emit(key)

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if not (0 <= row < len(self._rows)):
            return
        entry = self._rows[row]
        if column == _COL_BG:
            job = entry.bg_job
        elif column == _COL_TH:
            job = entry.th_job
        else:
            return
        if job is None:
            return
        if self._job_is_retryable(job):
            self.job_retry_requested.emit(job.id, entry.batch_id)
            return
        if job.status == "success" and job.output_image_path:
            self.job_open_requested.emit(job.output_image_path, job.id)

    @staticmethod
    def _job_is_failed(job) -> bool:
        return ControlsQueueCard._job_is_retryable(job)

    @staticmethod
    def _job_is_retryable(job) -> bool:
        status = str(getattr(job, "status", "") or "").strip().lower()
        if status in {"failed", "cancelled"}:
            return True
        return status == "pending" and bool(str(getattr(job, "error", "") or "").strip())

    @staticmethod
    def _job_is_success(job) -> bool:
        return (
            str(getattr(job, "status", "") or "").strip().lower() == "success"
            and bool(getattr(job, "output_image_path", None))
        )

    @staticmethod
    def _row_needs_image_recovery(entry: QueueRow) -> bool:
        jobs = [job for job in (entry.bg_job, entry.th_job) if job is not None]
        if not jobs:
            return False
        return any(not ControlsQueueCard._job_is_success(job) for job in jobs)

    def _emit_reload_requested(self, _checked: bool = False) -> None:
        self.reload_requested.emit()

    def _emit_job_retry_requested(self, job_id: str, batch_id: str, _checked: bool = False) -> None:
        self.job_retry_requested.emit(job_id, batch_id)

    def _emit_jobs_retry_requested(
        self,
        job_ids: list[str],
        batch_id: str,
        _checked: bool = False,
    ) -> None:
        self.jobs_retry_requested.emit(job_ids, batch_id)

    def _emit_jobs_regenerate_requested(
        self,
        job_ids: list[str],
        batch_id: str,
        _checked: bool = False,
    ) -> None:
        self.jobs_regenerate_requested.emit(job_ids, batch_id)

    def _emit_job_open_requested(self, path: str, job_id: str, _checked: bool = False) -> None:
        self.job_open_requested.emit(path, job_id)

    def _show_context_menu(self, position) -> None:
        index = self._table.indexAt(position)
        menu = QMenu(self)
        if not index.isValid():
            reload_action = menu.addAction("Reload queue")
            reload_action.triggered.connect(self._emit_reload_requested)
            if menu.actions():
                menu.exec(self._table.viewport().mapToGlobal(position))
            return

        row = index.row()
        if not (0 <= row < len(self._rows)):
            return
        entry = self._rows[row]
        failed_job_ids: list[str] = []
        if entry.bg_job and self._job_is_retryable(entry.bg_job):
            failed_job_ids.append(entry.bg_job.id)
        if entry.th_job and self._job_is_retryable(entry.th_job):
            failed_job_ids.append(entry.th_job.id)

        if entry.bg_job and self._job_is_retryable(entry.bg_job):
            bg_job = entry.bg_job
            action = menu.addAction("Retry Background (failed)")
            action.triggered.connect(
                partial(self._emit_job_retry_requested, bg_job.id, entry.batch_id)
            )
        if entry.th_job and self._job_is_retryable(entry.th_job):
            th_job = entry.th_job
            action = menu.addAction("Retry Thumbnail (failed)")
            action.triggered.connect(
                partial(self._emit_job_retry_requested, th_job.id, entry.batch_id)
            )
        if len(failed_job_ids) > 1:
            retry_ids = list(failed_job_ids)
            action = menu.addAction("Retry All Failed Images")
            action.triggered.connect(
                partial(self._emit_jobs_retry_requested, retry_ids, entry.batch_id)
            )
        elif entry.batch_id and self._row_needs_image_recovery(entry):
            action = menu.addAction("Retry Batch Failed Images")
            action.triggered.connect(
                partial(self._emit_jobs_retry_requested, [], entry.batch_id)
            )
        if entry.bg_job is not None:
            action = menu.addAction("Regenerate Background")
            action.triggered.connect(
                partial(
                    self._emit_jobs_regenerate_requested,
                    [entry.bg_job.id],
                    entry.batch_id,
                )
            )
        if entry.th_job is not None:
            action = menu.addAction("Regenerate Thumbnail")
            action.triggered.connect(
                partial(
                    self._emit_jobs_regenerate_requested,
                    [entry.th_job.id],
                    entry.batch_id,
                )
            )
        regen_ids: list[str] = []
        if entry.bg_job is not None:
            regen_ids.append(entry.bg_job.id)
        if entry.th_job is not None:
            regen_ids.append(entry.th_job.id)
        if len(regen_ids) >= 2:
            action = menu.addAction("Regenerate Background + Thumbnail")
            action.triggered.connect(
                partial(self._emit_jobs_regenerate_requested, list(regen_ids), entry.batch_id)
            )
        if entry.bg_job and self._job_is_success(entry.bg_job):
            bg_path = entry.bg_job.output_image_path or ""
            bg_job_id = entry.bg_job.id
            action = menu.addAction("Open Background File")
            action.triggered.connect(partial(self._emit_job_open_requested, bg_path, bg_job_id))
        if entry.th_job and self._job_is_success(entry.th_job):
            th_path = entry.th_job.output_image_path or ""
            th_job_id = entry.th_job.id
            action = menu.addAction("Open Thumbnail File")
            action.triggered.connect(partial(self._emit_job_open_requested, th_path, th_job_id))

        if menu.actions():
            menu.exec(self._table.viewport().mapToGlobal(position))
