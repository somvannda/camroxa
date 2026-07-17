"""Selected progress row detail panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.progress.widgets.operational_rows_card import EffectiveProgressRow
from shared.lib.manual_asset_paths import ManualAssetInspection, manual_inspection_key
from shared.lib.formatting import format_channel_role_label
from shared.lib.progress_presentation import (
    format_album_label,
    format_pipeline_step_text,
    format_run_date_label,
    format_youtube_compact,
    resolve_progress_error_message,
)
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class ProgressDetailCard(QFrame):
    open_folder_requested = Signal(str)
    open_run_folder_requested = Signal(str)
    sync_manual_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("progress_detail_card")
        self._manual_mode = False
        self._inspections: dict[str, ManualAssetInspection] = {}
        self._syncing_batch_id = ""
        self._entry: EffectiveProgressRow | None = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 22)
        root.setSpacing(12)

        title = QLabel("ROW DETAIL")
        title.setObjectName(SUBTITLE_LABEL_ID)
        title.setContentsMargins(2, 0, 0, 0)
        root.addWidget(title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        scroll_body = QWidget()
        body_layout = QVBoxLayout(scroll_body)
        body_layout.setContentsMargins(6, 4, 6, 10)
        body_layout.setSpacing(12)

        self._placeholder = QLabel(
            "Select a row to inspect export, merge, errors, and YouTube status."
        )
        self._placeholder.setObjectName(SUBTITLE_LABEL_ID)
        self._placeholder.setWordWrap(True)
        self._placeholder.setContentsMargins(2, 0, 0, 0)
        body_layout.addWidget(self._placeholder)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(2, 0, 2, 0)
        content_layout.setSpacing(10)

        self._header = QLabel("")
        self._header.setWordWrap(True)
        content_layout.addWidget(self._header)

        self._batch_id = QLabel("")
        self._batch_id.setObjectName(SUBTITLE_LABEL_ID)
        self._batch_id.setWordWrap(True)
        content_layout.addWidget(self._batch_id)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        content_layout.addWidget(self._error_label)

        self._notes = QLabel("")
        self._notes.setObjectName(SUBTITLE_LABEL_ID)
        self._notes.setWordWrap(True)
        content_layout.addWidget(self._notes)

        grid = QVBoxLayout()
        grid.setSpacing(14)
        grid.setContentsMargins(0, 4, 0, 0)
        self._converter_label = QLabel("")
        self._converter_label.setWordWrap(True)
        self._merge_label = QLabel("")
        self._merge_label.setWordWrap(True)
        self._youtube_label = QLabel("")
        self._youtube_label.setWordWrap(True)
        grid.addWidget(self._section("Export", self._converter_label))
        grid.addWidget(self._section("Merge", self._merge_label))
        grid.addWidget(self._section("YouTube", self._youtube_label))
        content_layout.addLayout(grid)

        self._run_dir = QLabel("")
        self._run_dir.setObjectName(SUBTITLE_LABEL_ID)
        self._run_dir.setWordWrap(True)
        content_layout.addWidget(self._run_dir)

        self._manual_panel = QWidget()
        manual_layout = QVBoxLayout(self._manual_panel)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)
        self._manual_status = QLabel("")
        self._manual_status.setObjectName(SUBTITLE_LABEL_ID)
        self._manual_status.setWordWrap(True)
        self._manual_missing = QLabel("")
        self._manual_missing.setObjectName(SUBTITLE_LABEL_ID)
        self._manual_missing.setWordWrap(True)
        manual_layout.addWidget(self._manual_status)
        manual_layout.addWidget(self._manual_missing)
        content_layout.addWidget(self._manual_panel)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 8, 0, 0)
        actions.setSpacing(8)
        self._open_run_btn = QPushButton("Open Run Folder")
        self._open_run_btn.clicked.connect(self._emit_open_run_folder)
        self._open_manual_btn = QPushButton("Open Manual Folder")
        self._open_manual_btn.clicked.connect(self._emit_open_manual_folder)
        self._continue_btn = QPushButton("Continue Pipeline")
        self._continue_btn.clicked.connect(self._emit_continue_pipeline)
        actions.addWidget(self._open_run_btn)
        actions.addWidget(self._open_manual_btn)
        actions.addWidget(self._continue_btn)
        actions.addStretch()
        content_layout.addLayout(actions)

        body_layout.addWidget(self._content)
        body_layout.addStretch()
        self._content.hide()

        self._scroll.setWidget(scroll_body)
        root.addWidget(self._scroll, 1)

    @staticmethod
    def _section(title: str, body: QLabel) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        heading = QLabel(title.upper())
        heading.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(heading)
        layout.addWidget(body)
        return wrapper

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = enabled
        self._render()

    def set_manual_inspections(self, inspections: dict[str, ManualAssetInspection]) -> None:
        self._inspections = inspections
        self._render()

    def set_syncing_batch_id(self, batch_id: str) -> None:
        self._syncing_batch_id = batch_id
        self._render()

    def set_entry(self, entry: EffectiveProgressRow | None) -> None:
        self._entry = entry
        self._render()

    def _render(self) -> None:
        entry = self._entry
        if entry is None:
            self._placeholder.show()
            self._content.hide()
            return

        self._placeholder.hide()
        self._content.show()

        row = entry.row
        meta = row.meta
        self._header.setText(
            f"{format_run_date_label(row.run_date)} · {format_album_label(row.album)} · "
            f"{row.channel} ({format_channel_role_label(meta.role)}) · "
            f"{entry.effective_stage} / {entry.effective_status}"
        )
        batch_id = str(meta.batch_id or row.batch or "").strip()
        self._batch_id.setText(f"Batch: {batch_id}" if batch_id else "Batch: —")

        error_message = resolve_progress_error_message(
            row,
            effective_stage=entry.effective_stage,
            effective_status=entry.effective_status,
            effective_notes=entry.effective_notes,
        )
        if error_message:
            self._error_label.setText(f"Error: {error_message}")
            self._error_label.show()
        else:
            self._error_label.hide()

        notes = str(entry.effective_notes or row.notes or "").strip()
        if notes and notes != error_message:
            self._notes.setText(notes)
            self._notes.show()
        else:
            self._notes.hide()

        self._converter_label.setText(
            format_pipeline_step_text(entry.effective_converter or row.converter)
        )
        self._merge_label.setText(format_pipeline_step_text(entry.effective_merge or row.merge))
        youtube_text = format_youtube_compact(row)
        if meta.youtube_url:
            youtube_text = f"{youtube_text}\n{meta.youtube_url}"
        self._youtube_label.setText(youtube_text)

        run_dir = str(meta.run_dir or "").strip()
        self._run_dir.setText(f"Run folder: {run_dir}" if run_dir else "Run folder: —")
        self._open_run_btn.setVisible(bool(run_dir))

        if self._manual_mode:
            key = manual_inspection_key(meta.batch_id, meta.profile_id, meta.role)
            inspection = self._inspections.get(key)
            self._manual_panel.show()
            self._open_manual_btn.setVisible(bool(inspection and inspection.directory))
            if inspection is None:
                self._manual_status.setText("Loading manual-folder status...")
                self._manual_missing.hide()
                self._continue_btn.hide()
            else:
                self._manual_status.setText(
                    f"Manual assets: {inspection.ready_count}/{inspection.total} ready · "
                    f"Long: {'Ready' if meta.long_ready else 'Missing'} · "
                    f"Reel: {'Ready' if meta.reel_ready else 'Missing'}\n"
                    f"{inspection.directory}"
                )
                if inspection.ready:
                    self._manual_missing.hide()
                else:
                    self._manual_missing.setText(
                        f"Missing: {', '.join(inspection.missing_labels)}"
                    )
                    self._manual_missing.show()
                show_continue = (
                    inspection.ready
                    and entry.effective_stage.lower() == "image"
                )
                self._continue_btn.setVisible(show_continue)
                self._continue_btn.setText(
                    "Syncing..." if self._syncing_batch_id == meta.batch_id else "Continue Pipeline"
                )
                self._continue_btn.setEnabled(self._syncing_batch_id != meta.batch_id)
        else:
            self._manual_panel.hide()
            self._open_manual_btn.hide()
            self._continue_btn.hide()

    def _emit_open_run_folder(self) -> None:
        if self._entry and self._entry.row.meta.run_dir:
            self.open_run_folder_requested.emit(self._entry.row.meta.run_dir)

    def _emit_open_manual_folder(self) -> None:
        if self._entry is None:
            return
        key = manual_inspection_key(
            self._entry.row.meta.batch_id,
            self._entry.row.meta.profile_id,
            self._entry.row.meta.role,
        )
        inspection = self._inspections.get(key)
        if inspection and inspection.directory:
            self.open_folder_requested.emit(inspection.directory)

    def _emit_continue_pipeline(self) -> None:
        if self._entry:
            self.sync_manual_requested.emit(self._entry.row.meta.batch_id)
