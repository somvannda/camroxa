"""Export queue panel — manual and pipeline export console (Phase 9f/9g)."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from shared.models.desktop import VideoExportState, VideoWorkspaceState
from shared.lib.export_bitrate import format_bitrate_mbps, recommended_export_bitrate_kbps
from shared.lib.output_resolutions import OUTPUT_RESOLUTION_OPTIONS, OUTPUT_RESOLUTION_VALUES
from shared.themes.deep_blue import (
    SETTINGS_SECONDARY_BUTTON_ID,
    START_BUTTON_ID,
    SUBTITLE_LABEL_ID,
)
from shared.widgets.window_title_bar import _load_icon_pixmap


class _TrackRemoveDelegate(QStyledItemDelegate):
    """Paint chrome close × on the right; keep theme blue selection (no red focus)."""

    _HIT = 22
    _ICON = 11
    _RIGHT_INSET = 10  # keep × clear of the row edge / selection frame

    def __init__(self, panel: "ExportQueuePanel") -> None:
        super().__init__(panel)
        self._panel = panel
        self._hover_row = -1
        self._hover_pos = QPoint(-1, -1)

    def set_hover(self, row: int, pos: QPoint) -> None:
        self._hover_row = int(row)
        self._hover_pos = QPoint(pos)

    def _remove_rect(self, item_rect: QRect) -> QRect:
        side = self._HIT
        return QRect(
            item_rect.right() - side - self._RIGHT_INSET,
            item_rect.center().y() - side // 2,
            side,
            side,
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Custom paint can fall back to the system highlight (often red on Windows).
        # Force Video-theme selection colors and drop the focus outline.
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        opt.palette.setColor(QPalette.ColorRole.Highlight, QColor("#1a3a5c"))
        opt.palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#4ac0ff"))
        # Full-row selection/hover via theme; elide text so it doesn't run under ×.
        avail = max(0, opt.rect.width() - self._HIT - self._RIGHT_INSET - 12)
        opt.text = opt.fontMetrics.elidedText(str(opt.text or ""), Qt.TextElideMode.ElideRight, avail)
        widget = opt.widget
        if widget is not None:
            style = widget.style()
        else:
            from PySide6.QtWidgets import QApplication

            style = QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        remove_rect = self._remove_rect(opt.rect)
        enabled = not bool(getattr(self._panel, "_export_running", False))
        hovered = (
            enabled
            and index.row() == self._hover_row
            and remove_rect.contains(self._hover_pos)
        )
        pressed = hovered and bool(
            getattr(self._panel, "_track_remove_pressed_row", -1) == index.row()
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        background = QColor(0, 0, 0, 0)
        if enabled and pressed:
            background = QColor(244, 63, 94, 70)
        elif enabled and hovered:
            background = QColor(244, 63, 94, 51)
        if background.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(remove_rect.adjusted(0, 0, -1, -1), 4, 4)

        icon_color = "#cbd5e1"
        if not enabled:
            icon_color = "#64748b"
        elif hovered:
            icon_color = "#fecdd3"
        icon = _load_icon_pixmap("window-close.svg", size=self._ICON, color=icon_color)
        x = remove_rect.x() + (remove_rect.width() - icon.width()) // 2
        y = remove_rect.y() + (remove_rect.height() - icon.height()) // 2
        painter.drawPixmap(x, y, icon)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: N802
        if getattr(self._panel, "_export_running", False):
            return super().editorEvent(event, model, option, index)
        remove_rect = self._remove_rect(option.rect)
        etype = event.type()
        if etype == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton and remove_rect.contains(event.position().toPoint()):
                self._panel._track_remove_pressed_row = index.row()
                if option.widget is not None:
                    option.widget.update(option.rect)
                return True
        if etype == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
            pressed_row = int(getattr(self._panel, "_track_remove_pressed_row", -1))
            self._panel._track_remove_pressed_row = -1
            if (
                event.button() == Qt.MouseButton.LeftButton
                and pressed_row == index.row()
                and remove_rect.contains(event.position().toPoint())
            ):
                path = str(index.data(Qt.ItemDataRole.UserRole) or "").strip()
                if path:
                    self._panel._remove_track_paths([path])
                return True
            if option.widget is not None:
                option.widget.update(option.rect)
        return super().editorEvent(event, model, option, index)


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
    export_resolution_changed = Signal(str)
    fps_changed = Signal(int)
    workers_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding_tracks = False
        self._binding_options = False
        self._track_paths: list[str] = []
        self._export_running = False
        self._track_remove_pressed_row = -1
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
        # Plain QListWidget items keep theme selection; delegate paints chrome ×.
        # InternalMove can swallow double-clicks on Windows — also catch
        # MouseButtonDblClick on the viewport and itemActivated.
        self._track_list = QListWidget()
        self._track_list.setObjectName("video_export_track_list")
        self._track_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._track_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._track_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._track_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._track_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._track_list.setMouseTracking(True)
        self._track_list.viewport().setMouseTracking(True)
        self._track_remove_delegate = _TrackRemoveDelegate(self)
        self._track_list.setItemDelegate(self._track_remove_delegate)
        self._track_list.currentRowChanged.connect(self._on_track_row_changed)
        self._track_list.itemDoubleClicked.connect(self._on_track_double_clicked)
        self._track_list.itemActivated.connect(self._on_track_double_clicked)
        self._track_list.installEventFilter(self)
        self._track_list.viewport().installEventFilter(self)
        self._track_list.model().rowsMoved.connect(self._on_track_rows_moved)
        track_layout.addWidget(self._track_list, 1)
        self._empty_tracks = QLabel("No preview music is attached yet.")
        self._empty_tracks.setObjectName(SUBTITLE_LABEL_ID)
        self._empty_tracks.setWordWrap(True)
        track_layout.addWidget(self._empty_tracks)
        columns.addWidget(track_card, 1)

        # Wrap the right stack in a widget so stretch 1:1 matches the track card width.
        right_host = QWidget()
        right_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_column = QVBoxLayout(right_host)
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(8)
        columns.addWidget(right_host, 1)

        actions_card = QFrame()
        actions_card.setObjectName("account_card")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(12, 10, 12, 10)
        actions_layout.setSpacing(6)
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
        self._export_toggle_btn = QPushButton("Manual Export")
        self._export_toggle_btn.setObjectName(START_BUTTON_ID)
        self._export_toggle_btn.setToolTip(
            "Manual export: render the selected MP3 list on this Video page.\n"
            "Counts as Manual exports (not Studio/pipeline)."
        )
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

        # Merge toggles on their own row.
        toggles_row = QHBoxLayout()
        toggles_row.setContentsMargins(0, 0, 0, 0)
        toggles_row.setSpacing(16)
        self._auto_merge_toggle = QCheckBox("Auto merge MP4")
        self._auto_merge_toggle.toggled.connect(self._on_auto_merge_toggled)
        self._shuffle_merge_toggle = QCheckBox("Shuffle merge")
        self._shuffle_merge_toggle.setToolTip(
            "When checked, merged MP4 order is randomized (like python_app).\n"
            "When unchecked, merge follows the track list order."
        )
        self._shuffle_merge_toggle.toggled.connect(self._on_shuffle_merge_toggled)
        toggles_row.addWidget(self._auto_merge_toggle)
        toggles_row.addWidget(self._shuffle_merge_toggle)
        toggles_row.addStretch(1)
        actions_layout.addLayout(toggles_row)

        # 2 dropdowns per row — compact controls.
        fields_host = QFrame()
        fields_host.setObjectName("video_export_fields")
        fields_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        fields_grid = QGridLayout(fields_host)
        fields_grid.setContentsMargins(0, 0, 0, 0)
        fields_grid.setHorizontalSpacing(8)
        fields_grid.setVerticalSpacing(4)
        fields_grid.setColumnStretch(1, 1)
        fields_grid.setColumnStretch(3, 1)

        self._resolution_combo = QComboBox()
        for value, label in OUTPUT_RESOLUTION_OPTIONS:
            self._resolution_combo.addItem(label, value)
        self._resolution_combo.setToolTip(
            "Export resolution — same list as the preview Output resolution.\n"
            "Use one resolution for the whole batch so Auto merge can join losslessly."
        )
        self._resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)

        self._speed_combo = QComboBox()
        self._speed_combo.addItem("Best Quality", "best_quality")
        self._speed_combo.addItem("Quality", "quality")
        self._speed_combo.addItem("Balance", "balanced")
        self._speed_combo.addItem("Fast", "fast")
        self._speed_combo.addItem("Very Fast", "very_fast")
        self._refresh_speed_tooltip()
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        self._fps_combo = QComboBox()
        for fps_value in (24, 30, 48, 60):
            self._fps_combo.addItem(f"{fps_value} FPS", fps_value)
        self._fps_combo.setToolTip(
            "Export frame rate. Higher = smoother motion (closer to preview), slower encode.\n"
            "Default 24 is fastest. Recommended bitrate scales with FPS."
        )
        self._fps_combo.currentIndexChanged.connect(self._on_fps_changed)
        self._refresh_speed_tooltip()

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 10)
        self._workers_spin.setToolTip(
            "Parallel export jobs. Quality / Best Quality always use 1 worker "
            "(multi-worker freezes the GPU on QHD+)."
        )
        self._workers_spin.valueChanged.connect(self._on_workers_changed)

        # Row 1: Resolution + Speed · Row 2: FPS + Workers
        self._place_export_field(fields_grid, 0, 0, "Resolution", self._resolution_combo)
        self._place_export_field(fields_grid, 0, 2, "Speed", self._speed_combo)
        self._place_export_field(fields_grid, 1, 0, "FPS", self._fps_combo)
        self._place_export_field(fields_grid, 1, 2, "Workers", self._workers_spin)

        actions_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        actions_layout.addWidget(fields_host)
        actions_layout.addStretch(1)
        right_column.addWidget(actions_card, 1)

        status_card = QFrame()
        status_card.setObjectName("account_card")
        status_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(10, 8, 10, 8)
        status_layout.setSpacing(4)
        status_title = QLabel("Status")
        status_title.setObjectName(SUBTITLE_LABEL_ID)
        status_layout.addWidget(status_title)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Overall: 0%")
        self._progress.setFixedHeight(18)
        status_layout.addWidget(self._progress)
        self._merge_progress = QProgressBar()
        self._merge_progress.setRange(0, 100)
        self._merge_progress.setValue(0)
        self._merge_progress.setTextVisible(True)
        self._merge_progress.setFormat("Merge: 0%")
        self._merge_progress.setFixedHeight(18)
        self._merge_progress.hide()
        status_layout.addWidget(self._merge_progress)
        self._stop_merge_btn = QPushButton("Stop Merge")
        self._stop_merge_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._stop_merge_btn.clicked.connect(self.stop_merge_requested.emit)
        self._stop_merge_btn.hide()
        status_layout.addWidget(self._stop_merge_btn)

        # Compact single-line fields — no section titles (saves vertical room for Actions).
        self._current_track = QLabel("Track: —")
        self._current_track.setObjectName(SUBTITLE_LABEL_ID)
        self._current_track.setWordWrap(False)
        status_layout.addWidget(self._current_track)

        self._status_message = QLabel("Ready")
        self._status_message.setObjectName(SUBTITLE_LABEL_ID)
        self._status_message.setWordWrap(True)
        status_layout.addWidget(self._status_message)

        self._detail_output = QLabel("Output: Not selected")
        self._detail_output.setObjectName(SUBTITLE_LABEL_ID)
        self._detail_output.setWordWrap(True)
        status_layout.addWidget(self._detail_output)
        right_column.addWidget(status_card, 0)

    _EXPORT_FIELD_HEIGHT = 24
    _EXPORT_LABEL_WIDTH = 72
    _EXPORT_CONTROL_MIN_WIDTH = 100

    def _place_export_field(
        self,
        grid: QGridLayout,
        row: int,
        col: int,
        label_text: str,
        control: QWidget,
    ) -> None:
        label = QLabel(label_text)
        label.setObjectName(SUBTITLE_LABEL_ID)
        label.setFixedWidth(self._EXPORT_LABEL_WIDTH)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        control.setFixedHeight(self._EXPORT_FIELD_HEIGHT)
        control.setMinimumWidth(self._EXPORT_CONTROL_MIN_WIDTH)
        control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if isinstance(control, QComboBox):
            control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            control.setMinimumContentsLength(6)
            view = control.view()
            if view is not None:
                view.setMinimumWidth(140)
                view.setTextElideMode(Qt.TextElideMode.ElideNone)
        grid.addWidget(label, row, col, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(control, row, col + 1, Qt.AlignmentFlag.AlignVCenter)

    def _parse_resolution_wh(self) -> tuple[int, int]:
        raw = str(self._resolution_combo.currentData() or "1920x1080").strip().lower()
        try:
            w_s, h_s = raw.split("x", 1)
            return max(16, int(w_s)), max(16, int(h_s))
        except Exception:
            return 1920, 1080

    def _refresh_speed_tooltip(self) -> None:
        width, height = self._parse_resolution_wh()
        fps = int(self._fps_combo.currentData() or 24) if hasattr(self, "_fps_combo") else 24
        speed = str(self._speed_combo.currentData() or "fast")
        kbps = recommended_export_bitrate_kbps(width, height, fps, speed)
        mbps = format_bitrate_mbps(kbps)
        self._speed_combo.setToolTip(
            "Encode uses CapCut-inspired Recommended bitrate "
            f"(currently ~{mbps} for {width}×{height} @ {fps}fps · {speed}).\n"
            "Scales with Resolution, FPS, and Speed.\n\n"
            "Best Quality — highest fidelity (full-color pipe + glow; higher Mbps).\n"
            "Quality — preview-parity (full color + spectrum glow).\n"
            "Balance — default throughput.\n"
            "Fast — quicker encode, softer spectrum/color.\n"
            "Very Fast — draft-speed encode."
        )

    def _on_auto_merge_toggled(self, checked: bool) -> None:
        if not self._binding_options:
            self.auto_merge_toggled.emit(bool(checked))

    def _on_shuffle_merge_toggled(self, checked: bool) -> None:
        if not self._binding_options:
            self.shuffle_merge_toggled.emit(bool(checked))

    def _on_resolution_changed(self, _index: int) -> None:
        self._refresh_speed_tooltip()
        if self._binding_options:
            return
        resolution = str(self._resolution_combo.currentData() or "").strip()
        if resolution:
            self.export_resolution_changed.emit(resolution)

    def _on_speed_changed(self, _index: int) -> None:
        self._clamp_workers_for_speed()
        self._refresh_speed_tooltip()
        if self._binding_options:
            return
        mode = str(self._speed_combo.currentData() or "fast")
        self.speed_mode_changed.emit(mode)

    def _clamp_workers_for_speed(self) -> None:
        mode = str(self._speed_combo.currentData() or "fast")
        if mode not in {"best_quality", "quality"}:
            return
        if int(self._workers_spin.value()) <= 1:
            return
        was_binding = self._binding_options
        self._binding_options = True
        try:
            self._workers_spin.setValue(1)
        finally:
            self._binding_options = was_binding
        if not was_binding:
            self.workers_changed.emit(1)

    def _on_fps_changed(self, _index: int) -> None:
        self._refresh_speed_tooltip()
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
        if watched is self._track_list and event is not None and not self._binding_tracks:
            if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                    if not self._export_running and self._track_list.selectedItems():
                        self._remove_selected_tracks()
                        return True
        if watched is self._track_list.viewport() and event is not None and not self._binding_tracks:
            etype = event.type()
            if etype in (QEvent.Type.MouseMove, QEvent.Type.HoverMove) and isinstance(event, QMouseEvent):
                pos = event.position().toPoint()
                item = self._track_list.itemAt(pos)
                row = self._track_list.row(item) if item is not None else -1
                self._track_remove_delegate.set_hover(row, pos)
                self._track_list.viewport().update()
            elif etype == QEvent.Type.Leave:
                self._track_remove_delegate.set_hover(-1, QPoint(-1, -1))
                self._track_remove_pressed_row = -1
                self._track_list.viewport().update()
            elif etype == QEvent.Type.MouseButtonDblClick and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    item = self._track_list.itemAt(event.position().toPoint())
                    if item is not None:
                        # Ignore double-clicks on the × hit zone.
                        row = self._track_list.row(item)
                        rect = self._track_list.visualItemRect(item)
                        if self._track_remove_delegate._remove_rect(rect).contains(event.position().toPoint()):
                            return True
                        self._on_track_double_clicked(item)
                        return True
            elif etype == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                # InternalMove drag often suppresses MouseButtonDblClick on Windows.
                # Treat two quick presses on the same row as play.
                if event.button() == Qt.MouseButton.LeftButton:
                    item = self._track_list.itemAt(event.position().toPoint())
                    if item is not None:
                        rect = self._track_list.visualItemRect(item)
                        if self._track_remove_delegate._remove_rect(rect).contains(event.position().toPoint()):
                            return False  # let delegate handle remove press
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

    def _add_track_list_item(self, name: str, path: str) -> None:
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(
            f"{name}\nClick × to remove from this list (file stays on disk)."
        )
        self._track_list.addItem(item)

    def _remove_track_paths(self, paths: list[str]) -> None:
        if self._binding_tracks or self._export_running:
            return
        remove_paths = {str(path).strip() for path in paths if str(path).strip()}
        if not remove_paths:
            return
        remaining = [path for path in self._track_paths if path not in remove_paths]
        self._track_paths = remaining
        self._binding_tracks = True
        try:
            for index in range(self._track_list.count() - 1, -1, -1):
                item = self._track_list.item(index)
                path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip() if item else ""
                if path in remove_paths:
                    self._track_list.takeItem(index)
        finally:
            self._binding_tracks = False
        self._empty_tracks.setVisible(not remaining)
        self.track_order_changed.emit(remaining)

    def _remove_selected_tracks(self) -> None:
        if self._binding_tracks or self._export_running:
            return
        selected = self._track_list.selectedItems()
        if not selected:
            return
        remove_paths = [
            str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
            for item in selected
            if str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        ]
        self._remove_track_paths(remove_paths)

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
        speed_mode: str = "fast",
        output_resolution: str = "1920x1080",
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
                        self._add_track_list_item(item.name, item.path)
                self._track_paths = paths
            selected_row = paths.index(selected_mp3) if selected_mp3 in paths else -1
            if self._track_list.currentRow() != selected_row:
                self._track_list.setCurrentRow(selected_row)
        finally:
            self._binding_tracks = False

        running = bool(export.running)
        merging = bool(export.merge_running)
        self._export_running = running
        self._track_list.viewport().update()
        has_output_file = bool(str(export.current_output_path or export.last_output_path or "").strip())
        has_output_folder = bool(str(export.output_dir or "").strip() or has_output_file)

        # Toggle button mirrors python_app: Export ↔ Stop Export.
        if running:
            self._export_toggle_btn.setEnabled(not stop_export_pending)
            self._export_toggle_btn.setText("Stopping..." if stop_export_pending else "Stop Export")
            self._export_toggle_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        else:
            self._export_toggle_btn.setEnabled(has_tracks and not busy)
            self._export_toggle_btn.setText("Starting Export..." if busy else "Manual Export")
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
            resolution = str(output_resolution or "1920x1080").strip() or "1920x1080"
            resolution_index = self._resolution_combo.findData(resolution)
            if resolution_index < 0 and resolution not in OUTPUT_RESOLUTION_VALUES:
                self._resolution_combo.addItem(resolution, resolution)
                resolution_index = self._resolution_combo.findData(resolution)
            self._resolution_combo.setCurrentIndex(resolution_index if resolution_index >= 0 else 2)
            speed_index = self._speed_combo.findData(str(speed_mode or "fast"))
            self._speed_combo.setCurrentIndex(speed_index if speed_index >= 0 else 0)
            fps_index = self._fps_combo.findData(int(export.fps or 24))
            self._fps_combo.setCurrentIndex(fps_index if fps_index >= 0 else 0)
            self._workers_spin.setValue(max(1, min(10, int(export.workers or 1))))
            self._clamp_workers_for_speed()
            self._auto_merge_toggle.setEnabled(not running)
            self._shuffle_merge_toggle.setEnabled(not running)
            self._resolution_combo.setEnabled(not running)
            self._speed_combo.setEnabled(not running)
            self._fps_combo.setEnabled(not running)
            self._workers_spin.setEnabled(not running)
        finally:
            self._binding_options = False
        self._refresh_speed_tooltip()

        completed = max(0, int(export.completed_jobs))
        total = max(0, int(export.total_jobs))
        percent = export.progress_percent
        if percent is None and total > 0:
            percent = int(round((completed / total) * 100))
        percent = max(0, min(100, int(percent or 0)))
        self._progress.setValue(percent)
        self._progress.setFormat(f"Overall: {percent}% · {completed}/{max(total, 1)} track(s)")
        merge_percent = 0
        if merging:
            try:
                merge_percent = max(0, min(100, int(export.merge_progress_percent or 0)))
            except (TypeError, ValueError):
                merge_percent = 0
        self._merge_progress.setRange(0, 100)
        self._merge_progress.setValue(merge_percent)
        self._merge_progress.setFormat(f"Merge: {merge_percent}%")
        self._merge_progress.setVisible(merging)
        self._stop_merge_btn.setVisible(merging and not stop_export_pending)

        current_track = Path(selected_mp3).name if (running and selected_mp3.strip()) else ""
        self._current_track.setText(f"Track: {current_track}" if current_track else "Track: —")
        self._status_message.setText(export.current_status or "Ready")

        output_lines = [f"Output: {export.output_dir or 'Not selected'}"]
        if export.current_output_path:
            output_lines.append(f"Target: {export.current_output_path}")
        elif export.last_output_path:
            output_lines.append(f"Last: {export.last_output_path}")
        if export.last_merged_output_path:
            output_lines.append(f"Merged: {export.last_merged_output_path}")
        self._detail_output.setText("\n".join(output_lines))
