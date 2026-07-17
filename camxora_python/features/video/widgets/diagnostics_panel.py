"""Collapsible diagnostics panel for the video left rail (Phase 9h)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.video_workspace_diagnostics import VideoWorkspaceDiagnosticsViewModel
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


class VideoWorkspaceDiagnosticsPanel(QGroupBox):
    remount_preview_requested = Signal()
    refresh_workspace_requested = Signal()
    reset_local_draft_requested = Signal()
    copy_diagnostics_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Diagnostics", parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.setObjectName("account_card")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 12, 12)
        root.setSpacing(8)

        subtitle = QLabel("Recovery and save state for the active workspace.")
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        badges = QHBoxLayout()
        badges.setSpacing(6)
        self._preview_badge = QLabel("Preview")
        self._save_badge = QLabel("Save")
        self._export_badge = QLabel("Export")
        self._pipeline_badge = QLabel("Pipeline")
        for badge in (self._preview_badge, self._save_badge, self._export_badge, self._pipeline_badge):
            badge.setObjectName(SUBTITLE_LABEL_ID)
            badges.addWidget(badge)
        badges.addStretch()
        badge_host = QWidget()
        badge_host.setLayout(badges)
        root.addWidget(badge_host)

        self._dirty_row = QHBoxLayout()
        self._dirty_row.setSpacing(6)
        dirty_host = QWidget()
        dirty_host.setLayout(self._dirty_row)
        root.addWidget(dirty_host)

        self._guidance_card = QFrame()
        self._guidance_card.setObjectName("account_card")
        guidance_layout = QVBoxLayout(self._guidance_card)
        guidance_layout.setContentsMargins(10, 10, 10, 10)
        guidance_layout.setSpacing(6)
        self._guidance_title = QLabel("")
        self._guidance_title.setObjectName(SUBTITLE_LABEL_ID)
        self._guidance_title.setWordWrap(True)
        self._guidance_detail = QLabel("")
        self._guidance_detail.setWordWrap(True)
        self._guidance_items = QLabel("")
        self._guidance_items.setWordWrap(True)
        guidance_layout.addWidget(self._guidance_title)
        guidance_layout.addWidget(self._guidance_detail)
        guidance_layout.addWidget(self._guidance_items)
        root.addWidget(self._guidance_card)

        self._status_message = QLabel("Ready")
        self._status_message.setObjectName(SUBTITLE_LABEL_ID)
        self._status_message.setWordWrap(True)
        root.addWidget(self._status_message)

        summary = QGridLayout()
        summary.setHorizontalSpacing(8)
        summary.setVerticalSpacing(6)
        self._template_value = QLabel("—")
        self._branch_value = QLabel("—")
        self._background_value = QLabel("—")
        self._track_value = QLabel("—")
        self._performance_value = QLabel("—")
        for row, (label, value) in enumerate(
            (
                ("Template", self._template_value),
                ("Branch", self._branch_value),
                ("Background", self._background_value),
                ("Track", self._track_value),
                ("Performance", self._performance_value),
            )
        ):
            title = QLabel(label)
            title.setObjectName(SUBTITLE_LABEL_ID)
            value.setWordWrap(True)
            summary.addWidget(title, row, 0)
            summary.addWidget(value, row, 1)
        summary_host = QWidget()
        summary_host.setLayout(summary)
        root.addWidget(summary_host)

        actions = QGridLayout()
        actions.setHorizontalSpacing(6)
        actions.setVerticalSpacing(6)
        self._remount_btn = QPushButton("Remount Preview")
        self._refresh_btn = QPushButton("Refresh Workspace")
        self._reset_btn = QPushButton("Reset Local Draft")
        self._copy_btn = QPushButton("Copy Diagnostics")
        for button in (self._remount_btn, self._refresh_btn, self._reset_btn, self._copy_btn):
            button.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._remount_btn.clicked.connect(self.remount_preview_requested.emit)
        self._refresh_btn.clicked.connect(self.refresh_workspace_requested.emit)
        self._reset_btn.clicked.connect(self.reset_local_draft_requested.emit)
        self._copy_btn.clicked.connect(self.copy_diagnostics_requested.emit)
        actions.addWidget(self._remount_btn, 0, 0)
        actions.addWidget(self._refresh_btn, 0, 1)
        actions.addWidget(self._reset_btn, 1, 0)
        actions.addWidget(self._copy_btn, 1, 1)
        actions_host = QWidget()
        actions_host.setLayout(actions)
        root.addWidget(actions_host)

        self.toggled.connect(self._on_toggled)
        self._on_toggled(self.isChecked())

    def _on_toggled(self, expanded: bool) -> None:
        for widget in (
            self._preview_badge,
            self._save_badge,
            self._export_badge,
            self._pipeline_badge,
            self._guidance_card,
            self._status_message,
            self._template_value,
            self._branch_value,
            self._background_value,
            self._track_value,
            self._performance_value,
            self._remount_btn,
            self._refresh_btn,
            self._reset_btn,
            self._copy_btn,
        ):
            widget.setVisible(expanded)

    def bind(self, model: VideoWorkspaceDiagnosticsViewModel) -> None:
        self._preview_badge.setText(model.preview_status_label)
        self._save_badge.setText(model.save_status_label)
        self._export_badge.setText(model.export_status_label)
        self._pipeline_badge.setText(model.pipeline_status_label)

        while self._dirty_row.count():
            item = self._dirty_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        dirty_added = False
        for domain in model.dirty_domains:
            if not domain.dirty:
                continue
            chip = QLabel(domain.label)
            chip.setObjectName(SUBTITLE_LABEL_ID)
            chip.setVisible(self.isChecked())
            self._dirty_row.addWidget(chip)
            dirty_added = True
        if not dirty_added:
            chip = QLabel("No unsaved domains")
            chip.setObjectName(SUBTITLE_LABEL_ID)
            chip.setVisible(self.isChecked())
            self._dirty_row.addWidget(chip)

        if model.preview_needs_attention:
            self._guidance_card.show()
            self._guidance_title.setText(model.preview_guidance_title)
            self._guidance_detail.setText(model.preview_guidance_detail)
            self._guidance_items.setText("\n".join(f"• {item}" for item in model.preview_guidance_items))
            self._status_message.hide()
        else:
            self._guidance_card.hide()
            self._status_message.show()
            self._status_message.setText(model.preview_status_message)

        self._template_value.setText(model.template_id or "No template selected")
        self._branch_value.setText(model.branch_label)
        self._background_value.setText(model.background_label)
        self._track_value.setText(model.track_label)
        self._performance_value.setText(model.performance_label)
        self._reset_btn.setEnabled(model.can_reset_local_draft)
