"""Image workspace page — job queue, prompts, and previews."""

from __future__ import annotations

from PySide6.QtCore import QTimer
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
from shared.lib.settings_workspace import resolve_kind_source_modes
from shared.models.auth import ProfileResponse, UserMeResponse
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
    ImageManualGenerateWorker,
    ImageOpenWorker,
    ImagePreviewLoadWorker,
    ImageRetryJobsWorker,
    ImageWorkspacePayload,
    ImageWorkspaceWorker,
    PatchSettingsWorker,
)

LOADING_MESSAGE = "Loading image workspace..."
REFRESHING_MESSAGE = "Refreshing image workspace…"

_EMPTY_BG_PROMPT = (
    "Background: Add a background prompt, or switch Background source to Category."
)
_EMPTY_TH_PROMPT = (
    "Thumbnail: Add a thumbnail prompt, or switch Thumbnail source to Category."
)
_PERSONAL_NOT_READY = (
    "{kind}: User reference is not available yet. "
    "Switch to Category or Prompt only."
)
_CREDIT_QUOTA_HINTS = (
    "credit",
    "quota",
    "insufficient",
    "allowance",
    "balance",
    "402",
)


class ImageView(PollablePageMixin, QScrollArea):
    # Background queue status only — keep slower than Electron's 4s so combos/prompts stay stable.
    poll_interval_ms = 12_000

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
        self._standalone_worker: ImageManualGenerateWorker | None = None
        self._pending_manual_select_key: str | None = None
        self._date_filter_banner_message: str | None = None
        self._clear_worker: ImageClearQueueWorker | None = None
        self._preview_worker: ImagePreviewLoadWorker | None = None
        self._open_worker: ImageOpenWorker | None = None
        self._profiles: list[ProfileResponse] = []
        self._image_jobs: list[ImageJobListItem] = []
        self._history = MusicHistoryListResponse()
        self._settings_raw: dict[str, object] = {}
        self._me: UserMeResponse | None = None
        self._selected_queue_key: str | None = None
        self._user_cleared_selection = False
        self._status_label = "Ready"
        self._loading = True
        self._is_error = False
        self._ever_loaded = False
        self._loaded_user_id: str | None = None
        self._local_workspace_restored = False
        self._prompts_initialized = False
        self._source_modes_initialized = False
        self._refresh_quiet = True
        self._preview_fingerprint = ""
        self._awaiting_regen_job_ids: set[str] = set()
        self._surfaced_job_errors: set[str] = set()
        self._local_save_timer = QTimer(self)
        self._local_save_timer.setSingleShot(True)
        self._local_save_timer.setInterval(400)
        self._local_save_timer.timeout.connect(self._persist_local_workspace_prefs)
        self._prompt_save_timer = QTimer(self)
        self._prompt_save_timer.setSingleShot(True)
        self._prompt_save_timer.setInterval(350)
        self._prompt_save_timer.timeout.connect(self._persist_image_settings)
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
            source_label="Background source",
        )
        self._thumbnail_preview = PreviewCard(
            "Thumbnail Preview",
            "Select a queue row to preview the thumbnail output.",
            source_label="Thumbnail source",
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
        self._controls_card.reload_requested.connect(self._manual_reload)
        self._controls_card.row_selected.connect(self._on_row_selected)
        self._controls_card.selection_cleared.connect(self._on_selection_cleared)
        self._controls_card.prompts_changed.connect(self._schedule_image_settings_save)
        self._controls_card.clear_queue_requested.connect(self._clear_queue)
        self._controls_card.job_retry_requested.connect(self._on_job_retry_requested)
        self._controls_card.jobs_retry_requested.connect(self._retry_jobs)
        self._controls_card.jobs_regenerate_requested.connect(self._regenerate_jobs)
        self._controls_card.manual_generation_requested.connect(self._on_manual_generation)
        self._controls_card.job_open_requested.connect(self._on_job_open_requested)
        self._background_preview.source_mode_changed.connect(self._schedule_image_settings_save)
        self._thumbnail_preview.source_mode_changed.connect(self._schedule_image_settings_save)

        self.setWidget(container)

    def _reset_for_account_change(self) -> None:
        self._loaded_user_id = None
        self._ever_loaded = False
        self._local_workspace_restored = False
        self._prompts_initialized = False
        self._source_modes_initialized = False
        self._refresh_quiet = True
        self._preview_fingerprint = ""
        self._awaiting_regen_job_ids.clear()
        self._surfaced_job_errors.clear()
        self._loading = True
        self._is_error = False
        self._profiles = []
        self._image_jobs = []
        self._history = MusicHistoryListResponse()
        self._settings_raw = {}
        self._me = None
        self._selected_queue_key = None
        self._user_cleared_selection = False
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
        if self._prompt_save_timer.isActive():
            self._prompt_save_timer.stop()
            self._persist_image_settings()
        PollablePageMixin.deactivate_page(self)
        restore_shell_status()

    def refresh_data(self) -> None:
        """Poll timer entry — quiet background refresh (does not reset source/prompt UI)."""
        self._refresh_workspace(quiet=True)

    def _manual_reload(self) -> None:
        self._refresh_workspace(quiet=False)

    def _refresh_workspace(self, *, quiet: bool) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._ever_loaded:
            self._apply_core_cache()
        self._refresh_quiet = bool(quiet)
        if self._ever_loaded and not quiet:
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
        if not self._refresh_quiet:
            restore_shell_status()
            self._controls_card.set_reload_enabled(True)

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, ImageWorkspacePayload):
            return
        quiet = self._refresh_quiet
        self._is_error = False
        self._loading = False
        self._ever_loaded = True
        if not quiet:
            self._error_banner.hide()
        self._loading_card.hide()
        self._content.show()

        if isinstance(payload.me, UserMeResponse):
            self._me = payload.me
        self._profiles = [profile for profile in payload.profiles if isinstance(profile, ProfileResponse)]
        self._image_jobs = list(getattr(payload.image_jobs, "items", []) or [])
        if isinstance(payload.music_history, MusicHistoryListResponse):
            self._history = payload.music_history
        settings = payload.settings
        if hasattr(settings, "model_dump"):
            server_settings = settings.model_dump(by_alias=True)
        elif isinstance(settings, dict):
            server_settings = settings
        else:
            server_settings = {}

        # Keep local prompt/source edits authoritative while the page is open.
        # Merge server settings underneath so other keys still refresh.
        if self._prompts_initialized or self._source_modes_initialized:
            merged = dict(server_settings)
            merged.update(self._current_settings_patch())
            self._settings_raw = merged
        else:
            self._settings_raw = server_settings

        if not self._prompts_initialized:
            prompts = normalize_image_prompt_settings(self._settings_raw)
            self._controls_card.set_prompts(
                prompts.image_background_prompt,
                prompts.image_thumbnail_prompt,
            )
            self._prompts_initialized = True
        if not self._source_modes_initialized:
            self._bind_source_modes_from_settings()

        self._refresh_presentation(reload_previews=not quiet)
        self._surface_regen_job_failures()
        self._loaded_user_id = cached_user_id(self._cache)

    def _bind_source_modes_from_settings(self) -> None:
        bg_mode, th_mode = resolve_kind_source_modes(self._settings_raw)
        self._background_preview.set_source_mode(bg_mode)
        self._thumbnail_preview.set_source_mode(th_mode)
        self._source_modes_initialized = True

    def _on_filters_changed(self) -> None:
        from shared.lib.formatting import today_ymd

        today = today_ymd()
        from_date = self._controls_card.from_date()
        to_date = self._controls_card.to_date()
        if self._date_filter_banner_message and not (
            (from_date and today < from_date) or (to_date and today > to_date)
        ):
            self._date_filter_banner_message = None
        self._schedule_local_workspace_save()
        self._refresh_presentation(reload_previews=True)

    def _apply_core_cache(self) -> bool:
        if self._cache is None or not self._cache.has_core():
            return False
        me, profiles, settings_raw, _descriptions, _structures, _moods = self._cache.snapshot_core()
        if not profiles or not settings_raw:
            return False
        self._is_error = False
        self._loading = False
        self._ever_loaded = True
        self._error_banner.hide()
        self._loading_card.hide()
        self._content.show()
        if isinstance(me, UserMeResponse):
            self._me = me
        self._profiles = [profile for profile in profiles if isinstance(profile, ProfileResponse)]
        self._settings_raw = settings_raw
        if not self._prompts_initialized:
            prompts = normalize_image_prompt_settings(self._settings_raw)
            self._controls_card.set_prompts(
                prompts.image_background_prompt,
                prompts.image_thumbnail_prompt,
            )
            self._prompts_initialized = True
        if not self._source_modes_initialized:
            self._bind_source_modes_from_settings()
        self._refresh_presentation(reload_previews=True)
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
        # Quiet poll failures stay in the status bar so we don't interrupt editing.
        if self._refresh_quiet:
            emit_shell_status(message or LOAD_ERROR, tone="warning")
            return
        self._show_workspace_error(message or LOAD_ERROR)

    def _refresh_presentation(self, *, reload_previews: bool = True) -> None:
        from_date = self._controls_card.from_date()
        to_date = self._controls_card.to_date()
        filtered_batches = filter_batches_by_date(self._history.batches, from_date, to_date)
        batch_ids = {batch.batch_id for batch in filtered_batches if batch.batch_id}
        filtered_jobs = filter_jobs_by_batches(self._image_jobs, batch_ids)
        rows = build_queue_rows(filtered_jobs, filtered_batches, self._profiles)

        if self._pending_manual_select_key:
            if any(row.key == self._pending_manual_select_key for row in rows):
                self._selected_queue_key = self._pending_manual_select_key
                self._user_cleared_selection = False
                self._pending_manual_select_key = None
                reload_previews = True
            # Keep pending until the new row appears in filtered results.
        elif self._selected_queue_key and not any(row.key == self._selected_queue_key for row in rows):
            self._selected_queue_key = rows[0].key if rows else ""
            self._user_cleared_selection = False
            reload_previews = True
        elif not self._selected_queue_key and rows and not self._user_cleared_selection:
            self._selected_queue_key = rows[0].key
            reload_previews = True

        if self._date_filter_banner_message:
            self._controls_card.set_filter_banner(self._date_filter_banner_message)
        else:
            self._controls_card.set_filter_banner(None)

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
        # Pass "" when user cleared selection so set_rows does not re-select row 0.
        selected_for_table: str | None
        if self._user_cleared_selection:
            selected_for_table = ""
        else:
            selected_for_table = self._selected_queue_key
        self._controls_card.set_rows(rows, selected_for_table)
        if reload_previews:
            self._load_previews(self._controls_card.selected_row(), force=True)
        else:
            self._load_previews(self._controls_card.selected_row(), force=False)
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
        self._user_cleared_selection = False
        self._selected_queue_key = key
        self._schedule_local_workspace_save()
        self._load_previews(self._controls_card.selected_row(), force=True)

    def _on_selection_cleared(self) -> None:
        self._user_cleared_selection = True
        self._selected_queue_key = ""
        self._preview_fingerprint = ""
        self._schedule_local_workspace_save()
        self._background_preview.set_image_bytes(None)
        self._thumbnail_preview.set_image_bytes(None)
        self._controls_card.set_footer_detail(
            "No row selected. Manual Generation creates a Not available queue row for today "
            "(credits/quota apply)."
        )

    def _preview_row_fingerprint(self, row) -> str:
        if row is None:
            return ""
        bg = row.bg_job
        th = row.th_job
        return "|".join(
            [
                str(getattr(bg, "id", "") or ""),
                str(getattr(bg, "status", "") or ""),
                str(getattr(bg, "output_image_path", "") or ""),
                str(getattr(bg, "updated_at", "") or ""),
                str(getattr(th, "id", "") or ""),
                str(getattr(th, "status", "") or ""),
                str(getattr(th, "output_image_path", "") or ""),
                str(getattr(th, "updated_at", "") or ""),
            ]
        )

    def _load_previews(self, row, *, force: bool = True) -> None:
        fingerprint = self._preview_row_fingerprint(row)
        if not force and fingerprint == self._preview_fingerprint:
            footer = build_footer_detail(row)
            self._controls_card.set_footer_detail(footer)
            return
        self._preview_fingerprint = fingerprint
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

    def _schedule_image_settings_save(self, *_args: object) -> None:
        self._prompt_save_timer.start()

    def _current_settings_patch(self) -> dict[str, object]:
        return {
            "imageBackgroundPrompt": self._controls_card.background_prompt(),
            "imageThumbnailPrompt": self._controls_card.thumbnail_prompt(),
            "imageBackgroundSourceMode": self._background_preview.source_mode(),
            "imageThumbnailSourceMode": self._thumbnail_preview.source_mode(),
        }

    def _persist_image_settings(self) -> None:
        if self._patch_worker is not None and self._patch_worker.isRunning():
            return
        patch = self._current_settings_patch()
        self._settings_raw.update(patch)
        worker = PatchSettingsWorker(self._api, patch, parent=self)
        worker.failed.connect(
            lambda message: self._show_workspace_error(
                str(message or "").strip() or "Unable to save image settings right now."
            )
        )
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
            settings_patch=self._current_settings_patch(),
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
        if force:
            block = self._preflight_regenerate(job_ids)
            if block:
                self._show_workspace_error(block)
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
        if self._prompt_save_timer.isActive():
            self._prompt_save_timer.stop()
        patch = self._current_settings_patch()
        self._settings_raw.update(patch)
        worker = ImageRetryJobsWorker(
            self._api,
            job_ids=job_ids if job_ids else None,
            batch_id=batch_id,
            force=force,
            settings_patch=patch,
            parent=self,
        )
        worker.succeeded.connect(self._on_retry_succeeded)
        worker.failed.connect(self._on_retry_failed)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        if force:
            self._awaiting_regen_job_ids = {str(job_id) for job_id in job_ids if str(job_id).strip()}
            notify_action("Regenerating image(s)… Credits/quota apply when generation runs.", tone="neutral")
        elif batch_id and not job_ids:
            notify_action("Retrying failed image jobs for batch…", tone="neutral")
        else:
            notify_action(f"Retrying {len(job_ids)} image job(s)…", tone="neutral")
        worker.start()

    def _regenerate_jobs(self, job_ids: list[str], batch_id: str | None = None) -> None:
        self._retry_jobs(job_ids, batch_id, force=True)

    def _on_manual_generation(self, kind: str) -> None:
        kind_value = str(kind or "").strip().lower()
        row = self._controls_card.selected_row()
        if row is None:
            self._start_standalone_generation(kind_value)
            return
        if kind_value == "background":
            job = row.bg_job
            label = "Background"
        else:
            job = row.th_job
            label = "Thumbnail"
        if job is None:
            self._show_workspace_error(
                f"This row has no {label} job to regenerate. Wait for the pipeline to create image jobs, "
                "or Deselect and use Manual Generation to create a Not available row for today."
            )
            return
        self._regenerate_jobs([job.id], row.batch_id)

    def _start_standalone_generation(self, kind: str) -> None:
        kind_value = "thumbnail" if kind == "thumbnail" else "background"
        mode = (
            self._thumbnail_preview.source_mode()
            if kind_value == "thumbnail"
            else self._background_preview.source_mode()
        )
        if mode == "personal_reference":
            self._show_workspace_error(
                _PERSONAL_NOT_READY.format(
                    kind="Thumbnail" if kind_value == "thumbnail" else "Background"
                )
            )
            return
        prompt = (
            self._controls_card.thumbnail_prompt()
            if kind_value == "thumbnail"
            else self._controls_card.background_prompt()
        ).strip()
        if mode == "prompt_only" and not prompt:
            self._show_workspace_error(
                _EMPTY_TH_PROMPT if kind_value == "thumbnail" else _EMPTY_BG_PROMPT
            )
            return
        if self._standalone_worker is not None and self._standalone_worker.isRunning():
            self._show_workspace_error("A Manual Generation is already in progress.")
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._show_workspace_error("An image retry is already in progress.")
            return

        profile_id = None
        if self._profiles:
            profile_id = str(self._profiles[0].id)

        if self._prompt_save_timer.isActive():
            self._prompt_save_timer.stop()
        patch = self._current_settings_patch()
        self._settings_raw.update(patch)

        kind_label = "Thumbnail" if kind_value == "thumbnail" else "Background"
        notify_action(
            f"Creating Not available row for today · generating {kind_label}…",
            tone="neutral",
        )
        self._controls_card.set_footer_detail(
            f"Created Not available row for today · generating {kind_label}…"
        )
        worker = ImageManualGenerateWorker(
            self._api,
            kind=kind_value,
            prompt=prompt or None,
            channel_profile_id=profile_id,
            settings_patch=patch,
            parent=self,
        )
        worker.succeeded.connect(self._on_manual_generate_succeeded)
        worker.failed.connect(self._on_manual_generate_failed)
        worker.finished.connect(lambda: setattr(self, "_standalone_worker", None))
        self._standalone_worker = worker
        worker.start()

    def _on_manual_generate_succeeded(self, payload: object) -> None:
        from shared.lib.formatting import today_ymd
        from shared.models.platform import ImageJobsManualGenerateResponse

        if not isinstance(payload, ImageJobsManualGenerateResponse):
            self._show_workspace_error("Manual Generation returned an unexpected response.")
            return

        batch_id = str(payload.batch_id or "").strip()
        profile_id = str(payload.profile_id or "").strip()
        kind_value = str(payload.kind or "").strip().lower()
        kind_label = "Thumbnail" if kind_value == "thumbnail" else "Background"
        if batch_id and profile_id:
            self._pending_manual_select_key = f"{batch_id}-{profile_id}-ok"
            self._user_cleared_selection = False
            self._selected_queue_key = self._pending_manual_select_key

        today = today_ymd()
        from_date = self._controls_card.from_date()
        to_date = self._controls_card.to_date()
        if (from_date and today < from_date) or (to_date and today > to_date):
            self._date_filter_banner_message = (
                "Created a Not available row for today — expand the date filter to see it."
            )
            self._controls_card.set_filter_banner(self._date_filter_banner_message)
        else:
            self._date_filter_banner_message = None
            self._controls_card.set_filter_banner(None)

        self._error_banner.hide()
        message = f"Created Not available row for today · generating {kind_label}…"
        self._status_label = message
        self._controls_card.set_footer_detail(message)
        notify_action(message, tone="success")
        self._refresh_workspace(quiet=False)

    def _on_manual_generate_failed(self, message: str) -> None:
        detail = str(message or "").strip() or "Manual Generation failed."
        self._status_label = "Manual Generation failed."
        self._show_workspace_error(detail)

    def _preflight_regenerate(self, job_ids: list[str]) -> str | None:
        kinds: set[str] = set()
        for job in self._image_jobs:
            if str(job.id) in {str(value) for value in job_ids}:
                kinds.add(str(getattr(job, "kind", "") or "").strip().lower())
        if not kinds and job_ids:
            # Fall back to selected row kinds when job list is stale.
            row = self._controls_card.selected_row()
            if row and row.bg_job and str(row.bg_job.id) in job_ids:
                kinds.add("background")
            if row and row.th_job and str(row.th_job.id) in job_ids:
                kinds.add("thumbnail")

        bg_mode = self._background_preview.source_mode()
        th_mode = self._thumbnail_preview.source_mode()
        if "background" in kinds:
            if bg_mode == "personal_reference":
                return _PERSONAL_NOT_READY.format(kind="Background")
            if bg_mode == "prompt_only" and not self._controls_card.background_prompt().strip():
                return _EMPTY_BG_PROMPT
        if "thumbnail" in kinds:
            if th_mode == "personal_reference":
                return _PERSONAL_NOT_READY.format(kind="Thumbnail")
            if th_mode == "prompt_only" and not self._controls_card.thumbnail_prompt().strip():
                return _EMPTY_TH_PROMPT

        if self._me is not None:
            try:
                balance = float(self._me.credit_balance)
            except (TypeError, ValueError):
                balance = None
            if balance is not None and balance <= 0:
                # Plan image quota may still cover the run — warn, do not hard-block.
                notify_action(
                    "Wallet shows 0 credits. Generation still uses plan image quota when available; "
                    "if quota is also exhausted the job will fail with a clear error.",
                    tone="warning",
                )
        return None

    def _surface_regen_job_failures(self) -> None:
        if not self._awaiting_regen_job_ids:
            return
        still_waiting: set[str] = set()
        for job in self._image_jobs:
            job_id = str(job.id)
            if job_id not in self._awaiting_regen_job_ids:
                continue
            status = str(getattr(job, "status", "") or "").strip().lower()
            error = str(getattr(job, "error", "") or "").strip()
            if status in {"pending", "running"}:
                still_waiting.add(job_id)
                continue
            if status == "failed" and error:
                key = f"{job_id}:{error}"
                if key not in self._surfaced_job_errors:
                    self._surfaced_job_errors.add(key)
                    kind = str(getattr(job, "kind", "") or "image").strip() or "image"
                    message = f"{kind.capitalize()} generation failed: {error}"
                    if any(hint in error.lower() for hint in _CREDIT_QUOTA_HINTS):
                        message = (
                            f"{kind.capitalize()} generation blocked (credits/quota): {error}"
                        )
                    self._show_workspace_error(message)
            # success or terminal without tracking → drop
        self._awaiting_regen_job_ids = still_waiting

    def _on_retry_succeeded(self, payload: object) -> None:
        from shared.models.platform import ImageJobsRetryResponse

        updated = 0
        if isinstance(payload, ImageJobsRetryResponse):
            updated = int(payload.updated or 0)
        was_force = bool(self._awaiting_regen_job_ids)
        if updated > 0:
            message = (
                f"Queued {updated} image job{'s' if updated != 1 else ''} for generation. "
                "Credits and plan image quota apply when each job runs."
            )
            self._status_label = message
            self._error_banner.hide()
            notify_action(message, tone="success")
        elif was_force:
            message = (
                "Could not regenerate this image. The server reset 0 jobs — usually because "
                "the job is already successful and this API build does not support force "
                "regenerate yet (common on production before deploy). Use sandbox "
                "(`python main.py sandbox`), or ask to deploy the image-jobs force retry API."
            )
            self._status_label = "No image jobs to reset."
            self._show_workspace_error(message)
        else:
            message = "No failed image jobs were reset. They may already be pending or running."
            self._status_label = "No image jobs to reset."
            self._show_workspace_error(message)
        self.refresh_data()

    def _on_retry_failed(self, message: str) -> None:
        self._awaiting_regen_job_ids.clear()
        self._status_label = "Unable to regenerate image."
        detail = str(message or "").strip() or "Unable to regenerate image jobs."
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
        # Do not rebuild the whole queue here — that fights with editing source modes.
