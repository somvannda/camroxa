"""Progress page — operational pipeline view with standard theme widgets."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from features.progress.widgets.error_banner import ProgressErrorBanner
from features.progress.widgets.operational_rows_card import EffectiveProgressRow, OperationalRowsCard
from features.progress.widgets.progress_detail_card import ProgressDetailCard
from features.progress.widgets.stats_row import ProgressStatsRow
from shared.lib.formatting import today_ymd
from shared.lib.manual_asset_paths import ManualAssetInspection, manual_inspection_key, normalize_image_source_mode
from shared.lib.video_runtime_inspection import ProgressRuntimePresentation, progress_runtime_key
from shared.models.auth import ProfileResponse
from shared.models.platform import (
    ProgressFilters,
    ProgressRow,
    UserSettingsResponse,
)
from shared.services.file_service import ensure_directory, open_path
from shared.services.platform_api import PlatformApi
from shared.services.video_pipeline_coordinator import get_video_pipeline_coordinator
from shared.services.video_workspace_service import get_video_workspace_service
from shared.services.workspace_cache import WorkspaceCache
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.pollable_page import PollablePageMixin
from shared.widgets.shell_date_edit import make_shell_date_edit
from shared.workers.data_workers import (
    BatchRetryDraftsWorker,
    BatchRetrySunoWorker,
    ImageRetryJobsWorker,
    ManualInspectionWorker,
    SettingsWorker,
    SyncManualImageWorker,
    WorkflowLoadResult,
    WorkflowLoadWorker,
)

DEFAULT_POLL_MS = 30_000
ACTIVE_POLL_MS = 8_000

HELPER_TEXT = (
    "Operational pipeline view for monitoring failures, waiting rows, and recovery actions."
)
SUMMARY_SUFFIX = (
    "Desktop MP3 downloading, converter truth, and merger truth now read the real "
    "desktop runtime when local outputs exist."
)
MANUAL_MODE_TEXT = (
    "Manual image mode is active. This page is the recovery handoff for missing "
    "`background-16x9`, `background-9x16`, `thumbnail-16x9`, and `thumbnail-9x16` "
    "assets before video work continues."
)

STAGE_OPTIONS = (
    ("All stages", "all"),
    ("Music", "music"),
    ("Image", "image"),
    ("Export", "export"),
    ("Merge", "merge"),
    ("YouTube", "youtube"),
    ("Done", "done"),
    ("Error", "error"),
)


class ProgressView(PollablePageMixin, QScrollArea):
    """Operational progress table with filters, runtime overlay, and recovery actions."""

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
        self._cache = cache or WorkspaceCache()
        self._worker: WorkflowLoadWorker | None = None
        self._settings_worker: SettingsWorker | None = None
        self._inspection_worker: ManualInspectionWorker | None = None
        self._sync_worker: SyncManualImageWorker | None = None
        self._image_retry_worker: ImageRetryJobsWorker | None = None
        self._draft_retry_worker: BatchRetryDraftsWorker | None = None
        self._suno_retry_worker: BatchRetrySunoWorker | None = None
        self._rows: list[ProgressRow] = []
        self._runtime_by_key: dict[str, ProgressRuntimePresentation] = {}
        self._manual_inspections: dict[str, ManualAssetInspection] = {}
        self._image_source_mode = "ai"
        self._loading = True
        self._is_error = False
        self._ever_loaded = False
        self._syncing_batch_id = ""
        self._progress_load_error = ""
        self._selected_entry: EffectiveProgressRow | None = None
        self._pending_continue: object | None = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        filter_card = QFrame()
        filter_card.setObjectName("account_card")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 16, 16, 16)
        filter_layout.setSpacing(8)

        filter_title = QLabel("Filters")
        filter_title.setObjectName(SUBTITLE_LABEL_ID)
        filter_layout.addWidget(filter_title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._from_date = make_shell_date_edit(
            initial=QDate.fromString(today_ymd(), "yyyy-MM-dd")
        )
        self._to_date = make_shell_date_edit(
            initial=QDate.fromString(today_ymd(), "yyyy-MM-dd")
        )
        self._active_only = QCheckBox("Active only")
        self._limit = QComboBox()
        self._limit.addItems(["10", "25", "50"])
        self._limit.setCurrentText("25")
        self._stage_filter = QComboBox()
        for label, _value in STAGE_OPTIONS:
            self._stage_filter.addItem(label)
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(QLabel("From"))
        toolbar.addWidget(self._from_date)
        toolbar.addWidget(QLabel("To"))
        toolbar.addWidget(self._to_date)
        toolbar.addWidget(self._active_only)
        toolbar.addWidget(QLabel("Limit"))
        toolbar.addWidget(self._limit)
        toolbar.addWidget(QLabel("Stage"))
        toolbar.addWidget(self._stage_filter)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addStretch()
        filter_layout.addLayout(toolbar)
        root.addWidget(filter_card)

        helper = QLabel(HELPER_TEXT)
        helper.setObjectName(SUBTITLE_LABEL_ID)
        helper.setWordWrap(True)
        helper.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        root.addWidget(helper)

        self._summary_label = QLabel("Loading progress rows...")
        self._summary_label.setObjectName(SUBTITLE_LABEL_ID)
        self._summary_label.setWordWrap(True)
        root.addWidget(self._summary_label)

        self._manual_banner = QLabel(MANUAL_MODE_TEXT)
        self._manual_banner.setObjectName(SUBTITLE_LABEL_ID)
        self._manual_banner.setWordWrap(True)
        self._manual_banner.hide()
        root.addWidget(self._manual_banner)

        self._stats_row = ProgressStatsRow()
        root.addWidget(self._stats_row, 0)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName(SUBTITLE_LABEL_ID)
        self._meta_label.setWordWrap(True)
        root.addWidget(self._meta_label)

        self._export_validation_label = QLabel("")
        self._export_validation_label.setObjectName(SUBTITLE_LABEL_ID)
        self._export_validation_label.setWordWrap(True)
        self._export_validation_label.hide()
        root.addWidget(self._export_validation_label)

        self._error_banner = ProgressErrorBanner()
        self._error_banner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._error_banner.hide()
        root.addWidget(self._error_banner, 0)

        self._rows_card = OperationalRowsCard()
        self._rows_card.open_folder_requested.connect(self._open_manual_folder)
        self._rows_card.open_run_folder_requested.connect(self._open_manual_folder)
        self._rows_card.sync_manual_requested.connect(self._sync_manual_assets)
        self._rows_card.retry_images_requested.connect(self._retry_images)
        self._rows_card.enqueue_images_requested.connect(self._enqueue_images)
        self._rows_card.retry_drafts_requested.connect(self._retry_failed_drafts)
        self._rows_card.retry_suno_requested.connect(self._retry_failed_suno)
        self._rows_card.force_export_regenerate_requested.connect(
            lambda row: self._run_video_pipeline_action(row, "force_export")
        )
        self._rows_card.rebuild_export_requested.connect(
            lambda row: self._run_video_pipeline_action(row, "rebuild_export")
        )
        self._rows_card.start_export_requested.connect(
            lambda row: self._run_video_pipeline_action(row, "rebuild_export")
        )
        self._rows_card.start_merge_requested.connect(
            lambda row: self._run_video_pipeline_action(row, "merge")
        )
        self._rows_card.cancel_job_requested.connect(self._cancel_active_video_job)
        self._rows_card.stop_exporting_requested.connect(self._stop_exporting)
        self._rows_card.continue_progress_requested.connect(self._continue_progress)
        self._rows_card.row_selected.connect(self._on_row_selected)

        self._detail_card = ProgressDetailCard()
        self._detail_card.open_folder_requested.connect(self._open_manual_folder)
        self._detail_card.open_run_folder_requested.connect(self._open_manual_folder)
        self._detail_card.sync_manual_requested.connect(self._sync_manual_assets)

        self._rows_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._rows_splitter.setChildrenCollapsible(False)
        self._rows_splitter.setStyleSheet(
            "QSplitter::handle { background: transparent; }"
        )
        self._rows_splitter.addWidget(self._wrap_splitter_panel(self._rows_card, right=10))
        self._rows_splitter.addWidget(self._wrap_splitter_panel(self._detail_card, left=10))
        self._rows_splitter.setStretchFactor(0, 4)
        self._rows_splitter.setStretchFactor(1, 1)
        self._rows_splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        root.addWidget(self._rows_splitter, 1)

        self._from_date.dateChanged.connect(lambda *_: self._on_filters_changed())
        self._to_date.dateChanged.connect(lambda *_: self._on_filters_changed())
        self._active_only.stateChanged.connect(lambda *_: self._on_filters_changed())
        self._limit.currentTextChanged.connect(lambda *_: self._on_filters_changed())
        self._stage_filter.currentTextChanged.connect(lambda *_: self._render_table())

        self.setWidget(container)
        self._container = container
        self._enter_loading_state()

    @staticmethod
    def _wrap_splitter_panel(widget: QWidget, *, left: int = 0, right: int = 0) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(left, 0, right, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        return wrap

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_container"):
            self._container.setMinimumHeight(max(self.viewport().height(), 480))

    def activate_page(self) -> None:
        self._refresh_settings()
        PollablePageMixin.activate_page(self)

    def deactivate_page(self) -> None:
        PollablePageMixin.deactivate_page(self)

    def _on_filters_changed(self) -> None:
        interval = ACTIVE_POLL_MS if self._active_only.isChecked() else DEFAULT_POLL_MS
        self._poll_timer.setInterval(interval)
        self.refresh_data()

    def _current_filters(self) -> ProgressFilters:
        return ProgressFilters(
            limit=int(self._limit.currentText()),
            active_only=self._active_only.isChecked(),
            from_date=self._from_date.date().toString("yyyy-MM-dd"),
            to_date=self._to_date.date().toString("yyyy-MM-dd"),
        )

    def _current_stage_filter(self) -> str:
        label = self._stage_filter.currentText()
        for option_label, value in STAGE_OPTIONS:
            if option_label == label:
                return value
        return "all"

    def refresh_data(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._ever_loaded:
            self._loading = True
            self._rows_card.show_loading()
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

    def _refresh_settings(self) -> None:
        if self._settings_worker is not None and self._settings_worker.isRunning():
            return
        worker = SettingsWorker(self._api, self)
        worker.succeeded.connect(self._on_settings_loaded)
        worker.finished.connect(lambda: setattr(self, "_settings_worker", None))
        self._settings_worker = worker
        worker.start()

    def _on_settings_loaded(self, payload: object) -> None:
        if not isinstance(payload, UserSettingsResponse):
            return
        self._image_source_mode = normalize_image_source_mode(payload.image_source_mode)
        manual_mode = self._image_source_mode == "manual"
        self._manual_banner.setVisible(manual_mode)
        self._rows_card.set_manual_mode(manual_mode)
        self._detail_card.set_manual_mode(manual_mode)
        if manual_mode and self._rows:
            self._refresh_manual_inspections()
        else:
            self._manual_inspections = {}
            self._rows_card.set_manual_inspections({})
            self._detail_card.set_manual_inspections({})
        self._render_table()

    def _refresh_manual_inspections(self) -> None:
        if self._image_source_mode != "manual" or not self._rows:
            self._manual_inspections = {}
            self._rows_card.set_manual_inspections({})
            self._detail_card.set_manual_inspections({})
            self._render_table()
            return
        if self._inspection_worker is not None and self._inspection_worker.isRunning():
            return
        worker = ManualInspectionWorker(self._rows, self)
        worker.succeeded.connect(self._on_manual_inspections_loaded)
        worker.finished.connect(lambda: setattr(self, "_inspection_worker", None))
        self._inspection_worker = worker
        worker.start()

    def _on_manual_inspections_loaded(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        self._manual_inspections = payload
        self._rows_card.set_manual_inspections(payload)
        self._detail_card.set_manual_inspections(payload)
        self._update_stats()
        self._render_table()

    def _on_row_selected(self, entry: object) -> None:
        if isinstance(entry, EffectiveProgressRow):
            self._selected_entry = entry
            self._detail_card.set_entry(entry)
        else:
            self._selected_entry = None
            self._detail_card.set_entry(None)
        self._update_export_validation()

    def _enter_loading_state(self) -> None:
        self._loading = True
        self._is_error = False
        self._error_banner.hide()
        self._summary_label.setText("Loading progress rows...")
        self._rows_card.show_loading()
        self._stats_row.set_summary_counts(active=0, converter=0, waiting=0, failed=0)
        self._update_meta_label(0)

    def _on_failed(self, message: str) -> None:
        self._loading = False
        self._is_error = True
        self._progress_load_error = str(message or "").strip()
        self._error_banner.show()
        if self._rows:
            self._render()
            return
        self._rows = []
        self._runtime_by_key = {}
        self._manual_inspections = {}
        self._summary_label.setText(f"Unable to load progress rows. {message}")
        self._rows_card.show_empty()
        self._stats_row.set_summary_counts(active=0, converter=0, waiting=0, failed=0)
        self._update_meta_label(0)

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, WorkflowLoadResult):
            return
        self._loading = False
        self._is_error = False
        self._progress_load_error = ""
        self._ever_loaded = True
        self._error_banner.hide()
        self._rows = payload.response.rows
        self._runtime_by_key = payload.runtime_by_key
        self._summary_label.setText(f"{payload.response.summary} {SUMMARY_SUFFIX}")
        self._render()
        self._refresh_manual_inspections()

    def _effective_rows(self) -> list[EffectiveProgressRow]:
        entries: list[EffectiveProgressRow] = []
        for row in self._rows:
            key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
            runtime = self._runtime_by_key.get(key)
            entries.append(
                EffectiveProgressRow(
                    row=row,
                    effective_status=runtime.status if runtime else row.status,
                    effective_converter=runtime.converter if runtime else row.converter,
                    effective_merge=runtime.merge if runtime else row.merge,
                    effective_stage=runtime.stage if runtime else row.stage,
                    effective_notes=runtime.notes if runtime else row.notes,
                    effective_converter_percent=runtime.converter_percent if runtime else None,
                    effective_merge_percent=runtime.merge_percent if runtime else None,
                )
            )
        return entries

    def _filtered_effective_rows(self) -> list[EffectiveProgressRow]:
        stage = self._current_stage_filter()
        entries = self._effective_rows()
        if stage == "all":
            return entries
        return [entry for entry in entries if self._matches_stage_filter(entry.effective_stage, stage)]

    @staticmethod
    def _matches_stage_filter(effective_stage: str, stage_filter: str) -> bool:
        normalized = str(effective_stage or "").strip().lower()
        aliases = {
            "export": {"export", "converter"},
            "merge": {"merge", "merger"},
        }
        allowed = aliases.get(stage_filter, {stage_filter})
        return normalized in allowed

    def _render(self) -> None:
        self._update_stats()
        self._render_table()
        self._update_export_validation()

    def _profile_for_row(self, row: ProgressRow | None) -> ProfileResponse | None:
        if row is None:
            return None
        _me, profiles, *_rest = self._cache.snapshot_core()
        if not profiles:
            return None
        profile_id = str(row.meta.profile_id or "").strip()
        for profile in profiles:
            if str(profile.id) == profile_id:
                return profile
        return None

    def _update_export_validation(self) -> None:
        from features.video.lib.export_readiness import evaluate_video_export_readiness

        entry = self._selected_entry
        if entry is None:
            self._export_validation_label.hide()
            return

        coordinator = get_video_pipeline_coordinator()
        auth_blocked = bool(coordinator is not None and coordinator.auth_blocked())
        readiness = evaluate_video_export_readiness(
            entry.row,
            self._profile_for_row(entry.row),
            workspace=get_video_workspace_service().get_workspace_state(),
            progress_load_error=self._progress_load_error if self._is_error else None,
            auth_blocked=auth_blocked,
        )
        if readiness.ready:
            self._export_validation_label.hide()
            return

        lines = "\n".join(f"• {issue}" for issue in readiness.issues)
        self._export_validation_label.setText(f"Export not ready:\n{lines}")
        self._export_validation_label.show()

    def _render_table(self) -> None:
        filtered = self._filtered_effective_rows()
        if self._loading:
            self._rows_card.show_loading()
            return
        if not filtered:
            self._rows_card.show_empty()
        else:
            self._rows_card.set_syncing_batch_id(self._syncing_batch_id)
            self._detail_card.set_syncing_batch_id(self._syncing_batch_id)
            self._rows_card.set_rows(filtered)
        self._update_meta_label(len(filtered))

    def _update_meta_label(self, visible_count: int) -> None:
        stage_label = self._stage_filter.currentText()
        loaded_count = len(self._rows)
        visible_suffix = "" if visible_count == 1 else "s"
        if loaded_count and visible_count != loaded_count:
            loaded_suffix = "" if loaded_count == 1 else "s"
            self._meta_label.setText(
                f"{visible_count} visible row{visible_suffix} · "
                f"{loaded_count} loaded row{loaded_suffix} · {stage_label}"
            )
            return
        self._meta_label.setText(
            f"{visible_count} visible row{visible_suffix} · {stage_label}"
        )

    def _update_stats(self) -> None:
        entries = self._effective_rows()
        active = sum(
            1 for entry in entries if entry.effective_stage.lower() not in {"done", "error"}
        )
        converter = sum(
            1
            for entry in entries
            if str(entry.effective_stage or "").strip().lower() in {"export", "converter", "merge", "merger"}
        )
        failed = sum(
            1
            for entry in entries
            if entry.effective_stage.lower() == "error"
            or entry.effective_status.lower() == "failed"
        )
        waiting = 0
        if self._image_source_mode == "manual":
            waiting = sum(
                1
                for entry in entries
                if entry.effective_stage.lower() == "image"
                and (
                    inspection := self._manual_inspections.get(
                        manual_inspection_key(
                            entry.row.meta.batch_id,
                            entry.row.meta.profile_id,
                            entry.row.meta.role,
                        )
                    )
                )
                and not inspection.ready
            )
        self._stats_row.set_summary_counts(
            active=active,
            converter=converter,
            waiting=waiting,
            failed=failed,
        )

    def _open_manual_folder(self, directory: str) -> None:
        if not directory:
            return
        ensure_directory(directory)
        open_path(directory)

    def _sync_manual_assets(self, batch_id: str) -> None:
        if not batch_id:
            self._show_retry_notice("Missing batch id for manual sync.")
            return
        if self._sync_worker is not None and self._sync_worker.isRunning():
            self._show_retry_notice("A manual sync is already in progress.")
            return
        self._show_retry_notice("Syncing manual image assets…", tone="neutral")
        self._syncing_batch_id = batch_id
        self._rows_card.set_syncing_batch_id(batch_id)
        self._detail_card.set_syncing_batch_id(batch_id)
        self._render_table()
        worker = SyncManualImageWorker(self._api, batch_id, self)
        worker.succeeded.connect(self._on_manual_sync_succeeded)
        worker.failed.connect(self._on_manual_sync_failed)
        worker.finished.connect(self._clear_sync_state)
        self._sync_worker = worker
        worker.start()

    def _on_manual_sync_succeeded(self, _payload: object) -> None:
        self._show_retry_notice("Manual assets synced. Refreshing progress…", tone="success")
        self.refresh_data()

    def _on_manual_sync_failed(self, message: str) -> None:
        detail = str(message or "").strip() or "Unable to sync manual image assets."
        self._show_retry_notice(detail, tone="error")
        self._clear_sync_state()

    def _retry_images(self, batch_id: str) -> None:
        if not batch_id:
            self._show_retry_notice("Missing batch id for image retry.")
            return
        if self._image_source_mode == "manual":
            self._show_retry_notice("Image retry is not available in manual image mode.")
            return
        if self._image_retry_worker is not None and self._image_retry_worker.isRunning():
            self._show_retry_notice("An image retry is already in progress.")
            return
        from shared.services.app_logger import log_info

        log_info(f"Progress image retry requested for batch {batch_id}.", category="image")
        self._error_banner.hide()
        worker = ImageRetryJobsWorker(
            self._api,
            batch_id=batch_id,
            parent=self,
        )
        worker.succeeded.connect(lambda payload, bid=batch_id: self._on_image_retry_succeeded(bid, payload))
        worker.failed.connect(self._on_image_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_image_retry_worker", None))
        self._image_retry_worker = worker
        worker.start()

    def _enqueue_images(self, batch_id: str) -> None:
        if not batch_id:
            self._show_retry_notice("Missing batch id for image enqueue.")
            return
        if self._image_source_mode == "manual":
            self._show_retry_notice("Image enqueue is not available in manual image mode.")
            return
        if self._image_retry_worker is not None and self._image_retry_worker.isRunning():
            self._show_retry_notice("An image job is already in progress.")
            return
        from shared.services.app_logger import log_info
        from shared.workers.data_workers import EnqueueImageJobsWorker

        log_info(f"Progress image enqueue requested for batch {batch_id}.", category="image")
        self._error_banner.hide()
        worker = EnqueueImageJobsWorker(self._api, [batch_id], parent=self)
        worker.succeeded.connect(lambda _payload: self.refresh_data())
        worker.failed.connect(self._on_image_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_image_retry_worker", None))
        self._image_retry_worker = worker
        worker.start()

    def _on_image_retry_succeeded(self, batch_id: str, payload: object) -> None:
        from shared.models.platform import ImageJobsRetryResponse

        updated = 0
        if isinstance(payload, ImageJobsRetryResponse):
            updated = int(payload.updated or 0)
        if updated > 0:
            self._error_banner.hide()
            self._show_retry_notice(
                f"Retry queued for {updated} image job(s). Refreshing progress…",
                tone="success",
            )
            self.refresh_data()
            return

        if batch_id:
            self._show_retry_notice(
                "No image jobs to retry — queueing image generation…",
                tone="neutral",
            )
            self._enqueue_images(batch_id)
            return

        self._show_retry_notice(
            "No failed image jobs were reset. They may already be pending or running.",
        )
        self.refresh_data()

    def _on_image_retry_failed(self, message: str) -> None:
        detail = str(message or "").strip() or "Unable to retry image jobs."
        self._show_retry_notice(detail)

    def _show_retry_notice(self, message: str, *, tone: str = "warning") -> None:
        from shared.services.action_feedback import notify_action

        text = str(message or "").strip()
        if not text:
            return
        self._error_banner.set_message(text)
        self._error_banner.show()
        notify_action(text, tone=tone)

    def _retry_failed_drafts(self, batch_id: str, song_ids: list[str]) -> None:
        if not batch_id or not song_ids:
            self._show_retry_notice("No failed drafts to retry.")
            return
        if self._draft_retry_worker is not None and self._draft_retry_worker.isRunning():
            self._show_retry_notice("A draft retry is already in progress.")
            return
        count = len(song_ids)
        suffix = "s" if count != 1 else ""
        self._show_retry_notice(f"Retrying failed drafts for {count} song{suffix}…", tone="neutral")
        worker = BatchRetryDraftsWorker(self._api, batch_id, song_ids, parent=self)
        worker.succeeded.connect(self._on_draft_retry_succeeded)
        worker.failed.connect(self._on_draft_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_draft_retry_worker", None))
        self._draft_retry_worker = worker
        worker.start()

    def _retry_failed_suno(self, batch_id: str, song_ids: list[str]) -> None:
        if not batch_id or not song_ids:
            self._show_retry_notice("No failed Suno submissions to retry.")
            return
        if self._suno_retry_worker is not None and self._suno_retry_worker.isRunning():
            self._show_retry_notice("A Suno retry is already in progress.")
            return
        count = len(song_ids)
        suffix = "s" if count != 1 else ""
        self._show_retry_notice(f"Retrying failed Suno for {count} song{suffix}…", tone="neutral")
        worker = BatchRetrySunoWorker(self._api, batch_id, song_ids, parent=self)
        worker.succeeded.connect(self._on_suno_retry_succeeded)
        worker.failed.connect(self._on_suno_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_suno_retry_worker", None))
        self._suno_retry_worker = worker
        worker.start()

    def _on_draft_retry_succeeded(self, count: int) -> None:
        queued = int(count or 0)
        if queued <= 0:
            self._show_retry_notice("No draft retries were queued.")
            return
        suffix = "s" if queued != 1 else ""
        self._show_retry_notice(
            f"Queued draft retry for {queued} song{suffix}. Refreshing progress…",
            tone="success",
        )
        self.refresh_data()

    def _on_draft_retry_failed(self, message: str) -> None:
        detail = str(message or "").strip() or "Unable to retry draft generation."
        self._show_retry_notice(detail)

    def _on_suno_retry_succeeded(self, count: int) -> None:
        queued = int(count or 0)
        if queued <= 0:
            self._show_retry_notice("No Suno retries were queued.")
            return
        suffix = "s" if queued != 1 else ""
        self._show_retry_notice(
            f"Queued Suno retry for {queued} song{suffix}. Refreshing progress…",
            tone="success",
        )
        self.refresh_data()

    def _on_suno_retry_failed(self, message: str) -> None:
        detail = str(message or "").strip() or "Unable to retry Suno submission."
        self._show_retry_notice(detail)

    def _clear_sync_state(self) -> None:
        self._syncing_batch_id = ""
        self._sync_worker = None
        self._rows_card.set_syncing_batch_id("")
        self._detail_card.set_syncing_batch_id("")
        self._render_table()

    def _cancel_active_video_job(self, row: ProgressRow | None = None) -> None:
        """Right-click: stop the active local export/merge so another Start Export can run."""
        _ = row  # reserved for future row-scoped cancel; pipeline is single-slot today
        coordinator = get_video_pipeline_coordinator()
        if coordinator is None:
            self._show_retry_notice("Video pipeline is not available yet.", tone="warning")
            return
        if not coordinator.is_busy():
            # Still attempt clear — recovers stale busy flags from a crashed worker.
            cleared = coordinator.cancel_active_export()
            if cleared:
                self._show_retry_notice(
                    "Cleared stuck export state. You can Start Export on another row.",
                    tone="success",
                )
            else:
                self._show_retry_notice(
                    "No active export/merge is running. Use Start Export on a ready row.",
                    tone="neutral",
                )
            self.refresh_data()
            return
        cancelled = coordinator.cancel_active_export()
        if cancelled:
            self._show_retry_notice(
                "Stopping active export/merge… You can start another job when it finishes.",
                tone="success",
            )
        else:
            self._show_retry_notice("Could not cancel the active video job.", tone="warning")
        self.refresh_data()

    def _stop_exporting(self, row: ProgressRow | None = None) -> None:
        """Hard stop + pause auto-video / helper agents until a manual Start."""
        _ = row
        from shared.services.auto_pipeline_pause import pause_auto_pipeline
        from shared.services.shell_status import emit_shell_status

        pause_auto_pipeline("Stopped exporting by user")
        coordinator = get_video_pipeline_coordinator()
        if coordinator is not None:
            coordinator.cancel_active_export()
            # Keep the persistent pause (cancel_active only sets a short cooldown).
            pause_auto_pipeline("Stopped exporting by user")
        emit_shell_status(
            "Exporting stopped. Auto pipeline paused until you Start Export on a row.",
            tone="warning",
        )
        self._show_retry_notice(
            "Exporting stopped. Auto-video and helpers stay paused until you "
            "Start Export, Rebuild, Continue Progress, or Start Merging on a row.",
            tone="success",
        )
        self.refresh_data()

    def _resume_auto_pipeline_for_manual_start(self) -> None:
        from shared.services.auto_pipeline_pause import resume_auto_pipeline
        from shared.services.shell_status import emit_shell_status

        if resume_auto_pipeline():
            emit_shell_status("Auto pipeline resumed (manual start).", tone="neutral")

    def _continue_progress(self, entry: object) -> None:
        """Right-click Continue Progress: advance this row from its current stage."""
        from features.progress.lib.continue_progress import (
            ContinueProgressPlan,
            resolve_continue_progress,
        )
        from shared.lib.manual_asset_paths import manual_inspection_key

        if not isinstance(entry, EffectiveProgressRow):
            self._show_retry_notice("Select a progress row to continue.", tone="warning")
            return

        key = manual_inspection_key(
            entry.row.meta.batch_id,
            entry.row.meta.profile_id,
            entry.row.meta.role,
        )
        plan = resolve_continue_progress(
            entry,
            manual_mode=self._image_source_mode == "manual",
            inspection=self._manual_inspections.get(key),
        )
        self._dispatch_continue_plan(plan)

    def _dispatch_continue_plan(self, plan: object) -> None:
        from features.progress.lib.continue_progress import ContinueProgressPlan

        if not isinstance(plan, ContinueProgressPlan):
            return
        if plan.action == "none":
            self._show_retry_notice(plan.label, tone="neutral")
            return

        if plan.action in {"start_export", "start_merge"}:
            coordinator = get_video_pipeline_coordinator()
            if coordinator is not None and coordinator.is_busy():
                coordinator.cancel_active_export()
                # Live cancel is async — retry shortly instead of failing immediately.
                if coordinator.is_busy():
                    self._pending_continue = plan
                    self._show_retry_notice(
                        "Stopping stuck export… Continue Progress will retry when free.",
                        tone="neutral",
                    )
                    from PySide6.QtCore import QTimer

                    QTimer.singleShot(2_000, self._flush_pending_continue)
                    return
                self._show_retry_notice(
                    "Cleared stuck export state, then continuing…",
                    tone="neutral",
                )

        self._pending_continue = None
        self._resume_auto_pipeline_for_manual_start()
        self._show_retry_notice(f"Continue Progress: {plan.label}…", tone="neutral")
        if plan.action == "retry_drafts":
            self._retry_failed_drafts(plan.batch_id, plan.song_ids)
        elif plan.action == "retry_suno":
            self._retry_failed_suno(plan.batch_id, plan.song_ids)
        elif plan.action == "enqueue_images":
            self._enqueue_images(plan.batch_id)
        elif plan.action == "retry_images":
            self._retry_images(plan.batch_id)
        elif plan.action == "sync_manual":
            self._sync_manual_assets(plan.batch_id)
        elif plan.action == "start_export":
            self._run_video_pipeline_action(plan.row, "rebuild_export")
        elif plan.action == "start_merge":
            self._run_video_pipeline_action(plan.row, "merge")

    def _flush_pending_continue(self) -> None:
        plan = self._pending_continue
        if plan is None:
            return
        coordinator = get_video_pipeline_coordinator()
        if coordinator is not None and coordinator.is_busy():
            # One more cancel poke, then wait again (up to ~10s total via re-arm).
            coordinator.cancel_active_export()
            attempts = int(getattr(self, "_pending_continue_attempts", 0) or 0) + 1
            self._pending_continue_attempts = attempts
            if attempts < 5:
                from PySide6.QtCore import QTimer

                QTimer.singleShot(2_000, self._flush_pending_continue)
                return
            self._pending_continue = None
            self._pending_continue_attempts = 0
            self._show_retry_notice(
                "Export is still busy. Use Cancel Active Export/Merge, then Continue Progress again.",
                tone="warning",
            )
            return
        self._pending_continue_attempts = 0
        self._dispatch_continue_plan(plan)

    def _run_video_pipeline_action(self, row: ProgressRow | None, action: str) -> None:
        if row is None:
            self._show_retry_notice("Select a run before starting video work.", tone="warning")
            return
        self._resume_auto_pipeline_for_manual_start()

        # Merge only needs exported MP4s in the run folder — do not require the
        # Video catalog template (that gate was blocking Start Merging / Continue).
        if action != "merge":
            from features.video.lib.export_readiness import evaluate_video_export_readiness

            readiness = evaluate_video_export_readiness(
                row,
                self._profile_for_row(row),
                workspace=get_video_workspace_service().get_workspace_state(),
                progress_load_error=self._progress_load_error if self._is_error else None,
                auth_blocked=False,
            )
            if not readiness.ready:
                detail = "\n".join(f"• {issue}" for issue in readiness.issues)
                self._show_retry_notice(f"Export not ready:\n{detail}", tone="warning")
                self._update_export_validation()
                return
        else:
            run_dir = str(row.meta.run_dir or "").strip()
            if not run_dir:
                self._show_retry_notice("Merge not ready: run folder path is missing.", tone="warning")
                return
            from pathlib import Path

            from features.video.lib.pipeline_merge import list_branch_export_outputs

            if not Path(run_dir).is_dir():
                self._show_retry_notice(f"Merge not ready: run folder does not exist:\n{run_dir}", tone="warning")
                return
            if not list_branch_export_outputs(run_dir, "long") and not list_branch_export_outputs(
                run_dir, "reel"
            ):
                self._show_retry_notice(
                    "Merge not ready: no exported MP4 files found in the run folder.",
                    tone="warning",
                )
                return

        coordinator = get_video_pipeline_coordinator()
        if coordinator is None:
            self._show_retry_notice("Video pipeline is not available yet.", tone="warning")
            return
        if coordinator.is_busy():
            self._show_retry_notice(
                "Video pipeline is already running. Right-click a row → "
                "Cancel Active Export/Merge, then Start Export again.",
                tone="warning",
            )
            return
        labels = {
            "force_export": "Force regenerating MP4 exports…",
            "rebuild_export": "Rebuilding missing MP4 exports…",
            "merge": "Starting video merge…",
        }
        self._show_retry_notice(labels.get(action, "Starting video action…"), tone="neutral")
        coordinator.run_manual_action(row, action)  # type: ignore[arg-type]
        self.refresh_data()
