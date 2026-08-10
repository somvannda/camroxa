"""Studio left rail — three cards: project, Scene tree, AI Designer."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.studio.widgets.ai_panel import AiDesignerPanel
from features.studio.widgets.scene_tree import StudioSceneTree
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel


def _compact_card(panel: SettingsPanel) -> SettingsPanel:
    if hasattr(panel, "_root"):
        panel._root.setContentsMargins(12, 12, 12, 12)
        panel._root.setSpacing(8)
    if hasattr(panel, "_body"):
        panel._body.setSpacing(8)
    return panel


class StudioLeftRail(QWidget):
    name_changed = Signal(str)
    project_selected = Signal(str)
    new_requested = Signal()
    save_requested = Signal()
    undo_requested = Signal()
    template_save_requested = Signal()
    node_selected = Signal(str)
    ai_generate_requested = Signal(str)
    ai_modify_requested = Signal(str)
    ai_improve_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # --- Card 1: project chrome ---
        project = _compact_card(
            SettingsPanel("Composition Studio", subtitle="", fill_available_height=False)
        )
        self._dirty_badge = QLabel("Ready")
        self._dirty_badge.setObjectName(SUBTITLE_LABEL_ID)
        project.add_action(self._dirty_badge)

        self._project_combo = QComboBox()
        self._project_combo.currentIndexChanged.connect(self._emit_project)
        project.add_widget(self._project_combo)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Composition name")
        self._name.textChanged.connect(self.name_changed.emit)
        project.add_widget(self._name)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        self._new_btn = QPushButton("New")
        self._new_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._new_btn.clicked.connect(self.new_requested.emit)
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._undo_btn.clicked.connect(self.undo_requested.emit)
        self._template_btn = QPushButton("Template")
        self._template_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._template_btn.setToolTip("Save template")
        self._template_btn.clicked.connect(self.template_save_requested.emit)
        for btn in (self._new_btn, self._save_btn, self._undo_btn, self._template_btn):
            actions.addWidget(btn)
        action_host = QWidget()
        action_host.setLayout(actions)
        project.add_widget(action_host)
        root.addWidget(project, stretch=0)

        # --- Card 2: scene tree ---
        scene = _compact_card(SettingsPanel("Scene", subtitle="", fill_available_height=True))
        self._tree = StudioSceneTree()
        self._tree.node_selected.connect(self.node_selected.emit)
        scene.add_widget(self._tree, stretch=1)
        root.addWidget(scene, stretch=1)

        # --- Card 3: AI Designer ---
        ai_card = _compact_card(
            SettingsPanel(
                "AI Designer",
                subtitle="Edits Scene JSON only — never pixels.",
                fill_available_height=False,
            )
        )
        self._ai = AiDesignerPanel()
        self._ai.generate_requested.connect(self.ai_generate_requested.emit)
        self._ai.modify_requested.connect(self.ai_modify_requested.emit)
        self._ai.improve_requested.connect(self.ai_improve_requested.emit)
        ai_card.add_widget(self._ai)
        root.addWidget(ai_card, stretch=0)

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
        self._dirty_badge.setText("Unsaved" if dirty else "Ready")
        self._save_btn.setEnabled(dirty)

    def set_status(self, text: str) -> None:
        self._dirty_badge.setText(text)

    def set_ai_explanation(self, text: str) -> None:
        self._ai.set_explanation(text)

    def select_node(self, key: str) -> None:
        self._tree.select_node(key)
