"""Image controls + queue card."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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

from features.create.widgets.icons import apply_button_icon, icon_label, section_heading
from features.create.widgets.studio_controls import StudioDateEdit
from features.create.widgets.studio_panel import NestedPanel, StudioPanel
from shared.lib.formatting import today_ymd
from shared.lib.formatting import format_channel_role_label
from shared.lib.image_workspace import (
    IMAGE_PROMPT_MAX_CHARS,
    QueueRow,
    clamp_image_prompt,
    format_queue_role_status,
    parse_queue_status_counts,
    split_queue_footer_detail,
)
from shared.themes.deep_blue import SHELL_TEXT_EDIT_ID
from shared.widgets.data_table import create_data_table

_COL_DATE = 0
_COL_ALBUM = 1
_COL_CHANNEL = 2
_COL_ROLE = 3
_COL_BG = 4
_COL_TH = 5
_COL_BG_FILE = 6
_COL_TH_FILE = 7

_QUEUE_ROW_HEIGHT = 32
_QUEUE_FIXED_COLUMN_WIDTHS: dict[int, int] = {
    _COL_DATE: 108,
    _COL_ROLE: 96,
    _COL_BG: 82,
    _COL_TH: 82,
}

_QUEUE_INTERACTIVE_COLUMN_WIDTHS: dict[int, int] = {
    _COL_ALBUM: 180,
    _COL_CHANNEL: 150,
}

_QUEUE_STRETCH_COLUMNS = (_COL_BG_FILE, _COL_TH_FILE)


def _status_foreground(status: str) -> QColor:
    normalized = status.lower()
    if "success" in normalized or normalized in {"✓", "ready"}:
        return QColor("#22C55E")
    if "run" in normalized:
        return QColor("#38BDF8")
    if "fail" in normalized:
        return QColor("#EF4444")
    if "wait" in normalized or "pending" in normalized:
        return QColor("#F59E0B")
    return QColor("#8FA4BB")


_QUEUE_STATUS_CAPTIONS = {
    "rows": "Albums in view",
    "pending": "Awaiting processing",
    "running": "Currently generating",
    "failed": "Need attention",
    "ready": "Assets complete",
}


class ControlsQueueCard(StudioPanel):
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
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._queue_count = QLabel("0")
        self._queue_count.setObjectName("ImageStatValue")
        self._queue_count.hide()
        self._summary_card, self._summary_counts, self._summary_message, self._summary_values = (
            self._make_queue_summary_card()
        )
        root.addWidget(self._summary_card)

        root.addWidget(section_heading("CONTROLS & QUEUE", "image"))

        helper = QLabel("Filter by date and use the queue to review background and thumbnail output together.")
        helper.setObjectName("PageSubtitle")
        helper.setWordWrap(True)
        root.addWidget(helper)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._from_date = self._make_date_edit()
        self._to_date = self._make_date_edit()
        from_label = QLabel("From")
        from_label.setObjectName("FieldLabel")
        to_label = QLabel("To")
        to_label.setObjectName("FieldLabel")
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._reload_btn, "refresh-cw")
        self._reload_btn.clicked.connect(self.reload_requested.emit)
        self._clear_filters_btn = QPushButton("Clear Filters")
        self._clear_filters_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._clear_filters_btn, "filter")
        self._clear_filters_btn.setToolTip("Reset the date range to today.")
        self._clear_filters_btn.clicked.connect(self.clear_filters)
        deselect = QPushButton("Deselect")
        deselect.setObjectName("SecondaryButton")
        apply_button_icon(deselect, "x")
        deselect.setToolTip(
            "Clear the selected queue row. Manual Generation then creates a Not available "
            "queue row for today."
        )
        deselect.clicked.connect(self.clear_selection)
        toolbar.addWidget(from_label)
        toolbar.addWidget(self._from_date)
        toolbar.addWidget(to_label)
        toolbar.addWidget(self._to_date)
        toolbar.addWidget(self._reload_btn)
        toolbar.addWidget(self._clear_filters_btn)
        toolbar.addWidget(deselect)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self._filter_banner = QLabel("")
        self._filter_banner.setObjectName("image_warning_text")
        self._filter_banner.setWordWrap(True)
        self._filter_banner.hide()
        root.addWidget(self._filter_banner)

        self._overview_row = QWidget()
        self._overview_row.setObjectName("TransparentBlock")
        stats = QGridLayout(self._overview_row)
        stats.setContentsMargins(0, 0, 0, 0)
        stats.setHorizontalSpacing(8)
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
            tile.setContentsMargins(10, 8, 10, 8)
            tile.setSpacing(2)
            heading = QLabel(label)
            heading.setObjectName("FieldLabel")
            value.setObjectName("ImageStatValue")
            tile.addWidget(heading)
            tile.addWidget(value)
            host = NestedPanel()
            host.setLayout(tile)
            stats.addWidget(host, 0, col)
        self._overview_row.hide()
        root.addWidget(self._overview_row)

        self._selected_panel = NestedPanel()
        selected_layout = QVBoxLayout(self._selected_panel)
        selected_layout.setContentsMargins(10, 8, 10, 8)
        selected_layout.setSpacing(2)
        selected_layout.addWidget(section_heading("SELECTED ALBUM", "search"))
        self._selected_album = QLabel("No album selected")
        self._selected_album.setObjectName("ImageSelectedTitle")
        self._selected_album.setWordWrap(True)
        self._selected_meta = QLabel("Select a queue row to inspect background and thumbnail.")
        self._selected_meta.setObjectName("PageSubtitle")
        self._selected_meta.setWordWrap(True)
        selected_layout.addWidget(self._selected_album)
        selected_layout.addWidget(self._selected_meta)
        self._selected_panel.hide()
        root.addWidget(self._selected_panel)

        queue_hint = QLabel(
            "One row per album and channel. Each album gets one shared background and thumbnail. "
            "Click a row to preview. Right-click to Retry or Regenerate."
        )
        queue_hint.setObjectName("PageSubtitle")
        queue_hint.setWordWrap(True)
        root.addWidget(queue_hint)

        self._table = create_data_table(
            ["Date", "Album", "Channel", "Role", "BG", "TH", "BG File", "TH File"]
        )
        self._table.setObjectName("image_queue_table")
        self._table.setWordWrap(False)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._configure_queue_table_columns()
        self._table.setMinimumHeight(320)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self._table, stretch=1)

        self._footer_detail = QLabel("")
        self._footer_detail.setObjectName("PageSubtitle")
        self._footer_detail.setWordWrap(True)
        self._footer_detail.hide()
        root.addWidget(self._footer_detail)

        prompts = QGridLayout()
        prompts.setHorizontalSpacing(10)
        self._background_prompt = self._make_prompt_edit(
            "Guide how the background should evolve from the chosen sample image."
        )
        self._thumbnail_prompt = self._make_prompt_edit(
            "Guide how the thumbnail should build on the generated background plus text style."
        )
        bg_header, self._background_counter = self._make_prompt_header("BACKGROUND PROMPT")
        th_header, self._thumbnail_counter = self._make_prompt_header("THUMBNAIL PROMPT")
        self._bg_manual_btn = QPushButton("Manual Generation")
        self._bg_manual_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._bg_manual_btn, "sparkles")
        self._bg_manual_btn.setToolTip(
            "With a row selected: regenerate that album background (credits/quota). "
            "With no row selected: create a Not available queue row for today and generate Background."
        )
        self._bg_manual_btn.clicked.connect(
            lambda: self.manual_generation_requested.emit("background")
        )
        self._th_manual_btn = QPushButton("Manual Generation")
        self._th_manual_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._th_manual_btn, "sparkles")
        self._th_manual_btn.setToolTip(
            "With a row selected: regenerate that album thumbnail (credits/quota). "
            "With no row selected: create a Not available queue row for today and generate Thumbnail."
        )
        self._th_manual_btn.clicked.connect(
            lambda: self.manual_generation_requested.emit("thumbnail")
        )
        prompts.addWidget(bg_header, 0, 0)
        prompts.addWidget(self._background_prompt, 1, 0)
        prompts.addWidget(self._bg_manual_btn, 2, 0)
        prompts.addWidget(th_header, 0, 1)
        prompts.addWidget(self._thumbnail_prompt, 1, 1)
        prompts.addWidget(self._th_manual_btn, 2, 1)
        prompts.setColumnStretch(0, 1)
        prompts.setColumnStretch(1, 1)
        root.addLayout(prompts)

        self._clear_btn = QPushButton("Clear Queue")
        self._clear_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._clear_btn, "x")
        self._clear_btn.clicked.connect(self.clear_queue_requested.emit)
        root.addWidget(self._clear_btn)

        self._rows: list[QueueRow] = []
        self._selected_key = ""

        self._from_date.dateChanged.connect(lambda *_: self.filters_changed.emit())
        self._to_date.dateChanged.connect(lambda *_: self.filters_changed.emit())
        self._background_prompt.textChanged.connect(
            lambda *_: self._on_prompt_edited(self._background_prompt, self._background_counter)
        )
        self._thumbnail_prompt.textChanged.connect(
            lambda *_: self._on_prompt_edited(self._thumbnail_prompt, self._thumbnail_counter)
        )
        self._refresh_prompt_counter(self._background_prompt, self._background_counter)
        self._refresh_prompt_counter(self._thumbnail_prompt, self._thumbnail_counter)

    def _configure_queue_table_columns(self) -> None:
        vertical = self._table.verticalHeader()
        vertical.setDefaultSectionSize(_QUEUE_ROW_HEIGHT)
        vertical.setMinimumSectionSize(_QUEUE_ROW_HEIGHT)
        vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
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
    def _make_queue_summary_card() -> tuple[QWidget, QWidget, QLabel, dict[str, QLabel]]:
        card = QWidget()
        card.setObjectName("TransparentBlock")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        counts = QWidget()
        counts.setObjectName("TransparentBlock")
        row = QHBoxLayout(counts)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        values: dict[str, QLabel] = {}
        icons = {
            "rows": ("list", "#8FA4BB"),
            "pending": ("clock", "#F59E0B"),
            "running": ("refresh-cw", "#38BDF8"),
            "failed": ("triangle-alert", "#EF4444"),
            "ready": ("check", "#22C55E"),
        }
        for label in ("Rows", "Pending", "Running", "Failed", "Ready"):
            key = label.lower()
            host = NestedPanel()
            tile = QHBoxLayout(host)
            tile.setContentsMargins(10, 8, 10, 8)
            tile.setSpacing(8)
            icon_name, color = icons[key]
            tile.addWidget(icon_label(icon_name, size=16, color=color), 0, Qt.AlignmentFlag.AlignTop)
            copy = QVBoxLayout()
            copy.setContentsMargins(0, 0, 0, 0)
            copy.setSpacing(2)
            heading = QLabel(label)
            heading.setObjectName("FieldLabel")
            value = QLabel("0")
            value.setObjectName("ImageStatValue")
            caption = QLabel(_QUEUE_STATUS_CAPTIONS[key])
            caption.setObjectName("PageSubtitle")
            copy.addWidget(heading)
            copy.addWidget(value)
            copy.addWidget(caption)
            tile.addLayout(copy, 1)
            row.addWidget(host, 1)
            values[key] = value

        message = QLabel("")
        message.setObjectName("PageSubtitle")
        message.setWordWrap(True)
        message.hide()
        layout.addWidget(counts)
        layout.addWidget(message)
        return card, counts, message, values

    @staticmethod
    def _make_date_edit():
        edit = StudioDateEdit()
        edit.setDate(QDate.fromString(today_ymd(), "yyyy-MM-dd"))
        edit.setFixedWidth(132)
        return edit

    @staticmethod
    def _make_prompt_edit(placeholder: str) -> QTextEdit:
        edit = QTextEdit()
        edit.setObjectName(SHELL_TEXT_EDIT_ID)
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(112)
        edit.setToolTip(f"Maximum {IMAGE_PROMPT_MAX_CHARS} characters (matches API image prompt gate).")
        return edit

    @staticmethod
    def _prompt_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _make_prompt_header(self, title: str) -> tuple[QWidget, QLabel]:
        host = QWidget()
        host.setObjectName("TransparentBlock")
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._prompt_label(title))
        row.addStretch(1)
        counter = QLabel(f"0 / {IMAGE_PROMPT_MAX_CHARS}")
        counter.setObjectName("PageSubtitle")
        counter.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(counter)
        return host, counter

    def _refresh_prompt_counter(self, edit: QTextEdit, counter: QLabel) -> None:
        length = len(edit.toPlainText())
        counter.setText(f"{length} / {IMAGE_PROMPT_MAX_CHARS}")
        if length >= IMAGE_PROMPT_MAX_CHARS:
            counter.setStyleSheet("color: #f87171;")
        else:
            counter.setStyleSheet("")

    def _on_prompt_edited(self, edit: QTextEdit, counter: QLabel) -> None:
        text = edit.toPlainText()
        if len(text) > IMAGE_PROMPT_MAX_CHARS:
            cursor = edit.textCursor()
            position = cursor.position()
            clamped = clamp_image_prompt(text)
            edit.blockSignals(True)
            edit.setPlainText(clamped)
            cursor = edit.textCursor()
            cursor.setPosition(min(position, len(clamped)))
            edit.setTextCursor(cursor)
            edit.blockSignals(False)
        self._refresh_prompt_counter(edit, counter)
        self.prompts_changed.emit()

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
        return clamp_image_prompt(self._background_prompt.toPlainText())

    def thumbnail_prompt(self) -> str:
        return clamp_image_prompt(self._thumbnail_prompt.toPlainText())

    def set_prompts(self, background: str, thumbnail: str) -> None:
        self._background_prompt.blockSignals(True)
        self._thumbnail_prompt.blockSignals(True)
        self._background_prompt.setPlainText(clamp_image_prompt(background))
        self._thumbnail_prompt.setPlainText(clamp_image_prompt(thumbnail))
        self._background_prompt.blockSignals(False)
        self._thumbnail_prompt.blockSignals(False)
        self._refresh_prompt_counter(self._background_prompt, self._background_counter)
        self._refresh_prompt_counter(self._thumbnail_prompt, self._thumbnail_counter)

    def set_stat_values(self, *, date_range: str, matched_batches: int, queue_status: str) -> None:
        self._date_range_value.setText(date_range)
        self._matched_batches_value.setText(str(matched_batches))
        self._queue_status_value.setText(queue_status)
        self._queue_status_value.setProperty("tone", self._queue_status_tone(queue_status))
        self._queue_status_value.style().unpolish(self._queue_status_value)
        self._queue_status_value.style().polish(self._queue_status_value)

    @staticmethod
    def _queue_status_tone(status: str) -> str:
        key = str(status or "").strip().lower()
        if any(token in key for token in ("fail", "error", "unable")):
            return "danger"
        if any(token in key for token in ("pending", "wait")):
            return "warning"
        if any(token in key for token in ("run", "generat", "process", "refresh")):
            return "active"
        if any(token in key for token in ("ready", "complete", "success", "cleared")):
            return "success"
        return "muted"

    def set_selected_album(self, row: QueueRow | None) -> None:
        if row is None:
            self._selected_album.setText("No album selected")
            self._selected_meta.setText("Select a queue row to inspect background and thumbnail.")
            return
        self._selected_album.setText(row.album_label or "—")
        role = format_channel_role_label(row.role)
        self._selected_meta.setText(f"{row.date_label} · {row.profile_name} ({role})")

    def clear_filters(self) -> None:
        today = today_ymd()
        self.set_date_range(today, today)
        self.filters_changed.emit()

    def set_queue_summary(self, summary: str) -> None:
        counts = parse_queue_status_counts(summary)
        if counts is None:
            self._summary_counts.hide()
            self._summary_message.setText(summary)
            self._summary_message.setVisible(bool(str(summary or "").strip()))
            return
        for key, value in counts.items():
            self._summary_values[key].setText(str(value))
        self._summary_message.hide()
        self._summary_counts.show()

    def set_footer_detail(self, detail: str) -> None:
        info, _errors = split_queue_footer_detail(detail)
        if info:
            self._footer_detail.setText(info)
            self._footer_detail.show()
        else:
            self._footer_detail.clear()
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
        self._reload_btn.setEnabled(enabled)

    def set_rows(self, rows: list[QueueRow], selected_key: str | None) -> None:
        self._rows = rows
        # None = caller wants default first row; "" = explicit deselection.
        if selected_key is None:
            self._selected_key = rows[0].key if rows else ""
        else:
            self._selected_key = selected_key
        self._queue_count.setText(str(len(rows)))
        if not rows:
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, 8)
            item = QTableWidgetItem(
                "No image jobs found. Try changing the date range or clearing the filters."
            )
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item.setToolTip("No image jobs found. Try changing the date range or clearing the filters.")
            self._table.setItem(0, 0, item)
            self._table.setRowHeight(0, _QUEUE_ROW_HEIGHT)
            self.set_selected_album(None)
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
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col_index in (_COL_BG, _COL_TH):
                    status = (
                        row.bg_job.status if row.bg_job and col_index == _COL_BG else (
                            row.th_job.status if row.th_job else value
                        )
                    )
                    item.setForeground(_status_foreground(str(status or "")))
                item.setToolTip(tooltips[col_index])
                self._table.setItem(row_index, col_index, item)
            self._table.setRowHeight(row_index, _QUEUE_ROW_HEIGHT)

        self._table.blockSignals(True)
        self._table.clearSelection()
        if self._selected_key:
            for row_index, row in enumerate(rows):
                if row.key == self._selected_key:
                    self._table.selectRow(row_index)
                    break
        self._table.blockSignals(False)
        self.set_selected_album(self.selected_row())

    def clear_selection(self) -> None:
        self._selected_key = ""
        self._table.clearSelection()
        self.set_selected_album(None)
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
                self.set_selected_album(self._rows[row_index])
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
