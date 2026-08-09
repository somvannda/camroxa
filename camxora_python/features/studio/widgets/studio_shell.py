"""Studio shell — modes + scene tree | preview | inspector + timeline (docs 06)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from features.studio.widgets.ai_panel import AiDesignerPanel
from features.studio.widgets.asset_browser_dialog import AssetBrowserDialog
from features.studio.widgets.beginner_panel import BeginnerPanel
from features.studio.widgets.developer_json import DeveloperJsonPanel
from features.studio.widgets.inspector_host import InspectorHost
from features.studio.widgets.preview_stage import StudioPreviewStage
from features.studio.widgets.scene_tree import StudioSceneTree
from features.studio.widgets.timeline_stub import StudioTimelineStub
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class StudioShell(QWidget):
    new_requested = Signal()
    save_requested = Signal()
    undo_requested = Signal()
    project_selected = Signal(str)
    name_changed = Signal(str)
    patch_requested = Signal(dict)
    export_json_requested = Signal()
    export_video_requested = Signal()
    select_audio_requested = Signal()
    mode_changed = Signal(str)
    template_save_requested = Signal()
    ai_generate_requested = Signal(str)
    ai_modify_requested = Signal(str)
    ai_improve_requested = Signal()
    json_apply_requested = Signal(dict)
    timeline_play_toggled = Signal(bool)
    timeline_seek_requested = Signal(float)
    favorite_toggled = Signal(str, bool)
    node_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        title = QLabel("Composition Studio")
        title.setObjectName(SUBTITLE_LABEL_ID)
        toolbar.addWidget(title)

        self._mode = QComboBox()
        for key, label in (
            ("beginner", "Beginner"),
            ("creator", "Creator"),
            ("expert", "Expert"),
            ("developer", "Developer"),
        ):
            self._mode.addItem(label, key)
        self._mode.setCurrentIndex(1)
        self._mode.currentIndexChanged.connect(self._emit_mode)
        toolbar.addWidget(self._mode)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(160)
        self._project_combo.currentIndexChanged.connect(self._emit_project)
        toolbar.addWidget(self._project_combo)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Composition name")
        self._name.setMinimumWidth(140)
        self._name.textChanged.connect(self.name_changed.emit)
        toolbar.addWidget(self._name)

        self._new_btn = QPushButton("New")
        self._new_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._new_btn.clicked.connect(self.new_requested.emit)
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._undo_btn.clicked.connect(self.undo_requested.emit)
        self._template_btn = QPushButton("Save template")
        self._template_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._template_btn.clicked.connect(self.template_save_requested.emit)
        self._browse_btn = QPushButton("Browse assets")
        self._browse_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._browse_btn.clicked.connect(self._open_asset_browser)
        self._audio_btn = QPushButton("Audio")
        self._audio_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._audio_btn.clicked.connect(self.select_audio_requested.emit)
        self._export_json_btn = QPushButton("Export JSON")
        self._export_json_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._export_json_btn.clicked.connect(self.export_json_requested.emit)
        self._export_video_btn = QPushButton("Export Video")
        self._export_video_btn.clicked.connect(self.export_video_requested.emit)
        for btn in (
            self._new_btn,
            self._save_btn,
            self._undo_btn,
            self._template_btn,
            self._browse_btn,
            self._audio_btn,
            self._export_json_btn,
            self._export_video_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        self._status = QLabel("Saved")
        self._status.setObjectName(SUBTITLE_LABEL_ID)
        toolbar.addWidget(self._status)
        root.addLayout(toolbar)

        self._stack = QStackedWidget()
        # 0 beginner
        self._beginner = BeginnerPanel()
        self._beginner.generate_requested.connect(self.ai_generate_requested.emit)
        self._stack.addWidget(self._beginner)

        # 1 creator/expert workspace
        workspace = QWidget()
        ws_layout = QVBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        tree_caption = QLabel("Scene")
        tree_caption.setObjectName(SUBTITLE_LABEL_ID)
        left_layout.addWidget(tree_caption)
        self._tree = StudioSceneTree()
        left_layout.addWidget(self._tree, stretch=1)
        self._ai = AiDesignerPanel()
        self._ai.generate_requested.connect(self.ai_generate_requested.emit)
        self._ai.modify_requested.connect(self.ai_modify_requested.emit)
        self._ai.improve_requested.connect(self.ai_improve_requested.emit)
        left_layout.addWidget(self._ai)
        splitter.addWidget(left)

        self._preview = StudioPreviewStage()
        splitter.addWidget(self._preview)

        self._inspector = InspectorHost()
        self._inspector.patch_requested.connect(self.patch_requested.emit)
        splitter.addWidget(self._inspector)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([260, 680, 360])
        ws_layout.addWidget(splitter, stretch=1)
        self._timeline = StudioTimelineStub()
        self._timeline.play_toggled.connect(self.timeline_play_toggled.emit)
        self._timeline.seek_requested.connect(self.timeline_seek_requested.emit)
        ws_layout.addWidget(self._timeline)
        self._stack.addWidget(workspace)

        # 2 developer
        self._dev = DeveloperJsonPanel()
        self._dev.apply_json_requested.connect(self.json_apply_requested.emit)
        self._stack.addWidget(self._dev)

        root.addWidget(self._stack, stretch=1)
        self._tree.node_selected.connect(self._on_node)
        self._switching_project = False
        self._asset_dialog: AssetBrowserDialog | None = None
        self._stack.setCurrentIndex(1)

    def _on_node(self, key: str) -> None:
        self._inspector.show_node(key)
        self.node_selected.emit(key)
        if self._asset_dialog is not None:
            self._asset_dialog.set_context_node(key)

    def _emit_mode(self, _index: int) -> None:
        mode = str(self._mode.currentData() or "creator")
        if mode == "beginner":
            self._stack.setCurrentIndex(0)
        elif mode == "developer":
            self._stack.setCurrentIndex(2)
        else:
            self._stack.setCurrentIndex(1)
            # Expert uses same workspace; inspectors already expose axes (denser later).
        self.mode_changed.emit(mode)

    def _open_asset_browser(self) -> None:
        if self._asset_dialog is None:
            dialog = AssetBrowserDialog(self)
            dialog.apply_requested.connect(self.patch_requested.emit)
            dialog.favorite_toggled.connect(self.favorite_toggled.emit)
            self._asset_dialog = dialog
        self._asset_dialog.show()
        self._asset_dialog.raise_()
        self._asset_dialog.activateWindow()

    def set_favorites(self, ids: list[str]) -> None:
        if self._asset_dialog is not None:
            self._asset_dialog.set_favorites(ids)

    def _emit_project(self, _index: int) -> None:
        if self._switching_project:
            return
        project_id = self._project_combo.currentData()
        if isinstance(project_id, str) and project_id:
            self.project_selected.emit(project_id)

    def set_projects(self, projects: list[tuple[str, str]], selected_id: str | None) -> None:
        self._switching_project = True
        self._project_combo.clear()
        for pid, name in projects:
            self._project_combo.addItem(name, pid)
        if selected_id:
            idx = self._project_combo.findData(selected_id)
            if idx >= 0:
                self._project_combo.setCurrentIndex(idx)
        self._switching_project = False

    def set_name(self, name: str) -> None:
        blocked = self._name.blockSignals(True)
        self._name.setText(name)
        self._name.blockSignals(blocked)

    def set_dirty(self, dirty: bool) -> None:
        self._status.setText("Unsaved" if dirty else "Saved")
        self._save_btn.setEnabled(dirty)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_export_busy(self, busy: bool) -> None:
        self._export_video_btn.setEnabled(not busy)
        self._export_json_btn.setEnabled(not busy)
        self._browse_btn.setEnabled(not busy)
        self._export_video_btn.setText("Exporting…" if busy else "Export Video")

    def bind_document(self, state: dict) -> None:
        self._inspector.bind_all(state)

    def apply_preview(self, doc: dict) -> None:
        self._preview.apply_document(doc)
        self._timeline.set_duration(self._preview.duration_sec())
        self._dev.set_document(doc)

    def set_ai_explanation(self, text: str) -> None:
        self._ai.set_explanation(text)

    def set_timeline_duration(self, duration_sec: float) -> None:
        self._timeline.set_duration(duration_sec)

    def set_timeline_position(self, time_sec: float) -> None:
        self._timeline.set_position(time_sec)

    def set_timeline_playing(self, playing: bool) -> None:
        self._timeline.set_playing(playing)

    def preview(self) -> StudioPreviewStage:
        return self._preview

    def select_node(self, key: str) -> None:
        self._tree.select_node(key)
        self._inspector.show_node(key)
