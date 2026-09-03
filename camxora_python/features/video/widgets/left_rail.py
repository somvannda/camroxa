"""Video workspace left rail — template controls and domain tabs."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from features.video.widgets.inspector_fields import cap_combo_min_widths
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel, make_scrollable_tab_page


class VideoLeftRail(SettingsPanel):
    template_name_changed = Signal(str)
    template_selected = Signal(str)
    new_requested = Signal()
    save_requested = Signal()
    delete_requested = Signal()
    export_requested = Signal()
    restore_original_requested = Signal()
    domain_tab_changed = Signal(str)

    _DOMAIN_TABS = (
        ("spectrum", "Spectrum"),
        ("background", "Background"),
        ("logo", "Logo"),
        ("particles", "Particles"),
        ("lightning", "Lightning"),
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        domain_pages: dict[str, QWidget] | None = None,
        diagnostics_panel: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Video Controls",
            subtitle="Template and domain inspectors",
            fill_available_height=True,
            parent=parent,
        )
        self._dirty_badge = QLabel("Ready")
        self._dirty_badge.setObjectName(SUBTITLE_LABEL_ID)
        self.add_action(self._dirty_badge)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Template name")
        self._name_input.textChanged.connect(self.template_name_changed.emit)
        self.add_widget(self._name_input)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self._new_btn = QPushButton("New")
        self._new_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._new_btn.setToolTip("Create a blank video template from scratch")
        self._new_btn.clicked.connect(self.new_requested.emit)
        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("TransportPrimary")
        self._save_btn.setToolTip("Save the current look into this video template.")
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._restore_original_btn = QPushButton("Restore original")
        self._restore_original_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._restore_original_btn.setToolTip(
            "Restore this video template to the snapshot saved when it was first created "
            "(or first saved after upgrade). Unsaved session edits are discarded."
        )
        self._restore_original_btn.clicked.connect(self.restore_original_requested.emit)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._delete_btn.clicked.connect(self.delete_requested.emit)
        self._export_btn = QPushButton("Export")
        self._export_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._export_btn.setToolTip("Export template as marketplace zip bundle")
        self._export_btn.clicked.connect(self.export_requested.emit)
        self._export_btn.setVisible(False)  # Hidden by default, shown only for admin
        actions.addWidget(self._new_btn)
        actions.addWidget(self._save_btn)
        actions.addWidget(self._restore_original_btn)
        actions.addWidget(self._delete_btn)
        actions.addWidget(self._export_btn)
        action_host = QWidget()
        action_host.setLayout(actions)
        self.add_widget(action_host)

        self._template_select = QComboBox()
        self._template_select.currentIndexChanged.connect(self._emit_template_selection)
        self.add_widget(self._template_select)

        self._domain_tabs = QTabWidget()
        self._domain_tabs.currentChanged.connect(self._emit_domain_tab)
        domain_pages = domain_pages or {}
        for key, label in self._DOMAIN_TABS:
            custom_page = domain_pages.get(key)
            if custom_page is not None:
                cap_combo_min_widths(custom_page)
                page = make_scrollable_tab_page(custom_page)
            else:
                page = QWidget()
                layout = QVBoxLayout(page)
                layout.setContentsMargins(8, 8, 8, 8)
                placeholder = QLabel(f"{label} inspector — Phase 9b")
                placeholder.setObjectName(SUBTITLE_LABEL_ID)
                placeholder.setWordWrap(True)
                layout.addWidget(placeholder)
                layout.addStretch()
            self._domain_tabs.addTab(page, label)
        self.add_widget(self._domain_tabs, stretch=1)
        if diagnostics_panel is not None:
            self.add_widget(diagnostics_panel)

        self._switching_template = False

    def _emit_template_selection(self, _index: int) -> None:
        if self._switching_template:
            return
        template_id = self._template_select.currentData()
        if isinstance(template_id, str) and template_id:
            self.template_selected.emit(template_id)

    def _emit_domain_tab(self, index: int) -> None:
        if 0 <= index < len(self._DOMAIN_TABS):
            self.domain_tab_changed.emit(self._DOMAIN_TABS[index][0])

    def set_dirty_state(self, *, workspace_dirty: bool, active_tab: str, tab_dirty: bool) -> None:
        tone = "Unsaved" if workspace_dirty else "Saved"
        tab_tone = f"{active_tab}*" if tab_dirty else active_tab
        self._dirty_badge.setText(f"{tone} · {tab_tone}")

    def set_templates(self, templates: list[tuple[str, str]], selected_id: str | None) -> None:
        self._switching_template = True
        self._template_select.clear()
        for template_id, name in templates:
            self._template_select.addItem(name, template_id)
        if selected_id:
            index = self._template_select.findData(selected_id)
            if index >= 0:
                self._template_select.setCurrentIndex(index)
        self._switching_template = False

    def set_template_name(self, name: str) -> None:
        blocked = self._name_input.blockSignals(True)
        self._name_input.setText(name)
        self._name_input.blockSignals(blocked)

    def select_domain_tab(self, tab_key: str) -> None:
        for index, (key, _label) in enumerate(self._DOMAIN_TABS):
            if key == tab_key:
                self._domain_tabs.setCurrentIndex(index)
                return

    def set_busy(self, *, saving: bool, deleting: bool) -> None:
        self._new_btn.setEnabled(not saving and not deleting)
        self._save_btn.setEnabled(not saving and not deleting)
        self._restore_original_btn.setEnabled(not saving and not deleting)
        self._delete_btn.setEnabled(not saving and not deleting)
        self._template_select.setEnabled(not saving)
        self._save_btn.setText("Saving..." if saving else "Save")
        self._delete_btn.setText("Deleting..." if deleting else "Delete")

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_btn.setEnabled(enabled)

    def set_export_visible(self, visible: bool) -> None:
        """Show the Export button only for authorized admin users."""
        self._export_btn.setVisible(visible)
