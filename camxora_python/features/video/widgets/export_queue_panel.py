"""Export queue panel — manual and pipeline export console (Phase 9f/9g)."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from shared.models.desktop import VideoExportState, VideoWorkspaceState
from shared.themes.deep_blue import (
    SETTINGS_SECONDARY_BUTTON_ID,
    START_BUTTON_ID,
    SUBTITLE_LABEL_ID,
)


class ExportQueuePanel(QWidget):
    """python_app-style export console: batch-export the selected track list
    with the current template. No pipeline run required."""

    mp3_selected = Signal(str)
    mp3_play_requested = Signal(str)
    track_order_changed = Signal(list)
    select_mp3_requested = Signal()
    manual_export_requested = Signal()
    stop_export_requested = Signal()
    stop_merge_requested = Signal()
    open_output_folder_requested = Signal()
    open_output_file_requested = Signal()
    auto_merge_toggled = Signal(bool)
    shuffle_merge_toggled = Signal(bool)
    speed_mode_changed = Signal(str)
    fps_changed = Signal(int)
    workers_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding_tracks = False
        self._binding_options = False
        self._track_paths: list[str] = []
        self._export_running = False
        # Manual double-click detection: InternalMove drag often swallows
        # Qt's MouseButtonDblClick on Windows.
        self._track_press_path = ""
        self._track_press_at = 0.0
        self._track_play_emit_at = 0.0
        # python_app export queue layout: track list on the left, actions and
        # status stacked on the right, side by side under the preview.
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        queue_title = QLabel("Export Queue")
        queue_title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(queue_title)
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)
        root.addLayout(columns, 1)

        track_card = QFrame()
        track_card.setObjectName("account_card")
        track_layout = QVBoxLayout(track_card)
        track_layout.setContentsMargins(12, 12, 12, 12)
        track_layout.setSpacing(8)
        track_title = QLabel("TRACK LIST")
        track_title.setObjectName(SUBTITLE_LABEL_ID)
        track_layout.addWidget(track_title)
        # QListWidget like python_app: left-aligned rows, drag to reorder.
        # InternalMove can swallow double-clicks on Windows — also catch
        # MouseButtonDblClick on the viewport and itemActivated.
        self._track_list = QListWidget()
        self._track_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._track_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._track_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._track_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._track_list.currentRowChanged.connect(self._on_track_row_changed)
        self._track_list.itemDoubleClicked.connect(self._on_track_double_clicked)
        self._track_list.itemActivated.connect(self._on_track_double_clicked)
        self._track_list.viewport().installEventFilter(self)
        self._track_list.model().rowsMoved.connect(self._on_track_rows_moved)
        track_layout.addWidget(self._track_list, 1)
        self._empty_tracks = QLabel("No preview music is attached yet.")
        self._empty_tracks.setObjectName(SUBTITLE_LABEL_ID)
        self._empty_tracks.setWordWrap(True)
        track_layout.addWidget(self._empty_tracks)
        columns.addWidget(track_card, 1)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(8)
        columns.addLayout(right_column, 1)

        actions_card = QFrame()
        actions_card.setObjectName("account_card")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(12, 12, 12, 12)
        actions_layout.setSpacing(8)
        actions_title = QLabel("Actions")
        actions_title.setObjectName(SUBTITLE_LABEL_ID)
        actions_layout.addWidget(actions_title)

        self._select_mp3_btn = QPushButton("Select MP3 Folder")
        self._select_mp3_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._select_mp3_btn.clicked.connect(self.select_mp3_requested.emit)
        self._open_folder_btn = QPushButton("Open Folder")
        self._open_folder_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._open_folder_btn.clicked.connect(self.open_output_folder_requested.emit)
        self._open_file_btn = QPushButton("Open File")
        self._open_file_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._open_file_btn.clicked.connect(self.open_output_file_requested.emit)
        # python_app-style toggle: starts the batch, becomes Stop while running.
        self._export_toggle_btn = QPushButton("Export")
        self._export_toggle_btn.setObjectName(START_BUTTON_ID)
        self._export_toggle_btn.clicked.connect(self._on_export_toggle_clicked)

        export_row = QHBoxLayout()
        export_row.setSpacing(6)
        export_row.addWidget(self._select_mp3_btn, 1)
        export_row.addWidget(self._export_toggle_btn, 1)
        actions_layout.addLayout(export_row)

        helper_row = QHBoxLayout()
        helper_row.setSpacing(6)
        helper_row.addWidget(self._open_folder_btn, 1)
        helper_row.addWidget(self._open_file_btn, 1)
        actions_layout.addLayout(helper_row)

        # Compact options: checkboxes left, fixed-width controls right (no stretch).
        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(16)

        toggles_col = QVBoxLayout()
        toggles_col.setContentsMargins(0, 0, 0, 0)
        toggles_col.setSpacing(6)
        self._auto_merge_toggle = QCheckBox("Auto merge MP4")
        self._auto_merge_toggle.toggled.connect(self._on_auto_merge_toggled)
        self._shuffle_merge_toggle = QCheckBox("Shuffle merge")
        self._shuffle_merge_toggle.setToolTip(
            "When checked, merged MP4 order is randomized (like python_app).\n"
            "When unchecked, merge follows the track list order."
        )
        self._shuffle_merge_toggle.toggled.connect(self._on_shuffle_merge_toggled)
        toggles_col.addWidget(self._auto_merge_toggle)
        toggles_col.addWidget(self._shuffle_merge_toggle)
        toggles_col.addStretch(1)
        options_row.addLayout(toggles_col, 0)

        fields_col = QVBoxLayout()
        fields_col.setContentsMargins(0, 0, 0, 0)
        fields_col.setSpacing(6)

        self._speed_combo = QComboBox()
        self._speed_combo.addItem("Balanced", "balanced")
        self._speed_combo.addItem("Fast", "fast")
        self._speed_combo.addItem("Very Fast", "very_fast")
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        fields_col.addLayout(self._compact_field_row("Speed", self._speed_combo))

        self._fps_combo = QComboBox()
        for fps_value in (24, 30, 48, 60):
            self._fps_combo.addItem(f"{fps_value} FPS", fps_value)
        self._fps_combo.setToolTip(
            "Export frame rate. Higher = smoother motion (closer to preview), slower encode.\n"
            "Default 24 is fastest."
        )
        self._fps_combo.currentIndexChanged.connect(self._on_fps_changed)
        fields_col.addLayout(self._compact_field_row("FPS", self._fps_combo))

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 10)
        self._workers_spin.valueChanged.connect(self._on_workers_changed)
        fields_col.addLayout(self._compact_field_row("Workers", self._workers_spin))

        options_row.addLayout(fields_col, 0)
        options_row.addStretch(1)
        actions_layout.addLayout(options_row)
        right_column.addWidget(actions_card)

        status_card = QFrame()
        status_card.setObjectName("account_card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setSpacing(6)
        status_title = QLabel("Status")
        status_title.setObjectName(SUBTITLE_LABEL_ID)
        status_layout.addWidget(status_title)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Overall: 0%")
        status_layout.addWidget(self._progress)
        self._merge_progress = QProgressBar()
        self._merge_progress.setRange(0, 0)  # busy indicator while merging
        self._merge_progress.setTextVisible(True)
        self._merge_progress.setFormat("Merging…")
        self._merge_progress.hide()
        status_layout.addWidget(self._merge_progress)
        self._stop_merge_btn = QPushButton("Stop Merge")
        self._stop_merge_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._stop_merge_btn.clicked.connect(self.stop_merge_requested.emit)
        self._stop_merge_btn.hide()
        status_layout.addWidget(self._stop_merge_btn)

        current_track_title = QLabel("Current Track")
        current_track_title.setObjectName(SUBTITLE_LABEL_ID)
        status_layout.addWidget(current_track_title)
        self._current_track = QLabel("")
        status_layout.addWidget(self._current_track)

        details_title = QLabel("Details")
        details_title.setObjectName(SUBTITLE_LABEL_ID)
        status_layout.addWidget(details_title)
        self._status_message = QLabel("Ready")
        self._status_message.setObjectName(SUBTITLE_LABEL_ID)
        self._status_message.setWordWrap(True)
        status_layout.addWidget(self._status_message)

        output_title = QLabel("Output")
        output_title.setObjectName(SUBTITLE_LABEL_ID)
        status_layout.addWidget(output_title)
        self._detail_output = QLabel("Output Folder: Not selected")
        self._detail_output.setObjectName(SUBTITLE_LABEL_ID)
        self._detail_output.setWordWrap(True)
        status_layout.addWidget(self._detail_output)
        right_column.addWidget(status_card)
        right_column.addStretch()

    def _compact_field_row(self, label_text: str, control: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName(SUBTITLE_LABEL_ID)
        label.setFixedWidth(56)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        control.setFixedWidth(118)
        row.addWidget(label, 0)
        row.addWidget(control, 0)
        row.addStretch(1)
        return row

    def _on_auto_merge_toggled(self, checked: bool) -> None:
        if not self._binding_options:
            self.auto_merge_toggled.emit(bool(checked))

    def _on_shuffle_merge_toggled(self, checked: bool) -> None:
        if not self._binding_options:
            self.shuffle_merge_toggled.emit(bool(checked))

    def _on_speed_changed(self, _index: int) -> None:
        if self._binding_options:
            return
        mode = str(self._speed_combo.currentData() or "balanced")
        self.speed_mode_changed.emit(mode)

    def _on_fps_changed(self, _index: int) -> None:
        if self._binding_options:
            return
        fps = int(self._fps_combo.currentData() or 24)
        self.fps_changed.emit(fps)

    def _on_workers_changed(self, value: int) -> None:
        if not self._binding_options:
            self.workers_changed.emit(max(1, min(10, int(value))))

    def _on_track_row_changed(self, row: int) -> None:
        if self._binding_tracks or row < 0:
            return
        item = self._track_list.item(row)
        path = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        if path:
            self.mp3_selected.emit(path)

    def _on_track_double_clicked(self, item: QListWidgetItem) -> None:
        if self._binding_tracks or item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not path:
            return
        # Reset manual double-click state and debounce duplicate handlers
        # (press-pair + MouseButtonDblClick / itemActivated).
        self._track_press_path = ""
        self._track_press_at = 0.0
        now = time.monotonic()
        if (now - self._track_play_emit_at) < 0.35:
            return
        self._track_play_emit_at = now
        self.mp3_play_requested.emit(path)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self._track_list.viewport() and event is not None and not self._binding_tracks:
            etype = event.type()
            if etype == QEvent.Type.MouseButtonDblClick and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    item = self._track_list.itemAt(event.position().toPoint())
                    if item is not None:
                        self._on_track_double_clicked(item)
                        return True
            elif etype == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                # InternalMove drag often suppresses MouseButtonDblClick on Windows.
                # Treat two quick presses on the same row as play.
                if event.button() == Qt.MouseButton.LeftButton:
                    item = self._track_list.itemAt(event.position().toPoint())
                    path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip() if item else ""
                    now = time.monotonic()
                    if (
                        path
                        and path == self._track_press_path
                        and (now - self._track_press_at) <= 0.45
                    ):
                        self._on_track_double_clicked(item)
                        return True
                    self._track_press_path = path
                    self._track_press_at = now
        return super().eventFilter(watched, event)

    def _on_track_rows_moved(self, *_args) -> None:
        if self._binding_tracks:
            return
        order = []
        for index in range(self._track_list.count()):
            item = self._track_list.item(index)
            path = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
            if path:
                order.append(path)
        self._track_paths = order
        self.track_order_changed.emit(order)

    def _on_export_toggle_clicked(self) -> None:
        if self._export_running:
            self.stop_export_requested.emit()
            return
        self.manual_export_requested.emit()

    def bind_workspace(
        self,
        workspace: VideoWorkspaceState | None,
        *,
        busy: bool = False,
        stop_export_pending: bool = False,
        speed_mode: str = "balanced",
    ) -> None:
        selected_mp3 = ""
        export = VideoExportState()
        if workspace is not None:
            selected_mp3 = workspace.selected_mp3_path
            export = workspace.export

        has_tracks = bool(workspace and workspace.mp3_list)
        self._empty_tracks.setVisible(not has_tracks)

        paths = [item.path for item in workspace.mp3_list] if workspace else []
        self._binding_tracks = True
        try:
            # Rebuild only when the set/order changed so an in-progress drag
            # isn't interrupted by unrelated export status updates.
            if paths != self._track_paths:
                self._track_list.clear()
                if workspace is not None:
                    for item in workspace.mp3_list:
                        row = QListWidgetItem(item.name)
                        row.setData(Qt.ItemDataRole.UserRole, item.path)
                        self._track_list.addItem(row)
                self._track_paths = paths
            selected_row = paths.index(selected_mp3) if selected_mp3 in paths else -1
            if self._track_list.currentRow() != selected_row:
                self._track_list.setCurrentRow(selected_row)
        finally:
            self._binding_tracks = False

        running = bool(export.running)
        merging = bool(export.merge_running)
        self._export_running = running
        has_output_file = bool(str(export.current_output_path or export.last_output_path or "").strip())
        has_output_folder = bool(str(export.output_dir or "").strip() or has_output_file)

        # Toggle button mirrors python_app: Export ↔ Stop Export.
        if running:
            self._export_toggle_btn.setEnabled(not stop_export_pending)
            self._export_toggle_btn.setText("Stopping..." if stop_export_pending else "Stop Export")
            self._export_toggle_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        else:
            self._export_toggle_btn.setEnabled(has_tracks and not busy)
            self._export_toggle_btn.setText("Starting Export..." if busy else "Export")
            self._export_toggle_btn.setObjectName(START_BUTTON_ID)
        self._export_toggle_btn.style().unpolish(self._export_toggle_btn)
        self._export_toggle_btn.style().polish(self._export_toggle_btn)

        self._select_mp3_btn.setEnabled(not running)
        self._open_folder_btn.setEnabled(has_output_folder and not running)
        self._open_file_btn.setEnabled(has_output_file and not running)

        self._binding_options = True
        try:
            self._auto_merge_toggle.setChecked(bool(export.auto_merge))
            self._shuffle_merge_toggle.setChecked(bool(export.shuffle_merge))
            speed_index = self._speed_combo.findData(str(speed_mode or "balanced"))
            self._speed_combo.setCurrentIndex(speed_index if speed_index >= 0 else 0)
            fps_index = self._fps_combo.findData(int(export.fps or 24))
            self._fps_combo.setCurrentIndex(fps_index if fps_index >= 0 else 0)
            self._workers_spin.setValue(max(1, min(10, int(export.workers or 1))))
            self._auto_merge_toggle.setEnabled(not running)
            self._shuffle_merge_toggle.setEnabled(not running)
            self._speed_combo.setEnabled(not running)
            self._fps_combo.setEnabled(not running)
            self._workers_spin.setEnabled(not running)
        finally:
            self._binding_options = False

        completed = max(0, int(export.completed_jobs))
        total = max(0, int(export.total_jobs))
        percent = export.progress_percent
        if percent is None and total > 0:
            percent = int(round((completed / total) * 100))
        percent = max(0, min(100, int(percent or 0)))
        self._progress.setValue(percent)
        self._progress.setFormat(f"Overall: {percent}% · {completed}/{max(total, 1)} track(s)")
        self._merge_progress.setVisible(merging)
        self._stop_merge_btn.setVisible(merging and not stop_export_pending)

        current_track = Path(selected_mp3).name if (running and selected_mp3.strip()) else ""
        self._current_track.setText(current_track or "—")
        self._status_message.setText(export.current_status or "Ready")

        output_lines = [f"Output Folder: {export.output_dir or 'Not selected'}"]
        if export.current_output_path:
            output_lines.append(f"Target: {export.current_output_path}")
        elif export.last_output_path:
            output_lines.append(f"Last: {export.last_output_path}")
        if export.last_merged_output_path:
            output_lines.append(f"Merged: {export.last_merged_output_path}")
        self._detail_output.setText("\n".join(output_lines))
