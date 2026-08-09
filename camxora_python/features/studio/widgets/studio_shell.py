"""Studio shell — toolbar + scene tree | preview | inspector + asset library (doc 06)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from features.studio.widgets.asset_library import AssetLibraryPanel
from features.studio.widgets.inspector_host import InspectorHost
from features.studio.widgets.preview_stage import StudioPreviewStage
from features.studio.widgets.scene_tree import StudioSceneTree
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
        toolbar.addSpacing(12)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(180)
        self._project_combo.currentIndexChanged.connect(self._emit_project)
        toolbar.addWidget(self._project_combo)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Composition name")
        self._name.setMinimumWidth(160)
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
        self._audio_btn = QPushButton("Audio")
        self._audio_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._audio_btn.setToolTip("Select MP3 for Studio video export")
        self._audio_btn.clicked.connect(self.select_audio_requested.emit)
        self._export_json_btn = QPushButton("Export JSON")
        self._export_json_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._export_json_btn.clicked.connect(self.export_json_requested.emit)
        self._export_video_btn = QPushButton("Export Video")
        self._export_video_btn.clicked.connect(self.export_video_requested.emit)
        toolbar.addWidget(self._new_btn)
        toolbar.addWidget(self._save_btn)
        toolbar.addWidget(self._undo_btn)
        toolbar.addWidget(self._audio_btn)
        toolbar.addWidget(self._export_json_btn)
        toolbar.addWidget(self._export_video_btn)
        toolbar.addStretch()
        self._status = QLabel("Saved")
        self._status.setObjectName(SUBTITLE_LABEL_ID)
        toolbar.addWidget(self._status)
        root.addLayout(toolbar)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self._tree = StudioSceneTree()
        left_layout.addWidget(self._tree, stretch=1)
        self._assets = AssetLibraryPanel()
        self._assets.apply_requested.connect(self.patch_requested.emit)
        left_layout.addWidget(self._assets, stretch=1)
        splitter.addWidget(left)

        self._preview = StudioPreviewStage()
        splitter.addWidget(self._preview)

        self._inspector = InspectorHost()
        self._inspector.patch_requested.connect(self.patch_requested.emit)
        splitter.addWidget(self._inspector)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([280, 640, 360])
        root.addWidget(splitter, stretch=1)

        self._tree.node_selected.connect(self._inspector.show_node)
        self._switching_project = False

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
        if busy:
            self._export_video_btn.setText("Exporting…")
        else:
            self._export_video_btn.setText("Export Video")

    def bind_document(self, state: dict) -> None:
        self._inspector.bind_all(state)

    def apply_preview(self, doc: dict) -> None:
        self._preview.apply_document(doc)

    def select_node(self, key: str) -> None:
        self._tree.select_node(key)
        self._inspector.show_node(key)
