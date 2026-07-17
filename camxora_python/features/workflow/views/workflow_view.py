"""Workflow page — 100% parity with WorkflowPage.tsx."""

from __future__ import annotations

from PySide6.QtCore import QDate, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.workflow.services.workflow_local_store import WorkflowLocalStore, WorkflowWorkspacePrefs
from features.workflow.lib.workflow_steps import build_workflow_steps, lane_needs_attention
from features.workflow.widgets.empty_state import WorkflowEmptyState
from features.workflow.widgets.error_banner import WorkflowErrorBanner
from features.workflow.widgets.lane_list import LaneListCard
from features.workflow.widgets.selected_run_panel import SelectedRunPanel
from features.workflow.widgets.stats_row import WorkflowStatsRow
from shared.lib.formatting import today_ymd
from shared.lib.page_account_scope import account_cache_mismatch, cached_user_id
from shared.lib.video_runtime_inspection import (
    ProgressRuntimePresentation,
    build_runtime_presentation_map,
    progress_runtime_key,
)
from shared.models.platform import ProgressFilters, ProgressRow
from shared.services.platform_api import PlatformApi
from shared.services.video_workspace_service import get_video_workspace_service
from shared.services.workspace_cache import WorkspaceCache
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.pollable_page import PollablePageMixin
from shared.workers.data_workers import WorkflowLoadResult, WorkflowLoadWorker, WorkflowRuntimeWorker

DEFAULT_POLL_MS = 12_000
ACTIVE_POLL_MS = 4_000
EXPORT_RUNTIME_POLL_MS = 1_500
LANE_COLUMN_WIDTH = 320

HELPER_TEXT = (
    "Visual timeline for one selected run. Use Progress for recovery actions "
    "and failed-row handling."
)


class WorkflowView(PollablePageMixin, QScrollArea):
    """Visual pipeline board driven by progress rows + desktop runtime inspection."""

    poll_interval_ms = DEFAULT_POLL_MS

    def __init__(
        self,
        api: PlatformApi,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        QScrollArea.__init__(self, parent)
        self._init_pollable()
        self._api = api
        self._cache = cache
        self._worker: WorkflowLoadWorker | None = None
        self._runtime_worker: WorkflowRuntimeWorker | None = None
        self._rows: list[ProgressRow] = []
        self._runtime_by_key: dict[str, ProgressRuntimePresentation] = {}
        self._selected_key = ""
        self._loading = True
        self._is_error = False
        self._ever_loaded = False
        self._loaded_user_id: str | None = None
        self._local_workspace_restored = False
        self._local_save_timer = QTimer(self)
        self._local_save_timer.setSingleShot(True)
        self._local_save_timer.setInterval(400)
        self._local_save_timer.timeout.connect(self._persist_local_workspace_prefs)
        self._runtime_timer = QTimer(self)
        self._runtime_timer.setInterval(EXPORT_RUNTIME_POLL_MS)
        self._runtime_timer.timeout.connect(self._refresh_runtime_overlay)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        filter_card = QFrame()
        filter_card.setObjectName("account_card")
        filter_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 16, 16, 16)
        filter_layout.setSpacing(8)

        filter_title = QLabel("Filters")
        filter_title.setObjectName(SUBTITLE_LABEL_ID)
        filter_layout.addWidget(filter_title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(QDate.fromString(today_ymd(), "yyyy-MM-dd"))
        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(QDate.fromString(today_ymd(), "yyyy-MM-dd"))
        self._active_only = QCheckBox("Active only")
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(QLabel("From"))
        toolbar.addWidget(self._from_date)
        toolbar.addWidget(QLabel("To"))
        toolbar.addWidget(self._to_date)
        toolbar.addWidget(self._active_only)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addStretch()
        filter_layout.addLayout(toolbar)
        root.addWidget(filter_card, 0)

        helper = QLabel(HELPER_TEXT)
        helper.setObjectName(SUBTITLE_LABEL_ID)
        helper.setWordWrap(True)
        helper.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        root.addWidget(helper, 0)

        self._stats_row = WorkflowStatsRow()
        root.addWidget(self._stats_row, 0)

        self._error_banner = WorkflowErrorBanner()
        self._error_banner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._error_banner.hide()
        root.addWidget(self._error_banner, 0)

        self._empty_state = WorkflowEmptyState()
        self._empty_state.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._empty_state, 1)

        self._content = QFrame()
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        self._lane_list = LaneListCard()
        self._lane_list.setFixedWidth(LANE_COLUMN_WIDTH)
        self._lane_list.lane_selected.connect(self._select_lane)
        self._selected_panel = SelectedRunPanel()
        content_layout.addWidget(self._lane_list, 0)
        content_layout.addWidget(self._selected_panel, 1)
        self._content.hide()
        root.addWidget(self._content, 1)

        self._from_date.dateChanged.connect(lambda *_: self._on_filters_changed())
        self._to_date.dateChanged.connect(lambda *_: self._on_filters_changed())
        self._active_only.stateChanged.connect(lambda *_: self._on_filters_changed())

        self.setWidget(container)
        self._enter_loading_state()

    def _reset_for_account_change(self) -> None:
        self._loaded_user_id = None
        self._ever_loaded = False
        self._local_workspace_restored = False
        self._rows = []
        self._runtime_by_key = {}
        self._selected_key = ""
        self._enter_loading_state()

    def _restore_local_workspace_prefs(self) -> None:
        prefs = WorkflowLocalStore().read_workspace_prefs()
        if prefs is None:
            return
        self._from_date.blockSignals(True)
        self._to_date.blockSignals(True)
        self._active_only.blockSignals(True)
        if prefs.from_date:
            parsed = QDate.fromString(prefs.from_date, "yyyy-MM-dd")
            if parsed.isValid():
                self._from_date.setDate(parsed)
        if prefs.to_date:
            parsed = QDate.fromString(prefs.to_date, "yyyy-MM-dd")
            if parsed.isValid():
                self._to_date.setDate(parsed)
        self._active_only.setChecked(prefs.active_only)
        if prefs.selected_key:
            self._selected_key = prefs.selected_key
        self._from_date.blockSignals(False)
        self._to_date.blockSignals(False)
        self._active_only.blockSignals(False)
        interval = ACTIVE_POLL_MS if prefs.active_only else DEFAULT_POLL_MS
        self._poll_timer.setInterval(interval)

    def _current_workspace_prefs(self) -> WorkflowWorkspacePrefs:
        return WorkflowWorkspacePrefs(
            from_date=self._from_date.date().toString("yyyy-MM-dd"),
            to_date=self._to_date.date().toString("yyyy-MM-dd"),
            active_only=self._active_only.isChecked(),
            selected_key=self._selected_key,
        )

    def _schedule_local_workspace_save(self) -> None:
        self._local_save_timer.start()

    def _persist_local_workspace_prefs(self) -> None:
        WorkflowLocalStore().write_workspace_prefs(self._current_workspace_prefs())

    def activate_page(self) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        if not self._local_workspace_restored:
            self._restore_local_workspace_prefs()
            self._local_workspace_restored = True
        PollablePageMixin.activate_page(self)

    def deactivate_page(self) -> None:
        if self._local_save_timer.isActive():
            self._local_save_timer.stop()
            self._persist_local_workspace_prefs()
        self._runtime_timer.stop()
        PollablePageMixin.deactivate_page(self)

    def _on_filters_changed(self) -> None:
        interval = ACTIVE_POLL_MS if self._active_only.isChecked() else DEFAULT_POLL_MS
        self._poll_timer.setInterval(interval)
        self._schedule_local_workspace_save()
        self.refresh_data()

    def _current_filters(self) -> ProgressFilters:
        return ProgressFilters(
            limit=80,
            active_only=self._active_only.isChecked(),
            from_date=self._from_date.date().toString("yyyy-MM-dd"),
            to_date=self._to_date.date().toString("yyyy-MM-dd"),
        )

    def refresh_data(self) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._ever_loaded:
            self._loading = True
        self._refresh_btn.setEnabled(False)
        worker = WorkflowLoadWorker(self._api, self._current_filters(), self)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._refresh_btn.setEnabled(True)

    def _enter_loading_state(self) -> None:
        self._loading = True
        self._is_error = False
        self._error_banner.hide()
        self._empty_state.show_loading()
        self._empty_state.show()
        self._content.hide()
        self._stats_row.set_summary_counts(runs=0, active=0, attention=0, done=0)
        self._selected_panel.show_loading()

    def _on_failed(self, _message: str) -> None:
        self._loading = False
        self._is_error = True
        self._error_banner.show()
        if self._rows:
            self._render()
            return
        self._rows = []
        self._runtime_by_key = {}
        self._selected_key = ""
        self._empty_state.show_empty()
        self._empty_state.show()
        self._content.hide()
        self._stats_row.set_summary_counts(runs=0, active=0, attention=0, done=0)
        self._selected_panel.show_no_selection()
        self._sync_runtime_timer()

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, WorkflowLoadResult):
            return
        self._loading = False
        self._is_error = False
        self._ever_loaded = True
        self._error_banner.hide()
        self._rows = payload.response.rows
        self._runtime_by_key = payload.runtime_by_key
        self._ensure_selected_key()
        self._render()
        self._sync_runtime_timer()
        self._loaded_user_id = cached_user_id(self._cache)

    def _refresh_runtime_overlay(self) -> None:
        if not self._rows or (self._runtime_worker is not None and self._runtime_worker.isRunning()):
            return
        worker = WorkflowRuntimeWorker(self._rows, self)
        worker.succeeded.connect(self._on_runtime_refreshed)
        worker.finished.connect(lambda: setattr(self, "_runtime_worker", None))
        self._runtime_worker = worker
        worker.start()

    def _on_runtime_refreshed(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        self._runtime_by_key = payload
        if self._rows:
            self._lane_list.set_lanes(self._rows, self._runtime_by_key, selected_key=self._selected_key)
            self._render_selected()
        self._sync_runtime_timer()

    def _sync_runtime_timer(self) -> None:
        if self._rows and get_video_workspace_service().export_is_active():
            if not self._runtime_timer.isActive():
                self._runtime_timer.start()
        else:
            self._runtime_timer.stop()

    def _ensure_selected_key(self) -> None:
        if not self._rows:
            self._selected_key = ""
            return
        keys = [
            progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
            for row in self._rows
        ]
        if self._selected_key not in keys:
            self._selected_key = keys[0]

    def _select_lane(self, lane_key: str) -> None:
        self._selected_key = lane_key
        self._schedule_local_workspace_save()
        self._render_selected()

    def _render(self) -> None:
        if not self._rows:
            if self._loading:
                self._empty_state.show_loading()
            else:
                self._empty_state.show_empty()
            self._empty_state.show()
            self._content.hide()
            if not self._is_error:
                self._stats_row.set_summary_counts(runs=0, active=0, attention=0, done=0)
            self._selected_panel.show_no_selection(loading=self._loading)
            return

        self._empty_state.hide()
        self._content.show()

        active_count = 0
        attention_count = 0
        completed_count = 0
        for row in self._rows:
            key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
            runtime = self._runtime_by_key.get(key)
            stage = (runtime.stage if runtime else row.stage).lower()
            if stage not in {"done", "error"}:
                active_count += 1
            if lane_needs_attention(row, runtime):
                attention_count += 1
            if stage == "done":
                completed_count += 1

        self._stats_row.set_summary_counts(
            runs=len(self._rows),
            active=active_count,
            attention=attention_count,
            done=completed_count,
        )
        self._lane_list.set_lanes(self._rows, self._runtime_by_key, selected_key=self._selected_key)
        self._render_selected()

    def _render_selected(self) -> None:
        if not self._rows:
            self._selected_panel.show_no_selection(loading=self._loading)
            return
        selected = next(
            (
                row
                for row in self._rows
                if progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
                == self._selected_key
            ),
            self._rows[0],
        )
        key = progress_runtime_key(selected.meta.batch_id, selected.meta.profile_id, selected.meta.role)
        runtime = self._runtime_by_key.get(key)
        steps = build_workflow_steps(selected, runtime)
        self._selected_panel.apply(selected, runtime, steps)

    def apply_runtime_for_tests(
        self,
        rows: list[ProgressRow],
        workspace=None,
    ) -> dict[str, ProgressRuntimePresentation]:
        """Rebuild runtime map synchronously — used by tests."""
        return build_runtime_presentation_map(rows, workspace)
