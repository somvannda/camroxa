from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QHeaderView, QComboBox, QCheckBox, QTextEdit, QDialog
from PyQt6.QtCore import Qt, QDate

from .helpers.style_helper import set_panel_role
from .helpers import widget_factory


class ProgressViewMixin:
    def _build_progress_workspace_page(self) -> QWidget:
        page = QWidget()
        set_panel_role(page, "center")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel("Progress")
        self._set_label_role(title, "sectionTitle")
        header_layout.addWidget(title)

        header_layout.addStretch(1)

        self.progress_from_date = widget_factory.create_calendar_picker(lambda: self._progress_controller._refresh_progress_table_async(), self.ui, width=118)
        self.progress_to_date = widget_factory.create_calendar_picker(lambda: self._progress_controller._refresh_progress_table_async(), self.ui, width=118)
        today = QDate.currentDate().toString("yyyy-MM-dd")
        widget_factory.set_calendar_picker_value(self.progress_from_date, today)
        widget_factory.set_calendar_picker_value(self.progress_to_date, today)
        header_layout.addWidget(QLabel("From"))
        header_layout.addWidget(self.progress_from_date)
        header_layout.addWidget(QLabel("To"))
        header_layout.addWidget(self.progress_to_date)

        self.progress_active_only = QCheckBox("Active only")
        self._set_widget_property(self.progress_active_only, "uiRole", "toggle")
        self.progress_active_only.stateChanged.connect(lambda _v=0: self._progress_controller._refresh_progress_table_async())
        header_layout.addWidget(self.progress_active_only)

        self.progress_limit_combo = QComboBox()
        self._apply_card_field(self.progress_limit_combo)
        self.progress_limit_combo.addItems(["10", "25", "50"])
        self.progress_limit_combo.setCurrentText("25")
        self.progress_limit_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.progress_limit_combo.setMinimumWidth(64)
        try:
            self.progress_limit_combo.view().setMinimumWidth(64)
        except Exception:
            pass
        self.progress_limit_combo.currentTextChanged.connect(lambda _t="": self._progress_controller._refresh_progress_table_async())
        header_layout.addWidget(self.progress_limit_combo)

        self.progress_refresh_button = QPushButton("Refresh")
        self._set_button_role(self.progress_refresh_button, "secondary")
        self.progress_refresh_button.clicked.connect(lambda: self._progress_controller._refresh_progress_table_async(force=True))
        header_layout.addWidget(self.progress_refresh_button)

        self.progress_cancel_all_button = QPushButton("Cancel All Jobs")
        self._set_button_role(self.progress_cancel_all_button, "danger")
        self.progress_cancel_all_button.clicked.connect(self._progress_controller._progress_cancel_all_pending_jobs)
        header_layout.addWidget(self.progress_cancel_all_button)

        layout.addWidget(header)

        self.progress_summary_label = QLabel("Ready")
        self._set_label_role(self.progress_summary_label, "statusMuted")
        layout.addWidget(self.progress_summary_label)

        self.progress_table = QTableWidget(0, 12)
        self._apply_card_field(self.progress_table)
        self.progress_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.progress_table.customContextMenuRequested.connect(lambda pos: self._progress_controller._on_progress_table_context_menu(pos))
        self.progress_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.progress_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.progress_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.progress_table.verticalHeader().setVisible(False)
        self.progress_table.setHorizontalHeaderLabels(
            ["Batch", "Run Date", "Channel", "Status", "Music", "Image", "Converter", "Merge", "YouTube", "Stage", "Notes", "Updated"]
        )
        # Use ResizeToContents for data columns, Stretch for the wider ones
        _hdr = self.progress_table.horizontalHeader()
        _hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Let Image, Converter, and Notes stretch to fill remaining space
        _hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)   # Image
        _hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)   # Converter
        _hdr.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)  # Notes
        self.progress_table.cellDoubleClicked.connect(self._progress_controller._on_progress_cell_double_clicked)
        layout.addWidget(self.progress_table, 1)

        self.progress_status_label = QLabel("Ready")
        self._set_label_role(self.progress_status_label, "statusMuted")
        layout.addWidget(self.progress_status_label)
        return page
