"""Run lane list — Create studio list chrome."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from features.workflow.lib.workflow_steps import (
    format_role_label,
    lane_needs_attention,
    resolve_run_status_label,
)
from shared.lib.ui_font import studio_font
from shared.lib.video_runtime_inspection import ProgressRuntimePresentation, progress_runtime_key
from shared.models.platform import ProgressRow


class LaneListCard(StudioPanel):
    """Selectable run lanes with Create table/list selection."""

    lane_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._selected_key = ""
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("RUN LANES")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        layout.addWidget(title)

        self._subtitle = QLabel("0 lanes · select one for the stage board.")
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        self._list = QListWidget()
        self._list.setObjectName("workflow_lane_list")
        self._list.setMinimumHeight(120)
        self._list.setAlternatingRowColors(True)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list.currentRowChanged.connect(self._on_current_row_changed)
        layout.addWidget(self._list, stretch=1)

    def set_lanes(
        self,
        rows: list[ProgressRow],
        runtime_by_key: dict[str, ProgressRuntimePresentation],
        *,
        selected_key: str,
    ) -> None:
        self._selected_key = selected_key
        count = len(rows)
        self._subtitle.setText(
            f"{count} lane{'s' if count != 1 else ''} · select one for the stage board."
        )

        self._updating = True
        self._list.blockSignals(True)
        self._list.clear()

        selected_row = -1
        for index, row in enumerate(rows):
            key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
            runtime = runtime_by_key.get(key)
            effective_stage = runtime.stage if runtime else row.stage
            effective_status = runtime.status if runtime else row.status
            status_label = resolve_run_status_label(
                effective_stage,
                effective_status,
                row,
                runtime.converter if runtime else row.converter,
                runtime.merge if runtime else row.merge,
            )
            role = format_role_label(row.meta.role)
            attention = " · needs attention" if lane_needs_attention(row, runtime) else ""
            primary = row.channel.strip() or "Unknown channel"
            secondary = f"{row.run_date} · {role} · {effective_stage} · {status_label}{attention}"
            item = QListWidgetItem(f"{primary}\n{secondary}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(f"{primary}\n{secondary}")
            self._list.addItem(item)
            if key == selected_key:
                selected_row = index

        if selected_row >= 0:
            self._list.setCurrentRow(selected_row)
        self._list.blockSignals(False)
        self._updating = False

    def _on_current_row_changed(self, row: int) -> None:
        if self._updating or row < 0:
            return
        item = self._list.item(row)
        if item is None:
            return
        lane_key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not lane_key or lane_key == self._selected_key:
            return
        self._selected_key = lane_key
        self.lane_selected.emit(lane_key)

    def select_key(self, lane_key: str) -> None:
        if lane_key == self._selected_key:
            return
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == lane_key:
                self._list.setCurrentRow(index)
                return
