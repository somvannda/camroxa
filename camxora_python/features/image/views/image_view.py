"""Image workspace page — job queue, prompts, and previews."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from features.image.services.image_local_store import ImageLocalStore, ImageWorkspacePrefs
from features.image.widgets.controls_queue_card import ControlsQueueCard
from features.image.widgets.error_banner import LOAD_ERROR, ImageErrorBanner
from features.image.widgets.preview_card import PreviewCard
from shared.lib.image_workspace import (
    build_footer_detail,
    build_queue_rows,
    build_queue_status_summary,
    filter_batches_by_date,
    filter_jobs_by_batches,
    normalize_image_prompt_settings,
)
from shared.lib.page_account_scope import account_cache_mismatch, cached_user_id
from shared.models.auth import ProfileResponse
from shared.models.platform import ImageJobListItem, MusicHistoryListResponse
from shared.services.file_service import open_path
from shared.services.platform_api import PlatformApi
from shared.services.action_feedback import notify_action
from shared.services.shell_status import emit_shell_status, restore_shell_status
from shared.services.workspace_cache import WorkspaceCache
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.pollable_page import PollablePageMixin
from shared.workers.data_workers import (
    ImageClearQueueWorker,
    ImageOpenWorker,
    ImagePreviewLoadWorker,
    ImageRetryJobsWorker,
    ImageWorkspacePayload,
    ImageWorkspaceWorker,
    PatchSettingsWorker,
)

LOADING_MESSAGE = "Loading image workspace..."
REFRESHING_MESSAGE = "Refreshing image workspace…"


class ImageView(PollablePageMixin, QScrollArea):
    poll_interval_ms = 4000

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
        self._worker: ImageWorkspaceWorker | None = None
        self._patch_worker: PatchSettingsWorker | None = None
        self._retry_worker: ImageRetryJobsWorker | None = None
        self._clear_worker: ImageClearQueueWorker | None = None
        self._preview_worker: ImagePreviewLoadWorker | None = None
        self._open_worker: ImageOpenWorker | None = None
        self._profiles: list[ProfileResponse] = []
        self._image_jobs: list[ImageJobListItem] = []
        self._history = MusicHistoryListResponse()
        self._settings_raw: dict[str, object] = {}
        self._selected_queue_key: str | None = None
        self._status_label = "Ready"
        self._loading = True
        self._is_error = False
        self._ever_loaded = False
        self._loaded_user_id: str | None = None
        self._local_workspace_restored = False
        self._prompts_initialized = False
        self._local_save_timer = QTimer(self)
        self._local_save_timer.setSingleShot(True)
        self._local_save_timer.setInterval(400)
        self._local_save_timer.timeout.connect(self._persist_local_workspace_prefs)
        self._prompt_save_timer = QTimer(self)
        self._prompt_save_timer.setSingleShot(True)
        self._prompt_save_timer.setInterval(350)
        self._prompt_save_timer.timeout.connect(self._persist_prompts)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self._error_banner = ImageErrorBanner()
        self._error_banner.hide()
        root.addWidget(self._error_banner)

        self._loading_card = QFrame()
        self._loading_card.setObjectName("account_card")
        loading_layout = QVBoxLayout(self._loading_card)
        loading_label = QLabel(LOADING_MESSAGE)
        loading_label.setObjectName(SUBTITLE_LABEL_ID)
        loading_layout.addWidget(loading_label)
        root.addWidget(self._loading_card)

        self._controls_card = ControlsQueueCard()
        self._background_preview = PreviewCard(
            "Background Preview",
            "Select a queue row to preview the background output.",
        )
        self._thumbnail_preview = PreviewCard(
            "Thumbnail Preview",
            "Select a queue row to preview the thumbnail output.",
        )

        preview_host = QWidget()
        previews = QVBoxLayout(preview_host)
        previews.setSpacing(12)
        previews.addWidget(self._background_preview)
        previews.addWidget(self._thumbnail_preview)

        self._content = QWidget()
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._controls_card, stretch=2)
        content_layout.addWidget(preview_host, stretch=1)

        self._content.hide()
        root.addWidget(self._content)

        self._controls_card.filters_changed.connect(self._on_filters_changed)
        self._controls_card.reload_requested.connect(self.refresh_data)
        self._controls_card.row_selected.connect(self._on_row_selected)
        self._controls_card.prompts_changed.connect(self._schedule_prompt_save)
        self._controls_card.clear_queue_requested.connect(self._clear_queue)
        self._controls_card.job_retry_requested.connect(self._on_job_retry_requested)
        self._controls_card.jobs_retry_requested.connect(self._retry_jobs)
        self._controls_card.jobs_regenerate_requested.connect(self._regenerate_jobs)
        self._controls_card.job_open_requested.connect(self._on_job_open_requested)

        self.setWidget(container)

    def _reset_for_account_change(self) -> None:
        self._loaded_user_id = None
        self._ever_loaded = False
        self._local_workspace_restored = False
        self._prompts_initialized = False
        self._loading = True
        self._is_error = False
        self._profiles = []
        self._image_jobs = []
        self._history = MusicHistoryListResponse()
        self._settings_raw = {}
        self._selected_queue_key = None
        self._error_banner.hide()
        self._loading_card.show()
        self._content.hide()

    def _restore_local_workspace_prefs(self) -> None:
        prefs = ImageLocalStore().read_workspace_prefs()
        if prefs is None:
            return
        if prefs.from_date and prefs.to_date:
            self._controls_card.set_date_range(prefs.from_date, prefs.to_date)
        if prefs.selected_queue_key:
            self._selected_queue_key = prefs.selected_queue_key

    def _current_workspace_prefs(self) -> ImageWorkspacePrefs:
        return ImageWorkspacePrefs(
            from_date=self._controls_card.from_date(),
            to_date=self._controls_card.to_date(),
            selected_queue_key=self._selected_queue_key or "",
        )

    def _schedule_local_workspace_save(self) -> None:
        self._local_save_timer.start()

    def _persist_local_workspace_prefs(self) -> None:
        ImageLocalStore().write_workspace_prefs(self._current_workspace_prefs())

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
        PollablePageMixin.deactivate_page(self)
        restore_shell_status()

    def refresh_data(self) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._ever_loaded:
            self._apply_core_cache()
        if self._ever_loaded:
            emit_shell_status(REFRESHING_MESSAGE)
            self._controls_card.set_reload_enabled(False)
        worker = ImageWorkspaceWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        self._worker = None
        restore_shell_status()
        self._controls_card.set_reload_enabled(True)

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, ImageWorkspacePayload):
            return
        self._is_error = False
        self._loading = False
        self._ever_loaded = True
        self._error_banner.hide()
        self._loading_card.hide()
        self._content.show()

        self._profiles = [profile for profile in payload.profiles if isinstance(profile, ProfileResponse)]
        self._image_jobs = list(getattr(payload.image_jobs, "items", []) or [])
        if isinstance(payload.music_history, MusicHistoryListResponse):
            self._history = payload.music_history
        settings = payload.settings
        if hasattr(settings, "model_dump"):
            self._settings_raw = settings.model_dump(by_alias=True)
        elif isinstance(settings, dict):
            self._settings_raw = settings
        else:
            self._settings_raw = {}

        if not self._prompts_initialized:
            prompts = normalize_image_prompt_settings(self._settings_raw)
            self._controls_card.set_prompts(
                prompts.image_background_prompt,
                prompts.image_thumbnail_prompt,
            )
            self._prompts_initialized = True

        self._refresh_presentation()
        self._loaded_user_id = cached_user_id(self._cache)

    def _on_filters_changed(self) -> None:
        self._schedule_local_workspace_save()
        self._refresh_presentation()

    def _apply_core_cache(self) -> bool:
        if self._cache is None or not self._cache.has_core():
            return False
        _me, profiles, settings_raw, _descriptions, _structures, _moods = self._cache.snapshot_core()
        if not profiles or not settings_raw:
            return False
        self._is_error = False
        self._loading = False
        self._ever_loaded = True
        self._error_banner.hide()
        self._loading_card.hide()
        self._content.show()
        self._profiles = [profile for profile in profiles if isinstance(profile, ProfileResponse)]
        self._settings_raw = settings_raw
        if not self._prompts_initialized:
            prompts = normalize_image_prompt_settings(self._settings_raw)
            self._controls_card.set_prompts(
                prompts.image_background_prompt,
                prompts.image_thumbnail_prompt,
            )
            self._prompts_initialized = True
        self._refresh_presentation()
        self._loaded_user_id = cached_user_id(self._cache)
        return True

    def _on_failed(self, message: str) -> None:
        self._loading = False
        if not self._ever_loaded:
            self._is_error = True
            self._loading_card.hide()
            self._content.hide()
            self._error_banner.set_message(message or LOAD_ERROR)
            self._error_banner.show()
            return
        self._show_workspace_error(message or LOAD_ERROR)

    def _refresh_presentation(self) -> None:
        from_date = self._controls_card.from_date()
        to_date = self._controls_card.to_date()
        filtered_batches = filter_batches_by_date(self._history.batches, from_date, to_date)
        batch_ids = {batch.batch_id for batch in filtered_batches if batch.batch_id}
        filtered_jobs = filter_jobs_by_batches(self._image_jobs, batch_ids)
        rows = build_queue_rows(filtered_jobs, filtered_batches, self._profiles)

        if self._selected_queue_key and not any(row.key == self._selected_queue_key for row in rows):
            self._selected_queue_key = rows[0].key if rows else None
        elif not self._selected_queue_key and rows:
            self._selected_queue_key = rows[0].key

        summary = build_queue_status_summary(
            grouped_row_count=len(rows),
            filtered_batch_count=len(filtered_batches),
            rows=rows,
        )
        self._controls_card.set_stat_values(
            date_range=f"{from_date} → {to_date}",
            matched_batches=len(filtered_batches),
            queue_status=self._status_label,
        )
        self._controls_card.set_queue_summary(summary)
        self._controls_card.set_clear_enabled(bool(batch_ids))
        self._controls_card.set_rows(rows, self._selected_queue_key)
        self._load_previews(self._controls_card.selected_row())

    def _on_job_open_requested(self, path: str, job_id: str) -> None:
        if self._open_worker is not None and self._open_worker.isRunning():
            return
        worker = ImageOpenWorker(
            self._api,
            path=path,
            job_id=job_id,
            parent=self,
        )
        worker.succeeded.connect(open_path)
        worker.failed.connect(lambda message: emit_shell_status(message, tone="warning"))
        worker.finished.connect(lambda: setattr(self, "_open_worker", None))
        self._open_worker = worker
        worker.start()

    def _on_row_selected(self, key: str) -> None:
        self._selected_queue_key = key
        self._schedule_local_workspace_save()
        self._load_previews(self._controls_card.selected_row())

    def _load_previews(self, row) -> None:
        if self._preview_worker is not None and self._preview_worker.isRunning():
            self._preview_worker.requestInterruption()
        footer = build_footer_detail(row)
        self._controls_card.set_footer_detail(footer)
        if row is None:
            self._background_preview.set_image_bytes(None)
            self._thumbnail_preview.set_image_bytes(None)
            return
        worker = ImagePreviewLoadWorker(
            api=self._api,
            bg_path=row.bg_job.output_image_path if row.bg_job else None,
            th_path=row.th_job.output_image_path if row.th_job else None,
            bg_job_id=row.bg_job.id if row.bg_job else None,
            th_job_id=row.th_job.id if row.th_job else None,
            footer_detail=footer,
            parent=self,
        )
        worker.succeeded.connect(self._on_preview_loaded)
        worker.finished.connect(lambda: setattr(self, "_preview_worker", None))
        self._preview_worker = worker
        worker.start()

    def _on_preview_loaded(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        self._background_preview.set_image_bytes(payload.get("bg_bytes"))
        self._thumbnail_preview.set_image_bytes(payload.get("th_bytes"))
        detail = payload.get("footer_detail")
        if isinstance(detail, str):
            self._controls_card.set_footer_detail(detail)

    def _schedule_prompt_save(self) -> None:
        self._prompt_save_timer.start()

    def _persist_prompts(self) -> None:
        if self._patch_worker is not None and self._patch_worker.isRunning():
            return
        patch = {
            "imageBackgroundPrompt": self._controls_card.background_prompt(),
            "imageThumbnailPrompt": self._controls_card.thumbnail_prompt(),
        }
        worker = PatchSettingsWorker(self._api, patch, parent=self)
        worker.failed.connect(lambda message: self._show_workspace_error("Unable to save image settings right now."))
        worker.finished.connect(lambda: setattr(self, "_patch_worker", None))
        self._patch_worker = worker
        worker.start()

    def _on_job_retry_requested(self, job_id: str, batch_id: str) -> None:
        from shared.services.app_logger import log_info

        log_info(f"Image queue retry requested for job {job_id}.", category="image")
        self._retry_job(job_id, batch_id=batch_id or None)

    def _retry_job(self, job_id: str, *, batch_id: str | None = None) -> None:
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._show_workspace_error("An image retry is already in progress.")
            return
        worker = ImageRetryJobsWorker(
            self._api,
            job_ids=[job_id],
            batch_id=batch_id,
            parent=self,
        )
        worker.succeeded.connect(self._on_retry_succeeded)
        worker.failed.connect(self._on_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        notify_action("Retrying image job…", tone="neutral")
        worker.start()

    def _retry_jobs(
        self,
        job_ids: list[str],
        batch_id: str | None = None,
        *,
        force: bool = False,
    ) -> None:
        if not job_ids and not batch_id:
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._show_workspace_error("An image retry is already in progress.")
            return
        from shared.services.app_logger import log_info

        action = "regenerate" if force else "retry"
        if batch_id and not job_ids:
            log_info(f"Image queue batch {action} requested for {batch_id}.", category="image")
        else:
            log_info(
                f"Image queue {action} requested for {len(job_ids)} job(s).",
                category="image",
            )
        worker = ImageRetryJobsWorker(
            self._api,
            job_ids=job_ids if job_ids else None,
            batch_id=batch_id,
            force=force,
            parent=self,
        )
        worker.succeeded.connect(self._on_retry_succeeded)
        worker.failed.connect(self._on_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        if force:
            notify_action("Regenerating Background + Thumbnail…", tone="neutral")
        elif batch_id and not job_ids:
            notify_action("Retrying failed image jobs for batch…", tone="neutral")
        else:
            notify_action(f"Retrying {len(job_ids)} image job(s)…", tone="neutral")
        worker.start()

    def _regenerate_jobs(self, job_ids: list[str], batch_id: str | None = None) -> None:
        self._retry_jobs(job_ids, batch_id, force=True)

    def _on_retry_succeeded(self, payload: object) -> None:
        from shared.models.platform import ImageJobsRetryResponse

        updated = 0
        if isinstance(payload, ImageJobsRetryResponse):
            updated = int(payload.updated or 0)
        if updated > 0:
            message = f"Queued {updated} image job{'s' if updated != 1 else ''} for generation."
            self._status_label = message
            self._error_banner.hide()
            notify_action(message, tone="success")
        else:
            message = "No image jobs were reset. They may already be pending or running."
            self._status_label = "No image jobs to reset."
            self._show_workspace_error(message)
        self.refresh_data()

    def _on_retry_failed(self, message: str) -> None:
        self._status_label = "Unable to retry job."
        detail = str(message or "").strip() or "Unable to retry image jobs."
        self._show_workspace_error(detail)

    def _clear_queue(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from_date = self._controls_card.from_date()
        to_date = self._controls_card.to_date()
        filtered_batches = filter_batches_by_date(self._history.batches, from_date, to_date)
        batch_ids = [batch.batch_id for batch in filtered_batches if batch.batch_id]
        if not batch_ids:
            return
        confirmed = QMessageBox.question(
            self,
            "Clear Queue",
            "Clear Image job queue for the current date range? This cannot be undone.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        if self._clear_worker is not None and self._clear_worker.isRunning():
            notify_action("A queue clear is already in progress.", tone="warning")
            return
        notify_action("Clearing image queue for selected date range…", tone="neutral")
        worker = ImageClearQueueWorker(self._api, batch_ids, parent=self)
        worker.succeeded.connect(self._on_clear_succeeded)
        worker.failed.connect(self._on_clear_failed)
        worker.finished.connect(lambda: setattr(self, "_clear_worker", None))
        self._clear_worker = worker
        worker.start()

    def _on_clear_succeeded(self, deleted: int) -> None:
        count = int(deleted or 0)
        message = f"Cleared {count} image job(s) from the queue."
        self._status_label = message
        self._error_banner.hide()
        notify_action(message, tone="success")
        self.refresh_data()

    def _on_clear_failed(self, message: str) -> None:
        self._status_label = "Unable to clear queue."
        self._show_workspace_error(message or "Unable to clear image queue.")

    def _show_workspace_error(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        self._error_banner.set_message(text)
        self._error_banner.show()
        notify_action(text, tone="error")
        self._refresh_presentation()
