from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QHeaderView
from PyQt6.QtCore import Qt

from .helpers.style_helper import set_panel_role


class YouTubeViewMixin:
    def _build_youtube_workspace_page(self) -> QWidget:
        page = QWidget()
        set_panel_role(page, "center")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel("YouTube Uploads")
        self._set_label_role(title, "sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.youtube_refresh_button = QPushButton("Refresh")
        self._set_button_role(self.youtube_refresh_button, "secondary")
        self.youtube_refresh_button.clicked.connect(lambda: self._refresh_youtube_jobs_table())
        header_layout.addWidget(self.youtube_refresh_button)
        self.youtube_retry_button = QPushButton("Retry")
        self._set_button_role(self.youtube_retry_button, "secondary")
        self.youtube_retry_button.clicked.connect(self._retry_selected_youtube_job)
        header_layout.addWidget(self.youtube_retry_button)
        self.youtube_cancel_button = QPushButton("Cancel")
        self._set_button_role(self.youtube_cancel_button, "danger")
        self.youtube_cancel_button.clicked.connect(self._cancel_youtube_upload)
        header_layout.addWidget(self.youtube_cancel_button)
        layout.addWidget(header)

        self.youtube_jobs_table = QTableWidget(0, 8)
        self._apply_card_field(self.youtube_jobs_table)
        self.youtube_jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.youtube_jobs_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.youtube_jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.youtube_jobs_table.verticalHeader().setVisible(False)
        self.youtube_jobs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.youtube_jobs_table.setHorizontalHeaderLabels(["Batch", "Profile", "Role", "File", "Status", "Attempts", "YouTube", "Error"])
        self.youtube_jobs_table.itemSelectionChanged.connect(self._on_youtube_row_selected)
        layout.addWidget(self.youtube_jobs_table, 1)

        self.youtube_status_label = QLabel("Ready")
        self._set_label_role(self.youtube_status_label, "statusMuted")
        layout.addWidget(self.youtube_status_label)
        return page

