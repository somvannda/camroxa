"""Settings workspace page — profiles, YouTube, publication, preferences, pools, Suno."""

from __future__ import annotations

# Sample packs are uploaded to VPS via admin portal; desktop install UI is retired.
from shared.lib.sample_pack_config import SERVER_MANAGED_SAMPLE_PACKS

import base64
import os
import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.icons import apply_button_icon
from features.create.widgets.studio_panel import StudioPanel, fill_studio_canvas, paint_studio_card
from features.settings.settings_styles import build_settings_page_qss
from features.settings.widgets.error_banner import LOAD_ERROR, SettingsErrorBanner
from shared.lib.ui_font import ensure_inter_loaded, studio_font
from shared.lib.app_paths import get_profile_media_cache_dir
from shared.lib.music_settings import build_music_prompt_defaults_patch, read_string_setting
from shared.lib.settings_workspace import (
    ProfileDraft,
    PublicationDraft,
    SunoSettingsDraft,
    SystemSettingsDraft,
    build_profile_draft,
    build_profile_payload,
    build_publication_draft,
    build_publication_payload,
    SUNO_VERSION_OPTIONS,
    build_suno_settings_draft,
    build_suno_settings_patch,
    build_system_settings_draft,
    build_system_settings_patch,
    get_profile_initials,
    get_profile_search_haystack,
    slugify_profile_folder_name,
    get_youtube_connect_button_label,
    get_youtube_connect_hint,
    get_youtube_status_label,
    publication_draft_equal,
    profile_payload_equal,
    toggle_library_sample,
)
from features.settings.widgets.user_owned_prompt_panel import UserOwnedPromptPanel
from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.platform import PromptNameOption, YouTubeConnectionResponse
from shared.services.app_logger import get_app_logger, log_error, log_info, log_warn
from shared.services.build_config import get_portal_base_url
from shared.services.ffmpeg_setup import (
    FFMPEG_DOWNLOAD_PAGE_URL,
    FFMPEG_SETUP_INSTRUCTIONS,
    ffmpeg_preferences_note,
)
from shared.services.file_service import list_directory_image_paths, open_external_url, open_path, read_file_bytes
from shared.services.log_sync import SyncLogsWorker, build_client_log_payload
from shared.services.platform_api import PlatformApi
from shared.services.session_service import SessionService
from shared.services.shell_status import emit_shell_status
from shared.services.workspace_cache import WorkspaceCache, cache_entry_is_fresh
from shared.themes.deep_blue import (
    MUSIC_SECTION_ID,
    SETTINGS_FOOTER_ERROR_ID,
    SETTINGS_FOOTER_ID,
    SETTINGS_FOOTER_STATUS_ID,
    SETTINGS_FOOTER_SUCCESS_ID,
    SETTINGS_FOOTER_WARNING_ID,
    SETTINGS_FORM_ROW_ID,
    SETTINGS_SECONDARY_BUTTON_ID,
    SHELL_TEXT_EDIT_ID,
    START_BUTTON_ID,
    SUBTITLE_LABEL_ID,
)
from shared.widgets.data_table import create_data_table, set_table_rows
from shared.widgets.settings_ui import (
    ProfileIdentityCard,
    SettingsPanel,
    form_row,
    make_fill_tab_page,
    make_scrollable_tab_page,
    make_two_column_fill_tab,
    mini_stat,
    note_box,
    path_row,
    two_column_row,
)
from shared.workers.data_workers import (
    ContentPoolWorker,
    DeleteProfileWorker,
    ImageSamplePacksWorker,
    MyPromptMutationResult,
    MyPromptMutationWorker,
    PatchSettingsWorker,
    ProfileMediaCacheResult,
    ProfileMediaCacheWorker,
    SamplePackInstallWorker,
    SaveProfileWorker,
    SettingsWorkspacePayload,
    SettingsWorkspaceWorker,
    YouTubeActionWorker,
    YouTubeConnectionsWorker,
    YouTubePlaylistsWorker,
)

LOADING_MESSAGE = "Loading settings workspace..."
TAB_LABELS = (
    "Profiles",
    "YouTube",
    "Publication",
    "Preferences",
    "Descriptions",
    "Structures",
    "Moods",
    "Pools",
    "Suno",
)
OUTPUT_RESOLUTIONS = ("1920x1080", "1080x1920", "1080x1080", "1280x720")
IMAGE_MODES = (("bg_thumb", "BG + TH"), ("bg_only", "BG Only"), ("thumb_only", "TH Only"))
VISIBILITY_OPTIONS = ("unlisted", "public", "private", "scheduled")
CATEGORY_OPTIONS = (
    ("10", "Music"),
    ("24", "Entertainment"),
    ("22", "People & Blogs"),
    ("20", "Gaming"),
    ("1", "Film & Animation"),
    ("2", "Autos & Vehicles"),
    ("15", "Pets & Animals"),
    ("17", "Sports"),
    ("19", "Travel & Events"),
    ("26", "Howto & Style"),
    ("27", "Education"),
)
YOUTUBE_CHUNK_SIZES = ("128", "256", "512")
CONTENT_POOL_PAGE_SIZE = 50


class _FramedHeader(CreateHeader):
    def paintEvent(self, event) -> None:  # noqa: N802
        paint_studio_card(self)


class SettingsView(QWidget):
    def __init__(
        self,
        api: PlatformApi,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
        session: SessionService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settings_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ensure_inter_loaded()
        self.setStyleSheet(build_settings_page_qss())
        self.setFont(studio_font(12))
        fill_studio_canvas(self)
        self._api = api
        self._cache = cache
        self._session = session
        self._worker: SettingsWorkspaceWorker | None = None
        self._my_prompt_worker: MyPromptMutationWorker | None = None
        self._my_prompt_mutation_kind: str | None = None
        self._save_profile_worker: SaveProfileWorker | None = None
        self._delete_profile_worker: DeleteProfileWorker | None = None
        self._patch_worker: PatchSettingsWorker | None = None
        self._youtube_worker: YouTubeActionWorker | None = None
        self._youtube_connections_worker: YouTubeConnectionsWorker | None = None
        self._youtube_poll_timer = QTimer(self)
        self._youtube_poll_timer.setInterval(3000)
        self._youtube_poll_timer.timeout.connect(self._poll_youtube_connections)
        self._youtube_poll_profile_id: str | None = None
        self._pool_worker: ContentPoolWorker | None = None
        self._playlists_worker: YouTubePlaylistsWorker | None = None
        self._sample_packs_worker: ImageSamplePacksWorker | None = None
        self._sample_pack_install_worker: SamplePackInstallWorker | None = None
        self._profile_media_cache_worker: ProfileMediaCacheWorker | None = None
        self._diag_sync_worker: SyncLogsWorker | None = None
        self._profiles: list[ProfileResponse] = []
        self._settings_raw: dict[str, object] = {}
        self._youtube_connections: list[YouTubeConnectionResponse] = []
        self._description_options: list[PromptNameOption] = []
        self._structure_options: list[PromptNameOption] = []
        self._mood_options: list[PromptNameOption] = []
        self._sample_packs: list[object] = []
        self._bg_sample_files: list[str] = []
        self._th_sample_files: list[str] = []
        self._profile_allowance: int | None = None
        self._profile_usage = 0
        self._selected_profile_key: str | None = None
        self._selected_description_id: str = ""
        self._selected_structure_id: str = ""
        self._selected_mood_id: str = ""
        self._baseline_description_id: str = ""
        self._baseline_structure_id: str = ""
        self._baseline_mood_id: str = ""
        self._profile_draft = ProfileDraft()
        self._baseline_profile_draft = ProfileDraft()
        self._publication_draft = PublicationDraft()
        self._baseline_publication_draft = PublicationDraft()
        self._system_draft = SystemSettingsDraft()
        self._baseline_system_draft = SystemSettingsDraft()
        self._suno_draft = SunoSettingsDraft()
        self._baseline_suno_draft = SunoSettingsDraft()
        self._status_message = "All supported Settings changes are saved."
        self._footer_tone = "neutral"
        self._footer_reset_timer = QTimer(self)
        self._footer_reset_timer.setSingleShot(True)
        self._footer_reset_timer.timeout.connect(self._reset_footer_success)
        self._binding_publication_tab = False
        self._binding_youtube_tab = False
        self._profile_folder_user_edited = False
        self._playlist_load_generation = 0
        self._playlist_auth_failed_profiles: set[str] = set()
        self._loading = True
        self._is_error = False
        self._ever_loaded = False
        self._loaded_user_id: str | None = None
        self._pool_kind = "openings"
        self._pool_offset = 0
        self._pool_total = 0
        self._pool_stats: object | None = None
        self._settings_fetched_at = 0.0
        self._pool_payload_cache: dict[tuple[str, int], dict[str, object]] = {}
        self._pool_payload_fetched_at: dict[tuple[str, int], float] = {}
        self._sample_packs_fetched_at = 0.0
        self._sample_library_scan_cache: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
        self._sample_library_scan_fetched_at: dict[tuple[str, str], float] = {}
        self._active_tab_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        header = _FramedHeader(
            title="Settings",
            subtitle="Manage channel profiles, YouTube, publication, prompts, and local preferences.",
            meta="",
            eyebrow="WORKSPACE",
        )
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.addWidget(header)

        self._error_banner = SettingsErrorBanner()
        self._error_banner.hide()
        root.addWidget(self._error_banner)

        self._loading_card = StudioPanel()
        loading_layout = QVBoxLayout(self._loading_card)
        loading_layout.setContentsMargins(12, 12, 12, 12)
        loading_label = QLabel(LOADING_MESSAGE)
        loading_label.setObjectName("PageSubtitle")
        loading_layout.addWidget(loading_label)
        root.addWidget(self._loading_card)

        self._tab_bar_card = StudioPanel()
        tab_bar_layout = QHBoxLayout(self._tab_bar_card)
        tab_bar_layout.setContentsMargins(8, 8, 8, 8)
        tab_bar_layout.setSpacing(6)
        self._tab_button_group = QButtonGroup(self)
        self._tab_button_group.setExclusive(True)
        self._tab_buttons: list[QPushButton] = []
        for index, label in enumerate(TAB_LABELS):
            button = QPushButton(label)
            button.setObjectName("FilterChip")
            button.setCheckable(True)
            button.clicked.connect(lambda checked, idx=index: self._set_active_tab(idx) if checked else None)
            self._tab_button_group.addButton(button, index)
            self._tab_buttons.append(button)
            tab_bar_layout.addWidget(button)
        tab_bar_layout.addStretch()
        self._tab_bar_card.hide()
        root.addWidget(self._tab_bar_card)

        self._content_host = QWidget()
        self._content_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(self._content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tabs = self._stack
        self._stack.addWidget(self._build_profiles_tab())
        self._stack.addWidget(self._build_youtube_tab())
        self._stack.addWidget(self._build_publication_tab())
        self._stack.addWidget(self._build_preferences_tab())
        self._stack.addWidget(self._build_prompt_library_tab("description"))
        self._stack.addWidget(self._build_prompt_library_tab("structure"))
        self._stack.addWidget(self._build_prompt_library_tab("mood"))
        self._stack.addWidget(self._build_pools_tab())
        self._stack.addWidget(self._build_suno_tab())
        content_layout.addWidget(self._stack, stretch=1)
        self._content_host.hide()
        root.addWidget(self._content_host, stretch=1)

        self._footer = QFrame()
        self._footer.setObjectName(SETTINGS_FOOTER_ID)
        self._footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        self._footer_status = QLabel(self._status_message)
        self._footer_status.setObjectName(SETTINGS_FOOTER_STATUS_ID)
        self._footer_status.setWordWrap(True)
        self._save_all_btn = QPushButton("Save All Changes")
        self._save_all_btn.setObjectName("SecondaryButton")
        apply_button_icon(self._save_all_btn, "check")
        self._save_all_btn.clicked.connect(self._save_all)
        footer_layout.addWidget(self._footer_status, stretch=1)
        footer_layout.addWidget(self._save_all_btn)
        self._footer.hide()
        root.addWidget(self._footer)

        self._tab_buttons[0].setChecked(True)

        from shared.services.video_template_catalog import VideoTemplateCatalogBus

        VideoTemplateCatalogBus.instance().changed.connect(self.refresh_profile_template_options)

    def refresh_profile_template_options(self) -> None:
        """Reload Profiles video/reel template dropdowns from the local catalog."""
        if not self._ever_loaded:
            return
        self._populate_template_combos()

    def _cached_user_id(self) -> str | None:
        if self._cache is None or self._cache.me is None:
            return None
        return self._cache.me.id

    def _account_cache_mismatch(self) -> bool:
        cached = self._cached_user_id()
        if self._loaded_user_id is None or cached is None:
            return False
        return cached != self._loaded_user_id

    def _reset_for_account_change(self) -> None:
        self._loaded_user_id = None
        self._ever_loaded = False
        self._loading = True
        self._is_error = False
        self._profiles = []
        self._selected_profile_key = None
        self._settings_fetched_at = 0.0
        self._error_banner.hide()
        self._loading_card.show()
        self._tab_bar_card.hide()
        self._content_host.hide()
        self._footer.hide()

    def activate_page(self) -> None:
        force = False
        if self._account_cache_mismatch():
            self._reset_for_account_change()
            force = True
        if self._ever_loaded:
            # Video create/save/delete may have happened while Settings was idle.
            self.refresh_profile_template_options()
            return
        self.refresh_data(force=force)

    def prewarm_from_cache(self) -> bool:
        """Hydrate from startup cache while the loading screen is still visible."""
        if self._account_cache_mismatch():
            self._reset_for_account_change()
        if self._ever_loaded:
            return True
        if not self._apply_core_cache():
            return False
        return True

    def refresh_data(self, *, force: bool = False) -> None:
        if self._account_cache_mismatch():
            self._reset_for_account_change()
            force = True
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._ever_loaded and not force:
            self._apply_core_cache()
            if self._ever_loaded and self._is_settings_workspace_fresh():
                return
        elif not force and self._ever_loaded and self._is_settings_workspace_fresh():
            return
        worker = SettingsWorkspaceWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, SettingsWorkspacePayload):
            return
        self._loading = False
        self._ever_loaded = True
        self._is_error = False
        self._error_banner.hide()
        self._loading_card.hide()
        self._tab_bar_card.show()
        self._content_host.show()
        self._footer.show()

        self._profiles = [item for item in payload.profiles if isinstance(item, ProfileResponse)]
        self._youtube_connections = self._normalize_youtube_connections(
            [item for item in payload.youtube_connections]
        )
        for connection in self._youtube_connections:
            if connection.status == "connected":
                self._playlist_auth_failed_profiles.discard(str(connection.profile_id))
        self._description_options = [item for item in payload.description_options if isinstance(item, PromptNameOption)]
        self._structure_options = [item for item in payload.structure_options if isinstance(item, PromptNameOption)]
        self._mood_options = [item for item in payload.mood_options if isinstance(item, PromptNameOption)]
        settings = payload.settings
        if hasattr(settings, "model_dump"):
            self._settings_raw = settings.model_dump(by_alias=True)
        elif isinstance(settings, dict):
            self._settings_raw = settings
        else:
            self._settings_raw = {}

        me = payload.me
        if isinstance(me, UserMeResponse):
            self._loaded_user_id = me.id
        self._profile_allowance = getattr(me, "profile_allowance", None)
        self._profile_usage = getattr(me, "channel_profile_count", len(self._profiles))

        if self._selected_profile_key and self._selected_profile_key != "new":
            if not any(profile.id == self._selected_profile_key for profile in self._profiles):
                self._selected_profile_key = self._profiles[0].id if self._profiles else None
        elif not self._selected_profile_key and self._profiles:
            self._selected_profile_key = self._profiles[0].id

        self._system_draft = build_system_settings_draft(self._settings_raw)
        self._baseline_system_draft = build_system_settings_draft(self._settings_raw)
        self._suno_draft = build_suno_settings_draft(self._settings_raw)
        self._baseline_suno_draft = build_suno_settings_draft(self._settings_raw)
        self._load_music_prompt_defaults_from_settings()
        self._bind_all_tabs()
        self._reload_my_prompt_panels()
        self._refresh_footer()
        self._sync_youtube_poll_timer()
        self._persist_workspace_cache(payload)

    def _is_settings_workspace_fresh(self) -> bool:
        if self._cache is not None:
            return self._cache.is_settings_workspace_fresh()
        return self._settings_fetched_at > 0 and cache_entry_is_fresh(self._settings_fetched_at)

    def _persist_workspace_cache(self, payload: SettingsWorkspacePayload) -> None:
        settings = payload.settings
        if hasattr(settings, "model_dump"):
            settings_raw = settings.model_dump(by_alias=True)
        elif isinstance(settings, dict):
            settings_raw = settings
        else:
            settings_raw = {}
        if self._cache is not None:
            self._cache.apply_settings_workspace(
                me=payload.me if isinstance(payload.me, UserMeResponse) else None,
                profiles=[item for item in payload.profiles if isinstance(item, ProfileResponse)],
                settings_raw=settings_raw,
                description_options=[item for item in payload.description_options if isinstance(item, PromptNameOption)],
                structure_options=[item for item in payload.structure_options if isinstance(item, PromptNameOption)],
                mood_options=[item for item in payload.mood_options if isinstance(item, PromptNameOption)],
                youtube_connections=[
                    item for item in payload.youtube_connections if isinstance(item, YouTubeConnectionResponse)
                ],
            )
        self._settings_fetched_at = time.time()

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

    def _apply_settings_extras_cache(self) -> bool:
        if self._cache is None:
            return False
        youtube_connections, fetched_at = self._cache.snapshot_settings_extras()
        if fetched_at <= 0:
            return False
        self._youtube_connections = self._normalize_youtube_connections(youtube_connections)
        self._settings_fetched_at = fetched_at
        return True

    def _apply_core_cache(self) -> bool:
        if self._cache is None or not self._cache.has_core():
            return False
        me, profiles, settings_raw, description_options, structure_options, mood_options = self._cache.snapshot_core()
        if not profiles or not settings_raw:
            return False
        self._loading = False
        self._ever_loaded = True
        self._is_error = False
        self._error_banner.hide()
        self._loading_card.hide()
        self._tab_bar_card.show()
        self._content_host.show()
        self._footer.show()
        self._profiles = [item for item in profiles if isinstance(item, ProfileResponse)]
        self._settings_raw = settings_raw
        self._description_options = [item for item in description_options if isinstance(item, PromptNameOption)]
        self._structure_options = [item for item in structure_options if isinstance(item, PromptNameOption)]
        self._mood_options = [item for item in mood_options if isinstance(item, PromptNameOption)]
        self._profile_allowance = getattr(me, "profile_allowance", None) if me is not None else None
        self._profile_usage = getattr(me, "channel_profile_count", len(self._profiles)) if me is not None else len(self._profiles)
        if isinstance(me, UserMeResponse):
            self._loaded_user_id = me.id
        if self._selected_profile_key and self._selected_profile_key != "new":
            if not any(profile.id == self._selected_profile_key for profile in self._profiles):
                self._selected_profile_key = self._profiles[0].id if self._profiles else None
        elif not self._selected_profile_key and self._profiles:
            self._selected_profile_key = self._profiles[0].id
        self._system_draft = build_system_settings_draft(self._settings_raw)
        self._baseline_system_draft = build_system_settings_draft(self._settings_raw)
        self._suno_draft = build_suno_settings_draft(self._settings_raw)
        self._baseline_suno_draft = build_suno_settings_draft(self._settings_raw)
        self._load_music_prompt_defaults_from_settings()
        self._apply_settings_extras_cache()
        self._apply_my_prompts_cache()
        self._bind_all_tabs()
        self._refresh_footer()
        return True

    def _apply_my_prompts_cache(self) -> bool:
        if self._cache is None:
            return False
        description_items, structure_items, mood_items, fetched_at = self._cache.snapshot_my_prompt_items()
        if fetched_at <= 0:
            return False
        self._apply_my_prompt_items(description_items, structure_items, mood_items)
        return True

    def _apply_my_prompt_items(
        self,
        description_items: list[object],
        structure_items: list[object],
        mood_items: list[object] | None = None,
    ) -> None:
        normalized_descriptions = [
            self._normalize_my_prompt_item(item)
            for item in description_items
            if isinstance(item, dict)
        ]
        normalized_structures = [
            self._normalize_my_prompt_item(item)
            for item in structure_items
            if isinstance(item, dict)
        ]
        normalized_moods = [
            self._normalize_my_prompt_item(item)
            for item in (mood_items or [])
            if isinstance(item, dict)
        ]
        if hasattr(self, "_my_description_panel"):
            self._my_description_panel.set_items(normalized_descriptions)
            if hasattr(self, "_descriptions_my_stat"):
                self._update_mini_stat_value(self._descriptions_my_stat, str(len(normalized_descriptions)))
        if hasattr(self, "_my_structure_panel"):
            self._my_structure_panel.set_items(normalized_structures)
            if hasattr(self, "_structures_my_stat"):
                self._update_mini_stat_value(self._structures_my_stat, str(len(normalized_structures)))
        if hasattr(self, "_my_mood_panel"):
            self._my_mood_panel.set_items(normalized_moods)
            if hasattr(self, "_moods_my_stat"):
                self._update_mini_stat_value(self._moods_my_stat, str(len(normalized_moods)))

    def _on_failed(self, message: str) -> None:
        self._loading = False
        if not self._ever_loaded:
            self._loading_card.hide()
            self._tab_bar_card.hide()
            self._content_host.hide()
            self._footer.hide()
            self._error_banner.set_message(message or LOAD_ERROR)
            self._error_banner.show()
            log_error(message or LOAD_ERROR, category="settings")
            return
        self._set_footer_notice(message or LOAD_ERROR, tone="error")
        log_error(message or LOAD_ERROR, category="settings")

    def _selected_profile(self) -> ProfileResponse | None:
        if not self._selected_profile_key or self._selected_profile_key == "new":
            return None
        for profile in self._profiles:
            if profile.id == self._selected_profile_key:
                return profile
        return None

    def _is_youtube_oauth_pending(self) -> bool:
        return any(
            connection.status in {"pending_browser", "awaiting_channel_selection"}
            for connection in self._youtube_connections
        )

    def _sync_youtube_poll_timer(self) -> None:
        if self._ever_loaded and self._is_youtube_oauth_pending():
            if not self._youtube_poll_timer.isActive():
                self._youtube_poll_timer.start()
        else:
            self._youtube_poll_timer.stop()

    def _poll_youtube_connections(self) -> None:
        if self._youtube_connections_worker is not None and self._youtube_connections_worker.isRunning():
            return
        worker = YouTubeConnectionsWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_youtube_connections_polled)
        worker.finished.connect(lambda: setattr(self, "_youtube_connections_worker", None))
        self._youtube_connections_worker = worker
        worker.start()

    def _on_youtube_connections_polled(self, connections: object) -> None:
        if not isinstance(connections, list):
            return
        self._youtube_connections = self._normalize_youtube_connections(
            [item for item in connections] if isinstance(connections, list) else []
        )
        if self._cache is not None:
            self._cache.apply_settings_workspace(youtube_connections=self._youtube_connections)
        self._bind_youtube_tab()
        profile = self._selected_profile()
        if profile:
            self._refresh_profile_identity(
                is_new=self._selected_profile_key == "new",
                profile=profile,
            )
        if TAB_LABELS[self._active_tab_index] == "Publication":
            self._bind_publication_tab()
        self._sync_youtube_poll_timer()

        poll_profile_id = self._youtube_poll_profile_id
        if not poll_profile_id:
            return
        connection = self._youtube_connection_for(poll_profile_id)
        if connection and connection.status == "connected" and connection.channel_title:
            self._youtube_poll_profile_id = None
            self._show_save_success(f"YouTube connected: {connection.channel_title}.")
            log_info(f"YouTube connected: {connection.channel_title}.", category="settings")
        elif connection and connection.status in {"error", "expired"}:
            self._youtube_poll_profile_id = None

    def _youtube_connection_for(self, profile_id: str | None) -> YouTubeConnectionResponse | None:
        if not profile_id:
            return None
        target_id = str(profile_id)
        for connection in self._youtube_connections:
            if str(connection.profile_id) == target_id:
                return connection
        return None

    def _dirty_tabs(self) -> list[str]:
        tabs: list[str] = []
        if self._selected_profile_key is not None:
            current = build_profile_payload(self._profile_draft, self._selected_profile() if self._selected_profile_key != "new" else None)
            baseline = build_profile_payload(self._baseline_profile_draft, self._selected_profile() if self._selected_profile_key != "new" else None)
            if not profile_payload_equal(current, baseline):
                tabs.append("Profiles")
        if self._selected_profile() and not publication_draft_equal(self._publication_draft, self._baseline_publication_draft):
            tabs.append("Publication")
        from shared.lib.settings_workspace import device_media_paths_dirty

        if build_system_settings_patch(
            self._system_draft,
            self._settings_raw,
            exclude_sample_pack_settings=SERVER_MANAGED_SAMPLE_PACKS,
        ) or device_media_paths_dirty(self._system_draft, self._settings_raw):
            tabs.append("Preferences")
        if build_suno_settings_patch(self._suno_draft, self._settings_raw):
            tabs.append("Suno")
        if self._music_prompt_defaults_patch():
            tabs.append("Music defaults")
        return tabs

    def _load_music_prompt_defaults_from_settings(self) -> None:
        self._baseline_description_id = read_string_setting(self._settings_raw, "defaultDescriptionId")
        self._baseline_structure_id = read_string_setting(self._settings_raw, "defaultStructureId")
        self._baseline_mood_id = read_string_setting(self._settings_raw, "defaultMoodId")
        self._selected_description_id = self._baseline_description_id
        self._selected_structure_id = self._baseline_structure_id
        self._selected_mood_id = self._baseline_mood_id

    def _sync_music_prompt_defaults_to_local_store(self) -> None:
        from dataclasses import replace

        from features.music.services.music_local_store import MusicLocalStore, MusicWorkspacePrefs

        store = MusicLocalStore()
        current = store.read_workspace_prefs() or MusicWorkspacePrefs()
        store.write_workspace_prefs(
            replace(
                current,
                selected_description_id=self._selected_description_id,
                selected_structure_id=self._selected_structure_id,
                selected_mood_id=self._selected_mood_id,
            )
        )

    def _resolve_saved_prompt_id(self, options: list[PromptNameOption], saved_id: str) -> str:
        normalized = str(saved_id or "").strip()
        if normalized and any(option.id == normalized for option in options):
            return normalized
        return options[0].id if options else ""

    def _music_prompt_defaults_patch(self) -> dict[str, object]:
        current = build_music_prompt_defaults_patch(
            default_description_id=self._selected_description_id,
            default_structure_id=self._selected_structure_id,
            default_mood_id=self._selected_mood_id,
        )
        baseline = build_music_prompt_defaults_patch(
            default_description_id=self._baseline_description_id,
            default_structure_id=self._baseline_structure_id,
            default_mood_id=self._baseline_mood_id,
        )
        return {key: value for key, value in current.items() if baseline.get(key) != value}

    def _apply_footer_frame_style(self, object_name: str) -> None:
        self._footer.setObjectName(object_name)
        self._footer_status.setObjectName(SETTINGS_FOOTER_STATUS_ID)
        self._footer_status.setStyleSheet("")
        style = self._footer.style()
        style.unpolish(self._footer)
        style.polish(self._footer)
        style.unpolish(self._footer_status)
        style.polish(self._footer_status)
        self._footer.update()

    def _footer_frame_for_tone(self, tone: str) -> str:
        if tone == "success":
            return SETTINGS_FOOTER_SUCCESS_ID
        if tone == "error":
            return SETTINGS_FOOTER_ERROR_ID
        if tone == "warning":
            return SETTINGS_FOOTER_WARNING_ID
        return SETTINGS_FOOTER_ID

    def _set_footer_notice(self, message: str, *, tone: str = "neutral", auto_reset_ms: int = 0) -> None:
        self._status_message = message
        self._footer_tone = tone
        if auto_reset_ms > 0:
            self._footer_reset_timer.start(auto_reset_ms)
        else:
            self._footer_reset_timer.stop()
        self._refresh_footer()

    def _show_save_success(self, message: str) -> None:
        self._set_footer_notice(message, tone="success", auto_reset_ms=5000)
        from shared.services.setup_readiness_service import refresh_setup_readiness

        refresh_setup_readiness(
            api=self._api,
            cache=self._cache,
            parent=self,
            force_network=True,
        )

    def _reset_footer_success(self) -> None:
        if self._footer_tone != "success":
            return
        if self._dirty_tabs():
            self._footer_tone = "neutral"
            self._refresh_footer()
            return
        self._set_footer_notice("All supported Settings changes are saved.", tone="neutral")

    def _refresh_footer(self) -> None:
        import time

        started = time.monotonic()
        dirty = self._dirty_tabs()
        elapsed_ms = (time.monotonic() - started) * 1000
        if elapsed_ms > 150:
            # This runs synchronously on the UI thread on every keystroke.
            # Seen in the wild: a broken workspace path made a downstream
            # dirty-check call attempt directory creation on every call,
            # stalling the whole app while the user typed. Surface it loudly
            # if this regresses again instead of silently freezing.
            log_warn(
                f"Settings dirty-check took {elapsed_ms:.0f}ms (UI thread) — investigate slow path in _dirty_tabs().",
                category="settings",
            )
        if dirty:
            self._footer_reset_timer.stop()
            self._footer_status.setText(f"Unsaved changes in {', '.join(dirty)}.")
            self._apply_footer_frame_style(SETTINGS_FOOTER_WARNING_ID)
        else:
            self._footer_status.setText(self._status_message)
            self._apply_footer_frame_style(self._footer_frame_for_tone(self._footer_tone))
        self._save_all_btn.setEnabled(bool(dirty))
        if hasattr(self, "_suno_save_btn"):
            self._suno_save_btn.setEnabled(bool(build_suno_settings_patch(self._suno_draft, self._settings_raw)))
        if hasattr(self, "_pub_save_btn"):
            publication_dirty = (
                self._selected_profile_key not in (None, "new")
                and not publication_draft_equal(self._publication_draft, self._baseline_publication_draft)
            )
            self._pub_save_btn.setEnabled(publication_dirty)

    def _bind_all_tabs(self) -> None:
        self._bind_profiles_tab()
        self._bind_youtube_tab()
        self._bind_publication_tab()
        self._bind_preferences_tab()
        self._bind_text_library_tab("description")
        self._bind_text_library_tab("structure")
        self._bind_text_library_tab("mood")
        self._bind_suno_tab()
        self._refresh_footer()

    def _set_active_tab(self, index: int) -> None:
        self._active_tab_index = index
        self._stack.setCurrentIndex(index)
        if TAB_LABELS[index] == "Pools":
            self._load_pools()
        elif TAB_LABELS[index] == "Preferences":
            if not SERVER_MANAGED_SAMPLE_PACKS:
                self._load_sample_packs()
                self._refresh_sample_library_lists()
        elif TAB_LABELS[index] == "YouTube":
            self._bind_youtube_tab()
        elif TAB_LABELS[index] == "Publication":
            self._load_publication_playlists()

    def _build_profiles_tab(self) -> QWidget:
        return make_two_column_fill_tab(
            self._build_profiles_left_panel(),
            self._build_profiles_right_panel(),
            left_stretch=0,
            right_stretch=1,
        )

    def _build_profiles_left_panel(self) -> QWidget:
        panel = SettingsPanel(
            "Your Profiles",
            subtitle="Select a profile to edit. Search matches name, folder name, and run prefix.",
            fill_available_height=True,
        )
        panel.setMinimumWidth(340)
        self._profile_search = QLineEdit()
        self._profile_search.setPlaceholderText("Search by name, folder, or prefix...")
        self._profile_search.textChanged.connect(self._filter_profile_list)
        self._profile_list = QListWidget()
        self._profile_list.setMinimumHeight(120)
        self._profile_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._profile_list.currentRowChanged.connect(self._on_profile_selected)
        self._new_profile_btn = QPushButton("Create profiles in portal")
        self._new_profile_btn.setToolTip(
            "New channel profiles are created in the CamXora account portal, not in the desktop app."
        )
        self._new_profile_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._new_profile_btn.clicked.connect(self._on_new_profile_clicked)
        panel.add_widget(self._profile_search)
        panel.add_widget(self._profile_list, stretch=1)
        panel.add_widget(self._new_profile_btn)
        return panel

    def _build_profiles_right_panel(self) -> QWidget:
        self._profile_editor_panel = SettingsPanel(
            "Profile",
            subtitle="Manage the selected profile here, or use the footer to save changes across tabs.",
            fill_available_height=True,
        )
        self._profile_editor_title = self._profile_editor_panel._root.itemAt(0).layout().itemAt(0).layout().itemAt(0).widget()
        self._profile_save_btn = QPushButton("Save Changes")
        self._profile_save_btn.clicked.connect(self._save_profile)
        self._profile_cancel_btn = QPushButton("Cancel Draft")
        self._profile_cancel_btn.clicked.connect(self._cancel_profile_draft)
        self._profile_delete_btn = QPushButton("Delete")
        self._profile_delete_btn.clicked.connect(self._delete_profile)
        self._profile_editor_panel.add_action(self._profile_save_btn)
        self._profile_editor_panel.add_action(self._profile_cancel_btn)
        self._profile_editor_panel.add_action(self._profile_delete_btn)

        self._profile_identity = ProfileIdentityCard()
        self._profile_editor_panel.add_widget(self._profile_identity)

        self._profile_name = QLineEdit()
        self._profile_folder = QLineEdit()
        self._profile_prefix = QLineEdit()
        self._profile_logo = QLineEdit()
        self._profile_cover = QLineEdit()
        self._profile_resolution = QComboBox()
        self._profile_resolution.addItems(OUTPUT_RESOLUTIONS)
        self._profile_image_mode = QComboBox()
        for value, label in IMAGE_MODES:
            self._profile_image_mode.addItem(label, value)
        self._profile_video_template = QComboBox()
        self._profile_video_template.setEditable(False)
        self._profile_video_template.addItem("No template selected", "")
        self._profile_reel_template = QComboBox()
        self._profile_reel_template.setEditable(False)
        self._profile_reel_template.addItem("No template selected", "")

        form = self._profile_editor_panel.add_scrolled_section()
        form.addWidget(form_row("Name", self._profile_name))
        form.addWidget(form_row("Folder name", self._profile_folder))
        form.addWidget(form_row("Run prefix (optional)", self._profile_prefix))
        form.addWidget(
            note_box(
                "Folder name is generated from the profile name (for example, "
                "\"Beattok Remixes\" -> \"beattok-remixes\") unless you edit it manually."
            )
        )
        form.addWidget(
            form_row(
                "Channel logo (center)",
                path_row(
                    line_edit=self._profile_logo,
                    on_browse=lambda: self._browse_profile_image("logo"),
                    on_open=lambda: self._open_path_field(self._profile_logo),
                ),
            )
        )
        form.addWidget(
            form_row(
                "Channel cover",
                path_row(
                    line_edit=self._profile_cover,
                    on_browse=lambda: self._browse_profile_image("cover"),
                    on_open=lambda: self._open_path_field(self._profile_cover),
                ),
            )
        )
        form.addWidget(form_row("Video template", self._profile_video_template))
        form.addWidget(form_row("Reel template", self._profile_reel_template))
        form.addWidget(form_row("Output resolution", self._profile_resolution))
        form.addWidget(form_row("Image mode", self._profile_image_mode))
        form.addWidget(
            note_box(
                "`BG + TH` creates both background and thumbnail jobs. "
                "`BG Only` or `TH Only` only affect future batches."
            )
        )

        for widget in (
            self._profile_prefix,
            self._profile_logo,
            self._profile_cover,
        ):
            widget.textChanged.connect(self._on_profile_field_changed)
        self._profile_name.textChanged.connect(self._sync_profile_folder_from_name)
        self._profile_name.textChanged.connect(self._on_profile_field_changed)
        self._profile_folder.textEdited.connect(self._on_profile_folder_edited)
        self._profile_resolution.currentTextChanged.connect(self._on_profile_field_changed)
        self._profile_image_mode.currentIndexChanged.connect(self._on_profile_field_changed)
        self._profile_video_template.currentIndexChanged.connect(self._on_profile_field_changed)
        self._profile_reel_template.currentIndexChanged.connect(self._on_profile_field_changed)
        return self._profile_editor_panel

    def _build_youtube_tab(self) -> QWidget:
        left = SettingsPanel(
            "Channel Connection",
            subtitle="Attach a YouTube channel to the selected profile and use it for publication settings.",
            fill_available_height=True,
        )
        self._youtube_connection_stat = mini_stat("Connection status", "Not connected")
        left.add_widget(self._youtube_connection_stat)
        self._youtube_profile = QComboBox()
        self._youtube_profile.currentIndexChanged.connect(self._on_youtube_profile_changed)
        left.add_widget(form_row("Profile", self._youtube_profile))
        self._youtube_channel_display = note_box("No YouTube channel is connected yet.")
        left.add_widget(form_row("Channel", self._youtube_channel_display))
        self._youtube_channel_row_host = QWidget()
        self._youtube_channel_row_layout = QVBoxLayout(self._youtube_channel_row_host)
        self._youtube_channel_row_layout.setContentsMargins(0, 0, 0, 0)
        left.add_widget(self._youtube_channel_row_host)
        btn_row = QHBoxLayout()
        self._youtube_connect_btn = QPushButton("Connect Channel")
        self._youtube_connect_btn.clicked.connect(self._start_youtube_connection)
        self._youtube_resync_btn = QPushButton("Resync Channel Data")
        self._youtube_resync_btn.clicked.connect(self._resync_youtube)
        self._youtube_disconnect_btn = QPushButton("Disconnect")
        self._youtube_disconnect_btn.clicked.connect(self._disconnect_youtube)
        btn_row.addWidget(self._youtube_connect_btn)
        btn_row.addWidget(self._youtube_resync_btn)
        btn_row.addWidget(self._youtube_disconnect_btn)
        btn_row.addStretch()
        left.add_layout(btn_row)
        self._youtube_connect_hint = note_box(
            "Connect once here, then keep publication defaults per profile in the Publication tab."
        )
        left.add_widget(self._youtube_connect_hint)
        left.add_stretch()

        right = SettingsPanel(
            "Channel Access",
            subtitle="Review the current YouTube connection state for the selected profile.",
            fill_available_height=True,
        )
        stats_row = QHBoxLayout()
        self._youtube_profile_stat = mini_stat("Selected profile", "No profile")
        self._youtube_channels_stat = mini_stat("Returned channels", "0")
        self._youtube_session_stat = mini_stat("Session", "Idle")
        stats_row.addWidget(self._youtube_profile_stat)
        stats_row.addWidget(self._youtube_channels_stat)
        stats_row.addWidget(self._youtube_session_stat)
        right.add_layout(stats_row)
        self._youtube_state_note = note_box("Select a profile first to review its YouTube connection state.")
        right.add_widget(self._youtube_state_note)
        self._youtube_connected_note = note_box("No YouTube channel is connected yet.")
        right.add_widget(self._youtube_connected_note)
        right.add_stretch()

        return make_two_column_fill_tab(left, right, left_stretch=0, right_stretch=1)

    def _build_publication_tab(self) -> QWidget:
        panel = SettingsPanel(
            "Publication",
            subtitle="Manage profile-specific publishing metadata and YouTube publishing defaults.",
            fill_available_height=True,
        )
        self._pub_save_btn = QPushButton("Save Publication")
        self._pub_save_btn.setEnabled(False)
        self._pub_save_btn.clicked.connect(self._save_publication)
        panel.add_action(self._pub_save_btn)

        form = panel.add_scrolled_section()

        self._publication_profile = QComboBox()
        self._publication_profile.currentIndexChanged.connect(self._on_publication_profile_changed)
        form.addWidget(form_row("Selected profile", self._publication_profile))
        self._pub_youtube_status = note_box("Not connected")
        form.addWidget(form_row("YouTube", self._pub_youtube_status))
        form.addWidget(
            form_row(
                "Channel access",
                note_box(
                    "Connect or change the YouTube channel from the YouTube tab. "
                    "Publication defaults here apply to the currently connected channel."
                ),
            )
        )
        self._pub_status_note = note_box("Publication defaults are up to date.")
        form.addWidget(form_row("Publication status", self._pub_status_note))

        self._pub_visibility = QComboBox()
        self._pub_visibility.addItems(VISIBILITY_OPTIONS)
        self._pub_visibility.currentTextChanged.connect(self._on_publication_visibility_changed)
        form.addWidget(form_row("Visibility", self._pub_visibility))

        self._pub_schedule_host = QWidget()
        self._pub_schedule_host.setObjectName(SETTINGS_FORM_ROW_ID)
        self._pub_schedule_host.setAutoFillBackground(False)
        self._pub_schedule_layout = QVBoxLayout(self._pub_schedule_host)
        self._pub_schedule_layout.setContentsMargins(0, 0, 0, 0)
        schedule_row = QHBoxLayout()
        self._pub_publish_hour = QComboBox()
        self._pub_publish_hour.addItems([str(value).zfill(2) for value in range(24)])
        self._pub_publish_minute = QComboBox()
        self._pub_publish_minute.addItems([str(value).zfill(2) for value in range(0, 60, 5)])
        self._pub_schedule_clear = QPushButton("Clear")
        self._pub_schedule_clear.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._pub_schedule_clear.clicked.connect(self._clear_publication_schedule)
        schedule_row.addWidget(self._pub_publish_hour)
        schedule_row.addWidget(self._pub_publish_minute)
        schedule_row.addWidget(self._pub_schedule_clear)
        self._pub_schedule_summary = note_box("This field only applies when visibility is set to Scheduled.")
        self._pub_schedule_layout.addLayout(schedule_row)
        self._pub_schedule_layout.addWidget(self._pub_schedule_summary)
        form.addWidget(form_row("Publish at", self._pub_schedule_host))

        self._pub_made_for_kids = QCheckBox("Made for kids")
        self._pub_made_for_kids.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pub_made_for_kids.toggled.connect(lambda *_: self._on_publication_field_changed())
        form.addWidget(form_row("Audience", self._pub_made_for_kids))
        self._pub_ai_use = QComboBox()
        self._pub_ai_use.addItem("No", False)
        self._pub_ai_use.addItem("Yes", True)
        self._pub_ai_use.currentIndexChanged.connect(lambda *_: self._on_publication_field_changed())
        form.addWidget(form_row("AI use", self._pub_ai_use))
        self._pub_category = QComboBox()
        for value, label in CATEGORY_OPTIONS:
            self._pub_category.addItem(label, value)
        self._pub_category.currentIndexChanged.connect(lambda *_: self._on_publication_field_changed())
        form.addWidget(form_row("Category", self._pub_category))
        self._pub_playlist = QComboBox()
        self._pub_playlist.setEditable(True)
        self._pub_playlist.currentTextChanged.connect(self._on_publication_field_changed)
        form.addWidget(form_row("Playlist", self._pub_playlist))

        self._pub_description = self._make_text_edit(min_height=120)
        self._pub_keywords = QLineEdit()
        self._pub_tags = QLineEdit()
        self._pub_title_template = QLineEdit()
        self._pub_description_template = self._make_text_edit(min_height=120)
        form.addWidget(form_row("Channel description", self._pub_description))
        form.addWidget(form_row("Keywords", self._pub_keywords))
        form.addWidget(form_row("Tags", self._pub_tags))
        form.addWidget(form_row("Title template", self._pub_title_template))
        form.addWidget(form_row("Description template", self._pub_description_template))

        for widget in (self._pub_keywords, self._pub_tags, self._pub_title_template):
            widget.textChanged.connect(self._on_publication_field_changed)
        for widget in (self._pub_description, self._pub_description_template):
            widget.textChanged.connect(self._on_publication_field_changed)
        self._pub_publish_hour.currentTextChanged.connect(self._on_publication_field_changed)
        self._pub_publish_minute.currentTextChanged.connect(self._on_publication_field_changed)

        return make_fill_tab_page(panel)

    def _build_preferences_tab(self) -> QWidget:
        # Same scroll path as Video rails / Publication (make_scrollable_tab_page).
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        paths_panel = SettingsPanel(
            "Local Paths",
            subtitle="This PC only — music/images land under the Suno root. Not synced to your account.",
        )
        workers_panel = SettingsPanel(
            "Workers",
            subtitle="Worker and chunk settings used by generation, rendering, and uploads.",
        )
        self._pref_ffmpeg = QLineEdit()
        self._pref_suno_output = QLineEdit()
        self._ffmpeg_download_btn = QPushButton("Download FFmpeg")
        self._ffmpeg_download_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._ffmpeg_download_btn.clicked.connect(self._on_download_ffmpeg_clicked)
        paths_panel.add_widget(
            form_row(
                "FFmpeg path",
                path_row(
                    line_edit=self._pref_ffmpeg,
                    on_browse=lambda: self._pick_file(self._pref_ffmpeg),
                    on_open=lambda: self._open_path_field(self._pref_ffmpeg),
                    extra_widgets=[self._ffmpeg_download_btn],
                ),
            )
        )
        paths_panel.add_widget(
            note_box(ffmpeg_preferences_note())
        )
        paths_panel.add_widget(
            form_row(
                "Suno output dir",
                path_row(
                    line_edit=self._pref_suno_output,
                    on_browse=lambda: self._pick_directory(self._pref_suno_output),
                    on_open=lambda: self._open_path_field(self._pref_suno_output),
                ),
            )
        )
        paths_panel.add_widget(
            note_box(
                "Batch folders are created as {channel}/{date_album} under this root. "
                "Downloads, merges, and images use the same tree (or app defaults). "
                "This folder is stored on this PC and is kept across updates — "
                "Camxora will not reset it to AppData if the drive is offline."
            )
        )

        worker_grid = QGridLayout()
        self._pref_music_workers = self._make_spinbox(1, 5)
        self._pref_image_workers = self._make_spinbox(1, 8)
        self._pref_export_workers = self._make_spinbox(1, 10)
        self._pref_merge_workers = self._make_spinbox(1, 2)
        self._pref_youtube_workers = self._make_spinbox(1, 5)
        self._pref_youtube_chunk = QComboBox()
        self._pref_youtube_chunk.addItems(YOUTUBE_CHUNK_SIZES)
        for index, (label, widget) in enumerate(
            (
                ("Music workers", self._pref_music_workers),
                ("Image workers", self._pref_image_workers),
                ("Export workers", self._pref_export_workers),
                ("Merge workers", self._pref_merge_workers),
                ("YouTube upload workers", self._pref_youtube_workers),
                ("YouTube chunk size (MB)", self._pref_youtube_chunk),
            )
        ):
            worker_grid.addWidget(form_row(label, widget), index // 2, index % 2)
        workers_panel.add_layout(worker_grid)
        workers_panel.add_widget(
            note_box("Keep worker counts aligned with your CPU, RAM, and expected workload.")
        )

        image_panel = SettingsPanel(
            "Image",
            subtitle=(
                "Background and thumbnail reference images are managed on the Camxora server. "
                "Generated files land in each batch run folder under your Suno output dir."
                if SERVER_MANAGED_SAMPLE_PACKS
                else "System-wide image folders and rendering defaults."
            ),
        )
        rendering_panel = SettingsPanel(
            "Rendering",
            subtitle="Image output resolution and style blending used by the desktop renderer.",
        )
        if SERVER_MANAGED_SAMPLE_PACKS:
            image_panel.add_widget(
                note_box(
                    "Your admin uploads sample ZIPs in the admin portal. Server-side image "
                    "generation uses those assets automatically — local sample folders and curation "
                    "are no longer required."
                )
            )
        else:
            self._pref_bg_samples_dir = QLineEdit()
            self._pref_th_samples_dir = QLineEdit()
            self._pref_image_output = QLineEdit()
            for label, field, picker in (
                ("BG samples dir", self._pref_bg_samples_dir, lambda: self._pick_directory(self._pref_bg_samples_dir)),
                ("Thumb samples dir", self._pref_th_samples_dir, lambda: self._pick_directory(self._pref_th_samples_dir)),
                ("Output dir (optional)", self._pref_image_output, lambda: self._pick_directory(self._pref_image_output)),
            ):
                image_panel.add_widget(
                    form_row(
                        label,
                        path_row(
                            line_edit=field,
                            on_browse=picker,
                            on_open=lambda field=field: self._open_path_field(field),
                        ),
                    )
                )

        self._pref_resolution = QComboBox()
        self._pref_resolution.addItems(OUTPUT_RESOLUTIONS)
        self._pref_style_strength = QSlider(Qt.Orientation.Horizontal)
        self._pref_style_strength.setRange(0, 100)
        self._pref_style_strength.setSingleStep(10)
        self._pref_style_strength.valueChanged.connect(self._on_style_strength_changed)
        self._pref_style_strength_label = QLabel("80 / 100")
        self._pref_style_strength_label.setObjectName(SUBTITLE_LABEL_ID)
        style_host = QVBoxLayout()
        style_host.addWidget(self._pref_style_strength)
        style_host.addWidget(self._pref_style_strength_label)
        style_widget = QWidget()
        style_widget.setLayout(style_host)
        self._pref_image_source = QComboBox()
        self._pref_image_source.addItem("AI Generated", "ai")
        self._pref_image_source.addItem("User Provided", "manual")
        self._pref_background_source = QComboBox()
        self._pref_background_source.addItem("Category", "category")
        self._pref_background_source.addItem("Prompt only", "prompt_only")
        self._pref_thumbnail_source = QComboBox()
        self._pref_thumbnail_source.addItem("Category", "category")
        self._pref_thumbnail_source.addItem("Prompt only", "prompt_only")
        # Thumbnail overlay stays AI/composite behind the scenes (no UI — locked product decision).
        self._pref_thumbnail_overlay_mode = "ai"
        rendering_panel.add_widget(form_row("Output resolution", self._pref_resolution))
        rendering_panel.add_widget(form_row("Style strength", style_widget))
        rendering_panel.add_widget(form_row("Image source mode", self._pref_image_source))
        self._bg_source_row = form_row("Background source", self._pref_background_source)
        self._th_source_row = form_row("Thumbnail source", self._pref_thumbnail_source)
        rendering_panel.add_widget(self._bg_source_row)
        rendering_panel.add_widget(self._th_source_row)
        rendering_panel.add_widget(
            note_box(
                "AI Generated uses Background/Thumbnail source: Category (admin samples) "
                "or Prompt only (text, no sample). "
                "User Provided skips AI — place final images in the run folder and continue the pipeline. "
                "Style strength applies when a Category sample is used."
            )
        )

        if not SERVER_MANAGED_SAMPLE_PACKS:
            sample_packs_panel = SettingsPanel(
                "Sample Pack Downloads",
                subtitle="Download background + thumbnail sample packs from Admin-managed links.",
            )
            self._sample_packs_reload_btn = QPushButton("Reload Packs")
            self._sample_packs_reload_btn.clicked.connect(lambda: self._load_sample_packs(force=True))
            sample_packs_panel.add_action(self._sample_packs_reload_btn)
            self._bg_pack_combo = QComboBox()
            self._th_pack_combo = QComboBox()
            self._bg_pack_install_btn = QPushButton("Install")
            self._bg_pack_install_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            self._bg_pack_install_btn.clicked.connect(self._on_install_background_pack)
            self._th_pack_install_btn = QPushButton("Install")
            self._th_pack_install_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            self._th_pack_install_btn.clicked.connect(self._on_install_thumbnail_pack)
            self._bg_pack_combo.currentIndexChanged.connect(lambda *_: self._update_sample_pack_install_buttons())
            self._th_pack_combo.currentIndexChanged.connect(lambda *_: self._update_sample_pack_install_buttons())
            sample_packs_panel.add_layout(
                two_column_row(
                    self._wrap_pack_subpanel("Background Packs", self._bg_pack_combo, self._bg_pack_install_btn),
                    self._wrap_pack_subpanel("Thumbnail Packs", self._th_pack_combo, self._th_pack_install_btn),
                )
            )

            library_panel = SettingsPanel(
                "Sample Library Manager",
                subtitle="Curate which background and thumbnail samples stay available for manual or random image generation.",
            )
            self._sample_refresh_btn = QPushButton("Refresh Samples")
            self._sample_refresh_btn.clicked.connect(lambda: self._refresh_sample_library_lists(force=True))
            library_panel.add_action(self._sample_refresh_btn)
            self._pref_bg_random = QCheckBox("Random background sample")
            self._pref_bg_random.setCursor(Qt.CursorShape.PointingHandCursor)
            self._pref_bg_random.toggled.connect(lambda *_: self._on_system_field_changed())
            self._pref_th_random = QCheckBox("Random thumbnail sample")
            self._pref_th_random.setCursor(Qt.CursorShape.PointingHandCursor)
            self._pref_th_random.toggled.connect(lambda *_: self._on_system_field_changed())
            self._bg_samples_list = QListWidget()
            self._bg_samples_list.itemClicked.connect(self._on_bg_sample_clicked)
            self._th_samples_list = QListWidget()
            self._th_samples_list.itemClicked.connect(self._on_th_sample_clicked)
            self._bg_selected_count = QLabel("Selected 0/5")
            self._bg_selected_count.setObjectName(SUBTITLE_LABEL_ID)
            self._th_selected_count = QLabel("Selected 0/5")
            self._th_selected_count.setObjectName(SUBTITLE_LABEL_ID)
            library_panel.add_layout(
                two_column_row(
                    self._wrap_sample_library(
                        "Background Samples",
                        "Click to curate up to 5 allowed images. Hover previews, click pins and selects.",
                        self._pref_bg_random,
                        self._bg_selected_count,
                        self._bg_samples_list,
                        "Random on rotates through your pinned subset when any are selected; otherwise it uses the full folder. "
                        "Least-used images are picked first (tracked in the database).",
                    ),
                    self._wrap_sample_library(
                        "Thumbnail Samples",
                        "Curate thumbnail styles separately so unselected images stay available only for random fallback.",
                        self._pref_th_random,
                        self._th_selected_count,
                        self._th_samples_list,
                        "Random on rotates through your pinned subset when any are selected; otherwise it uses the full folder. "
                        "Least-used images are picked first (tracked in the database).",
                    ),
                    align_top=True,
                )
            )

        for widget in (self._pref_ffmpeg, self._pref_suno_output):
            widget.textChanged.connect(self._on_system_field_changed)
        if not SERVER_MANAGED_SAMPLE_PACKS:
            for widget in (self._pref_bg_samples_dir, self._pref_th_samples_dir, self._pref_image_output):
                widget.textChanged.connect(self._on_system_field_changed)
            self._pref_bg_samples_dir.textChanged.connect(lambda *_: self._update_sample_pack_install_buttons())
            self._pref_th_samples_dir.textChanged.connect(lambda *_: self._update_sample_pack_install_buttons())
        for widget in (
            self._pref_music_workers,
            self._pref_image_workers,
            self._pref_export_workers,
            self._pref_merge_workers,
            self._pref_youtube_workers,
        ):
            widget.valueChanged.connect(lambda *_: self._on_system_field_changed())
        self._pref_youtube_chunk.currentTextChanged.connect(self._on_system_field_changed)
        self._pref_image_source.currentIndexChanged.connect(lambda *_: self._on_image_source_mode_changed())
        self._pref_resolution.currentTextChanged.connect(self._on_system_field_changed)
        self._pref_background_source.currentIndexChanged.connect(lambda *_: self._on_system_field_changed())
        self._pref_thumbnail_source.currentIndexChanged.connect(lambda *_: self._on_system_field_changed())
        self._update_ai_reference_controls_visibility()

        root.addLayout(two_column_row(paths_panel, workers_panel))
        root.addLayout(two_column_row(image_panel, rendering_panel))
        if not SERVER_MANAGED_SAMPLE_PACKS:
            root.addWidget(sample_packs_panel)
            root.addWidget(library_panel)

        diagnostics_panel = SettingsPanel(
            "Diagnostics",
            subtitle=(
                "Upload recent local logs to Camxora support without opening the raw console. "
                "Use this when support asks you to send diagnostics."
            ),
        )
        self._diag_status = QLabel("Logs stay on this computer until you send them.")
        self._diag_status.setObjectName(SUBTITLE_LABEL_ID)
        self._diag_status.setWordWrap(True)
        diagnostics_panel.add_widget(self._diag_status)
        diagnostics_panel.add_widget(
            note_box(
                "Secrets are redacted before upload. Raw HTML gateway errors are summarized. "
                "The full Diagnostics console is hidden unless support enables it on your build."
            )
        )
        self._send_diagnostics_btn = QPushButton("Send diagnostics")
        self._send_diagnostics_btn.setObjectName(START_BUTTON_ID)
        self._send_diagnostics_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_diagnostics_btn.setToolTip(
            "Upload recent local logs to Camxora so support can review them in the admin portal."
        )
        self._send_diagnostics_btn.clicked.connect(self._on_send_diagnostics)
        diagnostics_panel.add_widget(self._send_diagnostics_btn)
        root.addWidget(diagnostics_panel)

        return make_scrollable_tab_page(host)

    @staticmethod
    def _wrap_pack_subpanel(title: str, combo: QComboBox, install_btn: QPushButton) -> QWidget:
        frame = QWidget()
        frame.setObjectName(SETTINGS_FORM_ROW_ID)
        frame.setAutoFillBackground(False)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(heading)
        layout.addWidget(combo)
        layout.addWidget(install_btn)
        return frame

    @staticmethod
    def _wrap_subpanel(title: str, combo: QComboBox) -> QWidget:
        frame = QWidget()
        frame.setObjectName(SETTINGS_FORM_ROW_ID)
        frame.setAutoFillBackground(False)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(heading)
        layout.addWidget(combo)
        return frame

    def _wrap_sample_library(
        self,
        title: str,
        subtitle: str,
        random_toggle: QCheckBox,
        count_label: QLabel,
        sample_list: QListWidget,
        footer_text: str,
    ) -> QWidget:
        frame = QFrame()
        frame.setObjectName(MUSIC_SECTION_ID)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        header.setAlignment(Qt.AlignmentFlag.AlignTop)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName(SUBTITLE_LABEL_ID)
        sub = QLabel(subtitle)
        sub.setObjectName(SUBTITLE_LABEL_ID)
        sub.setWordWrap(True)
        text_col.addWidget(heading)
        text_col.addWidget(sub)
        header.addLayout(text_col, stretch=1)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 2, 0, 0)
        controls.setSpacing(10)
        controls.setAlignment(Qt.AlignmentFlag.AlignTop)
        controls.addWidget(random_toggle)
        controls.addWidget(count_label)
        header.addLayout(controls)
        layout.addLayout(header)

        sample_list.setMinimumHeight(160)
        sample_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(sample_list, stretch=1)
        layout.addWidget(note_box(footer_text))
        return frame

    @staticmethod
    def _prompt_option_label(option: PromptNameOption) -> str:
        suffix = " (mine)" if option.is_owned else ""
        return f"{option.name}{suffix}"

    def _build_prompt_library_tab(self, kind: str) -> QWidget:
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(12)

        stats_row = QHBoxLayout()
        catalog_stat = mini_stat("Camxora catalog", "0")
        my_stat = mini_stat("My library", "0")
        selected_stat = mini_stat("Default selection", "—")
        stats_row.addWidget(catalog_stat)
        stats_row.addWidget(my_stat)
        stats_row.addWidget(selected_stat)
        stats_row.addStretch()

        kind_label = {"description": "description", "structure": "structure", "mood": "mood"}[kind]
        overview_panel = SettingsPanel(
            "Library overview",
            subtitle=(
                f"Shared {kind_label} catalog, your custom prompts, and the current Music workspace default."
            ),
        )
        overview_panel.add_layout(stats_row)
        root.addWidget(overview_panel)

        catalog_left = SettingsPanel(
            "Camxora catalog",
            subtitle=(
                f"Shared {kind_label} names from Admin Portal. Click one to set it as the active Music default."
            ),
            fill_available_height=True,
        )
        catalog_left.setMinimumWidth(320)
        catalog_left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        catalog_list = QListWidget()
        catalog_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        catalog_list.currentRowChanged.connect(
            lambda row, prompt_kind=kind: self._on_text_library_selected(prompt_kind, row)
        )
        catalog_left.add_widget(catalog_list, stretch=1)

        catalog_right = SettingsPanel(
            "Default for Music",
            subtitle="Choose defaults for the Music page. Click Save All Changes to apply.",
            fill_available_height=True,
        )
        catalog_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        selector = QComboBox()
        selector.currentIndexChanged.connect(
            lambda _index, prompt_kind=kind: self._on_text_library_combo_changed(prompt_kind)
        )
        catalog_right.add_widget(form_row("Workspace default", selector))
        if kind == "description":
            self._description_structure_combo = QComboBox()
            self._description_structure_combo.currentIndexChanged.connect(
                lambda index: self._set_selected_structure(index)
            )
            catalog_right.add_widget(form_row("Default structure", self._description_structure_combo))
        selected_name = QLineEdit()
        selected_name.setReadOnly(True)
        catalog_right.add_widget(form_row("Selected name", selected_name))
        selection_note = note_box(
            "These defaults load automatically on the Music page. Use Save All Changes to persist."
        )
        catalog_right.add_widget(selection_note)
        catalog_right.add_widget(
            note_box(
                "Camxora catalog names are read-only here. Create your own prompts in User catalog below."
            )
        )
        catalog_right.add_stretch()

        placeholders = {
            "description": "Describe genre, mood, energy, and instrumentation...",
            "structure": "[Verse]\n[Chorus]\n[Verse]\n[Chorus]\n[Bridge]\n[Chorus]",
            "mood": "Describe the emotional tone, narrative feeling, and lyric atmosphere...",
        }
        my_panel = UserOwnedPromptPanel(
            list_title="User catalog",
            editor_title="Prompt editor",
            content_placeholder=placeholders[kind],
            parent=host,
        )
        my_panel.saved.connect(lambda prompt_kind=kind: self._save_my_prompt(prompt_kind))
        my_panel.deleted.connect(lambda prompt_kind=kind: self._delete_my_prompt(prompt_kind))
        my_panel.default_requested.connect(
            lambda item_id, prompt_kind=kind: self._apply_active_music_prompt(prompt_kind, item_id)
        )

        grid_host = QWidget()
        grid_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        grid.addWidget(catalog_left, 0, 0)
        grid.addWidget(catalog_right, 0, 1)
        grid.addWidget(my_panel.list_card, 1, 0)
        grid.addWidget(my_panel.editor_card, 1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, 320)

        main_section = QWidget()
        main_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_section.setMinimumHeight(560)
        main_layout = QVBoxLayout(main_section)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(grid_host, stretch=1)
        root.addWidget(main_section, stretch=1)

        if kind == "description":
            self._descriptions_stat = catalog_stat
            self._descriptions_my_stat = my_stat
            self._descriptions_selected_stat = selected_stat
            self._descriptions_list = catalog_list
            self._description_selector = selector
            self._description_selected_name = selected_name
            self._description_selection_note = selection_note
            self._my_description_panel = my_panel
        elif kind == "structure":
            self._structures_stat = catalog_stat
            self._structures_my_stat = my_stat
            self._structures_selected_stat = selected_stat
            self._structures_list = catalog_list
            self._structure_selector = selector
            self._structure_selected_name = selected_name
            self._structure_selection_note = selection_note
            self._my_structure_panel = my_panel
        else:
            self._moods_stat = catalog_stat
            self._moods_my_stat = my_stat
            self._moods_selected_stat = selected_stat
            self._moods_list = catalog_list
            self._mood_selector = selector
            self._mood_selected_name = selected_name
            self._mood_selection_note = selection_note
            self._my_mood_panel = my_panel

        return make_scrollable_tab_page(host)

    @staticmethod
    def _normalize_my_prompt_item(item: dict[str, object]) -> dict[str, str]:
        return {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "content": str(item.get("content") or ""),
        }

    def _my_prompt_panel(self, kind: str) -> UserOwnedPromptPanel:
        if kind == "description":
            return self._my_description_panel
        if kind == "mood":
            return self._my_mood_panel
        return self._my_structure_panel

    def _my_prompt_stat(self, kind: str) -> QFrame:
        if kind == "description":
            return self._descriptions_my_stat
        if kind == "mood":
            return self._moods_my_stat
        return self._structures_my_stat

    def _set_my_prompt_actions_enabled(self, kind: str, enabled: bool) -> None:
        panel = self._my_prompt_panel(kind)
        panel.set_actions_enabled(enabled)

    def _reload_my_prompt_panels(self, *, force_network: bool = False) -> None:
        if not force_network and self._apply_my_prompts_cache():
            return
        try:
            description_items = [
                self._normalize_my_prompt_item(item)
                for item in self._api.list_my_descriptions()
                if isinstance(item, dict)
            ]
            structure_items = [
                self._normalize_my_prompt_item(item)
                for item in self._api.list_my_structures()
                if isinstance(item, dict)
            ]
            mood_items = [
                self._normalize_my_prompt_item(item)
                for item in self._api.list_my_moods()
                if isinstance(item, dict)
            ]
        except Exception as exc:
            log_error("settings.my_prompts.load_failed", category="settings", exc=exc)
            description_items = []
            structure_items = []
            mood_items = []
        self._apply_my_prompt_items(description_items, structure_items, mood_items)
        if self._cache is not None:
            self._cache.apply_settings_workspace(
                my_description_items=description_items,
                my_structure_items=structure_items,
                my_mood_items=mood_items,
            )

    def _start_my_prompt_mutation(
        self,
        kind: str,
        *,
        creating: bool = False,
        prompt_id: str = "",
        name: str = "",
        content: str = "",
        delete: bool = False,
    ) -> None:
        if self._my_prompt_worker is not None and self._my_prompt_worker.isRunning():
            return
        worker = MyPromptMutationWorker(
            self._api,
            kind=kind,
            creating=creating,
            prompt_id=prompt_id,
            name=name,
            content=content,
            delete=delete,
            parent=self,
        )
        worker.succeeded.connect(self._on_my_prompt_mutation_succeeded)
        worker.failed.connect(self._on_my_prompt_mutation_failed)
        worker.finished.connect(lambda: setattr(self, "_my_prompt_worker", None))
        self._my_prompt_worker = worker
        self._my_prompt_mutation_kind = kind
        self._set_my_prompt_actions_enabled(kind, False)
        worker.start()

    def _on_my_prompt_mutation_succeeded(self, payload: object) -> None:
        if not isinstance(payload, MyPromptMutationResult):
            return
        panel = self._my_prompt_panel(payload.kind)
        stat = self._my_prompt_stat(payload.kind)
        if payload.deleted:
            self._clear_deleted_prompt_selection(payload)
            self._reload_my_prompt_panels()
            self._show_save_success("Custom prompt deleted.")
        else:
            if payload.item:
                panel.upsert_item(self._normalize_my_prompt_item(payload.item))
                self._update_mini_stat_value(stat, str(panel.item_count()))
            else:
                self._reload_my_prompt_panels()
            self._show_save_success("Custom prompt saved.")
        self._set_my_prompt_actions_enabled(payload.kind, True)
        self._my_prompt_mutation_kind = None
        self.refresh_data(force=True)

    def _on_my_prompt_mutation_failed(self, message: str) -> None:
        if self._my_prompt_mutation_kind is not None:
            self._set_my_prompt_actions_enabled(self._my_prompt_mutation_kind, True)
            self._my_prompt_mutation_kind = None
        self._show_error(message or "Unable to update custom prompt.")

    def _save_my_prompt(self, kind: str) -> None:
        panel = self._my_prompt_panel(kind)
        prompt_id, name, content, creating = panel.draft()
        if not name or not content:
            self._show_error("Name and content are required for your custom prompt.")
            return
        self._start_my_prompt_mutation(
            kind,
            creating=creating,
            prompt_id=prompt_id,
            name=name,
            content=content,
        )

    def _clear_deleted_prompt_selection(self, payload: MyPromptMutationResult) -> None:
        deleted_id = str(payload.prompt_id or "")
        if not deleted_id:
            return
        if payload.kind == "description" and self._selected_description_id == deleted_id:
            self._selected_description_id = ""
        elif payload.kind == "structure" and self._selected_structure_id == deleted_id:
            self._selected_structure_id = ""
        elif payload.kind == "mood" and self._selected_mood_id == deleted_id:
            self._selected_mood_id = ""

    def _delete_my_prompt(self, kind: str) -> None:
        panel = self._my_prompt_panel(kind)
        prompt_id, name, _content, creating = panel.draft()
        if creating or not prompt_id:
            return
        label = {"description": "description", "structure": "structure", "mood": "mood"}[kind]
        confirmed = QMessageBox.question(
            self,
            f"Delete My {label.title()}",
            f'Delete "{name or "this prompt"}"? It will be removed from your library and Music dropdowns. Past songs keep their history, but will no longer reference this prompt.',
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._start_my_prompt_mutation(kind, prompt_id=prompt_id, delete=True)

    def _build_pools_tab(self) -> QWidget:
        stats_row = QHBoxLayout()
        self._pool_openings_stat = mini_stat("Openings", "Unavailable")
        self._pool_titles_stat = mini_stat("Titles", "Unavailable")
        self._pool_albums_stat = mini_stat("Albums", "Unavailable")
        self._pool_ownership_stat = mini_stat("Ownership", "Admin Portal")
        stats_row.addWidget(self._pool_openings_stat)
        stats_row.addWidget(self._pool_titles_stat)
        stats_row.addWidget(self._pool_albums_stat)
        stats_row.addWidget(self._pool_ownership_stat)

        panel = SettingsPanel(
            "Content Pools",
            subtitle="Read-only pool visibility for users. Editing stays in the Admin Portal.",
            fill_available_height=True,
        )
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        kind_row = QHBoxLayout()
        self._pool_kind_buttons: dict[str, QPushButton] = {}
        for kind in ("openings", "titles", "albums"):
            button = QPushButton(kind.capitalize())
            button.setCheckable(True)
            button.clicked.connect(lambda checked, value=kind: self._set_pool_kind(value) if checked else None)
            self._pool_kind_buttons[kind] = button
            kind_row.addWidget(button)
        self._pool_kind_buttons["openings"].setChecked(True)
        left_layout.addLayout(kind_row)
        self._pools_table = create_data_table(["ID", "Name", "Used", "Created"])
        header = self._pools_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._pools_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_layout.addWidget(self._pools_table, stretch=1)
        pager = QHBoxLayout()
        self._pool_page_label = QLabel("Page 1")
        self._pool_page_label.setObjectName(SUBTITLE_LABEL_ID)
        self._pool_prev_btn = QPushButton("Prev")
        self._pool_prev_btn.clicked.connect(self._pool_prev_page)
        self._pool_next_btn = QPushButton("Next")
        self._pool_next_btn.clicked.connect(self._pool_next_page)
        pager.addWidget(self._pool_page_label, stretch=1)
        pager.addWidget(self._pool_prev_btn)
        pager.addWidget(self._pool_next_btn)
        left_layout.addLayout(pager)

        sidebar = QVBoxLayout()
        self._pool_current_note = note_box("Pool counts are unavailable right now.")
        sidebar.addWidget(self._wrap_info_block("Current pool", self._pool_current_note))
        sidebar.addWidget(
            self._wrap_info_block(
                "Editing scope",
                note_box("Users can review pool contents here. All editing stays in the Admin Portal."),
            )
        )
        sidebar.addStretch()
        sidebar_host = QWidget()
        sidebar_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sidebar_host.setMaximumWidth(280)
        sidebar_host.setLayout(sidebar)
        panel.add_layout(two_column_row(left, sidebar_host, left_stretch=4, right_stretch=1))

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(stats_row)
        layout.addWidget(panel, stretch=1)
        return make_fill_tab_page(content)

    @staticmethod
    def _wrap_info_block(title: str, body: QLabel) -> QWidget:
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(heading)
        layout.addWidget(body)
        return frame

    def _build_suno_tab(self) -> QWidget:
        panel = SettingsPanel(
            "Suno",
            subtitle="Manage Suno runtime defaults for timeout, retries, version, and merge behavior.",
            fill_available_height=True,
        )
        self._suno_save_btn = QPushButton("Save Suno")
        self._suno_save_btn.setEnabled(False)
        self._suno_save_btn.clicked.connect(self._save_suno_settings)
        panel.add_action(self._suno_save_btn)

        form = panel.add_scrolled_section()
        left = QVBoxLayout()
        right = QVBoxLayout()
        self._suno_version = QComboBox()
        self._suno_version.addItems(list(SUNO_VERSION_OPTIONS))
        self._suno_merge_enabled = QComboBox()
        self._suno_merge_enabled.addItem("Off", False)
        self._suno_merge_enabled.addItem("On", True)
        self._suno_timeout = self._make_spinbox(1000, 600000, step=1000)
        self._suno_retry = self._make_spinbox(0, 20)
        self._suno_merge_group = self._make_spinbox(0, 20)
        left.addWidget(form_row("Default Suno version", self._suno_version))
        left.addWidget(form_row("Auto merge downloads", self._suno_merge_enabled))
        left.addWidget(form_row("Merge group size", self._suno_merge_group))
        right.addWidget(form_row("Timeout (ms)", self._suno_timeout))
        right.addWidget(form_row("Retry count", self._suno_retry))
        left_host = QWidget()
        left_host.setObjectName(SETTINGS_FORM_ROW_ID)
        left_host.setAutoFillBackground(False)
        left_host.setLayout(left)
        right_host = QWidget()
        right_host.setObjectName(SETTINGS_FORM_ROW_ID)
        right_host.setAutoFillBackground(False)
        right_host.setLayout(right)
        form.addLayout(two_column_row(left_host, right_host))
        form.addWidget(note_box("Only the supported Suno defaults are shown here."))

        for widget in (self._suno_timeout, self._suno_retry, self._suno_merge_group):
            widget.valueChanged.connect(lambda *_: self._on_suno_field_changed())
        self._suno_version.currentTextChanged.connect(self._on_suno_field_changed)
        self._suno_merge_enabled.currentIndexChanged.connect(lambda *_: self._on_suno_field_changed())

        return make_fill_tab_page(panel)

    @staticmethod
    def _make_text_edit(*, min_height: int = 112):
        from PySide6.QtWidgets import QTextEdit

        edit = QTextEdit()
        edit.setObjectName(SHELL_TEXT_EDIT_ID)
        edit.setMinimumHeight(min_height)
        return edit

    @staticmethod
    def _make_spinbox(minimum: int, maximum: int, *, step: int = 1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        return spin

    def _pick_file(self, target: QLineEdit) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            target.setText(path)

    def _browse_profile_image(self, kind: str) -> None:
        """Browse a local image and stage it as base64 for profile save."""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select channel logo" if kind == "logo" else "Select channel cover",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif);;All files (*.*)",
        )
        if not path:
            return
        raw = read_file_bytes(path)
        if not raw:
            self._show_error("Unable to read the selected image file.")
            return
        encoded = base64.b64encode(raw).decode("ascii")
        if kind == "logo":
            self._profile_draft.logo_path = path
            self._profile_draft.logo_base64 = encoded
            self._profile_logo.blockSignals(True)
            self._profile_logo.setText(path)
            self._profile_logo.blockSignals(False)
        else:
            self._profile_draft.cover_path = path
            self._profile_draft.cover_base64 = encoded
            self._profile_cover.blockSignals(True)
            self._profile_cover.setText(path)
            self._profile_cover.blockSignals(False)
        self._refresh_footer()

    def _pick_directory(self, target: QLineEdit) -> None:
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            target.setText(path)

    def _open_path_field(self, target: QLineEdit) -> None:
        path = target.text().strip()
        if path:
            open_path(path)

    def _combo_set_by_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = 0
        combo.setCurrentIndex(index)

    def _template_id_from_combo(self, combo: QComboBox) -> str:
        data = combo.currentData()
        if data is None:
            return ""
        return str(data).strip()

    def _populate_template_combos(self) -> None:
        """Fill video/reel template dropdowns from the local video catalog.

        Always reads from ``VideoLocalStore`` so create/save/delete in Video
        (and marketplace installs) show up immediately, not a stale workspace cache.
        """
        templates: list[tuple[str, str, str]] = []
        try:
            from features.video.services.video_local_store import VideoLocalStore

            for item in VideoLocalStore().read_templates():
                template_id = str(item.get("id") or "").strip()
                if not template_id:
                    continue
                templates.append(
                    (
                        template_id,
                        str(item.get("name") or template_id).strip(),
                        str(item.get("source") or item.get("kind") or "").strip().lower(),
                    )
                )
        except Exception:
            templates = []

        video_items = [("", "No template selected")]
        reel_items = [("", "No template selected")]
        for template_id, name, kind in templates:
            if not template_id:
                continue
            label = name or template_id
            if "reel" in kind or "short" in kind:
                reel_items.append((template_id, label))
            else:
                video_items.append((template_id, label))
                # Also offer long-form templates for reel when no reel-specific ones exist.
                if len(reel_items) == 1:
                    pass

        # If there are no reel-tagged templates, allow selecting any template for reel.
        if len(reel_items) == 1 and len(video_items) > 1:
            reel_items = list(video_items)

        selected_video = self._template_id_from_combo(self._profile_video_template) or self._profile_draft.video_template_id
        selected_reel = self._template_id_from_combo(self._profile_reel_template) or self._profile_draft.reel_template_id

        self._profile_video_template.blockSignals(True)
        self._profile_reel_template.blockSignals(True)
        self._profile_video_template.clear()
        self._profile_reel_template.clear()
        for template_id, label in video_items:
            self._profile_video_template.addItem(label, template_id)
        for template_id, label in reel_items:
            self._profile_reel_template.addItem(label, template_id)
        # Keep unknown saved ids selectable so we don't wipe them.
        if selected_video and self._profile_video_template.findData(selected_video) < 0:
            self._profile_video_template.addItem(selected_video, selected_video)
        if selected_reel and self._profile_reel_template.findData(selected_reel) < 0:
            self._profile_reel_template.addItem(selected_reel, selected_reel)
        self._combo_set_by_data(self._profile_video_template, selected_video)
        self._combo_set_by_data(self._profile_reel_template, selected_reel)
        self._profile_video_template.blockSignals(False)
        self._profile_reel_template.blockSignals(False)

    def _resolve_profile_media_paths(self, profile: ProfileResponse | None, draft: ProfileDraft) -> ProfileDraft:
        """Fill in local cache paths for server logo/cover if already downloaded.

        Cache-only and network-free by design: this used to download missing
        files synchronously here, which blocked the entire UI thread on
        every profile switch whenever the file wasn't cached yet (a real,
        multi-megabyte network call with no protection against a slow or
        unreliable connection). Missing files are now fetched in the
        background by _start_profile_media_cache_download() instead.
        """
        if profile is None:
            return draft
        cache_dir = get_profile_media_cache_dir() / str(profile.id)

        logo_path = draft.logo_path.strip()
        if logo_path and not Path(logo_path).is_file():
            local_logo = cache_dir / "logo.png"
            if local_logo.is_file():
                draft.logo_path = str(local_logo)

        cover_path = draft.cover_path.strip()
        if cover_path and not Path(cover_path).is_file():
            local_cover = cache_dir / "cover.png"
            if local_cover.is_file():
                draft.cover_path = str(local_cover)
        return draft

    def _start_profile_media_cache_download(self, profile: ProfileResponse | None) -> None:
        """Kick off a background download for any logo/cover not yet cached locally."""
        if profile is None:
            return
        logo_path = str(getattr(self._profile_draft, "logo_path", "") or "").strip()
        cover_path = str(getattr(self._profile_draft, "cover_path", "") or "").strip()
        need_logo = bool(logo_path) and not Path(logo_path).is_file()
        need_cover = bool(cover_path) and not Path(cover_path).is_file()
        if not need_logo and not need_cover:
            return
        if self._profile_media_cache_worker is not None and self._profile_media_cache_worker.isRunning():
            # Let the in-flight download finish; it re-checks the cache next bind.
            return
        cache_dir = get_profile_media_cache_dir() / str(profile.id)
        worker = ProfileMediaCacheWorker(
            self._api,
            profile_id=str(profile.id),
            cache_dir=cache_dir,
            need_logo=need_logo,
            need_cover=need_cover,
            parent=self,
        )
        worker.succeeded.connect(self._on_profile_media_cached)
        worker.finished.connect(self._finish_profile_media_cache_worker)
        self._profile_media_cache_worker = worker
        worker.start()

    def _on_profile_media_cached(self, result: object) -> None:
        if not isinstance(result, ProfileMediaCacheResult):
            return
        # Ignore stale results from a profile the user already navigated away from.
        if self._selected_profile_key != result.profile_id:
            return
        if result.logo_path:
            self._profile_draft.logo_path = result.logo_path
            self._baseline_profile_draft.logo_path = result.logo_path
            self._profile_logo.blockSignals(True)
            self._profile_logo.setText(result.logo_path)
            self._profile_logo.blockSignals(False)
        if result.cover_path:
            self._profile_draft.cover_path = result.cover_path
            self._baseline_profile_draft.cover_path = result.cover_path
            self._profile_cover.blockSignals(True)
            self._profile_cover.setText(result.cover_path)
            self._profile_cover.blockSignals(False)

    def _finish_profile_media_cache_worker(self) -> None:
        self._profile_media_cache_worker = None

    def _filter_profile_list(self) -> None:
        """Filter the profile list without resetting the active draft."""
        term = self._profile_search.text().strip().lower()
        self._profile_list.blockSignals(True)
        self._profile_list.clear()
        for profile in self._profiles:
            if term and term not in get_profile_search_haystack(profile):
                continue
            item = QListWidgetItem(profile.name)
            item.setToolTip(profile.folder_name or profile.run_prefix or profile.output_resolution)
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self._profile_list.addItem(item)
            if profile.id == self._selected_profile_key:
                self._profile_list.setCurrentItem(item)
        self._profile_list.blockSignals(False)

    def _on_style_strength_changed(self, value: int) -> None:
        self._pref_style_strength_label.setText(f"{value} / 100")
        self._on_system_field_changed()

    def _on_image_source_mode_changed(self) -> None:
        self._update_ai_reference_controls_visibility()
        self._on_system_field_changed()

    def _update_ai_reference_controls_visibility(self) -> None:
        is_ai = str(self._pref_image_source.currentData() or "ai") != "manual"
        self._bg_source_row.setVisible(is_ai)
        self._th_source_row.setVisible(is_ai)
        self._pref_background_source.setEnabled(is_ai)
        self._pref_thumbnail_source.setEnabled(is_ai)

    def _on_download_ffmpeg_clicked(self) -> None:
        open_external_url(FFMPEG_DOWNLOAD_PAGE_URL)
        QMessageBox.information(
            self,
            "Download FFmpeg",
            f"{ffmpeg_preferences_note()}\n\n{FFMPEG_SETUP_INSTRUCTIONS}",
        )

    def _selected_sample_pack(self, combo: QComboBox) -> object | None:
        pack_id = str(combo.currentData() or "").strip()
        if not pack_id:
            return None
        for pack in self._sample_packs:
            if str(getattr(pack, "id", "")) == pack_id:
                return pack
        return None

    def _pack_install_url(self, pack: object) -> str:
        install_url = getattr(pack, "install_url", None)
        if callable(install_url):
            return str(install_url() or "").strip()
        return str(getattr(pack, "source_value", "") or getattr(pack, "download_url", "") or "").strip()

    def _update_sample_pack_install_buttons(self) -> None:
        if SERVER_MANAGED_SAMPLE_PACKS:
            return
        bg_pack = self._selected_sample_pack(self._bg_pack_combo)
        th_pack = self._selected_sample_pack(self._th_pack_combo)
        installing = self._sample_pack_install_worker is not None and self._sample_pack_install_worker.isRunning()
        self._bg_pack_install_btn.setEnabled(
            not installing and bg_pack is not None and bool(self._pref_bg_samples_dir.text().strip())
        )
        self._th_pack_install_btn.setEnabled(
            not installing and th_pack is not None and bool(self._pref_th_samples_dir.text().strip())
        )

    def _on_install_background_pack(self) -> None:
        pack = self._selected_sample_pack(self._bg_pack_combo)
        destination = self._pref_bg_samples_dir.text().strip()
        if pack is None:
            self._show_error("Select a background pack first.")
            return
        if not destination:
            self._show_error("Set the BG samples dir before installing a pack.")
            return
        url = self._pack_install_url(pack)
        if not url:
            self._show_error("This pack does not have a download link yet.")
            return
        self._start_sample_pack_install(url, destination, category="background")

    def _on_install_thumbnail_pack(self) -> None:
        pack = self._selected_sample_pack(self._th_pack_combo)
        destination = self._pref_th_samples_dir.text().strip()
        if pack is None:
            self._show_error("Select a thumbnail pack first.")
            return
        if not destination:
            self._show_error("Set the Thumb samples dir before installing a pack.")
            return
        url = self._pack_install_url(pack)
        if not url:
            self._show_error("This pack does not have a download link yet.")
            return
        self._start_sample_pack_install(url, destination, category="thumbnail")

    def _start_sample_pack_install(self, url: str, destination_dir: str, *, category: str) -> None:
        if self._sample_pack_install_worker is not None and self._sample_pack_install_worker.isRunning():
            return
        self._update_sample_pack_install_buttons()
        worker = SamplePackInstallWorker(url, destination_dir, parent=self)
        worker.succeeded.connect(
            lambda result, cat=category: self._on_sample_pack_installed(result, category=cat, destination_dir=destination_dir)
        )
        worker.failed.connect(self._on_sample_pack_install_failed)
        worker.finished.connect(self._finish_sample_pack_install_worker)
        self._sample_pack_install_worker = worker
        self._set_footer_notice(f"Installing {category} sample pack…", tone="neutral")
        worker.start()

    def _on_sample_pack_installed(self, result: object, *, category: str, destination_dir: str) -> None:
        installed_count = int(getattr(result, "installed_count", 0) or 0)
        self._show_save_success(
            f"Installed {installed_count} {category} image(s) into {destination_dir}."
        )
        self._refresh_sample_library_lists(force=True)
        self._update_sample_pack_install_buttons()

    def _on_sample_pack_install_failed(self, message: str) -> None:
        self._show_error(message or "Unable to install sample pack.")

    def _finish_sample_pack_install_worker(self) -> None:
        self._sample_pack_install_worker = None
        self._update_sample_pack_install_buttons()

    def _cancel_profile_draft(self) -> None:
        if self._selected_profile_key == "new":
            self._selected_profile_key = self._profiles[0].id if self._profiles else None
        self._bind_profiles_tab()
        self._refresh_footer()

    def _clear_publication_schedule(self) -> None:
        self._pub_publish_hour.setCurrentText("00")
        self._pub_publish_minute.setCurrentText("00")
        self._on_publication_field_changed()

    def _update_publication_schedule_visibility(self) -> None:
        scheduled = self._pub_visibility.currentText() == "scheduled"
        self._pub_schedule_host.setVisible(scheduled)
        if scheduled:
            self._pub_schedule_summary.setText(
                f"Scheduled uploads use the batch date and the saved time "
                f"{self._pub_publish_hour.currentText()}:{self._pub_publish_minute.currentText()}."
            )
        else:
            self._pub_schedule_summary.setText("This field only applies when visibility is set to Scheduled.")

    def _on_publication_visibility_changed(self) -> None:
        self._update_publication_schedule_visibility()
        self._on_publication_field_changed()

    def _profile_by_id(self, profile_id: object) -> ProfileResponse | None:
        if not profile_id:
            return None
        target = str(profile_id)
        for profile in self._profiles:
            if str(profile.id) == target:
                return profile
        return None

    def _upsert_profile_response(self, result: object) -> ProfileResponse | None:
        if not isinstance(result, ProfileResponse):
            return None
        self._profiles = [profile for profile in self._profiles if profile.id != result.id] + [result]
        return result

    def _set_selected_profile_id(self, profile_id: object) -> None:
        if not profile_id:
            return
        key = str(profile_id)
        if self._selected_profile_key == key:
            return
        self._selected_profile_key = key
        self._sync_profile_list_selection()
        self._bind_profiles_tab()
        self._bind_youtube_tab()
        self._bind_publication_tab()
        self._refresh_footer()

    def _sync_profile_list_selection(self) -> None:
        if not self._selected_profile_key or self._selected_profile_key == "new":
            return
        self._profile_list.blockSignals(True)
        for row in range(self._profile_list.count()):
            item = self._profile_list.item(row)
            if item is None:
                continue
            if str(item.data(Qt.ItemDataRole.UserRole)) == str(self._selected_profile_key):
                self._profile_list.setCurrentRow(row)
                break
        self._profile_list.blockSignals(False)

    def _load_publication_playlists(self) -> None:
        profile_id = self._publication_profile.currentData()
        connection = self._youtube_connection_for(profile_id)
        if not profile_id or not connection or connection.status != "connected":
            return
        profile_key = str(profile_id)
        if profile_key in self._playlist_auth_failed_profiles:
            return
        self._playlist_load_generation += 1
        generation = self._playlist_load_generation
        worker = YouTubePlaylistsWorker(self._api, str(profile_id), parent=self)
        worker.succeeded.connect(lambda payload, gen=generation: self._on_playlists_loaded(payload, gen))
        worker.failed.connect(lambda message, gen=generation: self._on_playlists_failed(message, gen))
        worker.finished.connect(lambda: setattr(self, "_playlists_worker", None))
        self._playlists_worker = worker
        worker.start()

    def _on_playlists_loaded(self, payload: object, generation: int) -> None:
        if generation != self._playlist_load_generation:
            return
        profile_id = self._publication_profile.currentData()
        if profile_id:
            self._playlist_auth_failed_profiles.discard(str(profile_id))
        playlists = getattr(payload, "playlists", None) or []
        current = self._publication_draft.playlist or self._pub_playlist.currentText()
        self._pub_playlist.blockSignals(True)
        self._pub_playlist.clear()
        self._pub_playlist.addItem("No playlist", "")
        for item in playlists:
            self._pub_playlist.addItem(getattr(item, "title", str(item)), getattr(item, "id", ""))
        index = self._pub_playlist.findText(current)
        if index >= 0:
            self._pub_playlist.setCurrentIndex(index)
        else:
            self._pub_playlist.setEditText(current)
        self._pub_playlist.blockSignals(False)

    def _on_playlists_failed(self, message: str, generation: int) -> None:
        if generation != self._playlist_load_generation:
            return
        lowered = message.lower()
        if "expired" in lowered or "revoked" in lowered or "invalid_grant" in lowered or "reconnect" in lowered:
            friendly = "YouTube sign-in expired for this profile. Reconnect from the YouTube tab."
            profile_id = self._publication_profile.currentData()
            if profile_id:
                self._playlist_auth_failed_profiles.add(str(profile_id))
            self._pub_status_note.setText(friendly)
            log_info(friendly, category="settings")
            self.refresh_data(force=True)
            return
        friendly = message or "Could not load YouTube playlists for this profile."
        self._pub_status_note.setText(friendly)
        log_error(friendly, category="settings")

    def _load_sample_packs(self, *, force: bool = False) -> None:
        if SERVER_MANAGED_SAMPLE_PACKS:
            return
        if self._sample_packs_worker is not None and self._sample_packs_worker.isRunning():
            return
        if not force:
            cached: list[object] | None = None
            if self._cache is not None and self._cache.is_image_sample_packs_fresh():
                cached = self._cache.snapshot_image_sample_packs()
            elif self._sample_packs and cache_entry_is_fresh(self._sample_packs_fetched_at):
                cached = self._sample_packs
            if cached is not None:
                self._on_sample_packs_loaded(cached)
                return
        worker = ImageSamplePacksWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_sample_packs_loaded)
        worker.failed.connect(lambda msg: self._show_error(msg or "Failed to reload packs."))
        worker.finished.connect(lambda: setattr(self, "_sample_packs_worker", None))
        self._sample_packs_worker = worker
        worker.start()

    def _on_sample_packs_loaded(self, payload: object) -> None:
        if isinstance(payload, list):
            packs = payload
        else:
            packs = getattr(payload, "items", None) or []
        self._sample_packs = list(packs)
        self._sample_packs_fetched_at = time.time()
        if self._cache is not None:
            self._cache.apply_image_sample_packs(self._sample_packs)
        self._bg_pack_combo.blockSignals(True)
        self._th_pack_combo.blockSignals(True)
        self._bg_pack_combo.clear()
        self._th_pack_combo.clear()
        self._bg_pack_combo.addItem("Select a background pack", "")
        self._th_pack_combo.addItem("Select a thumbnail pack", "")
        for pack in self._sample_packs:
            category = str(getattr(pack, "category", "")).lower().strip()
            name = getattr(pack, "name", "Pack")
            pack_id = getattr(pack, "id", "")
            if category in ("background", "bg", "bg_images", "backgrounds"):
                self._bg_pack_combo.addItem(str(name), pack_id)
            elif category in ("thumbnail", "th", "thumb", "thumbnails", "thumb_images"):
                self._th_pack_combo.addItem(str(name), pack_id)
        self._bg_pack_combo.blockSignals(False)
        self._th_pack_combo.blockSignals(False)
        self._update_sample_pack_install_buttons()

    def _refresh_sample_library_lists(self, *, force: bool = False) -> None:
        if SERVER_MANAGED_SAMPLE_PACKS:
            return
        bg_dir = self._pref_bg_samples_dir.text().strip()
        th_dir = self._pref_th_samples_dir.text().strip()
        scan_key = (bg_dir, th_dir)
        if not force:
            cached_scan: tuple[list[str], list[str]] | None = None
            if self._cache is not None and self._cache.is_sample_library_scan_fresh(bg_dir, th_dir):
                cached_scan = self._cache.snapshot_sample_library_scan(bg_dir, th_dir)
            elif scan_key in self._sample_library_scan_cache and cache_entry_is_fresh(
                self._sample_library_scan_fetched_at.get(scan_key, 0.0)
            ):
                cached_scan = self._sample_library_scan_cache[scan_key]
            if cached_scan is not None:
                self._bg_sample_files, self._th_sample_files = cached_scan
                self._apply_sample_library_lists()
                return
        self._bg_sample_files = list_directory_image_paths(bg_dir)
        self._th_sample_files = list_directory_image_paths(th_dir)
        self._sample_library_scan_cache[scan_key] = (list(self._bg_sample_files), list(self._th_sample_files))
        self._sample_library_scan_fetched_at[scan_key] = time.time()
        if self._cache is not None:
            self._cache.apply_sample_library_scan(
                bg_dir,
                th_dir,
                bg_files=self._bg_sample_files,
                th_files=self._th_sample_files,
            )
        self._apply_sample_library_lists()

    def _apply_sample_library_lists(self) -> None:
        self._populate_sample_list(self._bg_samples_list, self._bg_sample_files, self._system_draft.image_bg_samples)
        self._populate_sample_list(self._th_samples_list, self._th_sample_files, self._system_draft.image_thumb_samples)
        self._bg_selected_count.setText(f"Selected {len(self._system_draft.image_bg_samples)}/5")
        self._th_selected_count.setText(f"Selected {len(self._system_draft.image_thumb_samples)}/5")

    def _populate_sample_list(self, widget: QListWidget, files: list[str], selected: list[str]) -> None:
        widget.blockSignals(True)
        widget.clear()
        for path in files:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            if path in selected:
                item.setText(f"{item.text()} (Selected)")
            widget.addItem(item)
        widget.blockSignals(False)

    def _on_bg_sample_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return
        self._system_draft.image_bg_samples = toggle_library_sample(self._system_draft.image_bg_samples, path)
        self._refresh_sample_library_lists()
        self._on_system_field_changed()

    def _on_th_sample_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return
        self._system_draft.image_thumb_samples = toggle_library_sample(self._system_draft.image_thumb_samples, path)
        self._refresh_sample_library_lists()
        self._on_system_field_changed()

    def _set_pool_kind(self, kind: str) -> None:
        self._pool_kind = kind
        self._pool_offset = 0
        for key, button in self._pool_kind_buttons.items():
            button.setChecked(key == kind)
        self._load_pools()

    def _pool_prev_page(self) -> None:
        self._pool_offset = max(0, self._pool_offset - CONTENT_POOL_PAGE_SIZE)
        self._load_pools()

    def _pool_next_page(self) -> None:
        if self._pool_offset + CONTENT_POOL_PAGE_SIZE < self._pool_total:
            self._pool_offset += CONTENT_POOL_PAGE_SIZE
            self._load_pools()

    def _prompt_catalog_label(self, name: str, *, active: bool) -> str:
        base = str(name or "").replace(" · active", "").strip()
        return f"{base} · active" if active else base

    def _prompt_options_for_kind(self, kind: str) -> list[PromptNameOption]:
        if kind == "description":
            return self._description_options
        if kind == "mood":
            return self._mood_options
        return self._structure_options

    def _selected_prompt_id_for_kind(self, kind: str) -> str:
        if kind == "description":
            return self._selected_description_id
        if kind == "mood":
            return self._selected_mood_id
        return self._selected_structure_id

    def _set_selected_prompt_id_for_kind(self, kind: str, option_id: str) -> None:
        if kind == "description":
            self._selected_description_id = option_id
        elif kind == "mood":
            self._selected_mood_id = option_id
        else:
            self._selected_structure_id = option_id

    def _prompt_selector_for_kind(self, kind: str) -> QComboBox:
        if kind == "description":
            return self._description_selector
        if kind == "mood":
            return self._mood_selector
        return self._structure_selector

    def _prompt_list_for_kind(self, kind: str) -> QListWidget:
        if kind == "description":
            return self._descriptions_list
        if kind == "mood":
            return self._moods_list
        return self._structures_list

    def _prompt_selected_stat_for_kind(self, kind: str) -> QFrame:
        if kind == "description":
            return self._descriptions_selected_stat
        if kind == "mood":
            return self._moods_selected_stat
        return self._structures_selected_stat

    def _prompt_selected_name_for_kind(self, kind: str) -> QLineEdit:
        if kind == "description":
            return self._description_selected_name
        if kind == "mood":
            return self._mood_selected_name
        return self._structure_selected_name

    def _prompt_selection_note_for_kind(self, kind: str):
        if kind == "description":
            return self._description_selection_note
        if kind == "mood":
            return self._mood_selection_note
        return self._structure_selection_note

    def _prompt_catalog_stat_for_kind(self, kind: str) -> QFrame:
        if kind == "description":
            return self._descriptions_stat
        if kind == "mood":
            return self._moods_stat
        return self._structures_stat

    def _apply_active_music_prompt(self, kind: str, option_id: str) -> None:
        normalized = str(option_id or "").strip()
        options = self._prompt_options_for_kind(kind)
        if normalized and not any(option.id == normalized for option in options):
            return

        self._set_selected_prompt_id_for_kind(kind, normalized)

        selector = self._prompt_selector_for_kind(kind)
        select_index = selector.findData(normalized)
        if select_index >= 0:
            selector.blockSignals(True)
            selector.setCurrentIndex(select_index)
            selector.blockSignals(False)

        list_widget = self._prompt_list_for_kind(kind)
        matched_row = -1
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == normalized:
                matched_row = row
                break
        list_widget.blockSignals(True)
        list_widget.setCurrentRow(matched_row)
        list_widget.blockSignals(False)

        self._my_prompt_panel(kind).set_active_id(normalized)
        self._refresh_music_prompt_default_ui(kind)
        self._refresh_prompt_active_markers(kind)
        self._refresh_footer()

    def _refresh_music_prompt_default_ui(self, kind: str) -> None:
        options = self._prompt_options_for_kind(kind)
        active_id = self._selected_prompt_id_for_kind(kind)
        selected_stat = self._prompt_selected_stat_for_kind(kind)
        selected_name = self._prompt_selected_name_for_kind(kind)
        selected = next((option for option in options if option.id == active_id), None)
        label = self._prompt_option_label(selected) if selected is not None else "—"
        selected_name.setText(label)
        self._update_mini_stat_value(selected_stat, label)
        self._update_prompt_selection_note(kind, active_id or None)

    def _refresh_prompt_active_markers(self, kind: str) -> None:
        active_id = self._selected_prompt_id_for_kind(kind)
        options = self._prompt_options_for_kind(kind)
        catalog_options = [option for option in options if not option.is_owned]
        list_widget = self._prompt_list_for_kind(kind)
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            if item is None:
                continue
            option_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            option = next((entry for entry in catalog_options if entry.id == option_id), None)
            base_name = option.name if option is not None else str(item.text()).replace(" · active", "").strip()
            item.setText(self._prompt_catalog_label(base_name, active=option_id == active_id))
        self._my_prompt_panel(kind).set_active_id(active_id)

    def _prompt_selection_note_text(self, kind: str, option_id: str | None) -> str:
        options = self._prompt_options_for_kind(kind)
        selected = next((option for option in options if option.id == option_id), None)
        kind_label = {"description": "music description", "structure": "music structure", "mood": "music mood"}[kind]
        if not selected:
            return f"Select one {kind_label} from Camxora catalog or User catalog. Only one can be active."
        if selected.is_owned:
            return (
                f'Active default: your custom prompt "{selected.name}". '
                "Click Save All Changes to persist for the Music page."
            )
        if kind == "description":
            return (
                f'Active default: Camxora prompt "{selected.name}". '
                "Click Save All Changes to persist for the Music page."
            )
        if kind == "mood":
            return (
                f'Active default: Camxora mood "{selected.name}". '
                "Click Save All Changes to persist for the Music page."
            )
        return (
            f'Active default: Camxora structure "{selected.name}". '
            "Click Save All Changes to persist for the Music page."
        )

    def _update_prompt_selection_note(self, kind: str, option_id: str | None) -> None:
        note = self._prompt_selection_note_for_kind(kind)
        if note is not None:
            note.setText(self._prompt_selection_note_text(kind, option_id))

    def _on_text_library_selected(self, kind: str, row: int) -> None:
        list_widget = self._prompt_list_for_kind(kind)
        if row < 0:
            return
        item = list_widget.item(row)
        if item is None:
            return
        option_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self._apply_active_music_prompt(kind, option_id)

    def _on_text_library_combo_changed(self, kind: str) -> None:
        selector = self._prompt_selector_for_kind(kind)
        option_id = str(selector.currentData() or "")
        self._apply_active_music_prompt(kind, option_id)

    def _set_selected_structure(self, index: int) -> None:
        if index < 0:
            return
        option_id = self._description_structure_combo.itemData(index)
        if option_id:
            self._apply_active_music_prompt("structure", str(option_id))

    def _update_mini_stat_value(self, frame: QFrame, value: str) -> None:
        layout = frame.layout()
        if layout is None or layout.count() < 2:
            return
        label = layout.itemAt(1).widget()
        if isinstance(label, QLabel):
            label.setText(value)

    def _bind_profiles_tab(self) -> None:
        self._filter_profile_list()

        is_new = self._selected_profile_key == "new"
        profile = self._selected_profile() if not is_new else None
        if is_new:
            self._profile_draft = ProfileDraft()
        elif profile:
            self._profile_draft = self._resolve_profile_media_paths(profile, build_profile_draft(profile))
        else:
            self._profile_draft = ProfileDraft()
        self._baseline_profile_draft = build_profile_draft(profile)
        # Keep baseline paths aligned with resolved local cache paths for dirty checks.
        self._baseline_profile_draft.logo_path = self._profile_draft.logo_path
        self._baseline_profile_draft.cover_path = self._profile_draft.cover_path

        widgets = (
            self._profile_name,
            self._profile_folder,
            self._profile_prefix,
            self._profile_logo,
            self._profile_cover,
            self._profile_resolution,
            self._profile_image_mode,
            self._profile_video_template,
            self._profile_reel_template,
        )
        for widget in widgets:
            widget.blockSignals(True)

        self._populate_template_combos()
        # Re-block: populate_template_combos restores signals when it finishes.
        for widget in widgets:
            widget.blockSignals(True)
        self._profile_editor_title.setText(
            self._profile_draft.name or ("New profile" if is_new else "No profile selected")
        )
        self._profile_name.setText(self._profile_draft.name)
        self._profile_folder_user_edited = False
        self._profile_folder.setText(self._profile_draft.folder_name)
        self._sync_profile_folder_from_name()
        self._profile_prefix.setText(self._profile_draft.run_prefix)
        self._profile_logo.setText(self._profile_draft.logo_path)
        self._profile_cover.setText(self._profile_draft.cover_path)
        self._profile_resolution.setCurrentText(self._profile_draft.output_resolution)
        index = self._profile_image_mode.findData(self._profile_draft.image_mode)
        if index >= 0:
            self._profile_image_mode.setCurrentIndex(index)
        self._combo_set_by_data(self._profile_video_template, self._profile_draft.video_template_id)
        self._combo_set_by_data(self._profile_reel_template, self._profile_draft.reel_template_id)

        for widget in widgets:
            widget.blockSignals(False)

        self._on_profile_field_changed()
        self._refresh_profile_identity(is_new=is_new, profile=profile)
        can_create = False
        self._new_profile_btn.setEnabled(True)
        self._new_profile_btn.setText("Create profiles in portal")
        self._profile_cancel_btn.setVisible(False)
        self._profile_delete_btn.setEnabled(bool(profile))
        self._profile_save_btn.setText("Save Changes")
        self._profile_save_btn.setEnabled(bool(profile) and not is_new)
        self._start_profile_media_cache_download(profile)

    def _refresh_profile_identity(self, *, is_new: bool, profile: ProfileResponse | None) -> None:
        channel_title = self._profile_draft.name or (profile.name if profile else "No profile selected")
        if is_new:
            source_text = "Source: New inline profile"
            youtube_status_text = "Save this profile first before connecting a channel."
            youtube_connected = False
        else:
            source_text = "Source: Account profile"
            connection = self._youtube_connection_for(profile.id if profile else None)
            status = connection.status if connection else "not_connected"
            youtube_status_text = get_youtube_status_label(status)
            youtube_connected = status == "connected"
        self._profile_identity.set_identity(
            initials=get_profile_initials(channel_title),
            channel_title=channel_title,
            source_text=source_text,
            youtube_status_text=youtube_status_text,
            youtube_connected=youtube_connected,
        )

    def _bind_youtube_tab(self) -> None:
        self._binding_youtube_tab = True
        try:
            target_id = (
                self._selected_profile_key
                if self._selected_profile_key not in (None, "new")
                else None
            )
            self._youtube_profile.blockSignals(True)
            self._youtube_profile.clear()
            for profile in self._profiles:
                self._youtube_profile.addItem(profile.name, profile.id)
            if target_id:
                index = self._youtube_profile.findData(target_id)
                if index >= 0:
                    self._youtube_profile.setCurrentIndex(index)
            elif self._profiles:
                self._youtube_profile.setCurrentIndex(0)
            self._youtube_profile.blockSignals(False)

            profile_id = self._youtube_profile.currentData()
            profile = self._profile_by_id(profile_id)
            connection = self._youtube_connection_for(profile_id)
            status = connection.status if connection else "not_connected"
            status_label = get_youtube_status_label(status)
            self._update_mini_stat_value(self._youtube_connection_stat, status_label)
            self._update_mini_stat_value(self._youtube_profile_stat, profile.name if profile else "No profile")
            channel_count = len(connection.channels) if connection else 0
            if connection and connection.channel_id and channel_count == 0:
                channel_count = 1
            self._update_mini_stat_value(self._youtube_channels_stat, str(channel_count))
            session_label = {
                "pending_browser": "In progress",
                "awaiting_channel_selection": "Needs selection",
                "connected": "Ready",
            }.get(status, "Idle")
            self._update_mini_stat_value(self._youtube_session_stat, session_label)

            if connection and connection.channel_title:
                channel_text = connection.channel_title
                if connection.channel_id:
                    channel_text = f"{channel_text} ({connection.channel_id})"
            elif profile:
                channel_text = (
                    connection.message if connection and connection.message else "No YouTube channel is connected yet."
                )
            else:
                channel_text = "Select a profile to continue."
            self._youtube_channel_display.setText(channel_text)
            self._youtube_state_note.setText(
                connection.message
                if profile and connection and connection.message
                else (
                    "Select a profile first to review its YouTube connection state."
                    if not profile
                    else "No YouTube channel is connected yet."
                )
            )
            self._youtube_connected_note.setText(
                channel_text if connection and connection.channel_title else "No YouTube channel is connected yet."
            )
            self._youtube_connect_btn.setText(get_youtube_connect_button_label(status))
            self._youtube_connect_hint.setText(get_youtube_connect_hint(status))

            while self._youtube_channel_row_layout.count():
                item = self._youtube_channel_row_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._youtube_channel = QComboBox()
            if connection:
                for channel in connection.channels:
                    self._youtube_channel.addItem(channel.title, channel.id)
            if connection and connection.status == "awaiting_channel_selection":
                choose_row = QHBoxLayout()
                choose_row.addWidget(self._youtube_channel, stretch=1)
                self._youtube_select_btn = QPushButton("Attach Channel")
                self._youtube_select_btn.clicked.connect(self._select_youtube_channel)
                choose_row.addWidget(self._youtube_select_btn)
                host = QWidget()
                host.setLayout(choose_row)
                self._youtube_channel_row_layout.addWidget(form_row("Choose channel", host))

            self._youtube_connect_btn.setEnabled(bool(profile_id))
            self._youtube_disconnect_btn.setEnabled(bool(profile_id and status != "not_connected"))
            self._youtube_resync_btn.setEnabled(bool(profile_id and status == "connected"))
            if hasattr(self, "_youtube_select_btn"):
                self._youtube_select_btn.setEnabled(
                    bool(connection and connection.status == "awaiting_channel_selection" and connection.session_id)
                )
        finally:
            self._binding_youtube_tab = False

    def _bind_publication_tab(self) -> None:
        self._binding_publication_tab = True
        try:
            target_id = (
                self._selected_profile_key
                if self._selected_profile_key not in (None, "new")
                else None
            )
            self._publication_profile.blockSignals(True)
            self._publication_profile.clear()
            for profile in self._profiles:
                self._publication_profile.addItem(profile.name, profile.id)
            if target_id:
                index = self._publication_profile.findData(target_id)
                if index >= 0:
                    self._publication_profile.setCurrentIndex(index)
            elif self._profiles:
                self._publication_profile.setCurrentIndex(0)
            self._publication_profile.blockSignals(False)
            profile = self._profile_by_id(self._publication_profile.currentData())
            self._apply_publication_profile_data(profile)
        finally:
            self._binding_publication_tab = False

    def _apply_publication_profile_data(self, profile: ProfileResponse | None) -> None:
        is_new = self._selected_profile_key == "new"
        self._publication_draft = build_publication_draft(profile)
        self._baseline_publication_draft = build_publication_draft(profile)
        connection = self._youtube_connection_for(profile.id if profile else None)
        if is_new:
            youtube_text = "Save the new profile first before editing publication defaults."
        elif connection and connection.channel_title:
            youtube_text = f"{get_youtube_status_label(connection.status)}: {connection.channel_title}"
        else:
            youtube_text = get_youtube_status_label(connection.status if connection else "not_connected")
        self._pub_youtube_status.setText(youtube_text)
        dirty = not publication_draft_equal(self._publication_draft, self._baseline_publication_draft)
        self._pub_status_note.setText(
            "Publication settings are locked until the profile is saved."
            if is_new
            else ("You have unsaved publication changes." if dirty else "Publication defaults are up to date.")
        )

        pub_widgets = (
            self._pub_description,
            self._pub_keywords,
            self._pub_tags,
            self._pub_visibility,
            self._pub_publish_hour,
            self._pub_publish_minute,
            self._pub_category,
            self._pub_playlist,
            self._pub_ai_use,
            self._pub_title_template,
            self._pub_description_template,
            self._pub_made_for_kids,
        )
        for widget in pub_widgets:
            widget.blockSignals(True)

        self._pub_description.setPlainText(self._publication_draft.description)
        self._pub_keywords.setText(self._publication_draft.keywords)
        self._pub_tags.setText(self._publication_draft.tags)
        self._pub_visibility.setCurrentText(self._publication_draft.visibility)
        self._pub_publish_hour.setCurrentText(self._publication_draft.publish_hour)
        self._pub_publish_minute.setCurrentText(self._publication_draft.publish_minute)
        category_index = self._pub_category.findData(self._publication_draft.category)
        if category_index >= 0:
            self._pub_category.setCurrentIndex(category_index)
        self._pub_playlist.clear()
        self._pub_playlist.addItem("No playlist", "")
        self._pub_playlist.setEditText(self._publication_draft.playlist)
        self._pub_made_for_kids.setChecked(self._publication_draft.made_for_kids)
        ai_index = self._pub_ai_use.findData(self._publication_draft.ai_use)
        if ai_index >= 0:
            self._pub_ai_use.setCurrentIndex(ai_index)
        self._pub_title_template.setText(self._publication_draft.title_template)
        self._pub_description_template.setPlainText(self._publication_draft.description_template)

        for widget in pub_widgets:
            widget.blockSignals(False)

        self._update_publication_schedule_visibility()
        self._load_publication_playlists()

    def _on_send_diagnostics(self) -> None:
        if self._diag_sync_worker is not None and self._diag_sync_worker.isRunning():
            return
        payload = build_client_log_payload()
        if payload is None:
            self._diag_status.setText("Nothing to send yet — use the app a bit, then try again.")
            self._set_footer_notice("No log lines to send yet.", tone="warning")
            emit_shell_status("No log lines to send yet.")
            return
        line_count = int(payload.get("lineCount") or 0)
        self._send_diagnostics_btn.setEnabled(False)
        self._diag_status.setText(f"Sending {line_count} log line(s)…")
        self._set_footer_notice("Sending diagnostics…", tone="neutral")
        emit_shell_status("Sending diagnostics…")
        worker = SyncLogsWorker(self._api, payload, parent=self)
        worker.succeeded.connect(self._on_diagnostics_succeeded)
        worker.failed.connect(self._on_diagnostics_failed)
        worker.finished.connect(self._on_diagnostics_finished)
        self._diag_sync_worker = worker
        worker.start()

    def _on_diagnostics_succeeded(self, result: object) -> None:
        batch_id = ""
        if isinstance(result, dict):
            batch_id = str(result.get("id") or result.get("batchId") or "")
        msg = "Diagnostics sent to Camxora support."
        if batch_id:
            msg = f"Diagnostics sent · batch {batch_id[:8]}…"
        self._diag_status.setText(msg)
        self._set_footer_notice(msg, tone="success", auto_reset_ms=5000)
        emit_shell_status(msg)
        get_app_logger().info(f"Diagnostics upload succeeded ({batch_id or 'ok'})", category="log")

    def _on_diagnostics_failed(self, message: str) -> None:
        text = message or "Could not send diagnostics."
        self._diag_status.setText(text)
        self._set_footer_notice(text, tone="error")
        emit_shell_status(text)
        get_app_logger().error(f"Diagnostics upload failed: {text}", category="log")

    def _on_diagnostics_finished(self) -> None:
        self._send_diagnostics_btn.setEnabled(True)
        self._diag_sync_worker = None

    def _bind_preferences_tab(self) -> None:
        draft = self._system_draft
        self._pref_ffmpeg.setText(draft.ffmpeg_path)
        self._pref_suno_output.setText(draft.suno_output_dir)
        if not SERVER_MANAGED_SAMPLE_PACKS:
            self._pref_bg_samples_dir.setText(draft.image_background_samples_dir)
            self._pref_th_samples_dir.setText(draft.image_thumbnail_samples_dir)
            self._pref_image_output.setText(draft.image_output_dir)
        self._pref_music_workers.setValue(draft.perf_music_workers)
        self._pref_image_workers.setValue(draft.perf_image_workers)
        self._pref_export_workers.setValue(draft.perf_export_workers)
        self._pref_merge_workers.setValue(draft.perf_merge_workers)
        self._pref_youtube_workers.setValue(draft.perf_youtube_workers)
        chunk = str(draft.youtube_upload_chunk_size_mb)
        if self._pref_youtube_chunk.findText(chunk) < 0:
            self._pref_youtube_chunk.addItem(f"Current ({chunk} MB)", chunk)
        self._pref_youtube_chunk.setCurrentText(chunk)
        self._pref_style_strength.blockSignals(True)
        self._pref_style_strength.setValue(draft.style_strength)
        self._pref_style_strength.blockSignals(False)
        self._pref_style_strength_label.setText(f"{draft.style_strength} / 100")
        source_index = self._pref_image_source.findData(draft.image_source_mode)
        if source_index >= 0:
            self._pref_image_source.setCurrentIndex(source_index)
        bg_source_index = self._pref_background_source.findData(draft.image_background_source_mode)
        if bg_source_index >= 0:
            self._pref_background_source.setCurrentIndex(bg_source_index)
        th_source_index = self._pref_thumbnail_source.findData(draft.image_thumbnail_source_mode)
        if th_source_index >= 0:
            self._pref_thumbnail_source.setCurrentIndex(th_source_index)
        self._pref_thumbnail_overlay_mode = draft.thumbnail_overlay_mode or "ai"
        self._update_ai_reference_controls_visibility()
        self._pref_resolution.setCurrentText(draft.output_resolution)
        if not SERVER_MANAGED_SAMPLE_PACKS:
            self._pref_bg_random.setChecked(draft.image_bg_random)
            self._pref_th_random.setChecked(draft.image_thumb_random)
            self._refresh_sample_library_lists()

    def _bind_text_library_tab(self, kind: str) -> None:
        options = self._prompt_options_for_kind(kind)
        catalog_options = [option for option in options if not option.is_owned]
        my_count = sum(1 for option in options if option.is_owned)

        list_widget = self._prompt_list_for_kind(kind)
        selector = self._prompt_selector_for_kind(kind)
        catalog_stat = self._prompt_catalog_stat_for_kind(kind)
        my_stat = self._my_prompt_stat(kind)
        selected_stat = self._prompt_selected_stat_for_kind(kind)
        selected_id = self._selected_prompt_id_for_kind(kind)

        self._update_mini_stat_value(catalog_stat, str(len(catalog_options)))
        self._update_mini_stat_value(my_stat, str(my_count))

        list_widget.blockSignals(True)
        list_widget.clear()
        selector.blockSignals(True)
        selector.clear()
        for option in catalog_options:
            item = QListWidgetItem(option.name)
            item.setData(Qt.ItemDataRole.UserRole, option.id)
            list_widget.addItem(item)
        for option in options:
            selector.addItem(self._prompt_option_label(option), option.id)

        if kind == "description":
            self._description_structure_combo.blockSignals(True)
            self._description_structure_combo.clear()
            for option in self._structure_options:
                self._description_structure_combo.addItem(
                    self._prompt_option_label(option),
                    option.id,
                )
            structure_index = self._description_structure_combo.findData(self._selected_structure_id)
            if structure_index >= 0:
                self._description_structure_combo.setCurrentIndex(structure_index)
            self._description_structure_combo.blockSignals(False)

        selected_id = self._resolve_saved_prompt_id(options, selected_id)
        self._set_selected_prompt_id_for_kind(kind, selected_id)

        select_index = selector.findData(selected_id)
        if select_index >= 0:
            selector.setCurrentIndex(select_index)

        matched_row = -1
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == selected_id:
                matched_row = row
                break
        list_widget.setCurrentRow(matched_row)

        selected_label = selector.currentText() if select_index >= 0 else "—"
        self._prompt_selected_name_for_kind(kind).setText(selected_label)
        self._update_mini_stat_value(selected_stat, selected_label)
        self._update_prompt_selection_note(kind, selected_id or None)

        list_widget.blockSignals(False)
        selector.blockSignals(False)
        self._refresh_prompt_active_markers(kind)

    def _bind_suno_tab(self) -> None:
        draft = self._suno_draft
        widgets = (
            self._suno_version,
            self._suno_merge_enabled,
            self._suno_timeout,
            self._suno_retry,
            self._suno_merge_group,
        )
        for widget in widgets:
            widget.blockSignals(True)
        version = draft.suno_default_version or "v6"
        if self._suno_version.findText(version) < 0:
            self._suno_version.addItem(version)
        self._suno_version.setCurrentText(version)
        merge_index = self._suno_merge_enabled.findData(draft.suno_merge_enabled)
        if merge_index >= 0:
            self._suno_merge_enabled.setCurrentIndex(merge_index)
        self._suno_timeout.setValue(draft.suno_timeout_ms)
        self._suno_retry.setValue(draft.suno_retry_count)
        self._suno_merge_group.setValue(draft.suno_merge_group_size)
        for widget in widgets:
            widget.blockSignals(False)
        self._refresh_footer()

    def _load_pools(self, *, force: bool = False) -> None:
        if self._pool_worker is not None and self._pool_worker.isRunning():
            return
        cache_key = (self._pool_kind, self._pool_offset)
        if not force:
            cached: dict[str, object] | None = None
            if self._cache is not None and self._cache.is_content_pool_fresh(self._pool_kind, self._pool_offset):
                cached = self._cache.snapshot_content_pool(self._pool_kind, self._pool_offset)
            elif cache_key in self._pool_payload_cache and cache_entry_is_fresh(
                self._pool_payload_fetched_at.get(cache_key, 0.0)
            ):
                cached = self._pool_payload_cache[cache_key]
            if cached is not None:
                self._on_pools_loaded(cached)
                return
        worker = ContentPoolWorker(self._api, self._pool_kind, offset=self._pool_offset, parent=self)
        worker.succeeded.connect(self._on_pools_loaded)
        worker.finished.connect(lambda: setattr(self, "_pool_worker", None))
        self._pool_worker = worker
        worker.start()

    def _on_pools_loaded(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        cache_key = (self._pool_kind, self._pool_offset)
        self._pool_payload_cache[cache_key] = payload
        self._pool_payload_fetched_at[cache_key] = time.time()
        if self._cache is not None:
            self._cache.apply_content_pool(self._pool_kind, self._pool_offset, payload)
        stats = payload.get("stats")
        items = payload.get("items")
        self._pool_stats = stats
        for kind, stat_widget in (
            ("openings", self._pool_openings_stat),
            ("titles", self._pool_titles_stat),
            ("albums", self._pool_albums_stat),
        ):
            stat = getattr(stats, kind, None) if stats is not None else None
            if stat is not None:
                used = max(0, stat.total - stat.unused)
                self._update_mini_stat_value(stat_widget, f"{used} used / {stat.total}")
            else:
                self._update_mini_stat_value(stat_widget, "Unavailable")
        selected_stat = getattr(stats, self._pool_kind, None) if stats is not None else None
        if selected_stat is not None:
            used = max(0, selected_stat.total - selected_stat.unused)
            self._pool_current_note.setText(
                f"{selected_stat.total} total entries, {used} used, {selected_stat.unused} unused."
            )
        self._pool_total = getattr(items, "total", 0) if items is not None else 0
        page = self._pool_offset // CONTENT_POOL_PAGE_SIZE + 1
        total_pages = max(1, (self._pool_total + CONTENT_POOL_PAGE_SIZE - 1) // CONTENT_POOL_PAGE_SIZE)
        self._pool_page_label.setText(f"Page {page} / {total_pages}")
        self._pool_prev_btn.setEnabled(self._pool_offset > 0)
        self._pool_next_btn.setEnabled(self._pool_offset + CONTENT_POOL_PAGE_SIZE < self._pool_total)
        rows = []
        if items is not None:
            for item in getattr(items, "items", []):
                text = item.secondary_text if item.secondary_text else item.text
                if item.secondary_text:
                    text = f"{item.text} / {item.secondary_text}"
                rows.append([str(item.id), text, str(item.used_count), item.created_at or "—"])
        set_table_rows(self._pools_table, rows)

    def _on_profile_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self._profile_list.item(row)
        if item is None:
            return
        self._set_selected_profile_id(item.data(Qt.ItemDataRole.UserRole))

    def _on_youtube_profile_changed(self, index: int) -> None:
        if self._binding_youtube_tab or index < 0:
            return
        profile_id = self._youtube_profile.itemData(index)
        if profile_id:
            self._set_selected_profile_id(profile_id)

    def _on_new_profile_clicked(self) -> None:
        portal_url = f"{get_portal_base_url()}/dashboard/profiles"
        open_external_url(portal_url)
        QMessageBox.information(
            self,
            "Create profiles in portal",
            "New channel profiles are created in the CamXora account portal.\n\n"
            f"Open: {portal_url}\n\n"
            "After onboarding completes, refresh Settings to see new profiles here.",
        )

    def _start_new_profile(self) -> None:
        self._on_new_profile_clicked()

    def _on_clear_local_workspace(self) -> None:
        if self._session is None:
            self._show_error("Local workspace cleanup is unavailable.")
            return
        confirmed = QMessageBox.question(
            self,
            "Clear Local Workspace Data",
            "Remove saved desktop workspace layout for this account on this PC?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._session.forget_local_workspace()
        self._show_save_success("Local workspace data cleared for this account.")

    def _delete_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        confirmed = QMessageBox.question(
            self,
            "Delete Profile",
            f'Delete "{profile.name}"? Existing generated outputs stay on disk.',
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        worker = DeleteProfileWorker(self._api, profile.id, parent=self)
        worker.succeeded.connect(lambda *_: self._after_profile_deleted(profile.id))
        worker.failed.connect(lambda message: self._show_error(message))
        worker.start()

    def _after_profile_deleted(self, profile_id: str) -> None:
        self._profiles = [profile for profile in self._profiles if profile.id != profile_id]
        self._selected_profile_key = self._profiles[0].id if self._profiles else None
        self._show_save_success("Profile deleted.")
        self.refresh_data(force=True)

    def _sync_profile_folder_from_name(self) -> None:
        if self._profile_folder_user_edited:
            return
        slug = slugify_profile_folder_name(self._profile_name.text())
        self._profile_folder.blockSignals(True)
        self._profile_folder.setText(slug)
        self._profile_folder.blockSignals(False)

    def _on_profile_folder_edited(self) -> None:
        self._profile_folder_user_edited = True
        self._on_profile_field_changed()

    def _on_profile_field_changed(self) -> None:
        # Preserve staged base64 uploads while the user edits other fields.
        previous = self._profile_draft
        folder_name = (
            self._profile_folder.text()
            if self._profile_folder_user_edited
            else slugify_profile_folder_name(self._profile_name.text())
        )
        self._profile_draft = ProfileDraft(
            name=self._profile_name.text(),
            folder_name=folder_name,
            run_prefix=self._profile_prefix.text(),
            logo_path=self._profile_logo.text(),
            logo_base64=previous.logo_base64,
            cover_path=self._profile_cover.text(),
            cover_base64=previous.cover_base64,
            video_template_id=self._template_id_from_combo(self._profile_video_template),
            reel_template_id=self._template_id_from_combo(self._profile_reel_template),
            output_resolution=self._profile_resolution.currentText(),
            image_mode=self._profile_image_mode.currentData() or "bg_thumb",
        )
        self._profile_editor_title.setText(self._profile_draft.name or "New profile")
        self._refresh_profile_identity(is_new=self._selected_profile_key == "new", profile=self._selected_profile())
        self._refresh_footer()

    def _on_publication_profile_changed(self, index: int) -> None:
        if self._binding_publication_tab or index < 0:
            return
        profile_id = self._publication_profile.itemData(index)
        if not profile_id:
            return
        self._set_selected_profile_id(profile_id)

    def _on_publication_field_changed(self) -> None:
        self._publication_draft = PublicationDraft(
            description=self._pub_description.toPlainText(),
            keywords=self._pub_keywords.text(),
            tags=self._pub_tags.text(),
            visibility=self._pub_visibility.currentText(),
            publish_hour=self._pub_publish_hour.currentText(),
            publish_minute=self._pub_publish_minute.currentText(),
            made_for_kids=self._pub_made_for_kids.isChecked(),
            ai_use=bool(self._pub_ai_use.currentData()),
            category=str(self._pub_category.currentData() or "10"),
            playlist=self._pub_playlist.currentText(),
            title_template=self._pub_title_template.text(),
            description_template=self._pub_description_template.toPlainText(),
        )
        self._refresh_footer()

    def _on_system_field_changed(self) -> None:
        chunk_text = self._pref_youtube_chunk.currentText().split()[0]
        try:
            chunk_size = int(chunk_text)
        except ValueError:
            chunk_size = self._system_draft.youtube_upload_chunk_size_mb
        self._system_draft = SystemSettingsDraft(
            ffmpeg_path=self._pref_ffmpeg.text(),
            # Downloads / merged / image output are auto-defaults (not shown in Preferences).
            downloads_dir=self._system_draft.downloads_dir,
            suno_output_dir=self._pref_suno_output.text(),
            merged_dir=self._system_draft.merged_dir,
            image_output_dir=(
                self._system_draft.image_output_dir
                if SERVER_MANAGED_SAMPLE_PACKS
                else self._pref_image_output.text()
            ),
            image_background_samples_dir=(
                self._system_draft.image_background_samples_dir
                if SERVER_MANAGED_SAMPLE_PACKS
                else self._pref_bg_samples_dir.text()
            ),
            image_thumbnail_samples_dir=(
                self._system_draft.image_thumbnail_samples_dir
                if SERVER_MANAGED_SAMPLE_PACKS
                else self._pref_th_samples_dir.text()
            ),
            perf_music_workers=self._pref_music_workers.value(),
            perf_image_workers=self._pref_image_workers.value(),
            perf_export_workers=self._pref_export_workers.value(),
            perf_merge_workers=self._pref_merge_workers.value(),
            perf_youtube_workers=self._pref_youtube_workers.value(),
            youtube_upload_chunk_size_mb=chunk_size,
            style_strength=self._pref_style_strength.value(),
            image_source_mode=self._pref_image_source.currentData() or "ai",
            output_resolution=self._pref_resolution.currentText(),
            image_background_source_mode=self._pref_background_source.currentData() or "category",
            image_thumbnail_source_mode=self._pref_thumbnail_source.currentData() or "category",
            thumbnail_overlay_mode=self._pref_thumbnail_overlay_mode or "ai",
            image_bg_random=self._system_draft.image_bg_random if SERVER_MANAGED_SAMPLE_PACKS else self._pref_bg_random.isChecked(),
            image_thumb_random=self._system_draft.image_thumb_random if SERVER_MANAGED_SAMPLE_PACKS else self._pref_th_random.isChecked(),
            image_bg_samples=self._system_draft.image_bg_samples,
            image_thumb_samples=self._system_draft.image_thumb_samples,
        )
        self._refresh_footer()

    def _on_suno_field_changed(self) -> None:
        previous = self._suno_draft
        self._suno_draft = SunoSettingsDraft(
            suno_callback_url=previous.suno_callback_url,
            suno_timeout_ms=self._suno_timeout.value(),
            suno_retry_count=self._suno_retry.value(),
            suno_default_version=self._suno_version.currentText(),
            suno_merge_enabled=bool(self._suno_merge_enabled.currentData()),
            suno_merge_group_size=self._suno_merge_group.value(),
            suno_credits_reserve=previous.suno_credits_reserve,
            suno_credits_cost_music=previous.suno_credits_cost_music,
            suno_credits_cost_lyrics=previous.suno_credits_cost_lyrics,
        )
        self._refresh_footer()

    def _save_all(self) -> None:
        dirty = self._dirty_tabs()
        if not dirty:
            self._show_save_success("No changes to save.")
            return
        if "Profiles" in dirty:
            self._save_profile()
        if "Publication" in dirty:
            self._save_publication()
        if "Preferences" in dirty:
            self._save_system_settings()
        if "Suno" in dirty:
            self._save_suno_settings()
        if self._music_prompt_defaults_patch():
            self._save_music_prompt_defaults()

    def _save_music_prompt_defaults(self) -> None:
        patch = self._music_prompt_defaults_patch()
        if not patch:
            return
        worker = PatchSettingsWorker(self._api, patch, parent=self)
        worker.succeeded.connect(self._after_music_prompt_defaults_saved)
        worker.failed.connect(self._show_error)
        worker.start()
        self._patch_worker = worker

    def _after_music_prompt_defaults_saved(self, settings: object) -> None:
        if hasattr(settings, "model_dump"):
            self._settings_raw = settings.model_dump(by_alias=True)
        elif isinstance(settings, dict):
            self._settings_raw = settings
        self._load_music_prompt_defaults_from_settings()
        self._sync_music_prompt_defaults_to_local_store()
        if self._cache is not None:
            self._cache.apply_settings_workspace(settings_raw=self._settings_raw)
        self._bind_text_library_tab("description")
        self._bind_text_library_tab("structure")
        self._bind_text_library_tab("mood")
        self._show_save_success("Saved Music defaults.")
        log_info("Saved Music defaults.", category="settings")
        self._refresh_footer()

    def _save_profile(self) -> None:
        if self._selected_profile_key in (None, "new"):
            self._on_new_profile_clicked()
            return
        profile = self._selected_profile()
        payload = build_profile_payload(self._profile_draft, profile)
        worker = SaveProfileWorker(
            self._api,
            profile_id=self._selected_profile_key,
            payload=payload,
            parent=self,
        )
        worker.succeeded.connect(self._on_profile_saved)
        worker.failed.connect(self._show_error)
        worker.start()
        self._save_profile_worker = worker

    def _on_profile_saved(self, result: object) -> None:
        profile = self._upsert_profile_response(result)
        if profile is not None:
            self._selected_profile_key = profile.id
        self._show_save_success("Saved Profiles.")
        log_info("Saved Profiles.", category="settings")
        self.refresh_data(force=True)

    def _save_publication(self) -> None:
        profile_id = self._publication_profile.currentData()
        profile = self._profile_by_id(profile_id)
        if not profile:
            return
        youtube_config = build_publication_payload(self._publication_draft, dict(profile.youtube_config or {}))
        worker = SaveProfileWorker(
            self._api,
            profile_id=profile.id,
            payload={"youtube_config": youtube_config},
            parent=self,
        )
        worker.succeeded.connect(self._after_publication_saved)
        worker.failed.connect(self._show_error)
        worker.start()

    def _after_publication_saved(self, result: object) -> None:
        profile = self._upsert_profile_response(result)
        if profile is not None:
            self._selected_profile_key = profile.id
            self._apply_publication_profile_data(profile)
        self._show_save_success("Saved Publication.")
        log_info("Saved Publication.", category="settings")
        self.refresh_data(force=True)

    def _persist_device_media_paths_from_draft(self, draft: SystemSettingsDraft | None = None) -> None:
        from shared.lib.device_workspace_paths import persist_device_paths_from_settings
        from shared.lib.settings_workspace import device_paths_dict_from_draft
        from shared.lib.workspace_defaults import ensure_directory

        source = draft or self._system_draft
        payload = device_paths_dict_from_draft(source)
        persist_device_paths_from_settings(payload)
        suno = str(payload.get("sunoOutputDir") or "").strip()
        if suno:
            ensure_directory(suno)

    def _save_system_settings(self) -> None:
        from shared.lib.settings_workspace import device_media_paths_dirty

        paths_changed = device_media_paths_dirty(self._system_draft, self._settings_raw)
        if paths_changed:
            # Device store is authoritative — write the draft the user sees, never the API body.
            self._persist_device_media_paths_from_draft(self._system_draft)

        patch = build_system_settings_patch(
            self._system_draft,
            self._settings_raw,
            exclude_sample_pack_settings=SERVER_MANAGED_SAMPLE_PACKS,
        )
        if not patch and not paths_changed:
            return
        if not patch and paths_changed:
            self._after_local_paths_saved()
            return
        worker = PatchSettingsWorker(self._api, patch, parent=self)
        worker.succeeded.connect(lambda settings: self._after_settings_saved(settings, "Preferences"))
        worker.failed.connect(self._show_error)
        worker.start()
        self._patch_worker = worker

    def _save_suno_settings(self) -> None:
        patch = build_suno_settings_patch(self._suno_draft, self._settings_raw)
        if not patch:
            return
        worker = PatchSettingsWorker(self._api, patch, parent=self)
        worker.succeeded.connect(lambda settings: self._after_settings_saved(settings, "Suno"))
        worker.failed.connect(self._show_error)
        worker.start()
        self._patch_worker = worker

    def _after_local_paths_saved(self) -> None:
        """Preferences save that only changed device-local media roots (no API patch)."""
        self._persist_device_media_paths_from_draft(self._system_draft)
        try:
            from shared.services.music_download_coordinator import get_music_download_coordinator

            coordinator = get_music_download_coordinator()
            if coordinator is not None:
                coordinator.request_poll()
        except Exception:
            pass
        # Rebuild from cloud + device overlay so the UI matches what downloads will use.
        self._system_draft = build_system_settings_draft(self._settings_raw)
        self._baseline_system_draft = build_system_settings_draft(self._settings_raw)
        self._show_save_success("Saved Preferences.")
        log_info("Saved Preferences (local media paths).", category="settings")
        self._bind_preferences_tab()
        self._refresh_footer()

    def _after_settings_saved(self, settings: object, label: str) -> None:
        # Capture Preferences draft before settings_raw refresh — API must not wipe device paths.
        saved_system_draft = self._system_draft
        if hasattr(settings, "model_dump"):
            self._settings_raw = settings.model_dump(by_alias=True)
        self._persist_device_media_paths_from_draft(saved_system_draft)
        try:
            from shared.services.music_download_coordinator import get_music_download_coordinator

            coordinator = get_music_download_coordinator()
            if coordinator is not None:
                coordinator.request_poll()
        except Exception:
            pass
        self._system_draft = build_system_settings_draft(self._settings_raw)
        self._baseline_system_draft = build_system_settings_draft(self._settings_raw)
        self._suno_draft = build_suno_settings_draft(self._settings_raw)
        self._baseline_suno_draft = build_suno_settings_draft(self._settings_raw)
        self._show_save_success(f"Saved {label}.")
        log_info(f"Saved {label}.", category="settings")
        self._bind_preferences_tab()
        self._bind_suno_tab()

    def _start_youtube_connection(self) -> None:
        profile_id = self._youtube_profile.currentData()
        if not profile_id:
            return
        worker = YouTubeActionWorker(self._api, "start", profile_id=profile_id, parent=self)
        worker.succeeded.connect(self._on_youtube_started)
        worker.failed.connect(self._show_error)
        worker.start()
        self._youtube_worker = worker

    def _on_youtube_started(self, payload: object) -> None:
        auth_url = getattr(payload, "auth_url", None)
        if auth_url:
            webbrowser.open(str(auth_url))
        profile_id = self._youtube_profile.currentData()
        self._youtube_poll_profile_id = str(profile_id) if profile_id else None
        self._status_message = "YouTube browser sign-in started."
        self.refresh_data(force=True)
        self._sync_youtube_poll_timer()

    def _disconnect_youtube(self) -> None:
        profile_id = self._youtube_profile.currentData()
        if not profile_id:
            return
        worker = YouTubeActionWorker(self._api, "disconnect", profile_id=profile_id, parent=self)
        worker.succeeded.connect(lambda *_: self.refresh_data(force=True))
        worker.failed.connect(self._show_error)
        worker.start()

    def _resync_youtube(self) -> None:
        profile_id = self._youtube_profile.currentData()
        if not profile_id:
            return
        worker = YouTubeActionWorker(self._api, "resync", profile_id=profile_id, parent=self)
        worker.succeeded.connect(self._on_youtube_resynced)
        worker.failed.connect(self._show_error)
        worker.start()

    def _on_youtube_resynced(self, *_args: object) -> None:
        self._show_save_success("Resynced the connected YouTube channel data.")
        self.refresh_data(force=True)

    def _select_youtube_channel(self) -> None:
        profile_id = self._youtube_profile.currentData()
        connection = self._youtube_connection_for(profile_id)
        channel_id = self._youtube_channel.currentData()
        if not connection or not connection.session_id or not channel_id:
            return
        worker = YouTubeActionWorker(
            self._api,
            "select",
            session_id=connection.session_id,
            channel_id=channel_id,
            parent=self,
        )
        worker.succeeded.connect(lambda *_: self.refresh_data(force=True))
        worker.failed.connect(self._show_error)
        worker.start()

    def _show_error(self, message: str) -> None:
        self._set_footer_notice(message, tone="error")
        self._error_banner.set_message(message)
        self._error_banner.show()
        if message:
            log_error(message, category="settings")
