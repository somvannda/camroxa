"""Music workspace page — batch composer and song editor."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_panel import StudioPanel, fill_studio_canvas, paint_studio_card
from features.music.music_styles import build_music_page_qss
from features.music.services.music_local_store import MusicLocalStore, MusicWorkspacePrefs
from features.music.widgets.automation_card import AutomationCard
from features.music.widgets.channel_selection_card import ChannelSelectionCard
from features.music.widgets.error_banner import LOAD_ERROR, MusicErrorBanner
from features.music.widgets.history_card import HistoryCard, HistoryRow
from features.music.widgets.settings_strip import MusicSettingsStrip
from features.music.widgets.song_editor_card import SongEditorCard
from shared.lib.music_readiness import build_music_readiness_report
from shared.lib.manual_asset_paths import normalize_image_source_mode
from shared.lib.music_batch_plan import (
    CreateBatchesResult,
    format_create_batches_summary,
    format_failed_create_slots,
)
from shared.lib.music_composer import (
    ComposerState,
    DraftPoolSeedState,
    HistoryFiltersState,
    blank_composer_state,
    effect_preview_from_creativity,
    get_inclusive_date_list,
    get_inclusive_day_span,
    matches_history_filters,
    read_settings_dict,
    sanitize_selected_profile_ids,
    song_matches_history_status_filter,
    toggle_selected_profile_ids,
)
from shared.lib.music_costs import (
    format_button_credit_label,
    format_draft_slot_button_label,
    format_operation_cost_label,
    get_batch_generate_total_cost,
    get_music_plan_cost_breakdown,
    map_operation_costs,
)
from shared.lib.music_settings import (
    MusicSettingsState,
    build_music_settings_patch,
    build_music_settings_state,
    read_string_setting,
    save_status_message,
    settings_snapshot,
)
from shared.models.auth import ProfileResponse
from shared.models.platform import BatchCreateRequest, MusicHistoryBatch, MusicHistoryListResponse, MusicPlanPreflightRequest, MusicPlanPreflightResponse, SunoBlocklistRuntimeResponse, YouTubeConnectionResponse
from shared.services.app_logger import log_error, log_info
from shared.services.file_service import ensure_directory, open_path
from shared.lib.page_account_scope import account_cache_mismatch, cached_user_id
from shared.lib.ui_font import ensure_inter_loaded, studio_font
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache
from shared.themes.deep_blue import (
    PANEL_SCROLL_CONTENT_ID,
    PANEL_SCROLL_RIGHT_GUTTER_PX,
)
from shared.widgets.settings_ui import make_panel_scroll_area
from shared.workers.data_workers import (
    BatchRetryFailuresWorker,
    BatchStatusWorker,
    CreateBatchesWorker,
    DeleteFailedBatchWorker,
    DraftGenerationWorker,
    MusicHistoryRefreshWorker,
    MusicLanguagesWorker,
    MusicWorkspacePayload,
    MusicWorkspaceWorker,
    MusicPlanPreflightWorker,
    PatchSettingsWorker,
    PipelineRecoveryWorker,
    PolishLyricsWorker,
    RetrySongDraftWorker,
    RetrySongSunoWorker,
    RewriteBatchAlbumWorker,
    RewriteSongTitleWorker,
)

LOADING_MESSAGE = "Loading music workspace..."


class _FramedHeader(CreateHeader):
    def paintEvent(self, event) -> None:  # noqa: N802
        paint_studio_card(self)


class MusicView(QWidget):
    # Emitted from the lyrics-check worker thread; Qt queues them to the GUI
    # thread. `QTimer.singleShot` from that thread had no event loop to fire on.
    _suno_hits_ready = Signal(object)
    _suno_check_failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("music_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ensure_inter_loaded()
        self.setStyleSheet(build_music_page_qss())
        self.setFont(studio_font(12))
        fill_studio_canvas(self)
        self._api = api
        self._cache = cache
        self._worker: MusicWorkspaceWorker | None = None
        self._patch_worker: PatchSettingsWorker | None = None
        self._draft_worker: DraftGenerationWorker | None = None
        self._polish_worker: PolishLyricsWorker | None = None
        self._batch_worker: CreateBatchesWorker | None = None
        self._preflight_worker: MusicPlanPreflightWorker | None = None
        self._status_worker: BatchStatusWorker | None = None
        self._history_worker: MusicHistoryRefreshWorker | None = None
        self._language_worker: MusicLanguagesWorker | None = None
        self._pending_history_refresh = False
        self._retry_worker: (
            RetrySongDraftWorker
            | RetrySongSunoWorker
            | RewriteBatchAlbumWorker
            | RewriteSongTitleWorker
            | BatchRetryFailuresWorker
            | DeleteFailedBatchWorker
            | None
        ) = None
        self._pending_history_retry_kind = ""
        self._pending_title_rewrite_row: HistoryRow | None = None
        self._profiles: list[ProfileResponse] = []
        self._youtube_connections: list[YouTubeConnectionResponse] = []
        self._history = MusicHistoryListResponse()
        self._settings_raw: dict = {}
        self._music_settings = MusicSettingsState()
        self._composer = blank_composer_state("")
        self._local_workspace_restored = False
        self._draft_pool_seeds: DraftPoolSeedState | None = None
        self._selected_description_id = ""
        self._selected_structure_id = ""
        self._selected_mood_id = ""
        self._prompt_selection_touched = False
        self._selected_history_song_id: str | None = None
        self._latest_batch_id: str | None = None
        self._latest_batch_summary: str | None = None
        self._last_batch_status_key: tuple[object, ...] | None = None
        self._ensured_run_dirs: set[str] = set()
        self._save_status = "idle"
        self._settings_initialized = False
        self._last_persisted_settings = ""
        self._operation_costs: dict = {}
        self._loading = True
        self._is_error = False
        self._ever_loaded = False
        self._loaded_user_id: str | None = None
        self._history_filters = HistoryFiltersState()
        self._language_options: list[tuple[str, str]] = [("en", "English")]
        self._suno_blocklist: object | None = None
        self._generation_preflight: MusicPlanPreflightResponse | None = None
        self._description_options_by_id: dict[str, object] = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._persist_settings)
        self._local_save_timer = QTimer(self)
        self._local_save_timer.setSingleShot(True)
        self._local_save_timer.setInterval(400)
        self._local_save_timer.timeout.connect(self._persist_local_workspace_prefs)
        self._saved_reset_timer = QTimer(self)
        self._saved_reset_timer.setSingleShot(True)
        self._saved_reset_timer.setInterval(1800)
        self._saved_reset_timer.timeout.connect(lambda: self._set_save_status("idle"))
        self._batch_timer = QTimer(self)
        self._batch_timer.setInterval(2500)
        self._batch_timer.timeout.connect(self._poll_batch_status)
        self._preflight_timer = QTimer(self)
        self._preflight_timer.setSingleShot(True)
        self._preflight_timer.setInterval(350)
        self._preflight_timer.timeout.connect(self._run_preflight_check)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self._scroll = make_panel_scroll_area()
        fill_studio_canvas(self._scroll.viewport())

        container = QWidget()
        container.setObjectName(PANEL_SCROLL_CONTENT_ID)
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fill_studio_canvas(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, PANEL_SCROLL_RIGHT_GUTTER_PX, 0)
        root.setSpacing(12)

        header = _FramedHeader(
            title="Music",
            subtitle="Batch composer, song editor, channel pairs, and history.",
            meta="",
            eyebrow="WORKSPACE",
        )
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.addWidget(header)

        self._error_banner = MusicErrorBanner()
        self._error_banner.hide()
        root.addWidget(self._error_banner)

        self._loading_card = StudioPanel()
        loading_layout = QVBoxLayout(self._loading_card)
        loading_layout.setContentsMargins(12, 12, 12, 12)
        loading_label = QLabel(LOADING_MESSAGE)
        loading_label.setObjectName("PageSubtitle")
        loading_layout.addWidget(loading_label)
        root.addWidget(self._loading_card)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self._settings_strip = MusicSettingsStrip()
        self._settings_strip.changed.connect(self._on_strip_changed)
        content_layout.addWidget(self._settings_strip)

        self._song_card = SongEditorCard()
        self._suno_hits_ready.connect(self._apply_suno_online_hits)
        self._suno_check_failed.connect(self._on_suno_online_check_failed)
        self._primary_card = ChannelSelectionCard("Primary channels")
        self._secondary_card = ChannelSelectionCard("Secondary channels")
        self._automation_card = AutomationCard()
        self._song_card.draft_requested.connect(self._generate_draft)
        self._song_card.polish_requested.connect(self._polish_lyrics)
        self._song_card.copy_title_requested.connect(lambda: self._copy_text(self._song_card.title()))
        self._song_card.copy_lyrics_requested.connect(lambda: self._copy_text(self._song_card.lyrics()))
        self._song_card.copy_both_requested.connect(
            lambda: self._copy_text("\n\n".join(part for part in (self._song_card.title(), self._song_card.lyrics()) if part))
        )
        self._song_card.field_changed.connect(self._on_song_fields_changed)
        self._song_card.suno_auto_fixed.connect(self._on_suno_auto_fixed)
        self._song_card.suno_online_check_requested.connect(self._on_suno_online_check_requested)
        self._primary_card.toggled.connect(lambda profile_id: self._toggle_profile("primary", profile_id))
        self._secondary_card.toggled.connect(lambda profile_id: self._toggle_profile("secondary", profile_id))
        self._automation_card.generate_requested.connect(self._create_batches)
        self._automation_card.automation_changed.connect(self._on_automation_changed)
        self._automation_card.description_changed.connect(self._on_description_changed)
        self._automation_card.structure_changed.connect(self._on_structure_changed)
        self._automation_card.mood_changed.connect(self._on_mood_changed)
        self._automation_card.shuffle_changed.connect(self._on_shuffle_changed)
        self._automation_card.mood_shuffle_changed.connect(self._on_mood_shuffle_changed)
        self._song_card.setMinimumWidth(350)
        self._primary_card.setFixedWidth(245)
        self._secondary_card.setFixedWidth(245)
        main_row = QHBoxLayout()
        main_row.setSpacing(12)
        main_row.addWidget(self._song_card, stretch=14)
        main_row.addWidget(self._primary_card)
        main_row.addWidget(self._secondary_card)
        main_row.addWidget(self._automation_card, stretch=14)
        content_layout.addLayout(main_row, stretch=1)

        self._history_card = HistoryCard()
        self._history_card.filters_changed.connect(self._on_history_filters_changed)
        self._history_card.row_selected.connect(self._select_history_row)
        self._history_card.open_folder_requested.connect(self._open_history_folder)
        self._history_card.retry_draft_requested.connect(self._retry_history_draft)
        self._history_card.retry_suno_requested.connect(self._retry_history_suno)
        self._history_card.rewrite_album_requested.connect(self._rewrite_history_album)
        self._history_card.rewrite_title_requested.connect(self._rewrite_history_title)
        self._history_card.enqueue_images_requested.connect(self._enqueue_history_images)
        self._history_card.continue_video_requested.connect(self._continue_history_video)
        self._history_card.retry_batch_requested.connect(self._retry_history_batch)
        self._history_card.rewrite_batch_requested.connect(self._rewrite_history_batch)
        self._history_card.delete_batch_requested.connect(self._delete_failed_batch)
        self._history_card.refresh_requested.connect(self._refresh_history_status)
        self._history_card.recover_failed_requested.connect(self._recover_failed_pipeline)
        content_layout.addWidget(self._history_card)

        self._content.hide()
        root.addWidget(self._content)

        self._scroll.setWidget(container)
        page_layout.addWidget(self._scroll, stretch=1)

    def _flash_status(
        self,
        message: str,
        *,
        tone: str = "neutral",
        duration_ms: int = 5000,
    ) -> None:
        from shared.services.action_feedback import notify_action

        notify_action(message, tone=tone, duration_ms=duration_ms)

    def _restore_local_workspace_prefs(self) -> None:
        prefs = MusicLocalStore().read_workspace_prefs()
        if prefs is None:
            return
        if prefs.from_date and prefs.to_date:
            self._composer.from_date = prefs.from_date
            self._composer.to_date = prefs.to_date
        if prefs.primary_profile_ids:
            self._composer.primary_profile_ids = list(prefs.primary_profile_ids)
        if prefs.secondary_profile_ids:
            self._composer.secondary_profile_ids = list(prefs.secondary_profile_ids)
        # Restore the last explicit prompt selection. It only wins if the id is
        # still present in the workspace catalog; otherwise _apply_prompt_selection
        # treats it as stale and falls back to the server-configured default.
        if prefs.selected_description_id:
            self._selected_description_id = prefs.selected_description_id
        if prefs.selected_structure_id:
            self._selected_structure_id = prefs.selected_structure_id
        if prefs.selected_mood_id:
            self._selected_mood_id = prefs.selected_mood_id

    def _current_workspace_prefs(self) -> MusicWorkspacePrefs:
        return MusicWorkspacePrefs(
            from_date=self._composer.from_date,
            to_date=self._composer.to_date,
            primary_profile_ids=list(self._composer.primary_profile_ids),
            secondary_profile_ids=list(self._composer.secondary_profile_ids),
            selected_description_id=self._selected_description_id,
            selected_structure_id=self._selected_structure_id,
            selected_mood_id=self._selected_mood_id,
        )

    def _schedule_local_workspace_save(self) -> None:
        self._local_save_timer.start()

    def _persist_local_workspace_prefs(self) -> None:
        MusicLocalStore().write_workspace_prefs(self._current_workspace_prefs())

    def _reset_for_account_change(self) -> None:
        self._loaded_user_id = None
        self._ever_loaded = False
        self._local_workspace_restored = False
        self._settings_initialized = False
        self._loading = True
        self._is_error = False
        self._profiles = []
        self._youtube_connections = []
        self._history = MusicHistoryListResponse()
        self._settings_raw = {}
        self._composer = blank_composer_state("")
        self._selected_description_id = ""
        self._selected_structure_id = ""
        self._selected_mood_id = ""
        self._prompt_selection_touched = False
        self._error_banner.hide()
        self._loading_card.show()
        self._content.hide()

    def activate_page(self) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        if not self._local_workspace_restored:
            self._restore_local_workspace_prefs()
            self._local_workspace_restored = True
        self._bootstrap_language_options_from_cache()
        self._bootstrap_prompt_defaults_from_cache()
        self.refresh_language_options()
        self.refresh_data()

    def _bootstrap_prompt_defaults_from_cache(self) -> None:
        if not self._ever_loaded or self._cache is None or not self._cache.has_core():
            return
        _me, _profiles, settings_raw, description_options, structure_options, mood_options = self._cache.snapshot_core()
        if settings_raw:
            self._settings_raw = dict(settings_raw)
            self._sync_music_settings_defaults()
        if not description_options or not structure_options:
            return
        descriptions = [(item.id, item.name) for item in description_options]
        structures = [(item.id, item.name) for item in structure_options]
        moods = [(item.id, item.name) for item in mood_options]
        self._description_options_by_id = {item.id: item for item in description_options}
        self._apply_saved_prompt_defaults(descriptions, structures, moods)

    def _bootstrap_language_options_from_cache(self) -> None:
        if self._cache is None:
            return
        cached = self._cache.get_language_options()
        if cached:
            self._apply_language_options(cached)

    def refresh_language_options(self) -> None:
        if self._language_worker is not None and self._language_worker.isRunning():
            return
        worker = MusicLanguagesWorker(self._api, self)
        worker.succeeded.connect(self._on_language_options_loaded)
        worker.failed.connect(self._on_language_options_failed)
        worker.finished.connect(lambda: setattr(self, "_language_worker", None))
        self._language_worker = worker
        worker.start()

    def _on_language_options_loaded(self, payload: object) -> None:
        if not isinstance(payload, list) or not payload:
            return
        options: list[tuple[str, str]] = []
        for item in payload:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                code = str(item[0] or "").strip()
                label = str(item[1] or "").strip()
                if code and label:
                    options.append((code, label))
        if not options:
            return
        if self._cache is not None:
            self._cache.apply_warmup(language_options=options)
        self._apply_language_options(options)

    def _on_language_options_failed(self, message: str) -> None:
        log_error(message or "Failed to load language options", category="music")
        self._flash_status(message or "Could not load language options.", tone="warning")

    def _apply_language_options(self, options: list[tuple[str, str]]) -> None:
        self._language_options = list(options)
        self._settings_strip.set_language_options(self._language_options)
        if self._settings_initialized:
            self._settings_strip.apply_settings(
                language=self._music_settings.language,
                secondary_language=self._music_settings.secondary_language,
                creativity=self._music_settings.creativity,
                unique_opening=self._music_settings.unique_opening,
                use_content_pools=self._music_settings.use_content_pools,
                strict_level=self._music_settings.strict_level,
                history_window=self._music_settings.history_window,
                song_count=self._music_settings.song_count,
            )
            self._apply_description_language_mode(self._selected_description_id)

    def _apply_suno_blocklist(self, payload: object | None) -> None:
        if isinstance(payload, SunoBlocklistRuntimeResponse):
            blocklist = payload
        else:
            blocklist = None
        self._suno_blocklist = blocklist
        if blocklist is None:
            self._song_card.set_platform_suno_blocklist()
            return
        self._song_card.set_platform_suno_blocklist(
            replacements=dict(blocklist.replacements),
            block_terms=list(blocklist.block_terms),
            warn_terms=list(blocklist.warn_terms),
        )
        self._song_card.set_learned_suno_terms(self._merged_learned_suno_terms())

    def _merged_learned_suno_terms(self, extra: list[str] | None = None) -> list[str]:
        merged = [str(term).strip().lower() for term in self._music_settings.learned_suno_terms if str(term).strip()]
        seen = set(merged)
        for term in extra or []:
            normalized = str(term).strip().lower()
            if normalized and normalized not in seen:
                merged.append(normalized)
                seen.add(normalized)
        return merged

    def _remember_learned_suno_terms(self, terms: list[str]) -> None:
        merged = self._merged_learned_suno_terms(terms)
        if tuple(merged) == self._music_settings.learned_suno_terms:
            return
        self._music_settings = replace(self._music_settings, learned_suno_terms=tuple(merged))
        self._schedule_settings_save()
        self._song_card.set_learned_suno_terms(merged)

    def _on_suno_online_check_requested(self, title: str, lyrics: str) -> None:
        import threading

        learned_terms = self._merged_learned_suno_terms()

        def run() -> None:
            try:
                from shared.lib.suno_lyrics_sanitize import SunoLyricsRiskHit
                from shared.models.platform import LyricsSunoCheckRequest

                response = self._api.check_lyrics_suno(
                    LyricsSunoCheckRequest(
                        title=title,
                        lyrics=lyrics,
                        learned_terms=learned_terms,
                    )
                )
                hits = [
                    SunoLyricsRiskHit(
                        term=hit.term,
                        severity=hit.severity if hit.severity in {"block", "warn"} else "warn",
                        start=hit.start,
                        end=hit.end,
                        suggestion=hit.suggestion,
                    )
                    for hit in response.hits
                ]
                self._suno_hits_ready.emit(hits)
            except Exception as exc:  # noqa: BLE001
                log_error("music.suno_online_check_failed", category="music", exc=exc)
                self._suno_check_failed.emit(str(exc) or "Suno lyrics check failed.")

        threading.Thread(target=run, daemon=True).start()

    def _apply_suno_online_hits(self, hits: object) -> None:
        self._song_card.apply_online_suno_hits(hits)

    def _on_suno_online_check_failed(self, message: str) -> None:
        self._flash_status(message, tone="warning")

    def refresh_data(self) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._ever_loaded:
            if self._apply_core_cache():
                self._ever_loaded = True
            else:
                self._loading = True
                self._loading_card.show()
                self._content.hide()
                self._error_banner.hide()
        self._bootstrap_youtube_connections_from_cache()
        worker = MusicWorkspaceWorker(self._api, self)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def refresh_history(self) -> None:
        """Reload history only so batch progress appears song-by-song.

        Date filtering is applied client-side in ``_render_history``. Sending
        From/To to the API wiped the loaded list when the range was inverted or
        mismatched (empty response), which also broke Last batch / Show all.
        """
        if self._history_worker is not None and self._history_worker.isRunning():
            self._pending_history_refresh = True
            return
        limit = self._history_fetch_limit()
        worker = MusicHistoryRefreshWorker(self._api, limit=limit, parent=self)
        worker.succeeded.connect(self._on_history_refreshed)
        worker.failed.connect(self._on_history_refresh_failed)
        worker.finished.connect(self._finish_history_worker)
        self._history_worker = worker
        worker.start()

    def _on_history_filters_changed(self) -> None:
        """Re-render locally when History filters change (no API refetch)."""
        self._render_history()

    def _history_fetch_limit(self) -> int:
        """Cap history fetch by settings window and API max (100)."""
        try:
            window = int(getattr(self._music_settings, "history_window", 50) or 50)
        except (TypeError, ValueError):
            window = 50
        return max(8, min(100, window))

    def _finish_history_worker(self) -> None:
        self._history_worker = None
        if self._pending_history_refresh:
            self._pending_history_refresh = False
            self.refresh_history()

    def _on_history_refreshed(self, payload: object) -> None:
        if not isinstance(payload, MusicHistoryListResponse):
            return
        self._history = payload
        self._render_history()

    def _on_history_refresh_failed(self, message: str) -> None:
        if message:
            log_error(message, category="music")

    @staticmethod
    def _reconcile_prompt_selection(
        descriptions: list[tuple[str, str]],
        structures: list[tuple[str, str]],
        moods: list[tuple[str, str]],
        *,
        selected_description_id: str,
        selected_structure_id: str,
        selected_mood_id: str,
    ) -> tuple[str, str, str]:
        description_ids = {option_id for option_id, _name in descriptions}
        structure_ids = {option_id for option_id, _name in structures}
        mood_ids = {option_id for option_id, _name in moods}
        next_description_id = selected_description_id
        next_structure_id = selected_structure_id
        next_mood_id = selected_mood_id
        if not next_description_id and descriptions:
            next_description_id = descriptions[0][0]
        elif next_description_id not in description_ids:
            next_description_id = descriptions[0][0] if descriptions else ""
        from features.music.widgets.automation_card import FREE_STRUCTURE_SENTINELS

        if next_structure_id in FREE_STRUCTURE_SENTINELS:
            pass
        elif not next_structure_id and structures:
            next_structure_id = structures[0][0]
        elif next_structure_id not in structure_ids:
            next_structure_id = structures[0][0] if structures else ""
        if not next_mood_id and moods:
            next_mood_id = moods[0][0]
        elif next_mood_id and next_mood_id not in mood_ids:
            next_mood_id = moods[0][0] if moods else ""
        return next_description_id, next_structure_id, next_mood_id

    def _saved_prompt_defaults(self) -> tuple[str, str, str]:
        return (
            read_string_setting(self._settings_raw, "defaultDescriptionId"),
            read_string_setting(self._settings_raw, "defaultStructureId"),
            read_string_setting(self._settings_raw, "defaultMoodId"),
        )

    def _sync_music_settings_defaults(self) -> None:
        default_description_id, default_structure_id, default_mood_id = self._saved_prompt_defaults()
        if not self._settings_initialized:
            return
        self._music_settings = replace(
            self._music_settings,
            default_description_id=default_description_id,
            default_structure_id=default_structure_id,
            default_mood_id=default_mood_id,
        )

    def _apply_saved_prompt_defaults(
        self,
        descriptions: list[tuple[str, str]],
        structures: list[tuple[str, str]],
        moods: list[tuple[str, str]],
    ) -> None:
        self._apply_prompt_selection(descriptions, structures, moods)
        self._automation_card.set_selected_options(
            self._selected_description_id,
            self._selected_structure_id,
            self._selected_mood_id,
        )
        self._composer.description = self._automation_card.selected_description_name()
        self._composer.structure = self._automation_card.selected_structure_name()
        self._apply_description_language_mode(self._selected_description_id)

    @staticmethod
    def _pick_prompt_id(
        local_id: str,
        default_id: str,
        options: list[tuple[str, str]],
        *,
        allow_free_sentinels: bool = False,
    ) -> str:
        """Choose a prompt id: valid local selection, else server default, else first option.

        A local id that is no longer in the catalog is stale and must not override
        the server-configured default (see the stale-prefs guard test).
        """
        option_ids = {option_id for option_id, _name in options}
        if local_id:
            if local_id in option_ids:
                return local_id
            if allow_free_sentinels:
                from features.music.widgets.automation_card import FREE_STRUCTURE_SENTINELS

                if local_id in FREE_STRUCTURE_SENTINELS:
                    return local_id
        if default_id and default_id in option_ids:
            return default_id
        return options[0][0] if options else ""

    def _apply_prompt_selection(
        self,
        descriptions: list[tuple[str, str]],
        structures: list[tuple[str, str]],
        moods: list[tuple[str, str]],
    ) -> None:
        preferred_description_id, preferred_structure_id, preferred_mood_id = self._saved_prompt_defaults()
        if not self._prompt_selection_touched:
            self._selected_description_id = self._pick_prompt_id(
                self._selected_description_id,
                preferred_description_id,
                descriptions,
            )
            self._selected_structure_id = self._pick_prompt_id(
                self._selected_structure_id,
                preferred_structure_id,
                structures,
                allow_free_sentinels=True,
            )
            self._selected_mood_id = self._pick_prompt_id(
                self._selected_mood_id,
                preferred_mood_id,
                moods,
            )
        else:
            if not self._selected_description_id and descriptions:
                self._selected_description_id = descriptions[0][0]
            if not self._selected_structure_id and structures:
                self._selected_structure_id = structures[0][0]
            if not self._selected_mood_id and moods:
                self._selected_mood_id = moods[0][0]
        self._selected_description_id, self._selected_structure_id, self._selected_mood_id = (
            self._reconcile_prompt_selection(
                descriptions,
                structures,
                moods,
                selected_description_id=self._selected_description_id,
                selected_structure_id=self._selected_structure_id,
                selected_mood_id=self._selected_mood_id,
            )
        )

    def _finish_workspace_load(
        self,
        descriptions: list[tuple[str, str]],
        structures: list[tuple[str, str]],
        moods: list[tuple[str, str]],
    ) -> None:
        self._automation_card.set_options(descriptions, structures, moods)
        self._apply_saved_prompt_defaults(descriptions, structures, moods)
        self._apply_settings_to_ui()
        self._sync_profiles()
        self._refresh_presentation()

    def _on_failed(self, message: str) -> None:
        self._loading = False
        error_message = message or LOAD_ERROR
        if self._ever_loaded:
            self._loading_card.hide()
            self._content.show()
            self._error_banner.set_message(
                f"Refresh failed — showing last loaded data. {error_message}"
            )
            self._error_banner.show()
            self._flash_status(error_message, tone="warning")
            log_error(error_message, category="music")
            self.refresh_language_options()
            return
        self._is_error = True
        self._loading_card.hide()
        self._content.hide()
        self._error_banner.set_message(error_message)
        self._error_banner.show()
        log_error(error_message, category="music")

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, MusicWorkspacePayload):
            return
        self._loading = False
        self._is_error = False
        self._ever_loaded = True
        self._error_banner.hide()
        self._profiles = list(payload.profiles)
        self._youtube_connections = self._normalize_youtube_connections(list(payload.youtube_connections))
        if self._cache is not None:
            self._cache.apply_settings_workspace(youtube_connections=self._youtube_connections)
        self._history = payload.history
        self._language_options = list(payload.language_options or [("en", "English")])
        self._apply_suno_blocklist(payload.suno_blocklist)
        self._settings_raw = read_settings_dict(payload.settings)
        self._operation_costs = map_operation_costs(payload.operation_costs.items)
        if self._cache is not None:
            self._cache.apply_warmup(
                settings_raw=self._settings_raw,
                description_options=list(payload.description_options),
                structure_options=list(payload.structure_options),
                mood_options=list(payload.mood_options),
                language_options=self._language_options,
            )
        if not self._settings_initialized:
            self._music_settings = build_music_settings_state(
                self._settings_raw,
                language_options=tuple(self._language_options),
            )
            self._last_persisted_settings = settings_snapshot(self._music_settings)
            self._settings_initialized = True
        else:
            self._sync_music_settings_defaults()
        self._apply_language_options(self._language_options)
        descriptions = [(item.id, item.name) for item in payload.description_options]
        self._description_options_by_id = {
            item.id: item for item in payload.description_options
        }
        structures = [(item.id, item.name) for item in payload.structure_options]
        moods = [(item.id, item.name) for item in payload.mood_options]
        self._finish_workspace_load(descriptions, structures, moods)
        self._loaded_user_id = cached_user_id(self._cache)
        self._loading_card.hide()
        self._content.show()

    def _apply_core_cache(self) -> bool:
        if self._cache is None or not self._cache.has_core():
            return False
        _me, profiles, settings_raw, description_options, structure_options, mood_options = self._cache.snapshot_core()
        if not profiles or not settings_raw:
            return False
        self._loading = False
        self._is_error = False
        self._profiles = list(profiles)
        self._bootstrap_youtube_connections_from_cache()
        self._settings_raw = settings_raw
        cached_languages = self._cache.get_language_options() if self._cache is not None else []
        if cached_languages:
            self._language_options = list(cached_languages)
        if not self._settings_initialized:
            self._music_settings = build_music_settings_state(
                self._settings_raw,
                language_options=tuple(self._language_options),
            )
            self._last_persisted_settings = settings_snapshot(self._music_settings)
            self._settings_initialized = True
        else:
            self._sync_music_settings_defaults()
        self._apply_language_options(self._language_options)
        descriptions = [(item.id, item.name) for item in description_options]
        self._description_options_by_id = {item.id: item for item in description_options}
        structures = [(item.id, item.name) for item in structure_options]
        moods = [(item.id, item.name) for item in mood_options]
        self._finish_workspace_load(descriptions, structures, moods)
        self._loaded_user_id = cached_user_id(self._cache)
        self._loading_card.hide()
        self._content.show()
        return True

    def _apply_settings_to_ui(self) -> None:
        self._settings_strip.set_language_options(self._language_options)
        if self._composer.from_date and self._composer.to_date:
            self._settings_strip.apply_dates(self._composer.from_date, self._composer.to_date)
        self._settings_strip.apply_settings(
            language=self._music_settings.language,
            secondary_language=self._music_settings.secondary_language,
            creativity=self._music_settings.creativity,
            unique_opening=self._music_settings.unique_opening,
            use_content_pools=self._music_settings.use_content_pools,
            strict_level=self._music_settings.strict_level,
            history_window=self._music_settings.history_window,
            song_count=self._music_settings.song_count,
        )
        self._apply_description_language_mode(self._selected_description_id)
        self._automation_card.set_shuffle_structure(self._music_settings.shuffle_structure)
        self._automation_card.set_shuffle_mood(self._music_settings.shuffle_mood)
        # Re-assert free-mode shuffle lock after settings restore (order-safe).
        if self._automation_card.is_free_structure_selected():
            self._music_settings.shuffle_structure = False
            self._automation_card.set_shuffle_structure(False)
        self._automation_card.apply_automation_flags(
            auto_gen_image=self._music_settings.auto_gen_image,
            auto_gsuno=self._music_settings.auto_gsuno,
            auto_video_after_suno=self._music_settings.auto_video_after_suno,
            auto_merge_after_video=self._music_settings.auto_merge_after_video,
            auto_reel_after_video=self._music_settings.auto_reel_after_video,
            auto_upload_youtube=self._music_settings.auto_upload_youtube,
        )
        self._song_card.set_fields(
            title=self._composer.title,
            album=self._composer.album,
            lyrics=self._composer.lyrics,
            polish_strength=self._music_settings.polish_strength,
        )

    def _sync_profiles(self) -> None:
        if not self._composer.from_date:
            from shared.lib.formatting import today_ymd

            self._composer = blank_composer_state(today_ymd())
        primary = sanitize_selected_profile_ids(
            self._composer.primary_profile_ids,
            self._profiles,
            [self._profiles[0].id] if self._profiles else [],
        )
        secondary_fallback = self._profiles[min(1, len(self._profiles) - 1)].id if self._profiles else ""
        secondary = sanitize_selected_profile_ids(
            self._composer.secondary_profile_ids,
            self._profiles,
            [secondary_fallback] if secondary_fallback else [],
        )
        self._composer.primary_profile_ids = primary
        self._composer.secondary_profile_ids = secondary
        self._primary_card.set_profiles(self._profiles, primary)
        self._secondary_card.set_profiles(self._profiles, secondary)

    def _toggle_profile(self, side: str, profile_id: str) -> None:
        if side == "primary":
            self._composer.primary_profile_ids = toggle_selected_profile_ids(self._composer.primary_profile_ids, profile_id)
        else:
            self._composer.secondary_profile_ids = toggle_selected_profile_ids(self._composer.secondary_profile_ids, profile_id)
        self._sync_profiles()
        self._schedule_local_workspace_save()
        self._refresh_presentation()

    def _on_strip_changed(self) -> None:
        values = self._settings_strip.values()
        self._composer.from_date = str(values["from_date"])
        self._composer.to_date = str(values["to_date"])
        self._music_settings.language = str(values["language"])
        self._music_settings.secondary_language = str(values.get("secondary_language") or "")
        self._music_settings.creativity = int(values["creativity"])
        self._music_settings.unique_opening = bool(values["unique_opening"])
        self._music_settings.use_content_pools = bool(values["use_content_pools"])
        self._music_settings.strict_level = int(values["strict_level"])
        self._music_settings.history_window = int(values["history_window"])
        self._music_settings.song_count = int(values["song_count"])
        self._schedule_settings_save()
        self._schedule_local_workspace_save()
        self._refresh_presentation()

    def _on_automation_changed(self) -> None:
        values = self._automation_card.automation_values()
        self._music_settings.auto_gen_image = values["auto_gen_image"]
        self._music_settings.auto_gsuno = values["auto_gsuno"]
        self._music_settings.auto_video_after_suno = values["auto_video_after_suno"]
        self._music_settings.auto_merge_after_video = values["auto_merge_after_video"]
        self._music_settings.auto_reel_after_video = values["auto_reel_after_video"]
        self._music_settings.auto_upload_youtube = values["auto_upload_youtube"]
        self._schedule_settings_save()
        self._refresh_presentation()

    def _selected_profiles(self) -> list[ProfileResponse]:
        selected_ids = set(self._composer.primary_profile_ids) | set(self._composer.secondary_profile_ids)
        return [profile for profile in self._profiles if profile.id in selected_ids]

    def _normalize_youtube_connections(self, items: list[object]) -> list[YouTubeConnectionResponse]:
        normalized: list[YouTubeConnectionResponse] = []
        for item in items:
            if isinstance(item, YouTubeConnectionResponse):
                normalized.append(item)
            elif isinstance(item, dict):
                try:
                    normalized.append(YouTubeConnectionResponse.model_validate(item))
                except Exception:
                    continue
        return normalized

    def _bootstrap_youtube_connections_from_cache(self) -> None:
        if self._cache is None:
            return
        connections, _fetched_at = self._cache.snapshot_settings_extras()
        if connections:
            self._youtube_connections = self._normalize_youtube_connections(connections)

    def _build_readiness_report(self):
        return build_music_readiness_report(
            profiles=self._selected_profiles(),
            settings=self._settings_raw,
            youtube_connections=self._youtube_connections,
        )

    def _on_song_fields_changed(self) -> None:
        self._music_settings.polish_strength = self._song_card.polish_strength()
        self._composer.lyrics = self._song_card.lyrics()
        self._composer.title = self._song_card.title()
        self._composer.album = self._song_card.album()
        self._update_polish_button_state()
        self._schedule_settings_save()

    def _on_suno_auto_fixed(self, summary: str) -> None:
        self._flash_status(f"Suno auto-fix applied: {summary}", tone="success")

    def _update_polish_button_state(self) -> None:
        lyrics = self._song_card.lyrics().strip()
        has_primary = bool(self._primary_profiles())
        if not lyrics:
            self._song_card.set_polish_enabled(False, reason="Add lyrics before rewriting.")
        elif not has_primary:
            self._song_card.set_polish_enabled(
                False,
                reason="Select at least one primary channel (uses 1 draft from your allowance).",
            )
        else:
            self._song_card.set_polish_enabled(True)

    def _apply_description_language_mode(self, description_id: str) -> None:
        if len(self._language_options) < 2:
            return
        option = self._description_options_by_id.get(description_id)
        default_secondary = str(getattr(option, "default_secondary_language", "") or "").strip()
        vocal_mode = str(getattr(option, "vocal_mode", "") or "").strip().lower()
        if default_secondary or vocal_mode == "bilingual":
            self._settings_strip.set_bilingual_mode(
                True,
                default_secondary=default_secondary or self._music_settings.secondary_language or None,
            )

    def _on_description_changed(self, option_id: str) -> None:
        self._prompt_selection_touched = True
        self._selected_description_id = option_id
        self._composer.description = self._automation_card.selected_description_name()
        self._apply_description_language_mode(option_id)
        self._schedule_local_workspace_save()

    def _on_structure_changed(self, option_id: str) -> None:
        self._prompt_selection_touched = True
        self._selected_structure_id = option_id
        self._composer.structure = self._automation_card.selected_structure_name()
        # Free modes cannot shuffle templates — clear persisted preference so a later
        # settings apply / batch create cannot resurrect Shuffle under Suno/AI Structure.
        if self._automation_card.is_free_structure_selected():
            if self._music_settings.shuffle_structure:
                self._music_settings.shuffle_structure = False
                self._schedule_settings_save()
        else:
            self._music_settings.shuffle_structure = self._automation_card.shuffle_structure()
        self._schedule_local_workspace_save()

    def _on_mood_changed(self, option_id: str) -> None:
        self._prompt_selection_touched = True
        self._selected_mood_id = option_id
        self._schedule_local_workspace_save()

    def _on_shuffle_changed(self) -> None:
        self._music_settings.shuffle_structure = self._automation_card.shuffle_structure()
        self._schedule_settings_save()

    def _on_mood_shuffle_changed(self) -> None:
        self._music_settings.shuffle_mood = self._automation_card.shuffle_mood()
        self._schedule_settings_save()

    def _schedule_settings_save(self) -> None:
        if not self._settings_initialized:
            return
        snapshot = settings_snapshot(self._music_settings)
        if snapshot == self._last_persisted_settings:
            return
        # Multiple field edits within one debounce window (400ms) all land
        # here, but only one _persist_settings() call actually fires. Only
        # flash/log "Saving..." once per window instead of once per edit —
        # otherwise a single save shows up as 3 identical log lines.
        if not self._save_timer.isActive():
            self._set_save_status("saving")
        self._save_timer.start()

    def _persist_settings(self) -> None:
        if self._patch_worker is not None and self._patch_worker.isRunning():
            return
        patch = build_music_settings_patch(self._music_settings)
        snapshot = settings_snapshot(self._music_settings)
        worker = PatchSettingsWorker(self._api, patch, self)
        worker.succeeded.connect(lambda _payload: self._on_settings_saved(snapshot))
        worker.failed.connect(lambda _message: self._set_save_status("error"))
        worker.finished.connect(lambda: setattr(self, "_patch_worker", None))
        self._patch_worker = worker
        worker.start()

    def _on_settings_saved(self, snapshot: str) -> None:
        self._last_persisted_settings = snapshot
        self._settings_raw.update(build_music_settings_patch(self._music_settings))
        if self._cache is not None:
            self._cache.apply_settings_workspace(settings_raw=self._settings_raw)
        from shared.services.setup_readiness_service import refresh_setup_readiness

        refresh_setup_readiness(
            api=self._api,
            cache=self._cache,
            parent=self,
            force_network=False,
        )
        self._set_save_status("saved")
        self._saved_reset_timer.start()

    def _set_save_status(self, status: str) -> None:
        self._save_status = status
        if status == "idle":
            return
        tone = "success" if status == "saved" else "error" if status == "error" else "neutral"
        self._flash_status(save_status_message(status), tone=tone)

    def _primary_profiles(self) -> list[ProfileResponse]:
        return [profile for profile in self._profiles if profile.id in self._composer.primary_profile_ids]

    def _secondary_profiles(self) -> list[ProfileResponse]:
        return [profile for profile in self._profiles if profile.id in self._composer.secondary_profile_ids]

    def _refresh_presentation(self) -> None:
        day_span = get_inclusive_day_span(self._composer.from_date, self._composer.to_date)
        invalid = bool(self._composer.from_date and self._composer.to_date and day_span is None)
        if day_span is None:
            self._settings_strip.set_planned_days_text("Choose a valid inclusive date range.")
        else:
            suffix = "" if day_span == 1 else "s"
            self._settings_strip.set_planned_days_text(f"{day_span} planned day{suffix}")

        effects = effect_preview_from_creativity(self._music_settings.creativity)
        self._song_card.set_effect_values(effects["valence"], effects["danceability"], effects["instrumentalness"])
        lyric_cost = self._operation_costs.get("lyric")
        draft_label = format_button_credit_label("Draft", lyric_cost.credits_per_operation if lyric_cost else None)
        polish_label = format_draft_slot_button_label("Rewrite lyrics")
        self._song_card.set_button_labels(draft_label, polish_label)
        self._song_card.set_draft_enabled(not invalid and bool(self._composer.description.strip()))
        self._update_polish_button_state()

        image_source_mode = normalize_image_source_mode(self._settings_raw.get("imageSourceMode"))
        cost_args = (
            self._operation_costs.get("lyric"),
            self._operation_costs.get("music"),
            self._operation_costs.get("background_image"),
            self._primary_profiles(),
            self._secondary_profiles(),
            self._music_settings.song_count,
            self._music_settings.auto_gen_image,
            self._music_settings.auto_gsuno,
            day_span,
            image_source_mode,
            self._operation_costs.get("video"),
            self._operation_costs.get("video_merge"),
            self._music_settings.auto_video_after_suno,
            self._music_settings.auto_merge_after_video,
            self._music_settings.auto_reel_after_video,
        )
        breakdown = get_music_plan_cost_breakdown(*cost_args)
        total_cost = get_batch_generate_total_cost(*cost_args)
        preflight = self._generation_preflight
        if preflight and preflight.covered_by_subscription:
            if not self._music_settings.auto_gsuno and not self._music_settings.auto_gen_image:
                generate_label = "Generate drafts"
            else:
                generate_label = "Generate"
        elif total_cost is not None:
            generate_label = format_button_credit_label("Generate", total_cost)
        else:
            generate_label = "Generate"
        self._automation_card.set_generate_label(generate_label)
        overlapping = set(self._composer.primary_profile_ids) & set(self._composer.secondary_profile_ids)
        pair_mismatch = len(self._composer.primary_profile_ids) != len(self._composer.secondary_profile_ids)
        base_ready = (
            bool(self._composer.primary_profile_ids)
            and bool(self._composer.secondary_profile_ids)
            and not pair_mismatch
            and not overlapping
            and not invalid
        )
        readiness = self._build_readiness_report()
        setup_ready = readiness.generate_ready if base_ready else False
        can_generate = base_ready and setup_ready and (preflight.can_generate if preflight is not None else False)
        self._automation_card.set_auto_upload_enabled(bool(base_ready and readiness.upload_ready))
        self._automation_card.set_generate_enabled(can_generate)
        warnings = []
        if pair_mismatch:
            warnings.append("Primary and Secondary channel counts must match.")
        if overlapping:
            warnings.append("Choose different channels for each side.")
        if base_ready and not readiness.generate_ready:
            remaining = readiness.incomplete_generate_labels()
            if remaining:
                warnings.append(f"Complete setup: {remaining[0]}")
        if base_ready and preflight is not None and not preflight.can_generate and preflight.reason:
            warnings.append(preflight.reason)
        elif base_ready and preflight is None:
            warnings.append("Checking credits…")
        self._automation_card.set_warning_text(" ".join(warnings))
        if base_ready:
            self._schedule_preflight_check()

        costs = " · ".join(
            [
                format_operation_cost_label(self._operation_costs.get("lyric"), "Draft"),
                format_operation_cost_label(self._operation_costs.get("music"), "Suno"),
                format_operation_cost_label(self._operation_costs.get("background_image"), "Image"),
            ]
        )
        self._automation_card.set_cost_lines(costs)
        if breakdown is None:
            self._automation_card.set_plan_lines(
                "Select dates and matching channel pairs to estimate this run."
            )
        else:
            self._automation_card.set_plan_summary(
                batches=breakdown.planned_batch_count,
                songs=breakdown.planned_song_count,
                image_jobs=breakdown.image_total_jobs,
                draft_credits=breakdown.draft_total_cost,
                suno_credits=breakdown.suno_total_cost,
                image_credits=breakdown.image_total_cost,
                total_credits=total_cost,
                video_enabled=bool(
                    self._music_settings.auto_video_after_suno
                    or self._music_settings.auto_merge_after_video
                ),
                video_ops=breakdown.video_ops,
                merge_ops=breakdown.merge_ops,
                video_credits=breakdown.video_merge_total_cost,
            )
        self._automation_card.set_helper_text("")
        self._render_history()

    def _render_history(self) -> None:
        values = self._history_card.filter_values()
        raw_status = values.get("status") or ()
        if isinstance(raw_status, str):
            status = () if raw_status in {"", "all"} else (raw_status,)
        else:
            status = tuple(
                token
                for item in raw_status
                if (token := str(item or "").strip().lower()) and token != "all"
            )
        filters = HistoryFiltersState(
            from_date=str(values.get("from_date") or ""),
            to_date=str(values.get("to_date") or ""),
            last_batch_only=bool(values.get("last_batch_only")),
            status=status,
            batch_id=str(values.get("batch_id") or ""),
        )
        self._history_card.set_batch_filter_options(list(self._history.batches or []))
        rows: list[HistoryRow] = []
        row_number = 1
        matched_batches = 0
        matched_songs = 0
        for batch_index, batch in enumerate(self._history.batches):
            if not matches_history_filters(batch, filters, batch_index):
                continue
            song_rows = [
                song
                for song in batch.songs
                if song_matches_history_status_filter(
                    status=song.status,
                    suno_status=song.suno_status,
                    status_filter=filters.status,
                )
            ]
            if filters.status and not song_rows:
                continue
            matched_batches += 1
            rows.append(HistoryRow(batch=batch, is_batch_separator=True))
            for song in song_rows:
                rows.append(HistoryRow(row_number=row_number, batch=batch, song=song))
                row_number += 1
                matched_songs += 1
        loaded_batches = len(self._history.batches or [])
        loaded_songs = sum(len(batch.songs or []) for batch in (self._history.batches or []))
        if matched_batches == loaded_batches and matched_songs == loaded_songs:
            summary = self._history.summary or f"{loaded_batches} batches · {loaded_songs} songs"
        else:
            summary = (
                f"{matched_batches} batch{'es' if matched_batches != 1 else ''} · "
                f"{matched_songs} song{'s' if matched_songs != 1 else ''} shown "
                f"(of {loaded_batches} loaded)"
            )
        self._history_card.set_summary(summary, self._history.updated_at)
        self._history_card.set_rows(rows, self._selected_history_song_id)

    def _open_history_folder(self, path: str, _label: str) -> None:
        if path:
            open_path(path)

    def _refresh_history_status(self) -> None:
        log_info("Refreshing music history from server…", category="music")
        self._flash_status("Refreshing history…")
        self.refresh_history()

    def _retry_history_draft(self, row: HistoryRow) -> None:
        if row.song is None:
            self._flash_status("Select a song before retrying the draft.", tone="warning")
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A retry is already in progress.", tone="warning")
            return
        self._pending_history_retry_kind = "draft"
        worker = RetrySongDraftWorker(self._api, row.batch.batch_id, row.song.song_id, self)
        worker.succeeded.connect(self._on_history_retry_succeeded)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        log_info(f"Retrying draft for song #{row.song.batch_index + 1}…", category="music")
        self._flash_status(f"Retrying draft for song #{row.song.batch_index + 1}…")
        worker.start()

    def _rewrite_history_album(self, row: HistoryRow, role: str) -> None:
        batch_id = str(getattr(row.batch, "batch_id", "") or "").strip()
        if not batch_id:
            self._flash_status("Select a batch before rewriting the album.", tone="warning")
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A retry is already in progress.", tone="warning")
            return
        role_key = "alt" if str(role or "").strip().lower() == "alt" else "ok"
        label = "album 2" if role_key == "alt" else "album 1"
        worker = RewriteBatchAlbumWorker(self._api, batch_id, role=role_key, parent=self)
        worker.succeeded.connect(self._on_history_album_rewrite_succeeded)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        log_info(f"Rewriting {label} for batch {batch_id[:8]}…", category="music")
        self._flash_status(f"Rewriting {label}…")
        worker.start()

    def _rewrite_history_title(self, row: HistoryRow) -> None:
        if row.song is None:
            self._flash_status("Select a song before rewriting the title.", tone="warning")
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A retry is already in progress.", tone="warning")
            return
        self._pending_title_rewrite_row = row
        worker = RewriteSongTitleWorker(
            self._api,
            row.batch.batch_id,
            row.song.song_id,
            self,
        )
        worker.succeeded.connect(self._on_history_title_rewrite_succeeded)
        worker.failed.connect(self._on_history_title_rewrite_failed)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        log_info(f"Rewriting title for song #{row.song.batch_index + 1}…", category="music")
        self._flash_status(f"Rewriting title for song #{row.song.batch_index + 1}…")
        worker.start()

    def _on_history_title_rewrite_failed(self, message: str) -> None:
        self._pending_title_rewrite_row = None
        self._show_workspace_error(message)

    def _on_history_album_rewrite_succeeded(self, payload: object) -> None:
        from shared.models.platform import AlbumRewriteResponse

        if isinstance(payload, AlbumRewriteResponse):
            label = "Album 2" if payload.role == "alt" else "Album 1"
            album = str(payload.album or "").strip() or "—"
            self._flash_status(f"{label} rewritten: {album}", tone="success")
        else:
            self._flash_status("Album rewritten.", tone="success")
        self._error_banner.hide()
        self.refresh_history()
        self.refresh_data()

    def _on_history_title_rewrite_succeeded(self, payload: object) -> None:
        from shared.models.platform import TitleRewriteResponse

        pending_row = getattr(self, "_pending_title_rewrite_row", None)
        self._pending_title_rewrite_row = None
        new_title = ""
        if isinstance(payload, TitleRewriteResponse):
            new_title = str(payload.title or "").strip()
            title = new_title or "—"
            self._flash_status(f"Title rewritten: {title}", tone="success")
            if self._selected_history_song_id == payload.song_id:
                self._composer.title = title
                self._song_card.set_fields(
                    title=self._composer.title,
                    album=self._composer.album,
                    lyrics=self._composer.lyrics,
                    polish_strength=self._music_settings.polish_strength,
                )
        else:
            self._flash_status("Title rewritten.", tone="success")
        self._error_banner.hide()
        self.refresh_history()
        self.refresh_data()

        # After fixing a bad title, queue Suno when the song is still eligible.
        if (
            pending_row is not None
            and pending_row.song is not None
            and new_title
            and self._song_eligible_for_suno_retry(pending_row.song)
        ):
            track = int(getattr(pending_row.song, "batch_index", 0) or 0) + 1
            self._flash_status(
                f"Title rewritten — submitting Suno for song #{track}…",
                tone="success",
            )
            QTimer.singleShot(
                0,
                lambda: self._retry_history_suno(pending_row, title=new_title),
            )

    def _find_history_row(self, song_id: str | None) -> HistoryRow | None:
        if not song_id:
            return None
        for batch in self._history.batches:
            for song in batch.songs:
                if song.song_id == song_id:
                    return HistoryRow(batch=batch, song=song)
        return None

    @staticmethod
    def _song_eligible_for_suno_retry(song: object) -> bool:
        from shared.lib.music_status import is_song_suno_retry_eligible

        return is_song_suno_retry_eligible(
            str(getattr(song, "status", "") or ""),
            str(getattr(song, "suno_status", "") or "") or None,
        )

    def _retry_history_suno(
        self,
        row: HistoryRow,
        *,
        title: str | None = None,
        album: str | None = None,
        lyrics: str | None = None,
    ) -> None:
        if row.song is None:
            self._flash_status("Select a song before retrying Suno.", tone="warning")
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A retry is already in progress.", tone="warning")
            return
        self._pending_history_retry_kind = "suno"
        worker = RetrySongSunoWorker(
            self._api,
            row.batch.batch_id,
            row.song.song_id,
            title=title,
            album=album,
            lyrics=lyrics,
            parent=self,
        )
        worker.succeeded.connect(self._on_history_retry_succeeded)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        song_status = str(row.song.status or "").strip().lower()
        verb = "Submitting" if song_status == "draft_ready" else "Retrying"
        log_info(f"{verb} Suno for song #{row.song.batch_index + 1}…", category="music")
        self._flash_status(f"{verb} Suno for song #{row.song.batch_index + 1}…")
        worker.start()

    def _enqueue_history_images(self, row: HistoryRow) -> None:
        if self._retry_worker is not None and self._retry_worker.isRunning():
            return
        batch_id = str(row.batch.batch_id or "").strip()
        if not batch_id:
            return
        from shared.workers.data_workers import EnqueueImageJobsWorker

        worker = EnqueueImageJobsWorker(self._api, [batch_id], parent=self)
        worker.succeeded.connect(self._on_history_images_enqueued)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        log_info(f"Enqueueing images for batch {batch_id[:8]}…", category="image")
        self._flash_status("Enqueueing album images…")
        worker.start()

    def _on_history_images_enqueued(self, payload: object) -> None:
        from shared.models.platform import ImageJobsEnqueueResponse

        created = 0
        if isinstance(payload, ImageJobsEnqueueResponse):
            created = int(payload.created or 0)
        if created > 0:
            self._flash_status(
                f"Queued {created} image job(s).",
                tone="success",
            )
        else:
            self._flash_status("No new image jobs were created (they may already exist).")
        self._error_banner.hide()
        self.refresh_data()

    def _continue_history_video(self, row: HistoryRow) -> None:
        self._flash_status(
            "Images ready — open the Video page to continue Primary/Secondary export.",
            tone="success",
        )

    def _retry_history_batch(
        self,
        batch_id: str,
        draft_ids: list[str],
        suno_ids: list[str],
    ) -> None:
        if not batch_id or (not draft_ids and not suno_ids):
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            return
        total = len(draft_ids) + len(suno_ids)
        worker = BatchRetryFailuresWorker(
            self._api,
            batch_id,
            draft_ids,
            suno_ids,
            parent=self,
        )
        worker.succeeded.connect(
            lambda queued, bid=batch_id: self._on_history_batch_retry_succeeded(bid, queued)
        )
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        log_info(f"Retrying batch ({total} failed song(s))…", category="music")
        self._flash_status(f"Retrying batch ({total} song(s))…")
        worker.start()

    def _rewrite_history_batch(self, targets: object) -> None:
        from shared.services.pipeline_recovery_coordinator import mark_pipeline_song_busy

        if not isinstance(targets, list) or not targets:
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A recovery/retry is already running.", tone="warning")
            return
        if self._polish_worker is not None and self._polish_worker.isRunning():
            self._flash_status("A lyric rewrite is already running.", tone="warning")
            return
        for target in targets:
            song_id = str(getattr(target, "song_id", "") or "").strip()
            if song_id:
                mark_pipeline_song_busy(song_id, seconds=300)
        worker = PipelineRecoveryWorker(self._api, targets, parent=self)
        worker.progressed.connect(lambda msg: self._flash_status(msg, tone="neutral"))
        worker.succeeded.connect(self._on_pipeline_recovery_succeeded)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        count = len(targets)
        log_info(f"Batch rewrite→Suno started for {count} song(s)…", category="music")
        self._flash_status(f"Rewriting lyrics for {count} song(s)…")
        worker.start()

    def _on_history_batch_retry_succeeded(self, batch_id: str, queued: int) -> None:
        if queued > 0:
            self._latest_batch_id = batch_id
            self._latest_batch_summary = "Retry in progress"
            self._last_batch_status_key = None
            self._batch_timer.start()
            self._flash_status(
                f"Queued retry for {queued} song(s).",
                tone="success",
            )
        self._error_banner.hide()
        self.refresh_data()

    def _delete_failed_batch(self, batch_id: str) -> None:
        if not batch_id:
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A recovery/retry is already running.", tone="warning")
            return
        confirm = QMessageBox.question(
            self,
            "Delete failed batch",
            (
                "Delete this batch from History?\n\n"
                "Only batches with no successful or in-progress Suno audio can be "
                "deleted. Draft leftovers may be restored; wallet credits "
                "are not re-gifted.\n\n"
                "This cannot be undone."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        worker = DeleteFailedBatchWorker(self._api, batch_id, parent=self)
        worker.succeeded.connect(self._on_failed_batch_deleted)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        self._flash_status("Deleting failed batch…")
        worker.start()

    def _on_failed_batch_deleted(self, payload: object) -> None:
        from shared.models.platform import BatchDeleteResponse

        songs_deleted = 0
        draft_released = 0
        deleted_id = ""
        if isinstance(payload, BatchDeleteResponse):
            songs_deleted = int(payload.songs_deleted or 0)
            draft_released = int(payload.draft_quota_released or 0)
            deleted_id = str(payload.batch_id or "")
        if self._latest_batch_id and deleted_id and self._latest_batch_id == deleted_id:
            self._latest_batch_id = None
            self._latest_batch_summary = None
            self._last_batch_status_key = None
            self._batch_timer.stop()
        parts = [f"Deleted batch ({songs_deleted} song(s))."]
        if draft_released > 0:
            parts.append(f"Restored {draft_released} draft unit(s).")
        self._flash_status(" ".join(parts), tone="success")
        self._error_banner.hide()
        self.refresh_data()

    def _recover_failed_pipeline(self) -> None:
        from features.music.lib.pipeline_recovery import collect_recovery_targets

        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status("A recovery/retry is already running.", tone="warning")
            return
        targets = collect_recovery_targets(list(self._history.batches or []))
        if not targets:
            self._flash_status("No failed songs to recover in loaded history.", tone="neutral")
            return
        worker = PipelineRecoveryWorker(self._api, targets, parent=self)
        worker.progressed.connect(lambda msg: self._flash_status(msg, tone="neutral"))
        worker.succeeded.connect(self._on_pipeline_recovery_succeeded)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_retry_worker", None))
        self._retry_worker = worker
        log_info(f"Pipeline recovery started for {len(targets)} song(s)…", category="music")
        self._flash_status(f"Recovering {len(targets)} failed song(s)…")
        worker.start()

    def _on_pipeline_recovery_succeeded(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        recovered = int(data.get("recovered") or 0)
        rewrite = int(data.get("rewrite") or 0)
        draft = int(data.get("draft") or 0)
        suno = int(data.get("suno") or 0)
        skipped = int(data.get("skipped") or 0)
        parts = [f"{recovered} recovered"]
        if draft:
            parts.append(f"{draft} draft")
        if rewrite:
            parts.append(f"{rewrite} rewrite→Suno")
        if suno:
            parts.append(f"{suno} Suno retry")
        if skipped:
            parts.append(f"{skipped} skipped")
        tone = "success" if recovered else "warning"
        self._flash_status(" · ".join(parts), tone=tone)
        self._error_banner.hide()
        self.refresh_history()
        self.refresh_data()

    def _on_history_retry_succeeded(self, payload: object) -> None:
        from shared.models.platform import SongRetryResponse

        if isinstance(payload, SongRetryResponse):
            from features.music.lib.history_retry import history_track_number

            self._latest_batch_id = payload.batch_id
            self._latest_batch_summary = "Retry in progress"
            self._last_batch_status_key = None
            self._batch_timer.start()
            track_no = history_track_number(self._history, payload.song_id) if payload.song_id else None
            track_label = f" #{track_no}" if track_no else ""
            if self._pending_history_retry_kind == "suno":
                self._flash_status(
                    f"Suno retry queued for song{track_label}. Watching batch progress…",
                    tone="success",
                )
            else:
                self._flash_status(
                    f"Draft retry queued for song{track_label}. Watching batch progress…",
                    tone="success",
                )
        self._pending_history_retry_kind = ""
        self._error_banner.hide()
        self.refresh_data()

    def _select_history_row(self, row: HistoryRow) -> None:
        if row.song is None:
            return
        self._prompt_selection_touched = True
        self._selected_history_song_id = row.song.song_id
        self._draft_pool_seeds = None
        self._song_card.set_seed_notice("")
        if row.song.description_id:
            self._selected_description_id = row.song.description_id
        if row.song.structure_id:
            self._selected_structure_id = row.song.structure_id
        if row.song.mood_id:
            self._selected_mood_id = row.song.mood_id
        self._automation_card.set_selected_options(
            self._selected_description_id,
            self._selected_structure_id,
            self._selected_mood_id,
        )
        self._composer.title = row.song.title or self._composer.title
        self._composer.album = row.song.album or self._composer.album
        self._composer.lyrics = row.song.lyrics or self._composer.lyrics
        self._song_card.set_fields(
            title=self._composer.title,
            album=self._composer.album,
            lyrics=self._composer.lyrics,
            polish_strength=self._music_settings.polish_strength,
        )
        failure_message = str(row.song.suno_error_message or "").strip()
        learned_terms: list[str] = []
        stored_sanitize = row.song.suno_last_sanitize if isinstance(row.song.suno_last_sanitize, dict) else None
        if stored_sanitize:
            from shared.lib.suno_lyrics_sanitize import SunoSanitizeReplacement, format_suno_replacements

            replacements_raw = stored_sanitize.get("replacements") or []
            stored_replacements: list[SunoSanitizeReplacement] = []
            for item in replacements_raw:
                if not isinstance(item, dict):
                    continue
                stored_replacements.append(
                    SunoSanitizeReplacement(
                        field=str(item.get("field") or "text"),
                        source=str(item.get("source") or ""),
                        target=str(item.get("target") or ""),
                    )
                )
            summary = format_suno_replacements(stored_replacements)
            if summary:
                self._flash_status(
                    f"Suno sanitize applied on submit: {summary}",
                    tone="success",
                )
            for term in stored_sanitize.get("blocked_terms") or []:
                normalized = str(term).strip().lower()
                if normalized:
                    learned_terms.append(normalized)
        if failure_message:
            from shared.lib.suno_lyrics_sanitize import (
                extract_blocked_terms_from_suno_error,
                format_suno_replacements,
                infer_suno_replacements_from_learned_terms,
            )

            learned_terms.extend(extract_blocked_terms_from_suno_error(failure_message))
        if learned_terms:
            self._remember_learned_suno_terms(learned_terms)
        elif not stored_sanitize:
            self._song_card.set_learned_suno_terms(self._merged_learned_suno_terms())
        if failure_message and not stored_sanitize:
            from shared.lib.suno_lyrics_sanitize import (
                format_suno_replacements,
                infer_suno_replacements_from_learned_terms,
            )

            inferred = infer_suno_replacements_from_learned_terms(
                title=self._composer.title,
                lyrics=self._composer.lyrics,
                learned_terms=learned_terms,
            )
            summary = format_suno_replacements(inferred)
            if summary:
                self._flash_status(
                    f"Suno-safe wording on draft: {summary}",
                    tone="success",
                )
        elif not learned_terms and not stored_sanitize:
            self._song_card.set_learned_suno_terms(self._merged_learned_suno_terms())
        song_status = str(row.song.status or "").strip().lower()
        suno_status = str(row.song.suno_status or "").strip().lower()
        if failure_message and (song_status == "suno_failed" or suno_status == "suno_failed"):
            self._flash_status(f"Suno failed: {failure_message}", tone="warning", duration_ms=8000)
        self._refresh_presentation()

    def _generate_draft(self) -> None:
        if self._draft_worker is not None and self._draft_worker.isRunning():
            return
        self._composer.description = self._automation_card.selected_description_name()
        self._composer.structure = self._automation_card.selected_structure_name()
        if not self._composer.description.strip():
            self._show_workspace_error("Song description is required before generating a draft.")
            return
        payload = {
            "history_batches": self._history.batches,
            "history_window": self._music_settings.history_window,
            "unique_opening": self._music_settings.unique_opening,
            "use_content_pools": self._music_settings.use_content_pools,
            "language": self._music_settings.language,
            "secondary_language": self._music_settings.secondary_language or None,
            "creativity": self._music_settings.creativity,
            "description": self._composer.description,
            "structure": self._composer.structure,
            "description_id": self._selected_description_id or None,
            "structure_id": self._automation_card.selected_structure_id() or None,
            "structure_mode": self._automation_card.selected_structure_mode(),
            "mood_id": self._automation_card.selected_mood_id() or None,
            "channel_profile_id": self._primary_profiles()[0].id if self._primary_profiles() else None,
        }
        worker = DraftGenerationWorker(self._api, payload, self)
        worker.succeeded.connect(self._on_draft_generated)
        worker.failed.connect(self._show_workspace_error)
        worker.finished.connect(lambda: setattr(self, "_draft_worker", None))
        self._draft_worker = worker
        log_info("Generating song draft…", category="music")
        self._flash_status("Generating song draft…")
        worker.start()

    def _on_draft_generated(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        draft = payload.get("draft")
        pool_seeds = payload.get("pool_seeds")
        if draft is None:
            return
        self._error_banner.hide()
        self._composer.title = draft.title
        self._composer.album = draft.album
        self._composer.lyrics = draft.lyrics
        self._draft_pool_seeds = pool_seeds
        notice = ""
        if pool_seeds is not None:
            opening = pool_seeds.opening_seed.split("\n")[0] if pool_seeds.opening_seed else ""
            notice = (
                f'Draft seeded from pools and polished into a new result: title "{pool_seeds.title_seed}", '
                f'album "{pool_seeds.album_seed}"'
                + (f', opening "{opening}"' if opening else "")
                + ". The generated draft keeps these as inspiration, not as raw copy."
            )
        self._song_card.set_seed_notice(notice)
        self._song_card.set_fields(
            title=self._composer.title,
            album=self._composer.album,
            lyrics=self._composer.lyrics,
            polish_strength=self._music_settings.polish_strength,
        )
        self._refresh_presentation()
        log_info(f'Draft ready: "{self._composer.title}"', category="music")
        self._flash_status(f'Draft ready: "{self._composer.title}"', tone="success")

    def _resolve_polish_suno_row(self) -> HistoryRow | None:
        """Pick the history song that should receive a post-polish Suno retry."""
        row = self._find_history_row(self._selected_history_song_id)
        if row is not None and row.song is not None and self._song_eligible_for_suno_retry(row.song):
            return row

        if not self._history.batches:
            return None

        newest = self._history.batches[0]
        eligible = [
            HistoryRow(batch=newest, song=song)
            for song in newest.songs
            if self._song_eligible_for_suno_retry(song)
        ]
        if not eligible:
            return None

        title = (self._composer.title or self._song_card.title() or "").strip().casefold()
        if title:
            titled = [
                candidate
                for candidate in eligible
                if (candidate.song.title or "").strip().casefold() == title
            ]
            if len(titled) == 1:
                return titled[0]

        if len(eligible) == 1:
            return eligible[0]
        return None

    def _polish_lyrics(self) -> None:
        if self._polish_worker is not None and self._polish_worker.isRunning():
            return
        lyrics = self._song_card.lyrics().strip()
        if not lyrics:
            self._show_workspace_error("There are no lyrics to rewrite.")
            return
        primary = self._primary_profiles()
        if not primary:
            self._show_workspace_error("Select at least one primary channel before rewriting lyrics.")
            return
        payload = {
            "lyrics": lyrics,
            "strength": self._song_card.polish_strength(),
            "channel_profile_id": primary[0].id,
            "mood_id": self._automation_card.selected_mood_id() or self._selected_mood_id or None,
            "structure_id": self._automation_card.selected_structure_id() or None,
        }
        row = self._resolve_polish_suno_row()
        if row is not None and row.song is not None:
            payload["batch_id"] = row.batch.batch_id
            payload["song_id"] = row.song.song_id
            payload["title"] = (self._composer.title or row.song.title or "").strip() or None
            payload["album"] = (self._composer.album or row.song.album or "").strip() or None
            if row.song.mood_id:
                payload["mood_id"] = row.song.mood_id
            if row.song.structure_id:
                payload["structure_id"] = row.song.structure_id
            self._selected_history_song_id = row.song.song_id
            from shared.services.pipeline_recovery_coordinator import mark_pipeline_song_busy

            mark_pipeline_song_busy(row.song.song_id, seconds=180)
            log_info(
                f"Rewriting lyrics with Suno auto-retry for song #{row.song.batch_index + 1}…",
                category="music",
            )
        else:
            log_info(
                "Rewriting lyrics only — no eligible failed song linked for Suno auto-retry.",
                category="music",
            )
        worker = PolishLyricsWorker(self._api, payload, parent=self)
        worker.succeeded.connect(self._on_polish_complete)
        worker.failed.connect(self._show_workspace_error)
        polish_song_id = str(payload.get("song_id") or "")

        def _finish_polish_worker() -> None:
            self._polish_worker = None
            if polish_song_id:
                from shared.services.pipeline_recovery_coordinator import mark_pipeline_song_busy

                # Keep helper off this song while Suno callback settles.
                mark_pipeline_song_busy(polish_song_id, seconds=120)

        worker.finished.connect(_finish_polish_worker)
        self._polish_worker = worker
        log_info("Rewriting lyrics…", category="music")
        self._flash_status("Rewriting lyrics…")
        worker.start()

    def _on_polish_complete(self, payload: object) -> None:
        from shared.models.platform import LyricsPolishResponse

        if not isinstance(payload, LyricsPolishResponse):
            return
        self._error_banner.hide()
        self._composer.lyrics = payload.lyrics
        self._song_card.set_fields(
            title=self._composer.title,
            album=self._composer.album,
            lyrics=self._composer.lyrics,
            polish_strength=self._music_settings.polish_strength,
        )
        row = self._resolve_polish_suno_row()
        if payload.suno_queued and row is not None and row.song is not None:
            log_info(
                f"Rewrite complete — Suno queued for song #{row.song.batch_index + 1}.",
                category="music",
            )
            self._flash_status(
                f"Lyrics rewritten. Suno queued for song #{row.song.batch_index + 1}.",
                tone="success",
            )
            self.refresh_data()
            return

        self._flash_status("Lyrics rewritten.", tone="success")

        if row is None or row.song is None:
            log_info(
                "Rewrite complete without Suno — click a failed song in History, then rewrite again.",
                category="music",
            )
            self._flash_status(
                "Lyrics rewritten. Click a failed song in History, then rewrite again to auto-retry Suno.",
                tone="warning",
                duration_ms=10000,
            )
            return
        if not self._song_eligible_for_suno_retry(row.song):
            song_status = str(row.song.status or "").strip().lower()
            suno_status = str(row.song.suno_status or "").strip().lower()
            log_info(
                f"Rewrite complete without Suno — song status={song_status or 'unknown'} "
                f"suno_status={suno_status or 'unknown'}.",
                category="music",
            )
            self._flash_status(
                "Lyrics rewritten. This song is not eligible for Suno retry yet.",
                tone="warning",
                duration_ms=8000,
            )
            return
        if self._retry_worker is not None and self._retry_worker.isRunning():
            self._flash_status(
                "Lyrics rewritten. Suno retry already in progress.",
                tone="warning",
            )
            return
        log_info(
            f"Rewrite complete — submitting Suno for song #{row.song.batch_index + 1}…",
            category="music",
        )
        self._flash_status(
            f"Lyrics rewritten. Submitting Suno for song #{row.song.batch_index + 1}…",
        )
        self._retry_history_suno(
            row,
            title=self._composer.title,
            album=self._composer.album,
            lyrics=self._composer.lyrics,
        )

    def _schedule_preflight_check(self) -> None:
        self._preflight_timer.start()

    def _run_preflight_check(self) -> None:
        if self._preflight_worker is not None and self._preflight_worker.isRunning():
            return
        primary_ids = list(self._composer.primary_profile_ids)
        secondary_ids = list(self._composer.secondary_profile_ids)
        if not primary_ids or not secondary_ids or len(primary_ids) != len(secondary_ids):
            self._generation_preflight = None
            return
        if not self._composer.from_date or not self._composer.to_date:
            self._generation_preflight = None
            return
        if get_inclusive_day_span(self._composer.from_date, self._composer.to_date) is None:
            # Avoid 422 from API when saved/edited dates are inverted.
            self._generation_preflight = MusicPlanPreflightResponse(
                can_generate=False,
                reason="Choose a valid inclusive date range (To must be on or after From).",
            )
            self._refresh_presentation()
            return
        payload = MusicPlanPreflightRequest(
            ok_profile_ids=primary_ids,
            alt_profile_ids=secondary_ids,
            from_date=self._composer.from_date,
            to_date=self._composer.to_date,
            song_count=self._music_settings.song_count,
            auto_gen_image=self._music_settings.auto_gen_image,
            auto_gsuno=self._music_settings.auto_gsuno,
            auto_video_after_suno=self._music_settings.auto_video_after_suno,
            auto_merge_after_video=self._music_settings.auto_merge_after_video,
            auto_reel_after_video=self._music_settings.auto_reel_after_video,
        )
        worker = MusicPlanPreflightWorker(self._api, payload, parent=self)
        worker.succeeded.connect(self._on_preflight_succeeded)
        worker.failed.connect(self._on_preflight_failed)
        worker.finished.connect(self._finish_preflight_worker)
        self._preflight_worker = worker
        worker.start()

    def _on_preflight_succeeded(self, payload: object) -> None:
        if isinstance(payload, MusicPlanPreflightResponse):
            self._generation_preflight = payload
            self._refresh_presentation()

    def _on_preflight_failed(self, message: str) -> None:
        self._generation_preflight = MusicPlanPreflightResponse(
            can_generate=False,
            reason=message or "Unable to validate generation plan.",
        )
        self._refresh_presentation()

    def _finish_preflight_worker(self) -> None:
        self._preflight_worker = None

    def _create_batches(self) -> None:
        if self._generation_preflight is not None and not self._generation_preflight.can_generate:
            reason = self._generation_preflight.reason or "Generation is not available for the current plan."
            self._show_workspace_error(reason)
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return
        primary = self._primary_profiles()
        secondary = self._secondary_profiles()
        if not primary or not secondary or len(primary) != len(secondary):
            self._show_workspace_error("Select matching Primary and Secondary channels before generating.")
            return
        if set(self._composer.primary_profile_ids) & set(self._composer.secondary_profile_ids):
            self._show_workspace_error("Primary and Secondary channel lists must not contain the same profile.")
            return
        run_dates = get_inclusive_date_list(self._composer.from_date, self._composer.to_date)
        if not run_dates:
            self._show_workspace_error("Choose a valid batch date range before creating a batch.")
            return
        # The picker is the single source of truth: a missing description or (for
        # template mode) structure would otherwise reach Suno as the generic
        # "Contemporary pop" style or fail later at draft time.
        selected_description_id = self._automation_card.selected_description_id() or None
        if selected_description_id is None:
            self._show_workspace_error("Choose a song description before creating a batch.")
            return
        structure_mode = self._automation_card.selected_structure_mode()
        selected_structure_id = self._automation_card.selected_structure_id() or None
        if structure_mode == "template" and selected_structure_id is None:
            self._show_workspace_error("Choose a song structure before creating a batch.")
            return
        selected_mood_id = self._automation_card.selected_mood_id() or None
        image_source_mode = normalize_image_source_mode(self._settings_raw.get("imageSourceMode"))
        requests: list[BatchCreateRequest] = []
        for run_date in run_dates:
            for index, ok_profile in enumerate(primary):
                alt_profile = secondary[index]
                requests.append(
                    BatchCreateRequest(
                        ok_profile_id=ok_profile.id,
                        alt_profile_id=alt_profile.id,
                        description_id=selected_description_id,
                        structure_id=selected_structure_id,
                        mood_id=selected_mood_id,
                        structure_mode=structure_mode,
                        shuffle_structure=self._automation_card.shuffle_structure(),
                        shuffle_mood=self._automation_card.shuffle_mood(),
                        auto_gen_image=self._music_settings.auto_gen_image,
                        auto_gsuno=self._music_settings.auto_gsuno,
                        auto_video_after_suno=self._music_settings.auto_video_after_suno,
                        auto_merge_after_video=self._music_settings.auto_merge_after_video,
                        auto_reel_after_video=self._music_settings.auto_reel_after_video,
                        song_count=self._music_settings.song_count,
                        language=self._music_settings.language,
                        secondary_language=self._music_settings.secondary_language or None,
                        creativity_level=self._music_settings.creativity,
                        pairing_mode="match_key",
                        from_date=run_date,
                        to_date=run_date,
                    )
                )
        worker = CreateBatchesWorker(
            self._api,
            requests,
            parent=self,
        )
        worker.succeeded.connect(self._on_batches_created)
        worker.failed.connect(self._on_batch_create_failed)
        worker.finished.connect(self._finish_batch_worker)
        self._batch_worker = worker
        self._automation_card.set_generating(True)
        log_info(f"Creating {len(requests)} music batch run(s)…", category="music")
        self._flash_status(f"Creating {len(requests)} batch run{'s' if len(requests) != 1 else ''}…")
        worker.start()

    def _on_batch_create_failed(self, message: str) -> None:
        self._show_workspace_error(message)

    def _finish_batch_worker(self) -> None:
        self._batch_worker = None
        self._automation_card.set_generating(False)

    def _on_batches_created(self, payload: object) -> None:
        result: CreateBatchesResult | None = None
        created: list[object] = []
        if isinstance(payload, CreateBatchesResult):
            result = payload
            created = list(payload.created)
        elif isinstance(payload, list) and payload:
            created = list(payload)
            result = CreateBatchesResult(planned=len(created), created=created)
        else:
            return
        if created:
            self._error_banner.hide()
            last = created[-1]
            self._latest_batch_id = getattr(last, "batch_id", "") or self._latest_batch_id
        summary = format_create_batches_summary(result)
        if result.failed:
            failed_slots = format_failed_create_slots(result.failed)
            summary = f"{summary} Click Generate again to fill: {failed_slots}"
        self._latest_batch_summary = summary
        self._last_batch_status_key = None
        log_info(summary, category="music")
        if result.failed and not created:
            self._show_workspace_error(summary)
        elif result.failed:
            self._flash_status(summary, tone="warning", duration_ms=10000)
        else:
            self._error_banner.hide()
            self._flash_status(summary, tone="success", duration_ms=6000)
        if created:
            self._batch_timer.start()
        self.refresh_history()
        self.refresh_data()

    def _poll_batch_status(self) -> None:
        if not self._latest_batch_id:
            self._batch_timer.stop()
            return
        if self._status_worker is not None and self._status_worker.isRunning():
            return
        worker = BatchStatusWorker(self._api, self._latest_batch_id, self)
        worker.succeeded.connect(self._on_batch_status)
        worker.finished.connect(lambda: setattr(self, "_status_worker", None))
        self._status_worker = worker
        worker.start()

    def _format_batch_status_message(self, payload: object) -> str:
        from shared.models.platform import BatchStatusResponse

        if not isinstance(payload, BatchStatusResponse):
            return ""
        parts = [payload.status.replace("_", " ")]
        if payload.total_songs:
            parts.append(f"{payload.drafts_completed}/{payload.total_songs} drafts")
        if payload.suno_submitted or payload.suno_completed or payload.suno_failed:
            parts.append(f"{payload.suno_completed}/{payload.total_songs} Suno")
        return " · ".join(parts)

    def _on_batch_status(self, payload: object) -> None:
        from shared.models.platform import BatchStatusResponse

        if not isinstance(payload, BatchStatusResponse):
            return
        status_message = self._format_batch_status_message(payload)
        if payload.status == "failed" and payload.drafts_completed > 0:
            tone = "warning"
        else:
            tone = (
                "success"
                if payload.status == "completed"
                else "error"
                if payload.status == "failed"
                else "warning"
                if payload.status == "partial"
                else "neutral"
            )

        status_key = (
            payload.status,
            payload.drafts_completed,
            payload.drafts_failed,
            payload.suno_completed,
            payload.suno_failed,
        )
        if status_key != self._last_batch_status_key:
            self._last_batch_status_key = status_key
            self._flash_status(status_message, tone=tone, duration_ms=6000)

        self._ensure_batch_run_directories(payload)
        self.refresh_history()

        if payload.status in {"completed", "partial", "failed"}:
            self._batch_timer.stop()
            self._latest_batch_id = None
            self.refresh_data()

    def _ensure_batch_run_directories(self, payload: object) -> None:
        from shared.lib.device_workspace_paths import local_run_dir_for_disk
        from shared.models.platform import BatchStatusResponse

        if not isinstance(payload, BatchStatusResponse):
            return
        for directory in (payload.ok_run_dir, payload.alt_run_dir):
            path = local_run_dir_for_disk(str(directory or "").strip())
            if not path or path in self._ensured_run_dirs:
                continue
            ensure_directory(path)
            self._ensured_run_dirs.add(path)

    def _show_workspace_error(self, message: str) -> None:
        # Never fail silently: an empty/blank worker message still surfaces a
        # visible, logged error so the user knows the action did not run.
        text = str(message or "").strip() or "Music generation failed. Please try again."
        self._pending_history_retry_kind = ""
        self._flash_status(text, tone="error", duration_ms=7000)
        log_error(text, category="music")

    def _copy_text(self, value: str) -> None:
        if not value.strip():
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(value)

    def deactivate_page(self) -> None:
        self._batch_timer.stop()
