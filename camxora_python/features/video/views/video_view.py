"""Video workspace page — Phase 9a shell with template CRUD and draft save."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.logo_spectrum_bindings import (
    apply_logo_shape_draft_change,
    apply_logo_size_draft_change,
    apply_spectrum_attach_to_logo_draft_change,
)
from features.video.lib.spectrum_color_engine import (
    apply_spectrum_layer_color_patch,
    get_spectrum_layer_color_fallback,
)
from features.video.lib.particle_style_registry import (
    build_builtin_particle_preset_patch,
    build_unified_particle_preset_options,
    is_builtin_particle_preset_key,
    parse_pack_preset_key,
    resolve_active_particle_preset_key,
)
from features.video.lib.background_style_registry import (
    background_patch_touches_preset_fields,
    build_unified_background_preset_options,
    capture_background_preset,
    is_builtin_background_preset_key,
    resolve_background_preset_patch,
    restore_background_preset_to_factory,
)
from features.video.lib.logo_style_registry import (
    build_unified_logo_preset_options,
    capture_logo_preset,
    is_builtin_logo_preset_key,
    logo_patch_touches_preset_fields,
    resolve_logo_preset_patch,
    restore_logo_preset_to_factory,
)
from features.video.lib.particle_session_presets import (
    capture_session_particle_preset,
    particle_patch_touches_preset_fields,
    restore_particle_preset_to_factory,
)
from features.video.lib.spectrum_session_presets import (
    capture_session_spectrum_preset,
    get_session_spectrum_preset,
    is_session_spectrum_preset_key,
    restore_spectrum_preset_to_factory,
    spectrum_patch_touches_preset_fields,
)
from features.video.lib.spectrum_style_registry import (
    STACKED_LAYER_PRESETS,
    STYLE_PRESET_PATCHES,
    align_spectrum_layers_to_style_geometry,
    build_spectrum_preset_template,
    build_stacked_spectrum_preset_template,
    build_unified_spectrum_preset_options,
    heal_spectrum_layer_visibility,
    normalize_spectrum_preset_key_for_apply,
)
from features.video.lib.template_draft_domains import build_draft_dirty_state
from features.video.lib.text_editor import (
    TextCaseMode,
    add_text_overlay,
    apply_text_anchor_alignment,
    apply_text_case,
    delete_text_overlay,
    duplicate_text_overlay,
    move_text_overlay,
    resolve_selected_text_overlay_index,
    update_text_overlay_at,
)
from features.video.lib.text_style_registry import (
    apply_resolved_text_preset,
    capture_text_preset,
    is_builtin_text_preset_key,
    restore_text_preset_to_factory,
)
from features.video.lib.text_overlay_presets import clone_text_overlays
from features.video.lib.video_template_draft import (
    build_video_template_draft,
    clone_layer_records,
    draft_snapshot,
)
from features.video.lib.video_template_save import build_video_workspace_template_save_patch
from features.video.lib.effect_pack_draft_state import (
    apply_particle_pack_as_preset,
    apply_spectrum_pack_as_preset,
    build_applied_effect_pack_draft_state,
    build_cleared_effect_pack_draft_state,
)
from features.video.lib.effect_pack_runtime import (
    build_effect_pack_catalog_options,
    parse_effect_pack_catalog_value,
    resolve_effect_pack_selection_status,
    selection_to_value,
)
from features.video.export_gate import export_gate
from features.video.services.effect_pack_service import EffectPackService
from features.video.lib.video_workspace_diagnostics import (
    build_video_workspace_diagnostics,
    build_video_workspace_diagnostics_payload,
    serialize_diagnostics_payload,
)
from features.video.lib.preview_edit_modes import resolve_preview_edit_modes
from features.video.lib.pipeline_inputs import (
    build_video_pipeline_run_key,
    resolve_video_pipeline_inputs,
)
from features.video.lib.pipeline_merge import (
    collect_verified_merge_inputs,
    is_auto_merge_enabled_for_branch,
    merge_encode_settings_from_context,
    resolve_merge_encode_settings,
)
from features.video.lib.video_billing import consume_video_operation, refund_video_operation
from features.video.lib.export_telemetry import collect_hardware_hints, report_video_telemetry_async
from features.video.lib.render_scene_request import (
    PIPELINE_EXPORT_FPS,
    build_manual_render_scene_request,
    build_pipeline_export_output_path,
    build_pipeline_render_scene_request,
    normalize_export_fps,
)
from features.video.services.template_normalizer import TemplateNormalizer
from features.video.services.video_local_store import VideoLocalStore
from features.video.services.video_draft_store import (
    clear_video_workspace_draft_snapshot,
    read_video_workspace_draft_snapshot,
    write_video_workspace_draft_snapshot,
)
from features.video.widgets.background_inspector import BackgroundInspector
from features.video.widgets.export_queue_panel import ExportQueuePanel
from features.video.widgets.effect_pack_selector import EffectPackSelector
from features.video.widgets.diagnostics_panel import VideoWorkspaceDiagnosticsPanel
from features.video.widgets.left_rail import VideoLeftRail
from features.video.widgets.logo_inspector import LogoInspector
from features.video.widgets.particles_inspector import ParticlesInspector
from features.video.widgets.spectrum_inspector import SpectrumInspector
from features.video.widgets.lightning_inspector import LightningInspector
from features.video.widgets.right_rail import VideoRightRail
from features.video.widgets.stage_panel import VideoStagePanel
from features.video.widgets.text_domain_inspectors import AlbumInspector, TitleInspector
from features.video.lib.text_domain_registry import (
    capture_text_domain_preset,
    draft_style_snapshot,
    is_builtin_text_domain_preset,
    resolve_text_domain_preset_style,
    restore_text_domain_preset,
    style_patch_for_domain,
)
from features.video.lib.text_domain_runtime import (
    measure_album_layout_bounds,
    measure_title_layout_bounds,
    resolve_album_display_text,
    resolve_title_display_list,
)
from features.video.lib.track_display_name import format_title_marker, track_titles_from_paths
from features.video.lib.text_domain_registry import (
    album_settings_from_draft,
    title_settings_from_draft,
)
from shared.lib.export_codec import format_export_status_message, normalize_export_speed_mode
from shared.lib.export_tiers import normalize_export_tier, resolve_export_tier_settings
from shared.lib.page_account_scope import account_cache_mismatch, cached_user_id
from shared.models.desktop import (
    VideoExportState,
    VideoPlaybackState,
    VideoTemplateSummary,
    VideoWorkspaceState,
)
from shared.models.platform import ProgressRow
from shared.services.platform_api import PlatformApi
from shared.services.app_logger import log_error
from shared.services.action_feedback import notify_action
from shared.services.shell_status import restore_shell_status
from shared.services.video_template_catalog import emit_video_template_catalog_changed
from shared.services.video_pipeline_activity import track_video_pipeline_thread
from shared.services.video_workspace_service import get_video_workspace_service
from shared.services.workspace_cache import WorkspaceCache
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, VIDEO_WORKSPACE_ID
from shared.widgets.wheel_guard import guard_page_wheel_controls
from shared.workers.data_workers import PatchSettingsWorker, VideoPatchTemplateWorker, VideoWorkspaceWorker
from features.video.workers.manual_export_worker import ManualExportRequest, VideoManualExportWorker
from features.video.workers.pipeline_export_worker import PipelineExportRequest, VideoPipelineExportWorker
from features.video.workers.pipeline_merge_worker import PipelineMergeRequest, VideoPipelineMergeWorker
from features.video.workers.video_billing_worker import VideoBillingWorker
from features.video.workers.video_template_sync_worker import VideoTemplateSyncWorker

LOADING_MESSAGE = "Loading video workspace..."

# Left rail needs room for domain tabs + dense inspectors; right rail needs
# room for Album/Title style controls (fill mode, glow, gradients) without clipping.
VIDEO_RAIL_WIDTH = 420
VIDEO_RIGHT_RAIL_WIDTH = 380

# Diagnostics panel is dev-oriented; keep hidden in the default workspace UI.
SHOW_VIDEO_WORKSPACE_DIAGNOSTICS = False

EFFECT_PACK_DOMAIN_LABELS: dict[str, tuple[str, str]] = {
    "spectrum": (
        "Spectrum Pack",
        "Install and preview spectrum packs in the local workspace draft.",
    ),
    "background": (
        "Background Pack",
        "Install and apply background packs to the local draft.",
    ),
    "logo": (
        "Logo Pack",
        "Install and apply logo packs to the local draft.",
    ),
    "particles": (
        "Particles Pack",
        "Install and apply particle packs to the local draft.",
    ),
    "album": (
        "Album Pack",
        "Install and apply album text packs to the local draft.",
    ),
    "title": (
        "Playlist Pack",
        "Install and apply playlist-list packs to the local draft.",
    ),
}


class VideoView(QWidget):
    def __init__(
        self,
        api: PlatformApi,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(VIDEO_WORKSPACE_ID)
        self._api = api
        self._cache = cache
        self._store = VideoLocalStore()
        self._workspace: VideoWorkspaceState | None = None
        self._settings: dict[str, object] = {}
        self._template_draft: dict | None = None
        self._persisted_draft_snapshot = ""
        self._template_name_draft = ""
        self._active_particle_preset_key: str | None = None
        self._active_spectrum_preset_key: str | None = None
        self._active_background_preset_key: str | None = None
        self._active_logo_preset_key: str | None = None
        self._active_text_preset_key: str | None = None
        self._active_album_preset_key: str | None = None
        self._active_title_preset_key: str | None = None
        self._spectrum_layers: list[dict] = []
        self._selected_spectrum_layer_index = 0
        self._spectrum_instances: list[dict] = []
        self._selected_spectrum_instance_index = 0
        self._lightning_layers: list[dict] = []
        self._selected_lightning_layer_index = 0
        self._selected_text_overlay_index = 0
        self._active_domain_tab = "spectrum"
        self._active_side_tab = "album"
        self._preview_edit_focus = "domain"
        self._loading = True
        self._ever_loaded = False
        self._loaded_user_id: str | None = None
        self._is_error = False
        self._saving = False
        self._deleting = False
        self._pending_preview_auto_play = False
        self._worker: VideoWorkspaceWorker | None = None
        self._patch_worker: VideoPatchTemplateWorker | None = None
        self._template_sync_worker: VideoTemplateSyncWorker | None = None
        self._effect_pack_service = EffectPackService()
        self._effect_pack_catalog_items: list[dict] = []
        self._effect_pack_busy = False
        self._effect_pack_selectors: dict[str, EffectPackSelector] = {}
        self._template_normalizer = TemplateNormalizer()
        self._export_worker: VideoManualExportWorker | None = None
        self._pipeline_export_worker: VideoPipelineExportWorker | None = None
        self._pipeline_merge_worker: VideoPipelineMergeWorker | None = None
        self._billing_worker: VideoBillingWorker | None = None
        self._pipeline_merge_context: dict[str, object] | None = None
        self._video_billing_charge: dict[str, object] = {}
        self._merge_billing_charge: dict[str, object] = {}
        self._settings_patch_worker: PatchSettingsWorker | None = None
        self._pending_manual_billing: dict[str, object] | None = None
        self._resolution_save_pending = False
        self._export_start_pending = False
        self._pipeline_start_pending = False
        self._stop_export_pending = False
        self._pipeline_rows: list[ProgressRow] = []
        self._selected_pipeline_run_key = ""
        self._batch_queue: list[str] = []
        self._batch_total = 0
        self._batch_completed = 0
        self._batch_failures = 0
        self._batch_output_dir = ""
        self._batch_outputs: list[str] = []
        self._selected_pipeline_branch = "long"
        # Keep finished workers alive until wait()+deleteLater (avoids QThread
        # "Destroyed while thread is still running" on Stop / page teardown).
        self._lingering_export_threads: list[QThread] = []
        self._preview_remount_pending = False
        self._refresh_force_hydrate = False
        self._diagnostics_panel: VideoWorkspaceDiagnosticsPanel | None = None
        self._diagnostics_timer: QTimer | None = None
        if SHOW_VIDEO_WORKSPACE_DIAGNOSTICS:
            self._diagnostics_timer = QTimer(self)
            self._diagnostics_timer.setInterval(2000)
            self._diagnostics_timer.timeout.connect(self._update_diagnostics_panel)
        self._preview_update_timer = QTimer(self)
        self._preview_update_timer.setSingleShot(True)
        self._preview_update_timer.setInterval(48)
        self._preview_update_timer.timeout.connect(self._flush_preview_update)
        self._preview_scrub_end_timer = QTimer(self)
        self._preview_scrub_end_timer.setSingleShot(True)
        self._preview_scrub_end_timer.setInterval(180)
        self._preview_scrub_end_timer.timeout.connect(self._end_preview_scrub)
        self._preview_scrubbing = False
        self._dirty_state_timer = QTimer(self)
        self._dirty_state_timer.setSingleShot(True)
        self._dirty_state_timer.setInterval(120)
        self._dirty_state_timer.timeout.connect(self._flush_dirty_state)
        self._stage_summary_timer = QTimer(self)
        self._stage_summary_timer.setSingleShot(True)
        self._stage_summary_timer.setInterval(150)
        self._stage_summary_timer.timeout.connect(self._update_stage_summary)
        # Rebinding every inspector on each slider tick is expensive; coalesce
        # interactive value changes and rebind once the user pauses.
        self._inspector_rebind_timer = QTimer(self)
        self._inspector_rebind_timer.setSingleShot(True)
        self._inspector_rebind_timer.setInterval(200)
        self._inspector_rebind_timer.timeout.connect(self._flush_inspector_rebind)
        self._draft_persist_timer = QTimer(self)
        self._draft_persist_timer.setSingleShot(True)
        self._draft_persist_timer.setInterval(200)
        self._draft_persist_timer.timeout.connect(self._persist_local_draft_snapshot)
        self._hydrated_template_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._loading_card = QFrame()
        self._loading_card.setObjectName("account_card")
        loading_layout = QVBoxLayout(self._loading_card)
        loading_label = QLabel(LOADING_MESSAGE)
        loading_label.setObjectName(SUBTITLE_LABEL_ID)
        loading_layout.addWidget(loading_label)
        root.addWidget(self._loading_card)
        if self._cache_has_mountable_workspace():
            self._loading_card.hide()

        self._content = QWidget()
        self._content.hide()
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self._spectrum_inspector = SpectrumInspector()
        self._spectrum_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._spectrum_inspector.preset_apply_requested.connect(self._apply_spectrum_preset)
        self._spectrum_inspector.preset_restore_requested.connect(self._restore_spectrum_preset)
        self._spectrum_inspector.stacked_preset_apply_requested.connect(self._apply_stacked_spectrum_preset)
        self._spectrum_inspector.stacked_preset_clear_requested.connect(self._clear_stacked_spectrum_preset)
        self._spectrum_inspector.layer_patch_requested.connect(self._patch_selected_spectrum_layer)
        self._spectrum_inspector.layer_color_patch_requested.connect(self._patch_selected_spectrum_layer_color)
        self._spectrum_inspector.layer_add_requested.connect(self._add_spectrum_layer)
        self._spectrum_inspector.layer_duplicate_requested.connect(self._duplicate_spectrum_layer)
        self._spectrum_inspector.layer_delete_requested.connect(self._delete_spectrum_layer)
        self._spectrum_inspector.layer_move_up_requested.connect(self._move_spectrum_layer_up)
        self._spectrum_inspector.layer_move_down_requested.connect(self._move_spectrum_layer_down)
        self._spectrum_inspector.layer_selected.connect(self._select_spectrum_layer)
        self._spectrum_inspector.instance_selected.connect(self._select_spectrum_instance)
        self._spectrum_inspector.instance_add_requested.connect(self._add_spectrum_instance)
        self._spectrum_inspector.instance_duplicate_requested.connect(self._duplicate_spectrum_instance)
        self._spectrum_inspector.instance_delete_requested.connect(self._delete_spectrum_instance)
        self._spectrum_inspector.instance_move_up_requested.connect(self._move_spectrum_instance_up)
        self._spectrum_inspector.instance_move_down_requested.connect(self._move_spectrum_instance_down)
        self._spectrum_inspector.instance_patch_requested.connect(self._patch_selected_spectrum_instance)

        self._background_inspector = BackgroundInspector()
        self._background_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._background_inspector.preset_apply_requested.connect(self._apply_background_preset)
        self._background_inspector.preset_restore_requested.connect(self._restore_background_preset)
        self._background_inspector.reset_transform_requested.connect(self._reset_background_transform)
        self._background_inspector.select_background_requested.connect(self._select_background)

        self._logo_inspector = LogoInspector()
        self._logo_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._logo_inspector.preset_apply_requested.connect(self._apply_logo_preset)
        self._logo_inspector.preset_restore_requested.connect(self._restore_logo_preset)
        self._logo_inspector.logo_shape_apply_requested.connect(self._apply_logo_shape)
        self._logo_inspector.logo_size_apply_requested.connect(self._apply_logo_size)
        self._logo_inspector.spectrum_attach_toggle_requested.connect(self._toggle_spectrum_attachment)
        self._logo_inspector.spectrum_logo_gap_requested.connect(self._set_spectrum_logo_gap)
        self._logo_inspector.select_logo_requested.connect(self._select_logo)
        self._logo_inspector.logo_reset_center_requested.connect(self._reset_logo_center)

        self._particles_inspector = ParticlesInspector()
        self._particles_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._particles_inspector.preset_apply_requested.connect(self._apply_particle_preset)
        self._particles_inspector.preset_restore_requested.connect(self._restore_particle_preset)

        self._lightning_inspector = LightningInspector()
        self._lightning_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._lightning_inspector.preset_apply_requested.connect(self._apply_lightning_preset)
        self._lightning_inspector.layer_patch_requested.connect(self._patch_selected_lightning_layer)
        self._lightning_inspector.layer_add_requested.connect(self._add_lightning_layer)
        self._lightning_inspector.layer_duplicate_requested.connect(self._duplicate_lightning_layer)
        self._lightning_inspector.layer_delete_requested.connect(self._delete_lightning_layer)
        self._lightning_inspector.layer_move_up_requested.connect(self._move_lightning_layer_up)
        self._lightning_inspector.layer_move_down_requested.connect(self._move_lightning_layer_down)
        self._lightning_inspector.layer_selected.connect(self._select_lightning_layer)

        self._domain_inspectors = {
            "spectrum": self._spectrum_inspector,
            "background": self._background_inspector,
            "logo": self._logo_inspector,
            "particles": self._particles_inspector,
            "lightning": self._lightning_inspector,
        }
        for domain, inspector in self._domain_inspectors.items():
            if domain not in EFFECT_PACK_DOMAIN_LABELS:
                continue
            title, subtitle = EFFECT_PACK_DOMAIN_LABELS[domain]
            selector = EffectPackSelector(
                title=title,
                subtitle=subtitle,
                show_apply_combo=domain not in {"spectrum", "particles", "background", "logo", "lightning"},
            )
            selector.apply_requested.connect(
                lambda value, pack_domain=domain: self._apply_effect_pack(pack_domain, value)
            )
            selector.clear_requested.connect(
                lambda pack_domain=domain: self._clear_effect_pack(pack_domain)
            )
            selector.install_requested.connect(self._install_effect_pack)
            selector.reload_requested.connect(self._reload_effect_pack_catalog)
            selector.toggle_enabled_requested.connect(
                lambda pack_domain=domain: self._toggle_effect_pack_enabled(pack_domain)
            )
            selector.activate_requested.connect(
                lambda pack_domain=domain: self._activate_effect_pack_version(pack_domain)
            )
            selector.remove_requested.connect(
                lambda pack_domain=domain: self._remove_effect_pack_version(pack_domain)
            )
            inspector.mount_effect_pack_selector(selector)
            self._effect_pack_selectors[domain] = selector

        if SHOW_VIDEO_WORKSPACE_DIAGNOSTICS:
            panel = VideoWorkspaceDiagnosticsPanel()
            panel.remount_preview_requested.connect(self._remount_preview)
            panel.refresh_workspace_requested.connect(self._refresh_workspace_from_diagnostics)
            panel.reset_local_draft_requested.connect(self._reset_local_draft)
            panel.copy_diagnostics_requested.connect(self._copy_diagnostics)
            panel.toggled.connect(self._on_diagnostics_panel_toggled)
            self._diagnostics_panel = panel

        self._left_rail = VideoLeftRail(
            domain_pages=self._domain_inspectors,
            diagnostics_panel=self._diagnostics_panel,
        )
        self._stage = VideoStagePanel()
        self._stage.playback_command_requested.connect(self._issue_preview_playback_command)
        self._stage.playback_seek_requested.connect(self._seek_preview_playback)
        self._stage.spectrum_position_changed.connect(self._on_preview_spectrum_position_changed)
        self._stage.lightning_position_changed.connect(self._on_preview_lightning_position_changed)
        self._stage.logo_position_changed.connect(self._on_preview_logo_position_changed)
        self._stage.background_transform_changed.connect(self._on_preview_background_transform_changed)
        self._stage.text_domain_position_changed.connect(self._on_preview_text_domain_position_changed)
        self._stage.text_domain_box_resize_changed.connect(self._on_preview_text_domain_box_resize_changed)
        self._stage.text_domain_box_resized.connect(self._on_preview_text_domain_box_resized)
        self._stage.playback_state_changed.connect(self._on_preview_playback_state_changed)
        self._stage.output_resolution_changed.connect(self._save_output_resolution)
        self._stage.select_background_requested.connect(self._select_background)

        self._album_inspector = AlbumInspector()
        self._album_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._album_inspector.preset_apply_requested.connect(
            lambda preset: self._apply_text_domain_preset("album", preset)
        )
        self._album_inspector.preset_restore_requested.connect(
            lambda: self._restore_text_domain_preset("album")
        )

        self._title_inspector = TitleInspector()
        self._title_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._title_inspector.preset_apply_requested.connect(
            lambda preset: self._apply_text_domain_preset("title", preset)
        )
        self._title_inspector.preset_restore_requested.connect(
            lambda: self._restore_text_domain_preset("title")
        )

        for domain, inspector in (
            ("album", self._album_inspector),
            ("title", self._title_inspector),
        ):
            pack_title, pack_subtitle = EFFECT_PACK_DOMAIN_LABELS[domain]
            selector = EffectPackSelector(
                title=pack_title,
                subtitle=pack_subtitle,
                show_apply_combo=True,
            )
            selector.apply_requested.connect(
                lambda value, pack_domain=domain: self._apply_effect_pack(pack_domain, value)
            )
            selector.clear_requested.connect(
                lambda pack_domain=domain: self._clear_effect_pack(pack_domain)
            )
            selector.install_requested.connect(self._install_effect_pack)
            selector.reload_requested.connect(self._reload_effect_pack_catalog)
            selector.toggle_enabled_requested.connect(
                lambda pack_domain=domain: self._toggle_effect_pack_enabled(pack_domain)
            )
            selector.activate_requested.connect(
                lambda pack_domain=domain: self._activate_effect_pack_version(pack_domain)
            )
            selector.remove_requested.connect(
                lambda pack_domain=domain: self._remove_effect_pack_version(pack_domain)
            )
            inspector.mount_effect_pack_selector(selector)
            self._effect_pack_selectors[domain] = selector

        self._export_panel = ExportQueuePanel()
        self._export_panel.mp3_selected.connect(self._select_preview_mp3)
        self._export_panel.mp3_play_requested.connect(self._play_preview_mp3)
        self._export_panel.track_order_changed.connect(self._reorder_tracks)
        self._export_panel.select_mp3_requested.connect(self._pick_preview_mp3)
        self._export_panel.manual_export_requested.connect(self._start_manual_export)
        self._export_panel.stop_export_requested.connect(self._stop_active_export)
        self._export_panel.stop_merge_requested.connect(self._stop_active_export)
        self._export_panel.open_output_folder_requested.connect(self._open_export_output_folder)
        self._export_panel.open_output_file_requested.connect(self._open_export_output_file)
        self._export_panel.auto_merge_toggled.connect(self._set_auto_merge)
        self._export_panel.shuffle_merge_toggled.connect(self._set_shuffle_merge)
        self._export_panel.speed_mode_changed.connect(self._set_export_speed_mode)
        self._export_panel.export_resolution_changed.connect(self._set_export_resolution)
        self._export_panel.fps_changed.connect(self._set_export_fps)
        self._export_panel.workers_changed.connect(self._set_export_workers)
        # python_app layout: export queue console docks under the preview.
        self._stage.mount_export_panel(self._export_panel)

        self._right_rail = VideoRightRail(
            tab_pages={
                "album": self._album_inspector,
                "title": self._title_inspector,
            }
        )
        for rail, width in (
            (self._left_rail, VIDEO_RAIL_WIDTH),
            (self._right_rail, VIDEO_RIGHT_RAIL_WIDTH),
        ):
            rail.setMinimumWidth(width)
            rail.setMaximumWidth(width)
            policy = rail.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
            policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
            rail.setSizePolicy(policy)
        content_layout.addWidget(self._left_rail, stretch=0)
        content_layout.addWidget(self._stage, stretch=1)
        content_layout.addWidget(self._right_rail, stretch=0)
        self._content.hide()
        root.addWidget(self._content, stretch=1)

        self._left_rail.template_name_changed.connect(self._on_template_name_changed)
        self._left_rail.template_selected.connect(self._on_template_selected)
        self._left_rail.new_requested.connect(self._create_blank_template)
        self._left_rail.save_requested.connect(self._save_template)
        self._left_rail.delete_requested.connect(self._delete_template)
        self._left_rail.restore_original_requested.connect(self._restore_template_to_original)
        self._left_rail.export_requested.connect(self._export_template_for_marketplace)
        self._left_rail.domain_tab_changed.connect(self._on_domain_tab_changed)
        self._right_rail.side_tab_changed.connect(self._on_side_tab_changed)

        # Wheel over sliders/combos scrolls the panel unless the control is
        # focused, so casual scrolling can't change settings by accident.
        guard_page_wheel_controls(self)

        if self._try_mount_from_cache():
            self._loading_card.hide()

    def _mount_workspace(self, workspace: VideoWorkspaceState, settings: dict[str, object]) -> None:
        self._workspace = workspace
        self._settings = dict(settings)
        self._loading = False
        self._is_error = False
        self._loading_card.hide()
        self._content.show()
        self._hydrate_draft_from_workspace()
        self._refresh_effect_pack_catalog()
        get_video_workspace_service().set_workspace_state(self._workspace)
        self._render_workspace()
        self._ever_loaded = True
        self._loaded_user_id = cached_user_id(self._cache)
        # Show export button only for admin email
        self._update_export_button_visibility()

    def _cache_has_mountable_workspace(self) -> bool:
        settings_raw = self._cached_settings_raw()
        return bool(settings_raw)

    def _cached_settings_raw(self) -> dict[str, object]:
        if self._cache is None:
            return {}
        if self._cache.has_video_workspace():
            _workspace, settings = self._cache.snapshot_video_workspace()
            if settings:
                return dict(settings)
        _me, _profiles, settings_raw, _descriptions, _structures, _moods = self._cache.snapshot_core()
        return dict(settings_raw) if settings_raw else {}

    def _try_mount_from_cache(self) -> bool:
        if self._cache is not None and self._cache.has_video_workspace():
            workspace, settings = self._cache.snapshot_video_workspace()
            if workspace is not None and settings:
                self._mount_workspace(workspace, settings)
                return True
        settings_raw = self._cached_settings_raw()
        if not settings_raw:
            return False
        workspace = self._store.read_workspace_state(settings_raw)
        self._mount_workspace(workspace, settings_raw)
        if self._cache is not None:
            self._cache.apply_video_workspace(workspace, settings_raw)
        return True

    def _text_overlays(self) -> list[dict]:
        if not self._template_draft:
            return []
        overlays = self._template_draft.get("textOverlays")
        return clone_text_overlays(overlays)

    def _selected_text_overlay(self) -> dict | None:
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        if not overlays or index >= len(overlays):
            return None
        return overlays[index]

    def _set_text_overlays(
        self,
        overlays: list[dict],
        *,
        selected_index: int,
        defer_rebind: bool = False,
    ) -> None:
        if not self._template_draft:
            return
        self._template_draft = {**self._template_draft, "textOverlays": clone_text_overlays(overlays)}
        self._selected_text_overlay_index = selected_index
        self._update_inspectors(defer_rebind=defer_rebind)

    def _select_text_overlay(self, index: int) -> None:
        self._selected_text_overlay_index = max(0, index)
        self._update_inspectors()

    def _add_text_overlay(self) -> None:
        overlays = self._text_overlays()
        next_overlays, next_index = add_text_overlay(overlays)
        self._set_text_overlays(next_overlays, selected_index=next_index)

    def _duplicate_text_overlay(self) -> None:
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        if not overlays or index >= len(overlays):
            return
        next_overlays, next_index = duplicate_text_overlay(overlays, index)
        self._set_text_overlays(next_overlays, selected_index=next_index)

    def _delete_text_overlay(self) -> None:
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        if not overlays or index >= len(overlays):
            return
        next_overlays, next_index = delete_text_overlay(overlays, index)
        self._set_text_overlays(next_overlays, selected_index=next_index)

    def _move_text_overlay(self, direction: int) -> None:
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        if not overlays or index >= len(overlays):
            return
        moved = move_text_overlay(overlays, index, direction)
        if moved is None:
            return
        next_overlays, next_index = moved
        self._set_text_overlays(next_overlays, selected_index=next_index)

    def _apply_text_preset(self, preset: str) -> None:
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        if (
            is_builtin_text_preset_key(self._active_text_preset_key)
            and self._active_text_preset_key != preset
        ):
            capture_text_preset(
                self._active_text_preset_key,
                overlays=overlays,
                selected_index=index,
            )
        next_overlays, next_index = apply_resolved_text_preset(
            overlays,
            preset,
            selected_index=index,
        )
        if is_builtin_text_preset_key(preset):
            self._active_text_preset_key = preset
        self._set_text_overlays(next_overlays, selected_index=next_index)

    def _patch_selected_text_overlay(self, patch: dict) -> None:
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        selected = self._selected_text_overlay()
        if not selected:
            return
        next_overlays = update_text_overlay_at(overlays, index, {**selected, **patch})
        self._set_text_overlays(next_overlays, selected_index=index, defer_rebind=True)
        if is_builtin_text_preset_key(self._active_text_preset_key):
            capture_text_preset(
                self._active_text_preset_key,
                overlays=next_overlays,
                selected_index=index,
            )

    def _apply_text_case(self, mode: str) -> None:
        selected = self._selected_text_overlay()
        if not selected or mode not in {"upper", "lower", "title"}:
            return
        case_mode: TextCaseMode = mode  # type: ignore[assignment]
        self._patch_selected_text_overlay(
            {"text": apply_text_case(str(selected.get("text") or ""), case_mode)}
        )

    def _apply_text_anchor_alignment(self, alignment: str) -> None:
        selected = self._selected_text_overlay()
        if not selected or alignment not in {"left", "center", "right"}:
            return
        next_anchor = apply_text_anchor_alignment(str(selected.get("anchor") or "center"), alignment)
        self._patch_selected_text_overlay({"anchor": next_anchor})

    def _on_side_tab_changed(self, tab_key: str) -> None:
        self._active_side_tab = str(tab_key or "").strip().lower() or "album"
        self._preview_edit_focus = "side"
        self._update_inspectors()
        self._flush_preview_update()

    def _reset_for_account_change(self) -> None:
        self._loaded_user_id = None
        self._ever_loaded = False
        self._workspace = None
        self._template_draft = None
        self._settings = {}
        self._loading = True
        self._is_error = False
        self._loading_card.show()
        self._content.hide()
        get_video_workspace_service().set_workspace_state(None)

    def activate_page(self) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
        # Marketplace install invalidates the cached workspace; reload dropdown
        # so newly installed templates appear without remounting the draft.
        if (
            self._ever_loaded
            and self._workspace is not None
            and self._cache is not None
            and not self._cache.has_video_workspace()
        ):
            self.refresh_templates_from_store()
            return
        if self._ever_loaded and self._workspace is not None:
            return
        if self._try_mount_from_cache():
            return
        self.refresh_data()

    def refresh_templates_from_store(self) -> None:
        """Reload the template dropdown from disk without remounting an in-edit draft.

        Used after marketplace install so newly installed templates appear immediately
        when the Video page is already open or warm in the shell stack.
        """
        if self._workspace is None:
            if self._cache is not None:
                self._cache.invalidate_video_workspace()
            self.refresh_data(force=True)
            return

        raw = self._store.read_templates()
        summaries = [
            VideoTemplateSummary(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or "Untitled Template"),
                kind=str(item.get("source")) if item.get("source") else None,
                updated_at=str(item.get("updated_at") or "") or None,
            )
            for item in raw
            if item.get("id")
        ]
        self._workspace = self._workspace.model_copy(update={"templates": summaries})
        self._left_rail.set_templates(
            [(item.id, item.name) for item in summaries],
            self._workspace.template_id,
        )
        get_video_workspace_service().set_workspace_state(self._workspace)
        if self._cache is not None:
            self._cache.apply_video_workspace(self._workspace, self._settings)
        emit_video_template_catalog_changed()

    def deactivate_page(self) -> None:
        # Flush pending local draft so leaving Video mid-edit does not drop
        # the last ~200ms of changes across domain tabs.
        if self._draft_persist_timer.isActive():
            self._draft_persist_timer.stop()
            self._persist_local_draft_snapshot()
        if self._diagnostics_timer is not None:
            self._diagnostics_timer.stop()
        restore_shell_status()

    def refresh_data(self, *, force: bool = False) -> None:
        if account_cache_mismatch(self._loaded_user_id, self._cache):
            self._reset_for_account_change()
            force = True
        if self._worker is not None and self._worker.isRunning():
            return
        if not force and self._ever_loaded and self._workspace is not None:
            return

        self._refresh_force_hydrate = force
        if not force and not self._ever_loaded and self._try_mount_from_cache():
            return

        if not self._ever_loaded:
            self._loading = True
            self._loading_card.show()
            self._content.hide()

        if force and self._ever_loaded:
            notify_action("Refreshing video workspace…", tone="neutral")
        elif not self._ever_loaded:
            notify_action("Loading video workspace…", tone="neutral")

        worker = VideoWorkspaceWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        self._worker = None

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._on_failed("Invalid video workspace payload.")
            return
        workspace, settings = payload
        if not isinstance(workspace, VideoWorkspaceState):
            self._on_failed("Invalid video workspace state.")
            return
        if not isinstance(settings, dict):
            settings = {}

        had_workspace = self._workspace is not None
        force_hydrate = self._refresh_force_hydrate or not had_workspace
        self._refresh_force_hydrate = False
        self._settings = settings
        self._loading = False
        self._is_error = False
        self._ever_loaded = True
        self._loaded_user_id = cached_user_id(self._cache)
        self._loading_card.hide()
        self._content.show()

        if force_hydrate:
            self._workspace = workspace
            self._hydrate_draft_from_workspace()
            self._refresh_effect_pack_catalog()
            get_video_workspace_service().set_workspace_state(self._workspace)
            self._render_workspace()
        else:
            if not self._workspace_dirty():
                self._workspace = workspace
                get_video_workspace_service().set_workspace_state(self._workspace)
                self._update_export_panel()
                self._schedule_stage_summary_update()

        if self._cache is not None and self._workspace is not None:
            self._cache.apply_video_workspace(self._workspace, settings)

        restore_shell_status()
        if not had_workspace:
            notify_action("Video workspace loaded.", tone="success")

    def _on_failed(self, message: str) -> None:
        self._loading = False
        self._is_error = True
        self._loading_card.show()
        self._content.hide()
        restore_shell_status()
        notify_action(message or "Unable to load video workspace.", tone="error")

    def _hydrate_draft_from_workspace(self, *, force_from_saved: bool = False) -> None:
        if not self._workspace:
            return
        template_id = str(self._workspace.template_id or "")
        if (
            not force_from_saved
            and template_id
            and self._hydrated_template_id == template_id
            and self._template_draft is not None
        ):
            return

        template = dict(self._workspace.template)
        persisted_draft = build_video_template_draft(template, logo_path=self._workspace.logo_path, background_path=self._workspace.background_path)
        snapshot = None
        if template_id and not force_from_saved:
            snapshot = read_video_workspace_draft_snapshot(
                template_id,
                persisted_draft,
                self._workspace.template_name,
            )

        if snapshot:
            self._template_draft = snapshot["draft"]
            self._template_name_draft = str(snapshot.get("templateName") or self._workspace.template_name)
            layers = snapshot.get("layers")
            self._spectrum_layers = clone_layer_records(layers) if layers else clone_layer_records(template.get("layers"))
            lightning_layers = snapshot.get("lightningLayers")
            self._lightning_layers = (
                clone_layer_records(lightning_layers)
                if lightning_layers
                else clone_layer_records(template.get("lightningLayers"))
            )
        else:
            self._template_draft = persisted_draft
            self._template_name_draft = self._workspace.template_name
            self._spectrum_layers = clone_layer_records(template.get("layers"))
            self._lightning_layers = clone_layer_records(template.get("lightningLayers"))

        # Align non-toggle geometry (gravity) from known styles; Curve/Mirror stay user-owned.
        style_key = normalize_spectrum_preset_key_for_apply(
            str((self._template_draft or {}).get("style") or template.get("style") or "orbit-spikes")
        )
        if style_key in STYLE_PRESET_PATCHES and self._spectrum_layers:
            self._spectrum_layers = align_spectrum_layers_to_style_geometry(self._spectrum_layers, style_key)
        # Accidental opacity=0 on every ring makes the spectrum vanish and styles look broken.
        self._spectrum_layers = heal_spectrum_layer_visibility(self._spectrum_layers)
        # Extreme motion smoothing (~0.99) freezes the FFT envelope → “dead” ring.
        if self._template_draft is not None:
            try:
                smooth = float(self._template_draft.get("audioMotionSmoothing", 0.8) or 0.8)
            except (TypeError, ValueError):
                smooth = 0.8
            if smooth > 0.95:
                self._template_draft = {**self._template_draft, "audioMotionSmoothing": 0.85}

        from features.video.lib.spectrum_instance_registry import (
            migrate_legacy_spectrum_to_instances,
            normalize_spectrum_instances,
            project_instance_to_draft_fields,
        )
        snap_instances = snapshot.get("spectrumInstances") if snapshot else None
        if isinstance(snap_instances, list) and snap_instances:
            seeded = dict(template)
            seeded["layers"] = clone_layer_records(self._spectrum_layers) or clone_layer_records(template.get("layers"))
            self._spectrum_instances = normalize_spectrum_instances(snap_instances, template=seeded)
        else:
            # Prefer live layers on instance[0] after hydrate.
            seeded = dict(template)
            seeded["layers"] = clone_layer_records(self._spectrum_layers)
            if self._template_draft:
                seeded["style"] = self._template_draft.get("style") or seeded.get("style")
                seeded["position"] = {
                    "anchor": self._template_draft.get("anchor") or "center",
                    "x": self._template_draft.get("positionX", 0),
                    "y": self._template_draft.get("positionY", 0),
                }
                seeded["previewBindings"] = {
                    **(seeded.get("previewBindings") if isinstance(seeded.get("previewBindings"), dict) else {}),
                    "spectrumAttachToLogo": bool(self._template_draft.get("spectrumAttachToLogo", True)),
                    "spectrumLogoGap": float(self._template_draft.get("spectrumLogoGap", 0) or 0),
                }
                if self._template_draft.get("audioInputGain") is not None:
                    seeded["audioSettings"] = {
                        **(seeded.get("audioSettings") if isinstance(seeded.get("audioSettings"), dict) else {}),
                        "inputGain": self._template_draft.get("audioInputGain"),
                        "barHeight": self._template_draft.get("audioBarHeight", 1.0),
                        "bandContrast": self._template_draft.get("audioBandContrast", 1.0),
                        "transientFocus": self._template_draft.get("audioTransientFocus", 1.0),
                        "kickImpact": self._template_draft.get("audioKickImpact", 0.0),
                        "bassEmphasis": self._template_draft.get("audioBassEmphasis", 1.0),
                        "trebleShimmer": self._template_draft.get("audioTrebleShimmer", 1.0),
                        "peakHoldBlend": self._template_draft.get("audioPeakHoldBlend", 0.0),
                        "motionSmoothing": self._template_draft.get("audioMotionSmoothing", 0.8),
                        "flyingGlowWingMotionSpeed": self._template_draft.get("flyingGlowWingMotionSpeed", 1.0),
                        "flyingGlowWingRelease": self._template_draft.get("flyingGlowWingRelease", 0.9),
                    }
            self._spectrum_instances = migrate_legacy_spectrum_to_instances(seeded)
        if self._spectrum_instances:
            # Keep working layers as selected instance rings without wiping multi-instance data.
            self._selected_spectrum_instance_index = 0
            inst0 = self._spectrum_instances[0] if isinstance(self._spectrum_instances[0], dict) else {}
            inst0_layers = clone_layer_records(inst0.get("layers"))
            if self._spectrum_layers:
                if not inst0_layers or len(self._spectrum_instances) == 1:
                    self._spectrum_instances[0]["layers"] = clone_layer_records(self._spectrum_layers)
                else:
                    # Multi-instance snapshot: trust instance rings; project into the editor.
                    self._spectrum_layers = clone_layer_records(inst0_layers)
            elif inst0_layers:
                self._spectrum_layers = clone_layer_records(inst0_layers)
            if self._template_draft is not None:
                self._template_draft = {**self._template_draft, **project_instance_to_draft_fields(self._spectrum_instances[0])}

        self._hydrated_template_id = template_id
        self._persisted_draft_snapshot = draft_snapshot(self._template_draft)
        self._active_particle_preset_key = (
            resolve_active_particle_preset_key(self._template_draft) if self._template_draft else None
        )
        style = str((self._template_draft or {}).get("style") or "").strip()
        self._active_spectrum_preset_key = style if is_session_spectrum_preset_key(style) else None
        layer_count = len(self._spectrum_layers)
        lightning_count = len(self._lightning_layers)
        self._selected_lightning_layer_index = 0 if lightning_count == 0 else min(
            self._selected_lightning_layer_index,
            lightning_count - 1,
        )
        self._selected_spectrum_layer_index = 0 if layer_count == 0 else min(
            self._selected_spectrum_layer_index,
            layer_count - 1,
        )
        overlays = self._template_draft.get("textOverlays") if self._template_draft else []
        overlay_count = len(overlays) if isinstance(overlays, list) else 0
        self._selected_text_overlay_index = 0 if overlay_count == 0 else min(
            self._selected_text_overlay_index,
            overlay_count - 1,
        )

    def _render_workspace(self) -> None:
        if not self._workspace:
            return
        templates = [(item.id, item.name) for item in self._workspace.templates]
        self._left_rail.set_templates(templates, self._workspace.template_id)
        self._left_rail.set_template_name(self._template_name_draft)
        self._stage.set_preview_context(
            title=self._workspace.ui.preview_title,
            notes=list(self._workspace.ui.notes),
        )
        self._bind_inspectors()
        self._update_effect_pack_selectors()
        self._flush_preview_update()
        if self._workspace:
            self._stage.bind_playback(self._workspace.playback)
        self._update_export_panel()
        self._update_stage_summary()
        self._flush_dirty_state()

    def _bind_inspectors(self) -> None:
        if not self._template_draft:
            return
        self._spectrum_inspector.bind_draft(
            self._template_draft,
            layers=self._spectrum_layers,
            selected_layer_index=self._selected_spectrum_layer_index,
            instances=self._spectrum_instances,
            selected_instance_index=self._selected_spectrum_instance_index,
        )
        self._background_inspector.bind_draft(self._template_draft)
        self._logo_inspector.bind_draft(self._template_draft)
        self._particles_inspector.bind_draft(self._template_draft)
        self._lightning_inspector.bind_draft(
            self._template_draft,
            layers=self._lightning_layers,
            selected_layer_index=self._selected_lightning_layer_index,
        )

        track_paths = self._current_track_paths()
        album_settings = album_settings_from_draft(self._template_draft)
        title_settings = title_settings_from_draft(self._template_draft)
        album_text = resolve_album_display_text(
            album_settings,
            pipeline_album=str(self._settings.get("lastAlbumName") or self._settings.get("album") or ""),
        )
        title_lines = resolve_title_display_list(title_settings, track_paths=track_paths)
        self._album_inspector.bind_draft(
            self._template_draft,
            preview_lines=[album_text] if album_text else [],
        )
        self._title_inspector.bind_draft(
            self._template_draft,
            preview_lines=title_lines,
        )
        if bool(self._template_draft.get("titleEnabled")) and title_lines:
            self._right_rail.set_selection_label(f"{len(title_lines)} track(s)")
        elif bool(self._template_draft.get("albumEnabled")) and album_text:
            self._right_rail.set_selection_label("Album ready")
        else:
            self._right_rail.set_selection_label("Album / Title")

    def _current_track_paths(self) -> list[str]:
        if not self._workspace:
            return []
        return [str(item.path) for item in (self._workspace.mp3_list or []) if str(item.path or "").strip()]

    def _apply_text_domain_preset(self, domain: str, preset: str) -> None:
        if not self._template_draft or not is_builtin_text_domain_preset(preset):
            return
        active_attr = "_active_album_preset_key" if domain == "album" else "_active_title_preset_key"
        active_key = getattr(self, active_attr, None)
        if is_builtin_text_domain_preset(active_key) and active_key != preset:
            capture_text_domain_preset(domain, str(active_key), draft_style_snapshot(domain, self._template_draft))
        style = resolve_text_domain_preset_style(domain, preset)
        if not style:
            return
        setattr(self, active_attr, preset)
        prefix = "album" if domain == "album" else "title"
        # Keep CapCut box geometry (position + width) when swapping looks.
        # Always start presets at a screen-safe 10px size (effects stay readable).
        preserved = {
            f"{prefix}X": self._template_draft.get(f"{prefix}X"),
            f"{prefix}Y": self._template_draft.get(f"{prefix}Y"),
            f"{prefix}BoxWidth": self._template_draft.get(f"{prefix}BoxWidth"),
            f"{prefix}LetterSpacing": 0.0,
            f"{prefix}LineSpacing": 1.2,
            f"{prefix}FontSize": 10.0,
        }
        patch = {
            f"{prefix}StylePreset": preset,
            **style_patch_for_domain(domain, style),
            **{k: v for k, v in preserved.items() if v is not None},
        }
        self._patch_template_draft(patch)

    def _restore_text_domain_preset(self, domain: str) -> None:
        if not self._template_draft:
            return
        active_attr = "_active_album_preset_key" if domain == "album" else "_active_title_preset_key"
        preset = str(getattr(self, active_attr, None) or self._template_draft.get(
            "albumStylePreset" if domain == "album" else "titleStylePreset"
        ) or "")
        style = restore_text_domain_preset(domain, preset)
        if not style:
            return
        prefix = "album" if domain == "album" else "title"
        self._patch_template_draft(
            {
                f"{prefix}StylePreset": preset,
                **style_patch_for_domain(domain, style),
            }
        )

    def _update_inspectors(self, *, defer_rebind: bool = False, schedule_preview: bool = True) -> None:
        if defer_rebind:
            self._inspector_rebind_timer.start()
        else:
            self._inspector_rebind_timer.stop()
            self._bind_inspectors()
            self._update_effect_pack_selectors()
        if schedule_preview:
            self._schedule_preview_update()
        self._schedule_dirty_state_update()

    def _flush_inspector_rebind(self) -> None:
        self._bind_inspectors()
        self._update_effect_pack_selectors()

    def _schedule_preview_update(self, *, delay_ms: int = 48) -> None:
        self._preview_update_timer.start(max(0, int(delay_ms)))

    def _flush_preview_update(self) -> None:
        self._update_preview()

    def _mark_preview_scrubbing(self) -> None:
        """REQ-P2.5: enter reduced paint rate; schedule full flush when idle."""
        if not self._preview_scrubbing:
            self._preview_scrubbing = True
            try:
                self._stage.set_interactive_scrub(True)
            except Exception:
                pass
        self._preview_scrub_end_timer.start()

    def _end_preview_scrub(self) -> None:
        was = bool(self._preview_scrubbing)
        self._preview_scrubbing = False
        try:
            self._stage.set_interactive_scrub(False)
        except Exception:
            pass
        if was:
            # Canonical Full_Template_Push after scrub (REQ-P2.2).
            self._flush_preview_update()

    def _apply_live_scrub_patch(self, patch: dict) -> bool:
        """Apply allowlisted live patch; returns False when caller must full-push."""
        try:
            ok = bool(self._stage.apply_preview_patch(patch))
        except Exception:
            ok = False
        if ok:
            self._mark_preview_scrubbing()
        return ok

    def _schedule_dirty_state_update(self, *, delay_ms: int = 120) -> None:
        self._dirty_state_timer.start(max(0, int(delay_ms)))

    def _flush_dirty_state(self) -> None:
        self._update_dirty_state()
        if self._diagnostics_panel is not None and self._diagnostics_panel.isChecked():
            self._update_diagnostics_panel()

    def _schedule_local_draft_persist(self, *, delay_ms: int = 200) -> None:
        self._draft_persist_timer.start(max(0, int(delay_ms)))

    def _persist_local_draft_snapshot(self) -> None:
        if not self._workspace or not self._template_draft:
            return
        template_id = str(self._workspace.template_id or "")
        if not template_id:
            return
        write_video_workspace_draft_snapshot(
            template_id,
            template_name=self._template_name_draft,
            draft=self._template_draft,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
        )

    def _schedule_stage_summary_update(self, *, delay_ms: int = 150) -> None:
        self._stage_summary_timer.start(max(0, int(delay_ms)))

    def _update_export_panel(self) -> None:
        export_busy = (
            self._export_start_pending
            or self._pipeline_start_pending
            or bool(self._export_worker and self._export_worker.isRunning())
            or bool(self._pipeline_export_worker and self._pipeline_export_worker.isRunning())
            or bool(self._pipeline_merge_worker and self._pipeline_merge_worker.isRunning())
        )
        if (
            self._workspace
            and (self._workspace.export.running or self._workspace.export.merge_running)
            and not export_busy
        ):
            from shared.services.video_pipeline_activity import any_video_pipeline_threads_running

            if not any_video_pipeline_threads_running():
                self._workspace = self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": False,
                                "merge_running": False,
                                "current_status": (
                                    "Recovered stale export state — ready for a new export."
                                ),
                            }
                        )
                    }
                )
                get_video_workspace_service().set_workspace_state(self._workspace)
        output_resolution = "1920x1080"
        if self._workspace and str(self._workspace.output_resolution or "").strip():
            output_resolution = str(self._workspace.output_resolution).strip()
        elif str(self._settings.get("outputResolution") or "").strip():
            output_resolution = str(self._settings.get("outputResolution")).strip()
        self._export_panel.bind_workspace(
            self._workspace,
            busy=export_busy,
            stop_export_pending=self._stop_export_pending,
            speed_mode=normalize_export_speed_mode(self._settings.get("videoExportSpeedMode")),
            output_resolution=output_resolution,
        )

    def _selected_pipeline_row(self) -> ProgressRow | None:
        for row in self._pipeline_rows:
            if build_video_pipeline_run_key(row) == self._selected_pipeline_run_key:
                return row
        return self._pipeline_rows[0] if self._pipeline_rows else None

    def _build_pipeline_export_template(self, *, track_paths: list[str] | None = None) -> dict | None:
        if not self._workspace or not dict(self._workspace.template):
            return None
        template = dict(self._workspace.template)
        saved_draft = build_video_template_draft(template, logo_path=self._workspace.logo_path, background_path=self._workspace.background_path)
        # Prefer live draft + spectrum/lightning so unsaved preview edits export (WYSIWYG).
        draft = dict(self._template_draft) if isinstance(self._template_draft, dict) and self._template_draft else saved_draft
        self._flush_active_spectrum_instance_layers()
        layers = clone_layer_records(self._spectrum_layers or template.get("layers") or [])
        lightning_layers = clone_layer_records(self._lightning_layers or template.get("lightningLayers") or [])
        paths = [str(p) for p in (track_paths or self._current_track_paths()) if str(p or "").strip()]
        # Per-track active highlight is applied again in the export worker.
        return self._template_normalizer.to_renderer_dict(
            base=template,
            draft=draft,
            layers=layers,
            lightning_layers=lightning_layers,
            spectrum_instances=self._spectrum_instances,
            workspace={
                "logoPath": self._workspace.logo_path,
                "trackPaths": paths,
                "pipelineAlbum": str(
                    self._settings.get("lastAlbumName") or self._settings.get("album") or ""
                ),
            },
            track_paths=paths,
            active_track_path=None,
        )

    def _start_pipeline_export(self) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            notify_action("An export is already running.", tone="warning")
            return
        if self._pipeline_export_worker is not None and self._pipeline_export_worker.isRunning():
            notify_action("A pipeline export is already running.", tone="warning")
            return
        if self._pipeline_merge_worker is not None and self._pipeline_merge_worker.isRunning():
            notify_action("A video merge is already running.", tone="warning")
            return
        row = self._selected_pipeline_row()
        if row is None:
            notify_action("Select a pipeline run before exporting.", tone="warning")
            return
        branch = "reel" if self._selected_pipeline_branch == "reel" else "long"
        resolved = resolve_video_pipeline_inputs(row, branch)
        run_dir = str(resolved.run_dir or "").strip()
        background_path = str(resolved.background_path or "").strip()
        if not run_dir or not Path(run_dir).is_dir():
            notify_action("Selected run directory is missing.", tone="warning")
            return
        if not background_path or not Path(background_path).is_file():
            notify_action("Selected branch background image is missing.", tone="warning")
            return
        if not resolved.ready:
            notify_action("Selected branch assets are not ready yet.", tone="warning")
            return
        mp3_list = self._store.list_mp3_files(run_dir)
        if not mp3_list:
            notify_action("No MP3 files were found in the selected run directory.", tone="warning")
            return
        track_paths = [item.path for item in mp3_list]
        template = self._build_pipeline_export_template(track_paths=track_paths)
        if not template:
            notify_action("No active video template is loaded.", tone="warning")
            return

        scene = build_pipeline_render_scene_request(
            template=template,
            workspace={
                "templateId": self._workspace.template_id if self._workspace else None,
                "outputResolution": self._workspace.output_resolution if self._workspace else "1920x1080",
                "logoPath": self._workspace.logo_path if self._workspace else "",
                "selectedMp3Path": mp3_list[0].path,
            },
            run_dir=run_dir,
            background_path=background_path,
            branch=branch,
            batch_id=row.meta.batch_id,
            role=row.meta.role,
            selected_mp3_path=mp3_list[0].path,
            fps=self._resolve_export_fps(),
        )
        workers_raw = self._settings.get("videoExportWorkers", self._settings.get("perfExportWorkers", 1))
        try:
            worker_limit = max(1, min(10, int(workers_raw)))
        except (TypeError, ValueError):
            worker_limit = 1
        started_at_ms = int(time.time() * 1000)
        branch_label = "reel" if branch == "reel" else "long"
        auto_merge = is_auto_merge_enabled_for_branch(self._settings, branch)
        shuffle_merge = bool(self._settings.get("videoShuffleMerge", False))
        if self._workspace:
            shuffle_merge = bool(self._workspace.export.shuffle_merge)
        # Preserve MP3 tracklist order for non-shuffle merges (python_app always shuffled).
        ordered_mp4s = [
            build_pipeline_export_output_path(mp3_path=item.path, output_dir=run_dir, branch=branch)
            for item in mp3_list
        ]
        profile_id = str(getattr(row.meta, "profile_id", None) or "").strip() or None
        ref_base = f"{row.meta.batch_id}:{row.meta.role}:{branch}"
        try:
            video_bill = consume_video_operation(
                self._api,
                operation_type="video",
                count=len(mp3_list),
                channel_profile_id=profile_id,
                ref_id=f"video:{ref_base}",
            )
            self._video_billing_charge = {
                "operation_type": "video",
                "count": len(mp3_list),
                "charged_credit_units": video_bill.charged_credit_units,
                "channel_profile_id": profile_id,
                "ref_id": f"video:{ref_base}",
            }
        except Exception as exc:
            notify_action(f"Video export blocked (billing): {exc}", tone="warning")
            return
        encode_fields = self._encode_fields_for_merge_context(branch, pipeline=True)
        self._pipeline_merge_context = {
            "run_dir": run_dir,
            "branch": branch,
            "batch_id": row.meta.batch_id,
            "role": row.meta.role,
            "auto_merge": auto_merge,
            "shuffle": shuffle_merge,
            "mp4_paths": ordered_mp4s,
            "completed": len(mp3_list),
            "total": len(mp3_list),
            "profile_id": profile_id,
            "ref_base": ref_base,
            **encode_fields,
        }
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "selected_mp3_path": mp3_list[0].path,
                        "mp3_directory": run_dir,
                        "mp3_list": mp3_list,
                        "export": VideoExportState(
                            running=True,
                            branch=branch_label,
                            workers=worker_limit,
                            fps=self._resolve_export_fps(),
                            auto_merge=auto_merge,
                            shuffle_merge=shuffle_merge,
                            current_status=f"Starting {branch_label} export…",
                            output_dir=run_dir,
                            current_output_path=None,
                            total_jobs=len(mp3_list),
                            completed_jobs=0,
                            progress_percent=0,
                            started_at_ms=started_at_ms,
                        ),
                    }
                )
            )

        self._pipeline_start_pending = True
        self._update_export_panel()
        worker = VideoPipelineExportWorker(
            PipelineExportRequest(
                run_dir=run_dir,
                background_path=background_path,
                logo_path=str(self._workspace.logo_path if self._workspace else ""),
                branch=branch,
                batch_id=row.meta.batch_id,
                role=row.meta.role,
                template=template,
                mp3_paths=[item.path for item in mp3_list],
                settings=self._settings,
                width=int(scene.output.width),
                height=int(scene.output.height),
                fps=int(scene.output.fps),
                speed_mode=normalize_export_speed_mode(self._settings.get("videoExportSpeedMode")),
            ),
            parent=None,
        )
        worker.progressed.connect(self._on_pipeline_export_progress)
        worker.succeeded.connect(self._on_pipeline_export_succeeded)
        worker.failed.connect(self._on_pipeline_export_failed)
        worker.finished.connect(self._on_pipeline_export_worker_finished)
        worker.setObjectName("VideoPipelineExportWorker")
        self._pipeline_export_worker = worker
        track_video_pipeline_thread(worker)
        try:
            from shared.lib.app_icon import refresh_app_window_icon

            refresh_app_window_icon(self)
        except Exception:
            pass
        worker.start()
        try:
            from shared.lib.app_icon import refresh_app_window_icon

            QTimer.singleShot(250, lambda: refresh_app_window_icon(self))
            QTimer.singleShot(1500, lambda: refresh_app_window_icon(self))
        except Exception:
            pass
        notify_action(f"Started {branch_label} export from the selected pipeline run.")

    def _refund_billing_charge(
        self,
        charge: dict[str, object],
        *,
        reason: str,
        count: int | None = None,
    ) -> dict[str, object]:
        """Refund a consume charge; returns remaining charge (empty if fully refunded)."""
        if not charge:
            return {}
        original_count = max(1, int(charge.get("count") or 1))
        refund_count = original_count if count is None else max(0, min(original_count, int(count)))
        if refund_count <= 0:
            return dict(charge)
        charged = int(charge.get("charged_credit_units") or 0)
        refund_credits = int(round(charged * refund_count / original_count)) if charged else 0
        try:
            refund_video_operation(
                self._api,
                operation_type=str(charge.get("operation_type") or "video"),
                charged_credit_units=refund_credits,
                count=refund_count,
                channel_profile_id=charge.get("channel_profile_id"),
                ref_id=str(charge.get("ref_id") or "") or None,
                reason=reason,
            )
        except Exception:
            pass
        remaining = original_count - refund_count
        if remaining <= 0:
            return {}
        return {
            **charge,
            "count": remaining,
            "charged_credit_units": max(0, charged - refund_credits),
        }

    def _refund_video_billing_charge(self, reason: str, *, count: int | None = None) -> None:
        self._video_billing_charge = self._refund_billing_charge(
            dict(self._video_billing_charge or {}),
            reason=reason,
            count=count,
        )

    def _refund_merge_billing_charge(self, reason: str) -> None:
        self._merge_billing_charge = self._refund_billing_charge(
            dict(self._merge_billing_charge or {}),
            reason=reason,
        )

    def _clear_video_billing_charge(self) -> None:
        self._video_billing_charge = {}

    def _clear_merge_billing_charge(self) -> None:
        self._merge_billing_charge = {}

    def _report_export_telemetry(
        self,
        *,
        operation_type: str,
        track_count: int,
        completed_count: int,
        duration_ms: int | None = None,
        codec: str | None = None,
        ref_id: str | None = None,
    ) -> None:
        if duration_ms is None and self._workspace is not None:
            started = int(self._workspace.export.started_at_ms or 0)
            if started > 0:
                duration_ms = max(0, int(time.time() * 1000) - started)
        if codec is None and self._workspace is not None:
            codec = str(self._workspace.export.video_codec or "").strip() or None
        resolution = None
        width = int(self._settings.get("videoOutputWidth") or 0)
        height = int(self._settings.get("videoOutputHeight") or 0)
        if width > 0 and height > 0:
            resolution = f"{width}x{height}"
        hw = collect_hardware_hints(codec=codec)
        app_version = None
        try:
            from importlib.metadata import version

            app_version = version("camxora")
        except Exception:
            app_version = None
        payload = {
            "operation_type": operation_type,
            "ref_id": ref_id,
            "track_count": max(0, int(track_count)),
            "completed_count": max(0, int(completed_count)),
            "duration_ms": duration_ms,
            "codec": codec,
            "resolution": resolution,
            "fps": int(self._workspace.export.fps) if self._workspace else None,
            "export_tier": normalize_export_tier(
                self._settings.get("videoExportTier"), default="standard"
            ),
            "speed_mode": normalize_export_speed_mode(self._settings.get("videoExportSpeedMode")),
            "hw_cpu": hw.get("hw_cpu"),
            "hw_gpu": hw.get("hw_gpu"),
            "hw_encoder": hw.get("hw_encoder"),
            "app_version": app_version,
        }
        report_video_telemetry_async(self._api, payload)

    @staticmethod
    def _is_user_initiated_stop(message: str = "", *, stopped_flag: bool = False) -> bool:
        if stopped_flag:
            return True
        text = str(message or "").strip().lower()
        return "export stopped" in text or text == "video export stopped."

    @staticmethod
    def _refundable_units(
        charged: int,
        completed: int,
        *,
        user_stop: bool,
        in_progress: bool = False,
    ) -> int:
        """Units to refund. User stop keeps completed + in-progress; technical fail refunds all non-completed."""
        if charged <= 0:
            return 0
        keep = max(0, int(completed))
        if user_stop and in_progress:
            keep += 1
        return max(0, int(charged) - keep)

    def _apply_video_refund_for_outcome(
        self,
        *,
        reason: str,
        completed: int,
        user_stop: bool,
        in_progress: bool = False,
    ) -> None:
        charged = int(self._video_billing_charge.get("count") or 0)
        refund_count = self._refundable_units(
            charged,
            completed,
            user_stop=user_stop,
            in_progress=in_progress,
        )
        if refund_count:
            self._refund_video_billing_charge(reason, count=refund_count)
        else:
            self._clear_video_billing_charge()

    def _release_export_qthread(self, worker: QThread | None, *, wait_ms: int = 3_000) -> None:
        """Join then deleteLater so Stop/teardown never destroys a live QThread."""
        if worker is None:
            return
        from shared.services.video_pipeline_activity import untrack_video_pipeline_thread

        try:
            still_running = bool(worker.isRunning())
        except RuntimeError:
            untrack_video_pipeline_thread(worker)
            return
        if still_running:
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except Exception:
                    pass
            if not worker.wait(max(0, int(wait_ms))):
                # Still running: detach from this view so page teardown can't
                # destroy the C++ QThread while the OS thread is alive.
                worker.setParent(None)
                self._lingering_export_threads.append(worker)

                def _drop_lingering(_w: QThread = worker) -> None:
                    try:
                        self._lingering_export_threads.remove(_w)
                    except ValueError:
                        pass
                    untrack_video_pipeline_thread(_w)
                    _w.deleteLater()

                worker.finished.connect(_drop_lingering)
                return
        untrack_video_pipeline_thread(worker)
        worker.deleteLater()

    def _stop_active_export(self) -> None:
        self._stop_export_pending = True
        queued_remaining = len(self._batch_queue)
        self._batch_queue = []
        self._update_export_panel()
        if self._billing_worker is not None and self._billing_worker.isRunning():
            # Billing still in flight — keep stop pending; success handler refunds.
            notify_action("Stopping export…")
            return
        if self._export_worker is not None and self._export_worker.isRunning():
            notify_action("Stopping export…")
            self._release_export_qthread(self._export_worker, wait_ms=8_000)
            return
        if self._pipeline_export_worker is not None and self._pipeline_export_worker.isRunning():
            notify_action("Stopping pipeline export…")
            self._release_export_qthread(self._pipeline_export_worker, wait_ms=8_000)
            return
        if self._pipeline_merge_worker is not None and self._pipeline_merge_worker.isRunning():
            # Merge already started — user stop keeps the merge charge (compute spent).
            notify_action("Stopping video merge…")
            self._release_export_qthread(self._pipeline_merge_worker, wait_ms=8_000)
            return
        self._stop_export_pending = False
        # Between tracks: nothing in progress — refund only never-started queue items.
        if queued_remaining:
            self._apply_video_refund_for_outcome(
                reason="Manual export stopped (unused tracks).",
                completed=int(self._batch_completed or 0),
                user_stop=True,
                in_progress=False,
            )
        else:
            self._clear_video_billing_charge()
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": False,
                                "current_status": "Export stopped.",
                            }
                        )
                    }
                )
            )

    def _publish_workspace(self, workspace: VideoWorkspaceState) -> None:
        self._workspace = workspace
        get_video_workspace_service().set_workspace_state(workspace)
        self._update_export_panel()

    def _select_preview_mp3(self, path: str) -> None:
        if not path.strip():
            return
        self._workspace = self._store.set_mp3_path(path, settings=self._settings)
        self._publish_workspace(self._workspace)
        # Load the selected track into the GPU preview (required for Play / double-click).
        self._flush_preview_update()
        self._update_stage_summary()
        notify_action("Applied the selected preview track.", tone="success")

    def _play_preview_mp3(self, path: str) -> None:
        """Double-click a track: select it and start playback when audio is ready."""
        requested = str(path or "").strip()
        if not requested:
            return
        preview = getattr(self._stage, "_preview", None)
        already_loaded = (
            preview is not None
            and bool(getattr(preview, "audio_ready", False))
            and str(getattr(preview, "audio_path", "") or "").strip().lower() == requested.lower()
        )
        self._pending_preview_auto_play = True
        self._select_preview_mp3(requested)
        if already_loaded:
            # Same track already in the mixer — restart from the beginning now.
            try:
                preview.current_time = 0.0
                preview._audio_clock_base = 0.0
                preview._audio_clock_started_at = None
            except Exception:
                pass
            self._flush_pending_preview_auto_play()
            return
        # Retry until mixer decode is ready (analysis can still be running).
        self._flush_pending_preview_auto_play()
        for delay_ms in (50, 150, 350, 700, 1200, 2000):
            QTimer.singleShot(delay_ms, self._flush_pending_preview_auto_play)

    def _flush_pending_preview_auto_play(self) -> None:
        if not self._pending_preview_auto_play:
            return
        preview = getattr(self._stage, "_preview", None)
        if preview is None:
            return
        audio_path = str(getattr(preview, "audio_path", "") or "").strip()
        # Play as soon as the mixer can start — don't wait for FFT analysis.
        if bool(getattr(preview, "audio_ready", False)) and audio_path:
            self._pending_preview_auto_play = False
            # Force a fresh start so double-click always audibly begins playback.
            try:
                import pygame

                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                preview.audio_playing = False
                preview.current_time = 0.0
                preview._audio_clock_base = 0.0
                preview._audio_clock_started_at = None
            except Exception:
                pass
            self._stage.issue_playback_command("play")
            notify_action(f"Playing: {Path(audio_path).name}")

    def _reorder_tracks(self, paths: object) -> None:
        if not isinstance(paths, list):
            return
        previous = str(self._workspace.selected_mp3_path or "").strip() if self._workspace else ""
        before_count = len(self._workspace.mp3_list) if self._workspace else 0
        ordered = [str(path).strip() for path in paths if str(path).strip()]
        self._workspace = self._store.set_mp3_order(ordered, settings=self._settings)
        self._publish_workspace(self._workspace)
        self._update_inspectors()
        self._update_export_panel()
        if previous and previous not in ordered:
            self._flush_preview_update()
            self._update_stage_summary()
        if not ordered:
            notify_action("Track list cleared.", tone="success")
        elif len(ordered) < before_count:
            notify_action("Removed from track list.", tone="success")
        else:
            notify_action("Track order updated.", tone="success")

    def _patch_export_setting(self, patch: dict[str, object], status: str) -> None:
        """Persist an export option like python_app's _persist_setting_patch."""
        self._settings.update(patch)
        # parent=None so closing Video mid-save cannot destroy a live QThread.
        worker = PatchSettingsWorker(self._api, dict(patch), parent=None)
        worker.succeeded.connect(lambda *_: notify_action(status, tone="success"))
        worker.failed.connect(
            lambda message: notify_action(message or "Unable to save export settings.", tone="error")
        )
        self._settings_patch_worker = worker
        worker.start()

    def _set_auto_merge(self, enabled: bool) -> None:
        if not self._workspace:
            return
        self._publish_workspace(
            self._workspace.model_copy(
                update={"export": self._workspace.export.model_copy(update={"auto_merge": bool(enabled)})}
            )
        )
        self._patch_export_setting(
            {"autoMergeAfterVideo": bool(enabled)},
            "Auto merge enabled." if enabled else "Auto merge disabled.",
        )

    def _set_shuffle_merge(self, enabled: bool) -> None:
        if not self._workspace:
            return
        self._publish_workspace(
            self._workspace.model_copy(
                update={"export": self._workspace.export.model_copy(update={"shuffle_merge": bool(enabled)})}
            )
        )
        self._patch_export_setting(
            {"videoShuffleMerge": bool(enabled)},
            "Shuffle merge enabled." if enabled else "Merge will follow track list order.",
        )

    def _set_export_speed_mode(self, mode: str) -> None:
        normalized = normalize_export_speed_mode(mode)
        self._patch_export_setting({"videoExportSpeedMode": normalized}, "Export speed updated.")

    def _set_export_resolution(self, resolution: str) -> None:
        """Manual export Resolution = same OUTPUT_RESOLUTION_OPTIONS list as the stage."""
        normalized = str(resolution or "").strip()
        if not normalized:
            return
        # Concrete WxH replaces Draft/Standard/Master — keep Standard so FPS/speed apply.
        self._settings["videoExportTier"] = "standard"
        if self._workspace and normalized == str(self._workspace.output_resolution or "").strip():
            self._patch_export_setting(
                {"videoExportTier": "standard"},
                "Export resolution updated.",
            )
            return
        self._save_output_resolution(normalized, force_standard_tier=True)

    def _merge_encode_settings_for_branch(self, branch: str, *, pipeline: bool):
        tier = resolve_export_tier_settings(self._settings, pipeline=pipeline)
        fps = self._resolve_export_fps()
        if self._workspace and int(self._workspace.export.fps or 0) > 0:
            fps = normalize_export_fps(self._workspace.export.fps)
        return resolve_merge_encode_settings(
            self._settings,
            branch=branch,
            pipeline=pipeline,
            fps=fps,
            speed_mode=tier.speed_mode,
        )

    def _encode_fields_for_merge_context(self, branch: str, *, pipeline: bool) -> dict[str, object]:
        encode = self._merge_encode_settings_for_branch(branch, pipeline=pipeline)
        return {
            "encode_width": int(encode.width),
            "encode_height": int(encode.height),
            "encode_fps": int(encode.fps),
            "encode_speed_mode": str(encode.speed_mode),
            "settings": dict(self._settings),
        }

    def _resolve_export_fps(self) -> int:
        if self._workspace:
            return normalize_export_fps(self._workspace.export.fps)
        return normalize_export_fps(self._settings.get("videoExportFps", PIPELINE_EXPORT_FPS))

    def _set_export_fps(self, fps: int) -> None:
        normalized = normalize_export_fps(fps)
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={"export": self._workspace.export.model_copy(update={"fps": normalized})}
                )
            )
        self._patch_export_setting(
            {"videoExportFps": normalized},
            f"Export FPS set to {normalized}.",
        )

    def _set_export_workers(self, value: int) -> None:
        workers = max(1, min(10, int(value or 1)))
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={"export": self._workspace.export.model_copy(update={"workers": workers})}
                )
            )
        self._patch_export_setting({"videoExportWorkers": workers}, "Export workers updated.")

    def _pick_preview_mp3(self) -> None:
        # python_app "Select MP3 Folder": load every track from a directory.
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select MP3 Folder",
            self._workspace.mp3_directory if self._workspace else "",
        )
        if not directory:
            return
        self._workspace = self._store.set_mp3_directory(directory, settings=self._settings)
        self._publish_workspace(self._workspace)
        self._update_inspectors()
        self._schedule_stage_summary_update()
        count = len(self._workspace.mp3_list)
        notify_action(f"Loaded {count} track(s) from the selected folder.", tone="success")

    def _build_manual_export_scene(self, *, audio_path: str = ""):
        if not self._workspace or not self._template_draft:
            return None
        selected_mp3 = str(audio_path or self._workspace.selected_mp3_path or "")
        track_paths = self._current_track_paths()
        self._flush_active_spectrum_instance_layers()
        renderer_template = self._template_normalizer.to_renderer_dict(
            base=dict(self._workspace.template),
            draft=self._template_draft,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
            spectrum_instances=self._spectrum_instances,
            workspace={
                "logoPath": self._workspace.logo_path,
                "trackPaths": track_paths,
                "selectedMp3Path": selected_mp3,
                "pipelineAlbum": str(
                    self._settings.get("lastAlbumName") or self._settings.get("album") or ""
                ),
            },
            track_paths=track_paths,
            active_track_path=selected_mp3 or None,
        )
        tier = resolve_export_tier_settings(self._settings, pipeline=False)
        return build_manual_render_scene_request(
            template=renderer_template,
            template_draft=self._template_draft,
            workspace={
                "templateId": self._workspace.template_id,
                "logoPath": self._workspace.logo_path,
                "backgroundPath": self._workspace.background_path,
                "selectedMp3Path": selected_mp3,
                "outputResolution": tier.resolution,
            },
            background_path=self._workspace.background_path,
            selected_mp3_path=selected_mp3,
            fps=tier.fps,
        )

    def _start_manual_export(self) -> None:
        # python_app behavior: export the whole track list as one batch.
        if self._export_worker is not None and self._export_worker.isRunning():
            notify_action("An export is already running.", tone="warning")
            return
        if self._pipeline_export_worker is not None and self._pipeline_export_worker.isRunning():
            notify_action("A pipeline export is already running.", tone="warning")
            return
        if int(export_gate.active) > 0:
            notify_action(
                f"Another export still holds {export_gate.active} worker slot(s). "
                "Stop Export and wait a few seconds, then try again.",
                tone="warning",
            )
            return
        if not self._workspace:
            return
        tracks = [item.path for item in self._workspace.mp3_list]
        if not tracks and str(self._workspace.selected_mp3_path or "").strip():
            tracks = [str(self._workspace.selected_mp3_path)]
        if not tracks:
            notify_action("Select an MP3 folder before exporting.", tone="warning")
            return
        if not str(self._workspace.background_path or "").strip():
            notify_action("Select a background image before exporting.", tone="warning")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            str(self._settings.get("videoRenderOutputDir") or ""),
        )
        if not output_dir:
            return

        # Paint "Starting…" immediately — billing runs on a short QThread so the
        # Manual Export click stays responsive (was a 1–2s sync network stall).
        self._batch_queue = list(tracks)
        self._batch_total = len(tracks)
        self._batch_completed = 0
        self._batch_failures = 0
        self._batch_output_dir = output_dir
        self._batch_outputs = []
        started_at_ms = int(time.time() * 1000)
        self._export_start_pending = True
        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "export": VideoExportState(
                        running=True,
                        workers=max(1, int(self._workspace.export.workers or 1)),
                        fps=self._resolve_export_fps(),
                        auto_merge=self._workspace.export.auto_merge,
                        shuffle_merge=self._workspace.export.shuffle_merge,
                        current_status=f"Preparing export · {len(tracks)} track(s)…",
                        output_dir=output_dir,
                        total_jobs=self._batch_total,
                        completed_jobs=0,
                        progress_percent=0,
                        started_at_ms=started_at_ms,
                    )
                }
            )
        )
        self._update_export_panel()
        notify_action(f"Preparing export · {len(tracks)} track(s)…", tone="neutral")

        profile_id = None
        manual_ref = f"video_manual:{int(time.time())}"
        self._pending_manual_billing = {
            "operation_type": "video_manual",
            "count": len(tracks),
            "channel_profile_id": profile_id,
            "ref_id": manual_ref,
            "track_count": len(tracks),
            "output_dir": output_dir,
        }
        if self._billing_worker is not None and self._billing_worker.isRunning():
            self._release_export_qthread(self._billing_worker, wait_ms=2_000)
        worker = VideoBillingWorker(
            self._api,
            operation_type="video_manual",
            count=len(tracks),
            channel_profile_id=profile_id,
            ref_id=manual_ref,
            parent=None,
        )
        worker.succeeded.connect(self._on_manual_billing_succeeded)
        worker.failed.connect(self._on_manual_billing_failed)
        worker.finished.connect(self._on_billing_worker_finished)
        self._billing_worker = worker
        track_video_pipeline_thread(worker)
        worker.start()

    def _on_billing_worker_finished(self) -> None:
        self._billing_worker = None

    def _clear_manual_export_pending(self, *, status: str) -> None:
        self._export_start_pending = False
        self._pending_manual_billing = None
        self._batch_queue = []
        self._batch_total = 0
        self._batch_output_dir = ""
        self._batch_outputs = []
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": False,
                                "current_status": status,
                            }
                        )
                    }
                )
            )
        self._update_export_panel()

    def _on_manual_billing_succeeded(self, result: object) -> None:
        pending = dict(self._pending_manual_billing or {})
        self._pending_manual_billing = None
        if self._stop_export_pending:
            # User stopped while billing was in flight — refund the charge and bail.
            try:
                from features.video.lib.video_billing import VideoBillingResult, refund_video_operation

                charged = int(getattr(result, "charged_credit_units", 0) or 0)
                if isinstance(result, VideoBillingResult):
                    charged = int(result.charged_credit_units or 0)
                refund_video_operation(
                    self._api,
                    operation_type=str(pending.get("operation_type") or "video_manual"),
                    charged_credit_units=charged,
                    count=max(1, int(pending.get("count") or 1)),
                    channel_profile_id=pending.get("channel_profile_id"),
                    ref_id=str(pending.get("ref_id") or "") or None,
                    reason="Manual export stopped before start.",
                )
            except Exception:
                pass
            self._stop_export_pending = False
            self._clear_manual_export_pending(status="Export stopped.")
            notify_action("Export stopped.", tone="neutral")
            return

        from features.video.lib.video_billing import VideoBillingResult

        charged = 0
        if isinstance(result, VideoBillingResult):
            charged = int(result.charged_credit_units or 0)
        else:
            charged = int(getattr(result, "charged_credit_units", 0) or 0)

        track_count = max(1, int(pending.get("track_count") or pending.get("count") or 1))
        output_dir = str(pending.get("output_dir") or self._batch_output_dir or "")
        self._video_billing_charge = {
            "operation_type": str(pending.get("operation_type") or "video_manual"),
            "count": track_count,
            "charged_credit_units": charged,
            "channel_profile_id": pending.get("channel_profile_id"),
            "ref_id": pending.get("ref_id"),
        }
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "current_status": f"Starting batch: {track_count} track(s) → {output_dir}",
                            }
                        )
                    }
                )
            )
        self._start_next_batch_export()

    def _on_manual_billing_failed(self, message: str) -> None:
        detail = str(message or "billing failed").strip() or "billing failed"
        self._stop_export_pending = False
        self._clear_manual_export_pending(status=f"Manual export blocked (billing): {detail}")
        notify_action(f"Manual export blocked (billing): {detail}", tone="warning")

    def _start_next_batch_export(self) -> None:
        if not self._batch_queue:
            return
        audio_path = self._batch_queue.pop(0)
        scene = self._build_manual_export_scene(audio_path=audio_path)
        if scene is None:
            self._on_export_failed("The live preview scene is not ready yet.")
            self._on_export_worker_finished()
            return

        from features.video.lib.render_scene_request import build_manual_export_output_path

        output_path = build_manual_export_output_path(
            audio_path=audio_path,
            output_dir=self._batch_output_dir,
        )
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "selected_mp3_path": audio_path,
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": True,
                                "current_status": f"Exporting {Path(audio_path).name}…",
                                "current_output_path": output_path,
                            }
                        ),
                    }
                )
            )

        tier = resolve_export_tier_settings(self._settings, pipeline=False)
        self._export_start_pending = True
        self._update_export_panel()
        try:
            from shared.lib.app_icon import refresh_app_window_icon

            refresh_app_window_icon(self)
        except Exception:
            pass
        preview = self._stage.preview_widget() if self._stage.gpu_preview_available() else None
        worker = VideoManualExportWorker(
            ManualExportRequest(
                scene=scene,
                settings=self._settings,
                speed_mode=tier.speed_mode,
                output_dir=self._batch_output_dir,
                preview=preview,
            ),
            parent=None,
        )
        worker.setObjectName("VideoManualExportWorker")
        worker.progressed.connect(self._on_export_progress)
        worker.succeeded.connect(self._on_export_succeeded)
        worker.failed.connect(self._on_export_failed)
        worker.finished.connect(self._on_export_worker_finished)
        self._export_worker = worker
        track_video_pipeline_thread(worker)
        worker.start()
        try:
            from shared.lib.app_icon import refresh_app_window_icon
            from PySide6.QtCore import QTimer

            # GLFW export windows appear after the worker starts; restamp once they map.
            QTimer.singleShot(250, lambda: refresh_app_window_icon(self))
            QTimer.singleShot(1500, lambda: refresh_app_window_icon(self))
        except Exception:
            pass
        notify_action(f"Exporting {Path(audio_path).name}…", tone="neutral")

    def _stop_manual_export(self) -> None:
        self._stop_active_export()

    def _batch_overall_percent(self, track_percent: int | None) -> int:
        total = max(1, int(self._batch_total or 1))
        track = max(0, min(100, int(track_percent or 0)))
        overall = ((self._batch_completed + self._batch_failures) * 100 + track) / total
        return max(0, min(100, int(round(overall))))

    def _on_export_progress(self, payload: object) -> None:
        if not isinstance(payload, dict) or not self._workspace:
            return
        percent = payload.get("progressPercent")
        video_codec = str(payload.get("videoCodec") or self._workspace.export.video_codec or "").strip() or None
        message = format_export_status_message(
            str(payload.get("message") or payload.get("status") or "Exporting…"),
            video_codec=video_codec,
        )
        overall = (
            self._batch_overall_percent(percent)
            if isinstance(percent, int)
            else self._workspace.export.progress_percent
        )
        export_updates: dict[str, object] = {
            "running": True,
            "current_status": message,
            "progress_percent": overall,
            "completed_jobs": self._batch_completed,
        }
        if video_codec:
            export_updates["video_codec"] = video_codec
        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "export": self._workspace.export.model_copy(update=export_updates)
                }
            )
        )

    def _on_export_succeeded(self, output_path: object) -> None:
        self._export_start_pending = False
        self._batch_completed += 1
        if isinstance(output_path, str) and output_path.strip():
            self._batch_outputs.append(output_path)
        if not isinstance(output_path, str) or not self._workspace:
            return
        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "export": self._workspace.export.model_copy(
                        update={
                            "current_status": f"Exported {Path(output_path).name}",
                            "current_output_path": None,
                            "last_output_path": output_path,
                            "progress_percent": self._batch_overall_percent(0),
                            "completed_jobs": self._batch_completed,
                        }
                    )
                }
            )
        )

    def _on_export_failed(self, message: str) -> None:
        self._export_start_pending = False
        self._batch_failures += 1
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "current_status": message or "Track export failed.",
                            }
                        )
                    }
                )
            )
        notify_action(message or "Track export failed.", tone="error")
        log_error(message or "Track export failed.", category="video")

    def prepare_app_quit(self) -> None:
        """Stop batch chaining and cancel live exports before window teardown."""
        self._stop_export_pending = True
        self._batch_queue = []
        self._export_start_pending = False
        for worker in (self._export_worker, self._pipeline_export_worker, self._billing_worker):
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    cancel = getattr(worker, "cancel", None)
                    if callable(cancel):
                        cancel()
            except RuntimeError:
                pass

    def _on_export_worker_finished(self) -> None:
        # Batch chaining lives here so the finished worker is fully released
        # before the next one starts (python_app keeps going after failures).
        self._export_start_pending = False
        worker = self._export_worker
        self._export_worker = None
        self._release_export_qthread(worker, wait_ms=1_000)
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting() or self._stop_export_pending:
            self._batch_queue = []
            if not is_app_quitting():
                self._finalize_batch_export(stopped=True)
            return
        if self._batch_queue:
            self._start_next_batch_export()
            return
        self._finalize_batch_export(stopped=False)
        self._update_export_panel()

    def _finalize_batch_export(self, *, stopped: bool) -> None:
        if not self._workspace:
            return
        completed = self._batch_completed
        total = max(1, int(self._batch_total or 1))
        failures = self._batch_failures
        manual_ref = str(self._video_billing_charge.get("ref_id") or "") or None
        # User stop: keep completed + cancelled in-progress track; refund never-started only.
        # Technical fail: refund every track that did not produce an output.
        self._apply_video_refund_for_outcome(
            reason=(
                "Manual export stopped (unused tracks)."
                if stopped
                else "Manual export tracks failed."
            ),
            completed=completed,
            user_stop=stopped,
            in_progress=stopped,
        )
        self._report_export_telemetry(
            operation_type="video_manual",
            track_count=total,
            completed_count=completed,
            ref_id=manual_ref,
        )
        if stopped:
            self._stop_export_pending = False
            message = f"Export stopped · {completed}/{total} video(s) finished."
        elif failures:
            message = f"Export complete · {completed}/{total} video(s), {failures} failed."
        else:
            message = f"Export complete · {completed}/{total} video(s)."

        auto_merge = bool(self._workspace.export.auto_merge)
        if not stopped and auto_merge and completed >= 2 and self._batch_output_dir:
            shuffle_merge = bool(self._workspace.export.shuffle_merge)
            ffmpeg_path = str(self._settings.get("ffmpegPath") or "ffmpeg")
            verified_paths = collect_verified_merge_inputs(
                list(self._batch_outputs),
                run_dir=self._batch_output_dir,
                branch="long",
                ffmpeg_path=ffmpeg_path,
            )
            if len(verified_paths) < 2:
                message = (
                    f"{message} Merge skipped — need at least two usable MP4 files "
                    f"(found {len(verified_paths)})."
                )
            else:
                encode_fields = self._encode_fields_for_merge_context("long", pipeline=False)
                self._pipeline_merge_context = {
                    "run_dir": self._batch_output_dir,
                    "branch": "long",
                    "batch_id": f"manual-{int(time.time())}",
                    "role": "PRIMARY",
                    "auto_merge": True,
                    "completed": completed,
                    "total": total,
                    # Verified on-disk outputs only (never stamped/missing paths).
                    "mp4_paths": verified_paths,
                    "shuffle": shuffle_merge,
                    **encode_fields,
                }
                self._publish_workspace(
                    self._workspace.model_copy(
                        update={
                            "export": self._workspace.export.model_copy(
                                update={
                                    "running": True,
                                    "merge_running": True,
                                    "merge_progress_percent": 0,
                                    "current_status": "Merging video outputs…",
                                    "progress_percent": 100,
                                    "completed_jobs": completed,
                                }
                            )
                        }
                    )
                )
                self._start_pipeline_merge()
                return

        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "export": self._workspace.export.model_copy(
                        update={
                            "running": False,
                            "current_status": message,
                            "current_output_path": None,
                            "progress_percent": 100 if not stopped else self._workspace.export.progress_percent,
                            "completed_jobs": completed,
                        }
                    )
                }
            )
        )
        notify_action(
            message,
            tone="warning" if (failures or stopped or "Merge skipped" in message) else "success",
        )

    def _on_pipeline_export_progress(self, payload: object) -> None:
        if not isinstance(payload, dict) or not self._workspace:
            return
        completed = payload.get("completedJobs")
        total = payload.get("totalJobs")
        percent = payload.get("progressPercent")
        video_codec = str(payload.get("videoCodec") or self._workspace.export.video_codec or "").strip() or None
        message = format_export_status_message(
            str(payload.get("message") or payload.get("status") or "Exporting…"),
            video_codec=video_codec,
        )
        current_path = str(payload.get("currentMp3Path") or "")
        output_path = str(payload.get("outputPath") or "")
        updates: dict[str, object] = {
            "running": True,
            "current_status": message,
        }
        if video_codec:
            updates["video_codec"] = video_codec
        if isinstance(completed, int):
            updates["completed_jobs"] = completed
        if isinstance(total, int):
            updates["total_jobs"] = total
        if isinstance(percent, int):
            updates["progress_percent"] = percent
        if current_path:
            updates["current_output_path"] = output_path or None
        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "selected_mp3_path": current_path or self._workspace.selected_mp3_path,
                    "export": self._workspace.export.model_copy(update=updates),
                }
            )
        )

    def _on_pipeline_export_succeeded(self, payload: object) -> None:
        self._pipeline_start_pending = False
        if not isinstance(payload, dict) or not self._workspace:
            return

        message = str(payload.get("message") or "Pipeline export completed.")
        last_output = str(payload.get("lastOutputPath") or "").strip() or None
        completed = int(payload.get("completed") or self._workspace.export.total_jobs or 0)
        total = int(payload.get("total") or self._workspace.export.total_jobs or completed)
        studio_ref = str(self._video_billing_charge.get("ref_id") or "") or None
        # Partial delivery without user stop = technical shortfall → refund undelivered.
        self._apply_video_refund_for_outcome(
            reason="Pipeline export completed with fewer tracks than charged.",
            completed=completed,
            user_stop=False,
            in_progress=False,
        )
        self._report_export_telemetry(
            operation_type="video",
            track_count=total,
            completed_count=completed,
            codec=str(payload.get("videoCodec") or "").strip() or None,
            ref_id=studio_ref,
        )
        merge_context = dict(self._pipeline_merge_context or {})
        merge_context["completed"] = completed
        merge_context["total"] = total
        self._pipeline_merge_context = merge_context

        if merge_context.get("auto_merge"):
            branch_label = "reel" if str(merge_context.get("branch") or "") == "reel" else "long"
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": True,
                                "merge_running": True,
                                "merge_progress_percent": 0,
                                "current_status": f"Merging {branch_label} video outputs…",
                                "current_output_path": None,
                                "last_output_path": last_output,
                                "progress_percent": 100,
                                "completed_jobs": completed,
                                "total_jobs": total,
                            }
                        )
                    }
                )
            )
            self._start_pipeline_merge()
            return

        self._stop_export_pending = False
        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "export": self._workspace.export.model_copy(
                        update={
                            "running": False,
                            "merge_running": False,
                            "current_status": message,
                            "current_output_path": None,
                            "last_output_path": last_output,
                            "progress_percent": 100,
                            "completed_jobs": completed,
                            "total_jobs": total,
                        }
                    )
                }
            )
        )
        notify_action(message, tone="success")
        # Single-track runs skip merge — treat export finish as conclusive completion.
        if int(merge_context.get("total") or completed or 0) <= 1:
            from shared.lib.pipeline_completion import mark_desktop_pipeline_complete

            mark_desktop_pipeline_complete(
                self._api,
                batch_id=str(merge_context.get("batch_id") or ""),
                profile_id=str(merge_context.get("profile_id") or ""),
                role=str(merge_context.get("role") or "OK"),
                run_dir=str(merge_context.get("run_dir") or ""),
            )

    def _start_pipeline_merge(self) -> None:
        context = dict(self._pipeline_merge_context or {})
        run_dir = str(context.get("run_dir") or "").strip()
        branch = str(context.get("branch") or "long").strip()
        if not run_dir:
            self._on_pipeline_merge_failed("Pipeline merge context is missing a run directory.")
            return
        mp4_paths_raw = [str(path) for path in (context.get("mp4_paths") or []) if str(path).strip()]
        ffmpeg_path = str(self._settings.get("ffmpegPath") or "ffmpeg")
        verified_paths = collect_verified_merge_inputs(
            mp4_paths_raw,
            run_dir=run_dir,
            branch=branch,
            ffmpeg_path=ffmpeg_path,
        )
        if len(verified_paths) < 2:
            self._on_pipeline_merge_failed(
                f"Merge skipped — need at least two usable MP4 files (found {len(verified_paths)})."
            )
            return
        context["mp4_paths"] = verified_paths
        self._pipeline_merge_context = context
        profile_id = str(context.get("profile_id") or "").strip() or None
        ref_base = str(context.get("ref_base") or "")
        try:
            merge_bill = consume_video_operation(
                self._api,
                operation_type="video_merge",
                count=1,
                channel_profile_id=profile_id,
                ref_id=f"video_merge:{ref_base}",
            )
            self._merge_billing_charge = {
                "operation_type": "video_merge",
                "count": 1,
                "charged_credit_units": merge_bill.charged_credit_units,
                "channel_profile_id": profile_id,
                "ref_id": f"video_merge:{ref_base}",
            }
        except Exception as exc:
            notify_action(f"Merge blocked (billing): {exc}", tone="warning")
            if self._workspace:
                self._publish_workspace(
                    self._workspace.model_copy(
                        update={
                            "export": self._workspace.export.model_copy(
                                update={
                                    "running": False,
                                    "merge_running": False,
                                    "current_status": f"Export complete; merge blocked (billing): {exc}",
                                }
                            )
                        }
                    )
                )
            return
        mp4_paths = tuple(verified_paths)
        encode = merge_encode_settings_from_context(context, pipeline=True)
        # Manual batches stash pipeline=False encode fields; prefer context values either way.
        if str(context.get("batch_id") or "").startswith("manual-"):
            encode = merge_encode_settings_from_context(context, pipeline=False)
        worker = VideoPipelineMergeWorker(
            PipelineMergeRequest(
                run_dir=run_dir,
                branch=branch,
                batch_id=str(context.get("batch_id") or ""),
                role=str(context.get("role") or ""),
                ffmpeg_path=ffmpeg_path,
                completed=int(context.get("completed") or 0),
                total=int(context.get("total") or 0),
                mp4_paths=mp4_paths,
                shuffle=bool(context.get("shuffle", True)),
                encode=encode,
            ),
            parent=None,
        )
        worker.progressed.connect(self._on_pipeline_merge_progress)
        worker.succeeded.connect(self._on_pipeline_merge_succeeded)
        worker.failed.connect(self._on_pipeline_merge_failed)
        worker.finished.connect(self._on_pipeline_merge_worker_finished)
        self._pipeline_merge_worker = worker
        track_video_pipeline_thread(worker)
        worker.start()
        notify_action("Merging video outputs…", tone="neutral")

    def _on_pipeline_merge_progress(self, payload: object) -> None:
        if not isinstance(payload, dict) or not self._workspace:
            return
        message = str(payload.get("message") or "Merging video outputs…")
        merge_percent = payload.get("progress")
        try:
            merge_progress = max(0, min(100, int(merge_percent))) if merge_percent is not None else None
        except (TypeError, ValueError):
            merge_progress = None
        update: dict[str, object] = {
            "running": True,
            "merge_running": True,
            "current_status": message,
        }
        if merge_progress is not None:
            update["merge_progress_percent"] = merge_progress
        self._publish_workspace(
            self._workspace.model_copy(
                update={"export": self._workspace.export.model_copy(update=update)}
            )
        )

    def _on_pipeline_merge_succeeded(self, payload: object) -> None:
        self._stop_export_pending = False
        self._clear_merge_billing_charge()
        if not isinstance(payload, dict) or not self._workspace:
            return
        message = str(payload.get("message") or "Pipeline merge completed.")
        merged_output = str(payload.get("mergedOutputPath") or "").strip() or None
        completed = int(payload.get("completed") or self._workspace.export.completed_jobs or 0)
        total = int(payload.get("total") or self._workspace.export.total_jobs or completed)
        self._publish_workspace(
            self._workspace.model_copy(
                update={
                    "export": self._workspace.export.model_copy(
                        update={
                            "running": False,
                            "merge_running": False,
                            "merge_progress_percent": None,
                            "current_status": message,
                            "current_output_path": None,
                            "last_merged_output_path": merged_output,
                            "progress_percent": 100,
                            "completed_jobs": completed,
                            "total_jobs": total,
                        }
                    )
                }
            )
        )
        notify_action(message, tone="success")
        merge_context = dict(self._pipeline_merge_context or {})
        from shared.lib.pipeline_completion import mark_desktop_pipeline_complete

        mark_desktop_pipeline_complete(
            self._api,
            batch_id=str(merge_context.get("batch_id") or ""),
            profile_id=str(merge_context.get("profile_id") or ""),
            role=str(merge_context.get("role") or "OK"),
            run_dir=str(
                merge_context.get("run_dir")
                or (self._workspace.export.output_dir if self._workspace else "")
                or ""
            ),
        )

    def _on_pipeline_merge_failed(self, message: str) -> None:
        user_stop = self._is_user_initiated_stop(
            message,
            stopped_flag=self._stop_export_pending,
        )
        self._stop_export_pending = False
        if user_stop:
            # User cancelled after merge started — keep merge charge.
            self._clear_merge_billing_charge()
        else:
            self._refund_merge_billing_charge(message or "Video merge failed.")
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": False,
                                "merge_running": False,
                                "merge_progress_percent": None,
                                "current_status": message or "Video merge failed.",
                            }
                        )
                    }
                )
            )
        notify_action(message or "Video merge failed.", tone="error")
        log_error(message or "Video merge failed.", category="video")

    def _on_pipeline_merge_worker_finished(self) -> None:
        worker = self._pipeline_merge_worker
        self._pipeline_merge_worker = None
        self._pipeline_merge_context = None
        self._release_export_qthread(worker, wait_ms=1_000)
        self._update_export_panel()

    def _on_pipeline_export_failed(self, message: str) -> None:
        self._pipeline_start_pending = False
        user_stop = self._is_user_initiated_stop(
            message,
            stopped_flag=self._stop_export_pending,
        )
        self._stop_export_pending = False
        completed = int(self._workspace.export.completed_jobs or 0) if self._workspace else 0
        self._apply_video_refund_for_outcome(
            reason=(
                "Pipeline export stopped (unused tracks)."
                if user_stop
                else (message or "Pipeline export failed.")
            ),
            completed=completed,
            user_stop=user_stop,
            in_progress=user_stop,
        )
        self._report_export_telemetry(
            operation_type="video",
            track_count=int(self._video_billing_charge.get("count") or completed or 0),
            completed_count=completed,
            ref_id=str(self._video_billing_charge.get("ref_id") or "") or None,
        )
        if self._workspace:
            self._publish_workspace(
                self._workspace.model_copy(
                    update={
                        "export": self._workspace.export.model_copy(
                            update={
                                "running": False,
                                "current_status": message or "Pipeline export failed.",
                            }
                        )
                    }
                )
            )
        notify_action(message or "Pipeline export failed.", tone="error")
        log_error(message or "Pipeline export failed.", category="video")

    def _on_pipeline_export_worker_finished(self) -> None:
        self._pipeline_start_pending = False
        # If cancel finished without a failed signal, still apply user-stop refund rules once.
        if self._stop_export_pending and self._video_billing_charge:
            completed = int(self._workspace.export.completed_jobs or 0) if self._workspace else 0
            self._apply_video_refund_for_outcome(
                reason="Pipeline export stopped (unused tracks).",
                completed=completed,
                user_stop=True,
                in_progress=True,
            )
        self._stop_export_pending = False
        worker = self._pipeline_export_worker
        self._pipeline_export_worker = None
        self._release_export_qthread(worker, wait_ms=1_000)
        self._update_export_panel()

    def _open_export_output_folder(self) -> None:
        if not self._workspace:
            return
        export = self._workspace.export
        folder = str(export.output_dir or "").strip()
        if not folder:
            current = str(export.current_output_path or export.last_output_path or "").strip()
            folder = str(Path(current).parent) if current else ""
        if folder and Path(folder).is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _open_export_output_file(self) -> None:
        if not self._workspace:
            return
        export = self._workspace.export
        target = str(export.current_output_path or export.last_output_path or "").strip()
        if target and Path(target).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def _update_preview(self) -> None:
        if not self._workspace or not self._template_draft or self._loading:
            return
        track_paths = self._current_track_paths()
        active_track = str(self._workspace.selected_mp3_path or "")
        self._flush_active_spectrum_instance_layers()
        renderer_template = self._template_normalizer.to_renderer_dict(
            base=dict(self._workspace.template),
            draft=self._template_draft,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
            spectrum_instances=self._spectrum_instances,
            workspace={
                "logoPath": self._workspace.logo_path,
                "trackPaths": track_paths,
                "selectedMp3Path": active_track,
                "pipelineAlbum": str(
                    self._settings.get("lastAlbumName") or self._settings.get("album") or ""
                ),
            },
            track_paths=track_paths,
            active_track_path=active_track or None,
        )
        aspect = self._workspace.preview_aspect_ratio
        background_edit, spectrum_position_edit, text_domain_edit, lightning_position_edit, logo_position_edit = (
            resolve_preview_edit_modes(
                self._active_domain_tab,
                self._active_side_tab,
                edit_focus=self._preview_edit_focus,
            )
        )
        self._stage.set_preview_edit_modes(
            background=background_edit,
            spectrum_position=spectrum_position_edit,
            text_domain=text_domain_edit,
            lightning_position=lightning_position_edit,
            logo_position=logo_position_edit,
        )
        self._stage.set_selected_lightning_layer_index(self._selected_lightning_layer_index)
        if hasattr(self._stage, "set_selected_spectrum_instance_index"):
            self._stage.set_selected_spectrum_instance_index(self._selected_spectrum_instance_index)
        self._sync_text_drag_overlay(text_domain_edit)
        self._stage.set_renderer_preview(
            template=renderer_template,
            background_path=self._workspace.background_path,
            logo_path=self._workspace.logo_path,
            mp3_path=self._workspace.selected_mp3_path,
            aspect_width=int(aspect.width),
            aspect_height=int(aspect.height),
        )
        self._schedule_stage_summary_update()

    def _sync_text_drag_overlay(self, text_domain: str) -> None:
        """Keep transparent drag catcher in sync with Album/Title draft (GPU draws text)."""
        if not self._template_draft:
            return
        key = str(text_domain or "").strip().lower()
        if key not in {"album", "title"}:
            self._stage.bind_text_drag_overlay(
                domain="",
                enabled=False,
                lines=[],
                anchor="top-left",
                x=0.0,
                y=0.0,
                font_family="Arial",
                font_size=36.0,
                bold=False,
                italic=False,
                color="#ffffff",
                box_width=0.0,
                line_spacing=1.2,
                letter_spacing=0.0,
                content_width=0.0,
                content_height=0.0,
            )
            return
        track_paths = self._current_track_paths()
        if key == "album":
            settings = album_settings_from_draft(self._template_draft)
            text = resolve_album_display_text(
                settings,
                pipeline_album=str(self._settings.get("lastAlbumName") or self._settings.get("album") or ""),
            )
            lines = [text] if text else []
            style = settings.get("style") if isinstance(settings.get("style"), dict) else {}
            bounds = measure_album_layout_bounds(text, style) if text else {"contentWidth": 0.0, "contentHeight": 0.0}
            self._stage.bind_text_drag_overlay(
                domain="album",
                enabled=bool(settings.get("enabled")) and bool(lines),
                lines=lines,
                anchor="top-left",
                x=float(style.get("x", 0) or 0),
                y=float(style.get("y", 0) or 0),
                font_family=str(style.get("fontFamily") or "Arial"),
                font_size=float(style.get("fontSize", 10) or 10),
                bold=bool(style.get("bold", False)),
                italic=bool(style.get("italic", False)),
                color=str(style.get("color") or "#ffffff"),
                render_base_height=float(self._template_draft.get("renderBaseHeight") or 450.0),
                box_width=float(style.get("boxWidth", 0) or 0),
                line_spacing=float(style.get("lineSpacing", 1.2) or 1.2),
                letter_spacing=float(style.get("letterSpacing", 0) or 0),
                content_width=float(bounds.get("contentWidth", 0) or 0),
                content_height=float(bounds.get("contentHeight", 0) or 0),
            )
            return
        settings = title_settings_from_draft(self._template_draft)
        titles = resolve_title_display_list(settings, track_paths=track_paths)
        style = settings.get("style") if isinstance(settings.get("style"), dict) else {}
        # Show numbered lines so the ghost matches the GPU title list.
        lines: list[str] = []
        list_style = str(settings.get("listStyle") or "numbered")
        indent = str(settings.get("numberIndent") or "aligned")
        for index, title in enumerate(titles[:24]):
            marker = format_title_marker(index, list_style, total=len(titles), indent=indent)
            lines.append(f"{marker}{title}".strip() if not marker else f"{marker}{title}")
        if str(settings.get("layout") or "").lower() == "list_card":
            from features.video.lib.playlist_list_card import playlist_list_card_bounds

            card = playlist_list_card_bounds(settings, titles)
            self._stage.bind_text_drag_overlay(
                domain="title",
                enabled=bool(settings.get("enabled")) and bool(titles),
                lines=lines or ["Playlist"],
                anchor="top-left",
                x=float(card["x"]),
                y=float(card["y"]),
                font_family=str(style.get("fontFamily") or "Arial"),
                font_size=float(style.get("fontSize", 10) or 10),
                bold=bool(style.get("bold", False)),
                italic=bool(style.get("italic", False)),
                color=str(style.get("color") or "#ffffff"),
                render_base_height=float(self._template_draft.get("renderBaseHeight") or 450.0),
                box_width=float(card["contentWidth"]),
                line_spacing=float(style.get("lineSpacing", 1.2) or 1.2),
                letter_spacing=float(style.get("letterSpacing", 0) or 0),
                content_width=float(card["contentWidth"]),
                content_height=float(card["contentHeight"]),
            )
            return
        bounds = (
            measure_title_layout_bounds(
                titles,
                list_style=str(settings.get("listStyle") or "number"),
                layout=str(settings.get("layout") or "column"),
                style=style,
                number_indent=indent,
            )
            if titles
            else {"contentWidth": 0.0, "contentHeight": 0.0}
        )
        from features.video.lib.text_domain_runtime import playlist_panel_frame_pad

        pad = playlist_panel_frame_pad(settings, style)
        pill_extra = 0.0
        if bool(settings.get("nowPlayingPill")) and titles:
            font_size = float(style.get("fontSize", 10) or 10)
            pill_extra = float(max(14.0, font_size * 1.15) + max(4.0, font_size * 0.35))
        self._stage.bind_text_drag_overlay(
            domain="title",
            enabled=bool(settings.get("enabled")) and bool(lines),
            lines=lines,
            anchor="top-left",
            x=float(style.get("x", 0) or 0),
            y=float(style.get("y", 0) or 0),
            font_family=str(style.get("fontFamily") or "Arial"),
            font_size=float(style.get("fontSize", 10) or 10),
            bold=bool(style.get("bold", False)),
            italic=bool(style.get("italic", False)),
            color=str(style.get("color") or "#ffffff"),
            render_base_height=float(self._template_draft.get("renderBaseHeight") or 450.0),
            box_width=float(style.get("boxWidth", 0) or 0),
            line_spacing=float(style.get("lineSpacing", 1.2) or 1.2),
            letter_spacing=float(style.get("letterSpacing", 0) or 0),
            content_width=float(bounds.get("contentWidth", 0) or 0) + pad * 2.0,
            content_height=float(bounds.get("contentHeight", 0) or 0) + pad * 2.0 + pill_extra,
        )

    def _update_stage_summary(self) -> None:
        if not self._workspace:
            return
        background_path = str(self._workspace.background_path or "").strip()
        background_source = "Manual preview background" if background_path else "No background attached"

        logo_path = str(self._workspace.logo_path or "").strip()
        track_path = str(self._workspace.selected_mp3_path or "").strip()
        run_directory = str(self._workspace.mp3_directory or "").strip()

        track_detail = ""
        if track_path:
            parent = str(Path(track_path).parent)
            track_detail = f"{Path(track_path).name} · {parent}"

        self._right_rail.bind_asset_summary(
            background_path=background_path,
            background_source_label=background_source,
            logo_path=logo_path,
            track_path=track_path,
            track_detail=track_detail,
            run_directory=run_directory,
        )
        self._stage.bind_output_resolution(
            self._workspace.output_resolution,
            pending=self._resolution_save_pending,
        )
        self._stage.set_current_track(track_path)

    def _save_output_resolution(self, resolution: str, *, force_standard_tier: bool = False) -> None:
        if not self._workspace:
            return
        normalized = str(resolution or "").strip()
        if not normalized or normalized == self._workspace.output_resolution:
            return
        if self._settings_patch_worker is not None and self._settings_patch_worker.isRunning():
            return

        self._resolution_save_pending = True
        notify_action("Saving output resolution…", tone="neutral")
        self._workspace = self._store.set_output_resolution(normalized, settings=self._settings)
        self._settings["outputResolution"] = normalized
        self._settings["imageResolution"] = normalized
        patch: dict[str, object] = {
            "outputResolution": normalized,
            "imageResolution": normalized,
        }
        if force_standard_tier:
            self._settings["videoExportTier"] = "standard"
            patch["videoExportTier"] = "standard"
        self._update_stage_summary()
        self._update_preview()
        self._update_export_panel()

        worker = PatchSettingsWorker(
            self._api,
            patch,
            parent=None,
        )
        worker.succeeded.connect(self._on_output_resolution_saved)
        worker.failed.connect(self._on_output_resolution_save_failed)
        worker.finished.connect(lambda: setattr(self, "_settings_patch_worker", None))
        self._settings_patch_worker = worker
        worker.start()

    def _on_output_resolution_saved(self, _payload: object) -> None:
        self._resolution_save_pending = False
        if self._workspace:
            self._update_stage_summary()
        notify_action("Output resolution updated.", tone="success")

    def _on_output_resolution_save_failed(self, message: str) -> None:
        self._resolution_save_pending = False
        if self._workspace:
            self._update_stage_summary()
        notify_action(message or "Unable to update output resolution right now.", tone="error")

    def _issue_preview_playback_command(self, command: str) -> None:
        self._stage.issue_playback_command(command)

    def _seek_preview_playback(self, time_sec: float) -> None:
        self._stage.seek_preview(time_sec)

    def _on_preview_playback_state_changed(self, payload: object) -> None:
        if not isinstance(payload, dict) or not self._workspace:
            return
        playback = VideoPlaybackState(
            is_playing=bool(payload.get("isPlaying")),
            is_ready=bool(payload.get("isReady")),
            is_loading=bool(payload.get("isLoading")),
            current_time_sec=float(payload.get("currentTimeSec") or 0.0),
            duration_sec=float(payload.get("durationSec") or 0.0),
        )
        self._workspace = self._workspace.model_copy(update={"playback": playback})
        self._stage.sync_playback_transport(playback)
        try:
            from shared.services.music_download_coordinator import get_music_download_coordinator
            from shared.services.video_pipeline_coordinator import get_video_pipeline_coordinator

            playing = bool(playback.is_playing)
            music = get_music_download_coordinator()
            if music is not None:
                music.set_preview_playing(playing)
            pipeline = get_video_pipeline_coordinator()
            if pipeline is not None:
                pipeline.set_preview_playing(playing)
        except Exception:
            pass
        # Double-click auto-play: start once mixer decode is ready.
        if self._pending_preview_auto_play and playback.is_ready:
            self._flush_pending_preview_auto_play()

    def _on_preview_spectrum_position_changed(self, x: int, y: int) -> None:
        if not self._template_draft:
            return
        pos_cfg = self._template_draft.get("position") if isinstance(self._template_draft.get("position"), dict) else {}
        anchor = str(pos_cfg.get("anchor") or self._template_draft.get("anchor") or "center")
        self._patch_template_draft({"anchor": anchor, "positionX": int(x), "positionY": int(y)})
        if self._spectrum_instances:
            idx = max(0, min(self._selected_spectrum_instance_index, len(self._spectrum_instances) - 1))
            inst = dict(self._spectrum_instances[idx]) if isinstance(self._spectrum_instances[idx], dict) else {}
            inst["x"] = float(x)
            inst["y"] = float(y)
            inst["anchor"] = anchor
            self._spectrum_instances[idx] = inst

    def _on_preview_lightning_position_changed(self, x: int, y: int) -> None:
        if not self._lightning_layers:
            return
        index = max(0, min(self._selected_lightning_layer_index, len(self._lightning_layers) - 1))
        self._patch_selected_lightning_layer({"x": float(x), "y": float(y)})

    def _on_preview_logo_position_changed(self, x: int, y: int) -> None:
        if not self._template_draft:
            return
        patch: dict = {"logoPositionX": int(x), "logoPositionY": int(y)}
        # While attached, shared spectrum position must move with the logo.
        if bool(self._template_draft.get("spectrumAttachToLogo", True)):
            anchor = str(self._template_draft.get("anchor") or "center")
            patch.update({"anchor": anchor, "positionX": int(x), "positionY": int(y)})
        self._patch_template_draft(patch)

    def _reset_logo_center(self) -> None:
        """Center the logo (and attached spectrum) in the preview frame."""
        if not self._template_draft:
            return
        patch: dict = {"logoPositionX": 0, "logoPositionY": 0}
        if bool(self._template_draft.get("spectrumAttachToLogo", True)):
            patch.update({"anchor": "center", "positionX": 0, "positionY": 0})
        self._patch_template_draft(patch)
        notify_action("Logo centered in the preview.", tone="success")

    def _on_preview_text_domain_position_changed(self, domain: str, x: float, y: float) -> None:
        """Persist Album/Title offsets after GPU real-time drag ends."""
        if not self._template_draft:
            return
        key = str(domain or "").strip().lower()
        if key == "album":
            patch = {"albumX": float(x), "albumY": float(y)}
        elif key == "title":
            patch = {"titleX": float(x), "titleY": float(y)}
        else:
            return
        self._template_draft = {**self._template_draft, **patch}
        self._inspector_rebind_timer.start()
        self._schedule_dirty_state_update()
        self._schedule_local_draft_persist()
        # Quiet resync so inject_text_domains matches the baked GPU position.
        self._schedule_preview_update(delay_ms=60)

    def _text_domain_box_patch(self, domain: str, patch: object) -> dict:
        """Map overlay resize patch → draft keys."""
        if not isinstance(patch, dict):
            return {}
        key = str(domain or "").strip().lower()
        if key not in {"album", "title"}:
            return {}
        prefix = "album" if key == "album" else "title"
        out: dict = {}
        if "boxWidth" in patch:
            out[f"{prefix}BoxWidth"] = float(max(0.0, min(2000.0, float(patch["boxWidth"]))))
        if "fontSize" in patch:
            out[f"{prefix}FontSize"] = float(max(5.0, min(200.0, float(patch["fontSize"]))))
        if "letterSpacing" in patch:
            out[f"{prefix}LetterSpacing"] = float(max(-20.0, min(40.0, float(patch["letterSpacing"]))))
        if "lineSpacing" in patch:
            out[f"{prefix}LineSpacing"] = float(max(0.8, min(2.5, float(patch["lineSpacing"]))))
        if "x" in patch:
            out[f"{prefix}X"] = float(max(-2000.0, min(2000.0, float(patch["x"]))))
        if "y" in patch:
            out[f"{prefix}Y"] = float(max(-2000.0, min(2000.0, float(patch["y"]))))
        return out

    def _on_preview_text_domain_box_resize_changed(self, domain: str, patch: object) -> None:
        """Live CapCut reflow while resizing — update draft + GPU, skip heavy persist."""
        if not self._template_draft:
            return
        out = self._text_domain_box_patch(domain, patch)
        if not out:
            return
        self._template_draft = {**self._template_draft, **out}
        # Immediate preview so wrap/scale track the handle (~30 fps throttled upstream).
        self._flush_preview_update()

    def _on_preview_text_domain_box_resized(self, domain: str, patch: object) -> None:
        """Persist CapCut-like box transform after resize (wrap and/or scale)."""
        out = self._text_domain_box_patch(domain, patch)
        if not out:
            return
        self._patch_template_draft(out)
        self._schedule_local_draft_persist()
        self._schedule_dirty_state_update()
        self._flush_preview_update()

    def _on_preview_background_transform_changed(self, offset_x: float, offset_y: float, scale: float) -> None:
        if not self._workspace or not self._template_draft:
            return
        template = dict(self._workspace.template)
        background_settings = template.get("backgroundSettings")
        background_settings = dict(background_settings) if isinstance(background_settings, dict) else {}
        background_settings.update(
            {
                "userOffsetX": float(offset_x),
                "userOffsetY": float(offset_y),
                "userScale": float(scale),
            }
        )
        template["backgroundSettings"] = background_settings
        self._workspace = self._workspace.model_copy(update={"template": template})
        self._template_draft = {
            **self._template_draft,
            "backgroundUserScale": float(scale),
        }
        self._schedule_dirty_state_update()

    def _select_background(self) -> None:
        if not self._template_draft:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select background image",
            self._workspace.background_path if self._workspace else "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        self._workspace = self._store.set_background_path(path, settings=self._settings)
        self._template_draft = {**self._template_draft, "backgroundPath": path}
        self._publish_workspace(self._workspace)
        self._update_inspectors()
        self._update_dirty_state()
        self._update_preview()
        notify_action("Applied the selected background image.", tone="success")

    def _effect_pack_selection(self, domain: str) -> dict[str, str] | None:
        if not self._template_draft:
            return None
        effect_packs = self._template_draft.get("effectPacks")
        if not isinstance(effect_packs, dict):
            return None
        entry = effect_packs.get(domain)
        if not isinstance(entry, dict):
            return None
        pack_id = str(entry.get("packId") or "").strip()
        version = str(entry.get("version") or "").strip()
        if not pack_id or not version:
            return None
        return {"packId": pack_id, "version": version}

    def _effect_pack_status(self, domain: str) -> dict:
        return resolve_effect_pack_selection_status(
            domain,
            self._effect_pack_selection(domain),
            self._effect_pack_catalog_items,
        )

    def _refresh_effect_pack_catalog(self) -> None:
        catalog = self._effect_pack_service.list_catalog()
        items = catalog.get("items")
        self._effect_pack_catalog_items = items if isinstance(items, list) else []
        self._update_effect_pack_selectors()

    def _update_effect_pack_selectors(self) -> None:
        for domain, selector in self._effect_pack_selectors.items():
            status = self._effect_pack_status(domain)
            options = build_effect_pack_catalog_options(domain, self._effect_pack_catalog_items)
            selector.bind_state(
                options=options,
                selected_value=selection_to_value(status.get("selection")),
                status=status,
                busy=self._effect_pack_busy,
            )
        self._update_spectrum_preset_options()
        self._update_particle_preset_options()
        self._update_background_preset_options()
        self._update_logo_preset_options()

    def _update_spectrum_preset_options(self) -> None:
        options = build_unified_spectrum_preset_options(self._effect_pack_catalog_items)
        self._spectrum_inspector.set_preset_options(options)

    def _update_particle_preset_options(self) -> None:
        options = build_unified_particle_preset_options(self._effect_pack_catalog_items)
        self._particles_inspector.set_preset_options(options)

    def _update_background_preset_options(self) -> None:
        options = build_unified_background_preset_options(self._effect_pack_catalog_items)
        self._background_inspector.set_preset_options(options)

    def _update_logo_preset_options(self) -> None:
        options = build_unified_logo_preset_options(self._effect_pack_catalog_items)
        self._logo_inspector.set_preset_options(options)

    def _resolve_effect_pack_catalog_item(self, domain: str, value: str) -> dict | None:
        selection = parse_effect_pack_catalog_value(value)
        if not selection:
            return None
        for item in self._effect_pack_catalog_items:
            if (
                item.get("domain") == domain
                and item.get("packId") == selection.get("packId")
                and item.get("version") == selection.get("version")
                and item.get("status") in {"ready", "available"}
            ):
                return item
        return None

    def _apply_effect_pack(self, domain: str, value: str) -> None:
        if not self._template_draft or not self._workspace:
            return
        item = self._resolve_effect_pack_catalog_item(domain, value)
        if not item:
            notify_action(f"Selected {domain} pack is unavailable.", tone="warning")
            return
        result = build_applied_effect_pack_draft_state(
            current_draft=self._template_draft,
            current_template=dict(self._workspace.template),
            logo_path=self._workspace.logo_path,
            domain=domain,
            item=item,
        )
        self._template_draft = result["nextDraft"]
        if domain == "spectrum":
            next_layers = result.get("nextLayers")
            if isinstance(next_layers, list):
                self._spectrum_layers = clone_layer_records(next_layers)
            self._selected_spectrum_layer_index = 0
            notify_action(f"Previewing {item.get('name')} ({item.get('version')}) in the local workspace draft.", tone="success")
        else:
            notify_action(f"Applied {item.get('name')} ({item.get('version')}) to the local {domain} draft.", tone="success")
        self._update_inspectors()
        self._update_dirty_state()

    def _clear_effect_pack(self, domain: str) -> None:
        if not self._template_draft or not self._workspace:
            return
        if domain == "spectrum":
            self._template_draft = build_video_template_draft(
                dict(self._workspace.template),
                logo_path=self._workspace.logo_path,
                background_path=self._workspace.background_path,
            )
            self._spectrum_layers = clone_layer_records(self._workspace.template.get("layers"))
            self._selected_spectrum_layer_index = 0
            notify_action("Restored the saved spectrum pack selection.", tone="success")
        else:
            result = build_cleared_effect_pack_draft_state(
                current_draft=self._template_draft,
                domain=domain,
            )
            self._template_draft = result["nextDraft"]
            notify_action(f"Cleared the local {domain} pack reference.", tone="success")
        self._update_inspectors()
        self._update_dirty_state()

    def _install_effect_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select effect pack zip",
            "",
            "Zip archives (*.zip)",
        )
        if not path:
            return
        self._effect_pack_busy = True
        self._update_effect_pack_selectors()
        result = self._effect_pack_service.install_from_file(path)
        self._effect_pack_busy = False
        if not result.get("ok"):
            notify_action(str(result.get("error") or "Unable to install effect pack."), tone="error")
            self._update_effect_pack_selectors()
            return
        item = result.get("item")
        if isinstance(item, dict):
            notify_action(
                f"Installed {item.get('name')} ({item.get('version')}) for {item.get('domain')}.",
                tone="success",
            )
        self._refresh_effect_pack_catalog()

    def _reload_effect_pack_catalog(self) -> None:
        self._effect_pack_busy = True
        self._update_effect_pack_selectors()
        self._refresh_effect_pack_catalog()
        self._effect_pack_busy = False
        self._update_effect_pack_selectors()
        notify_action("Reloaded the local effect pack catalog.", tone="success")

    def _toggle_effect_pack_enabled(self, domain: str) -> None:
        item = self._effect_pack_status(domain).get("item")
        if not isinstance(item, dict):
            return
        pack_id = str(item.get("packId") or "")
        enabled = not bool(item.get("enabled"))
        self._effect_pack_busy = True
        self._update_effect_pack_selectors()
        result = self._effect_pack_service.set_enabled(pack_id, enabled=enabled)
        self._effect_pack_busy = False
        if not result.get("ok"):
            notify_action(str(result.get("error") or "Unable to update effect pack state."), tone="error")
            self._update_effect_pack_selectors()
            return
        label = "Enabled" if enabled else "Disabled"
        notify_action(f"{label} {item.get('name')} ({item.get('version')}).")
        self._refresh_effect_pack_catalog()

    def _activate_effect_pack_version(self, domain: str) -> None:
        item = self._effect_pack_status(domain).get("item")
        if not isinstance(item, dict):
            return
        pack_id = str(item.get("packId") or "")
        version = str(item.get("version") or "")
        self._effect_pack_busy = True
        self._update_effect_pack_selectors()
        result = self._effect_pack_service.activate_version(pack_id, version)
        self._effect_pack_busy = False
        if not result.get("ok"):
            notify_action(str(result.get("error") or "Unable to activate effect pack version."), tone="error")
            self._update_effect_pack_selectors()
            return
        notify_action(f"Activated {item.get('name')} ({item.get('version')}).", tone="success")
        self._refresh_effect_pack_catalog()

    def _remove_effect_pack_version(self, domain: str) -> None:
        item = self._effect_pack_status(domain).get("item")
        if not isinstance(item, dict):
            return
        pack_id = str(item.get("packId") or "")
        version = str(item.get("version") or "")
        self._effect_pack_busy = True
        self._update_effect_pack_selectors()
        result = self._effect_pack_service.remove_version(pack_id, version)
        self._effect_pack_busy = False
        if not result.get("ok"):
            notify_action(str(result.get("error") or "Unable to remove effect pack version."), tone="error")
            self._update_effect_pack_selectors()
            return
        notify_action(f"Removed {item.get('name')} ({item.get('version')}).", tone="success")
        self._refresh_effect_pack_catalog()


    def _flush_active_spectrum_instance_layers(self) -> None:
        """Write working draft + ring layers into the selected Spectrum instance.

        Preview/export read per-instance ``style`` (waveform vs bars). Preset
        apply updates the flat draft; without this sync, Magma Ridge / Aurora /
        Plasma keep drawing as the previous bar style.
        """
        if not self._spectrum_instances:
            return
        from features.video.lib.spectrum_instance_registry import apply_draft_fields_to_instance

        idx = max(0, min(self._selected_spectrum_instance_index, len(self._spectrum_instances) - 1))
        inst = dict(self._spectrum_instances[idx]) if isinstance(self._spectrum_instances[idx], dict) else {}
        if self._template_draft:
            inst = apply_draft_fields_to_instance(inst, self._template_draft)
        inst["layers"] = clone_layer_records(self._spectrum_layers)
        self._spectrum_instances[idx] = inst

    def _commit_spectrum_preset_to_preview(self) -> None:
        """After style/stack preset changes: sync instance, inspectors, dirty, preview."""
        self._flush_active_spectrum_instance_layers()
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()

    def _project_selected_spectrum_instance(self) -> None:
        from features.video.lib.spectrum_instance_registry import (
            normalize_spectrum_instance,
            project_instance_to_draft_fields,
        )
        if not self._spectrum_instances:
            return
        idx = max(0, min(self._selected_spectrum_instance_index, len(self._spectrum_instances) - 1))
        inst = normalize_spectrum_instance(self._spectrum_instances[idx], index=idx)
        self._spectrum_instances[idx] = inst
        self._spectrum_layers = clone_layer_records(inst.get("layers") or [])
        self._selected_spectrum_layer_index = 0 if not self._spectrum_layers else min(
            self._selected_spectrum_layer_index, len(self._spectrum_layers) - 1
        )
        if self._template_draft is not None:
            self._template_draft = {**self._template_draft, **project_instance_to_draft_fields(inst)}

    def _set_spectrum_instances(self, instances: list[dict], *, selected_index: int) -> None:
        from features.video.lib.spectrum_instance_registry import normalize_spectrum_instances
        self._spectrum_instances = normalize_spectrum_instances(instances)
        self._selected_spectrum_instance_index = max(0, min(selected_index, max(len(self._spectrum_instances) - 1, 0)))
        self._project_selected_spectrum_instance()
        if hasattr(self, "_stage") and self._stage is not None:
            if hasattr(self._stage, "set_selected_spectrum_instance_index"):
                self._stage.set_selected_spectrum_instance_index(self._selected_spectrum_instance_index)
        self._update_inspectors()
        self._schedule_dirty_state_update()
        self._schedule_preview_update()

    def _select_spectrum_instance(self, index: int) -> None:
        self._flush_active_spectrum_instance_layers()
        self._selected_spectrum_instance_index = max(0, index)
        self._project_selected_spectrum_instance()
        if hasattr(self._stage, "set_selected_spectrum_instance_index"):
            self._stage.set_selected_spectrum_instance_index(self._selected_spectrum_instance_index)
        self._update_inspectors()
        self._schedule_preview_update()

    def _patch_selected_spectrum_instance(self, patch: dict) -> None:
        from features.video.lib.spectrum_instance_registry import normalize_spectrum_instance
        if not self._spectrum_instances:
            return
        idx = max(0, min(self._selected_spectrum_instance_index, len(self._spectrum_instances) - 1))
        current = self._spectrum_instances[idx] if isinstance(self._spectrum_instances[idx], dict) else {}
        next_inst = {**current, **(patch if isinstance(patch, dict) else {})}
        next_inst["layers"] = clone_layer_records(self._spectrum_layers)
        self._spectrum_instances[idx] = normalize_spectrum_instance(next_inst, index=idx)
        self._project_selected_spectrum_instance()
        self._update_inspectors(defer_rebind=True)
        self._schedule_dirty_state_update()
        self._schedule_preview_update()

    def _add_spectrum_instance(self) -> None:
        from features.video.lib.spectrum_instance_registry import default_spectrum_instance, normalize_spectrum_instances
        self._flush_active_spectrum_instance_layers()
        instances = list(self._spectrum_instances)
        if len(instances) >= 8:
            notify_action("Maximum of 8 Spectrums.", tone="warning")
            return
        basis = dict(instances[-1]) if instances else default_spectrum_instance(index=1)
        nxt = default_spectrum_instance(index=len(instances) + 1, layers=basis.get("layers") or self._spectrum_layers)
        nxt["x"] = float(basis.get("x", 0) or 0) + 40.0
        nxt["y"] = float(basis.get("y", 0) or 0)
        nxt["spectrumAttachToLogo"] = False
        instances.append(nxt)
        self._set_spectrum_instances(instances, selected_index=len(instances) - 1)

    def _duplicate_spectrum_instance(self) -> None:
        from features.video.lib.spectrum_instance_registry import default_spectrum_instance
        self._flush_active_spectrum_instance_layers()
        instances = list(self._spectrum_instances)
        if not instances or len(instances) >= 8:
            if len(instances) >= 8:
                notify_action("Maximum of 8 Spectrums.", tone="warning")
            return
        idx = max(0, min(self._selected_spectrum_instance_index, len(instances) - 1))
        basis = dict(instances[idx])
        name = str(basis.get("name") or "").strip()
        nxt = {
            **basis,
            "id": f"spectrum-{len(instances) + 1}",
            "name": f"{name} Copy" if name else f"Spectrum {len(instances) + 1}",
            "x": float(basis.get("x", 0) or 0) + 36.0,
            "layers": clone_layer_records(basis.get("layers") or self._spectrum_layers),
        }
        instances.append(nxt)
        self._set_spectrum_instances(instances, selected_index=len(instances) - 1)

    def _delete_spectrum_instance(self) -> None:
        instances = list(self._spectrum_instances)
        if len(instances) < 2:
            return
        idx = max(0, min(self._selected_spectrum_instance_index, len(instances) - 1))
        instances.pop(idx)
        self._set_spectrum_instances(instances, selected_index=max(0, idx - 1))

    def _move_spectrum_instance_up(self) -> None:
        instances = list(self._spectrum_instances)
        idx = max(0, min(self._selected_spectrum_instance_index, len(instances) - 1))
        if idx <= 0 or len(instances) < 2:
            return
        self._flush_active_spectrum_instance_layers()
        instances[idx - 1], instances[idx] = instances[idx], instances[idx - 1]
        self._set_spectrum_instances(instances, selected_index=idx - 1)

    def _move_spectrum_instance_down(self) -> None:
        instances = list(self._spectrum_instances)
        idx = max(0, min(self._selected_spectrum_instance_index, len(instances) - 1))
        if idx >= len(instances) - 1 or len(instances) < 2:
            return
        self._flush_active_spectrum_instance_layers()
        instances[idx + 1], instances[idx] = instances[idx], instances[idx + 1]
        self._set_spectrum_instances(instances, selected_index=idx + 1)

    def _set_spectrum_layers(
        self,
        layers: list[dict],
        *,
        selected_index: int,
        defer_rebind: bool = False,
        schedule_preview: bool = True,
    ) -> None:
        self._spectrum_layers = clone_layer_records(layers)
        self._selected_spectrum_layer_index = selected_index
        self._flush_active_spectrum_instance_layers()
        self._remember_active_spectrum_preset_session()
        self._update_inspectors(defer_rebind=defer_rebind, schedule_preview=schedule_preview)
        self._schedule_dirty_state_update()
        if schedule_preview:
            self._schedule_preview_update()

    def _set_lightning_layers(
        self,
        layers: list[dict],
        *,
        selected_index: int,
        defer_rebind: bool = False,
    ) -> None:
        from features.video.lib.lightning_style_registry import normalize_lightning_layers

        self._lightning_layers = normalize_lightning_layers(clone_layer_records(layers))
        self._selected_lightning_layer_index = selected_index
        self._update_inspectors(defer_rebind=defer_rebind)
        self._schedule_dirty_state_update()

    def _select_lightning_layer(self, index: int) -> None:
        self._selected_lightning_layer_index = max(0, index)
        self._stage.set_selected_lightning_layer_index(self._selected_lightning_layer_index)
        self._update_inspectors()

    def _patch_selected_lightning_layer(self, patch: dict) -> None:
        layers = clone_layer_records(self._lightning_layers)
        if not layers:
            from features.video.lib.lightning_style_registry import default_lightning_layer

            layers = [default_lightning_layer(index=1)]
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        current = layers[index] if isinstance(layers[index], dict) else {}
        next_layer = {**current, **(patch if isinstance(patch, dict) else {})}
        if isinstance(patch, dict) and isinstance(patch.get("color"), dict):
            color = current.get("color") if isinstance(current.get("color"), dict) else {}
            next_layer["color"] = {**color, **patch["color"]}
        layers[index] = next_layer
        structural = {"style", "direction", "blend", "name", "enabled", "trigger", "seedLock"}
        defer = not any(key in patch for key in structural)
        self._set_lightning_layers(layers, selected_index=index, defer_rebind=defer)

    def _apply_lightning_preset(self, preset_key: str) -> None:
        from features.video.lib.lightning_style_registry import (
            build_lightning_preset_layer_patch,
            is_lightning_preset_key,
        )

        if not is_lightning_preset_key(preset_key):
            return
        patch = build_lightning_preset_layer_patch(preset_key)
        if not patch:
            return
        # Ensure lightning is on when applying a look.
        if self._template_draft is not None and not bool(self._template_draft.get("lightningEnabled", False)):
            self._patch_template_draft({"lightningEnabled": True})
        self._patch_selected_lightning_layer(dict(patch))

    def _add_lightning_layer(self) -> None:
        from features.video.lib.lightning_style_registry import default_lightning_layer

        layers = clone_layer_records(self._lightning_layers)
        next_index = len(layers) + 1
        layers.append(default_lightning_layer(index=next_index))
        self._set_lightning_layers(layers, selected_index=len(layers) - 1)

    def _duplicate_lightning_layer(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        if not layers:
            self._add_lightning_layer()
            return
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        copy = dict(layers[index])
        copy["id"] = f"lightning-{len(layers) + 1}"
        copy["name"] = f"{copy.get('name', 'Bolt')} copy"
        layers.append(copy)
        self._set_lightning_layers(layers, selected_index=len(layers) - 1)

    def _delete_lightning_layer(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        if len(layers) <= 1:
            return
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        del layers[index]
        self._set_lightning_layers(layers, selected_index=max(0, index - 1))

    def _move_lightning_layer_up(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        if index <= 0:
            return
        layers[index - 1], layers[index] = layers[index], layers[index - 1]
        self._set_lightning_layers(layers, selected_index=index - 1)

    def _move_lightning_layer_down(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        if index >= len(layers) - 1:
            return
        layers[index + 1], layers[index] = layers[index], layers[index + 1]
        self._set_lightning_layers(layers, selected_index=index + 1)

    def _select_spectrum_layer(self, index: int) -> None:
        self._selected_spectrum_layer_index = max(0, index)
        self._update_inspectors()

    def _patch_selected_spectrum_layer(self, patch: dict) -> None:
        from features.video.lib.preview_scrub_patch import (
            layer_patch_is_scrub_allowlisted,
            layer_scrub_values,
        )

        layers = clone_layer_records(self._spectrum_layers)
        if not layers:
            layers = [{}]
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1))
        current = layers[index] if isinstance(layers[index], dict) else {}
        next_patch = dict(patch) if isinstance(patch, dict) else {}
        # Fill Circle is a disc fill of the ring — enable Circle Form when needed.
        if next_patch.get("fillCircle") is True and not bool(current.get("curved", False)):
            next_patch["curved"] = True
            next_patch["mirrored"] = True
        layers[index] = {**current, **next_patch}
        # Peak Caps used to require Peak Hold Blend > 0; auto-arm a usable hold.
        if next_patch.get("peakCapsEnabled") is True and self._template_draft is not None:
            try:
                hold = float(self._template_draft.get("audioPeakHoldBlend", 0.0) or 0.0)
            except (TypeError, ValueError):
                hold = 0.0
            if hold <= 0.001:
                self._template_draft = {**self._template_draft, "audioPeakHoldBlend": 0.45}
                if self._spectrum_instances:
                    from features.video.lib.spectrum_instance_registry import apply_draft_fields_to_instance
                    idx = max(0, min(self._selected_spectrum_instance_index, len(self._spectrum_instances) - 1))
                    self._spectrum_instances[idx] = apply_draft_fields_to_instance(
                        self._spectrum_instances[idx],
                        {"audioPeakHoldBlend": 0.45},
                    )
        # Geometry / form changes need an immediate inspector rebind (Circle Form, etc.).
        structural = {
            "curved", "mirrored", "gravity", "blend_mode", "name",
            "fillCircle", "solidBand", "reflectionEnabled", "peakCapsEnabled",
        }
        defer = not any(key in next_patch for key in structural)
        scrub_ok = False
        if layer_patch_is_scrub_allowlisted(next_patch):
            scrub_ok = self._apply_live_scrub_patch(
                {
                    "layerIndex": index,
                    "instanceIndex": int(self._selected_spectrum_instance_index),
                    "layer": layer_scrub_values(next_patch),
                }
            )
        self._set_spectrum_layers(
            layers,
            selected_index=index,
            defer_rebind=defer,
            schedule_preview=not scrub_ok,
        )

    def _patch_selected_spectrum_layer_color(self, patch: dict) -> None:
        layers = clone_layer_records(self._spectrum_layers)
        if not layers:
            layers = [{}]
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1))
        current = layers[index] if isinstance(layers[index], dict) else {}
        layers[index] = apply_spectrum_layer_color_patch(
            current,
            patch,
            get_spectrum_layer_color_fallback(index),
        )
        self._set_spectrum_layers(layers, selected_index=index)

    def _add_spectrum_layer(self) -> None:
        layers = clone_layer_records(self._spectrum_layers)
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1)) if layers else 0
        basis = dict(layers[index]) if layers and isinstance(layers[index], dict) else {}
        # Keep rings visually separable: bump radius and reset opacity if missing/zeroed.
        try:
            base_gap = float(basis.get("radiusOffset") or 0.0)
        except (TypeError, ValueError):
            base_gap = 0.0
        max_gap = 0.0
        for item in layers:
            if not isinstance(item, dict):
                continue
            try:
                max_gap = max(max_gap, float(item.get("radiusOffset") or 0.0))
            except (TypeError, ValueError):
                pass
        next_gap = max(base_gap + 18.0, max_gap + 18.0)
        opacity = basis.get("opacity")
        try:
            opacity_f = float(opacity) if opacity is not None else 1.0
        except (TypeError, ValueError):
            opacity_f = 1.0
        if opacity_f <= 0.0:
            opacity_f = 1.0
        layers.append(
            {
                **basis,
                "name": "New Ring",
                "radiusOffset": next_gap,
                "opacity": opacity_f,
            }
        )
        self._set_spectrum_layers(layers, selected_index=len(layers) - 1)

    def _duplicate_spectrum_layer(self) -> None:
        layers = clone_layer_records(self._spectrum_layers)
        if not layers:
            return
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1))
        basis = dict(layers[index]) if isinstance(layers[index], dict) else {}
        name = str(basis.get("name") or "").strip()
        try:
            base_gap = float(basis.get("radiusOffset") or 0.0)
        except (TypeError, ValueError):
            base_gap = 0.0
        layers.append(
            {
                **basis,
                "name": f"{name} Copy" if name else "Layer Copy",
                "radiusOffset": base_gap + 12.0,
            }
        )
        self._set_spectrum_layers(layers, selected_index=len(layers) - 1)

    def _delete_spectrum_layer(self) -> None:
        layers = clone_layer_records(self._spectrum_layers)
        if len(layers) < 2:
            return
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1))
        layers.pop(index)
        self._set_spectrum_layers(layers, selected_index=max(0, index - 1))

    def _move_spectrum_layer_up(self) -> None:
        layers = clone_layer_records(self._spectrum_layers)
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1))
        if index <= 0 or len(layers) < 2:
            return
        layers[index - 1], layers[index] = layers[index], layers[index - 1]
        self._set_spectrum_layers(layers, selected_index=index - 1)

    def _move_spectrum_layer_down(self) -> None:
        layers = clone_layer_records(self._spectrum_layers)
        index = max(0, min(self._selected_spectrum_layer_index, len(layers) - 1))
        if index >= len(layers) - 1 or len(layers) < 2:
            return
        layers[index + 1], layers[index] = layers[index], layers[index + 1]
        self._set_spectrum_layers(layers, selected_index=index + 1)

    def _patch_template_draft(self, patch: dict) -> None:
        if not self._template_draft:
            return
        from features.video.lib.preview_scrub_patch import (
            draft_patch_is_scrub_allowlisted,
            particle_draft_to_settings_patch,
        )

        self._template_draft = {**self._template_draft, **patch}
        from features.video.lib.spectrum_instance_registry import apply_draft_fields_to_instance
        spectrum_keys = {
            "style", "anchor", "positionX", "positionY",
            "spectrumAttachToLogo", "spectrumLogoGap",
            "audioInputGain", "audioBarHeight", "audioBandContrast",
            "audioTransientFocus", "audioKickImpact", "audioBassEmphasis",
            "audioTrebleShimmer", "audioPeakHoldBlend", "audioMotionSmoothing",
            "flyingGlowWingMotionSpeed", "flyingGlowWingRelease",
        }
        if spectrum_keys & set(patch.keys()) and self._spectrum_instances:
            idx = max(0, min(self._selected_spectrum_instance_index, len(self._spectrum_instances) - 1))
            self._spectrum_instances[idx] = apply_draft_fields_to_instance(
                self._spectrum_instances[idx], patch
            )
            self._spectrum_instances[idx]["layers"] = clone_layer_records(self._spectrum_layers)
        if particle_patch_touches_preset_fields(patch):
            self._remember_active_particle_preset_session()
        if spectrum_patch_touches_preset_fields(patch):
            self._remember_active_spectrum_preset_session()
        if background_patch_touches_preset_fields(patch):
            self._remember_active_background_preset_session()
        if logo_patch_touches_preset_fields(patch):
            self._remember_active_logo_preset_session()

        scrub_ok = False
        if draft_patch_is_scrub_allowlisted(patch):
            settings_patch = particle_draft_to_settings_patch(patch)
            if settings_patch:
                scrub_ok = self._apply_live_scrub_patch({"particlesSettings": settings_patch})

        # The control that emitted the patch already shows the new value;
        # rebind the rest once the user pauses instead of on every tick.
        self._update_inspectors(defer_rebind=True, schedule_preview=not scrub_ok)
        self._schedule_dirty_state_update()
        if scrub_ok:
            return
        if {"particlesEnabled", "spectrumEnabled", "backgroundEnabled", "logoEnabled"} & set(patch.keys()):
            self._flush_preview_update()
        elif spectrum_keys & set(patch.keys()):
            self._schedule_preview_update()
        elif particle_patch_touches_preset_fields(patch) or background_patch_touches_preset_fields(patch) or logo_patch_touches_preset_fields(patch):
            self._schedule_preview_update()

    def _remember_active_particle_preset_session(self) -> None:
        if not self._template_draft:
            return
        # Prefer the last applied/tracked preset. If the dropdown still shows a
        # built-in look (common after tweaks break exact factory match), treat
        # that selection as the session slot so edits are not lost.
        active = self._active_particle_preset_key
        if not is_builtin_particle_preset_key(active):
            active = resolve_active_particle_preset_key(self._template_draft)
        if not is_builtin_particle_preset_key(active):
            active = self._particles_inspector.selected_preset_key()
        if not is_builtin_particle_preset_key(active):
            return
        self._active_particle_preset_key = active
        capture_session_particle_preset(active, self._template_draft)

    def _remember_active_spectrum_preset_session(self) -> None:
        if not self._template_draft:
            return
        active = self._active_spectrum_preset_key
        if not is_session_spectrum_preset_key(active):
            active = self._spectrum_inspector.selected_preset_key()
        if not is_session_spectrum_preset_key(active):
            style = str(self._template_draft.get("style") or "").strip()
            active = style if is_session_spectrum_preset_key(style) else None
        if not is_session_spectrum_preset_key(active):
            return
        self._active_spectrum_preset_key = active
        capture_session_spectrum_preset(active, self._template_draft, self._spectrum_layers)

    def _remember_active_background_preset_session(self) -> None:
        if not self._template_draft:
            return
        active = self._active_background_preset_key
        if not is_builtin_background_preset_key(active):
            active = self._background_inspector.selected_preset_key()
        if not is_builtin_background_preset_key(active):
            return
        self._active_background_preset_key = active
        capture_background_preset(active, self._template_draft)

    def _remember_active_logo_preset_session(self) -> None:
        if not self._template_draft:
            return
        active = self._active_logo_preset_key
        if not is_builtin_logo_preset_key(active):
            active = self._logo_inspector.selected_preset_key()
        if not is_builtin_logo_preset_key(active):
            return
        self._active_logo_preset_key = active
        capture_logo_preset(active, self._template_draft)

    def _reset_background_transform(self) -> None:
        if self._workspace:
            template = dict(self._workspace.template)
            background_settings = template.get("backgroundSettings")
            background_settings = dict(background_settings) if isinstance(background_settings, dict) else {}
            background_settings.update(
                {
                    "userOffsetX": 0.0,
                    "userOffsetY": 0.0,
                    "userScale": 1.0,
                }
            )
            template["backgroundSettings"] = background_settings
            self._workspace = self._workspace.model_copy(update={"template": template})
        self._patch_template_draft({"backgroundUserScale": 1})
        self._update_preview()

    def _apply_logo_shape(self, logo_shape: str) -> None:
        if not self._template_draft:
            return
        self._template_draft = apply_logo_shape_draft_change(self._template_draft, logo_shape)
        self._update_inspectors()
        self._update_dirty_state()

    def _apply_logo_size(self, logo_size_step: float) -> None:
        if not self._template_draft:
            return
        self._template_draft = apply_logo_size_draft_change(self._template_draft, logo_size_step)
        self._update_inspectors()
        self._update_dirty_state()

    def _toggle_spectrum_attachment(self, attach: bool) -> None:
        if not self._template_draft:
            return
        self._template_draft = apply_spectrum_attach_to_logo_draft_change(self._template_draft, attach)
        self._update_inspectors()
        self._update_dirty_state()

    def _set_spectrum_logo_gap(self, gap: float) -> None:
        self._patch_template_draft({"spectrumLogoGap": gap})

    def _select_logo(self) -> None:
        if not self._template_draft:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select logo",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        self._workspace = self._store.set_logo_path(path, settings=self._settings)
        self._template_draft = {**self._template_draft, "logoPath": path}
        self._publish_workspace(self._workspace)
        self._update_inspectors()
        self._update_dirty_state()
        self._update_preview()
        notify_action("Applied the selected logo.", tone="success")

    def _apply_particle_preset(self, preset_key: str) -> None:
        if not self._workspace or not self._template_draft:
            return
        # Keep the previous preset's latest tweaks for this app session.
        previous = self._active_particle_preset_key
        if not is_builtin_particle_preset_key(previous):
            # Combo already moved to the new value; use the inspector's
            # remembered previous selection when active tracking was empty.
            previous = self._particles_inspector.previous_preset_key()
        if is_builtin_particle_preset_key(previous) and previous != preset_key:
            capture_session_particle_preset(previous, self._template_draft)

        pack_selection = parse_pack_preset_key(preset_key)
        if pack_selection:
            item = self._resolve_effect_pack_catalog_item(
                "particles",
                f"{pack_selection['packId']}::{pack_selection['version']}",
            )
            if not item:
                notify_action("Selected particle pack is unavailable.", tone="warning")
                return
            result = apply_particle_pack_as_preset(
                current_draft=self._template_draft,
                current_template=dict(self._workspace.template),
                logo_path=self._workspace.logo_path,
                item=item,
            )
            self._template_draft = result["nextDraft"]
            self._active_particle_preset_key = None
            self._update_inspectors()
            self._update_dirty_state()
            self._flush_preview_update()
            notify_action(f"Applied pack preset: {item.get('name')}.", tone="success")
            return

        patch = build_builtin_particle_preset_patch(preset_key)
        if not patch:
            notify_action("Unable to apply that particle preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, **patch}
        self._active_particle_preset_key = preset_key
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()

    def _apply_background_preset(self, preset_key: str) -> None:
        if not self._workspace or not self._template_draft:
            return
        previous = self._active_background_preset_key
        if not is_builtin_background_preset_key(previous):
            previous = self._background_inspector.previous_preset_key()
        if is_builtin_background_preset_key(previous) and previous != preset_key:
            capture_background_preset(previous, self._template_draft)

        pack_selection = parse_pack_preset_key(preset_key)
        if pack_selection:
            item = self._resolve_effect_pack_catalog_item(
                "background",
                f"{pack_selection['packId']}::{pack_selection['version']}",
            )
            if not item:
                notify_action("Selected background pack is unavailable.", tone="warning")
                return
            result = build_applied_effect_pack_draft_state(
                current_draft=self._template_draft,
                current_template=dict(self._workspace.template),
                logo_path=self._workspace.logo_path,
                domain="background",
                item=item,
            )
            self._template_draft = result["nextDraft"]
            self._active_background_preset_key = None
            self._update_inspectors()
            self._update_dirty_state()
            self._flush_preview_update()
            notify_action(f"Applied pack preset: {item.get('name')}.", tone="success")
            return

        patch = resolve_background_preset_patch(preset_key)
        if not patch:
            notify_action("Unable to apply that background preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, **patch}
        self._active_background_preset_key = preset_key
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()

    def _apply_logo_preset(self, preset_key: str) -> None:
        if not self._workspace or not self._template_draft:
            return
        previous = self._active_logo_preset_key
        if not is_builtin_logo_preset_key(previous):
            previous = self._logo_inspector.previous_preset_key()
        if is_builtin_logo_preset_key(previous) and previous != preset_key:
            capture_logo_preset(previous, self._template_draft)

        pack_selection = parse_pack_preset_key(preset_key)
        if pack_selection:
            item = self._resolve_effect_pack_catalog_item(
                "logo",
                f"{pack_selection['packId']}::{pack_selection['version']}",
            )
            if not item:
                notify_action("Selected logo pack is unavailable.", tone="warning")
                return
            result = build_applied_effect_pack_draft_state(
                current_draft=self._template_draft,
                current_template=dict(self._workspace.template),
                logo_path=self._workspace.logo_path,
                domain="logo",
                item=item,
            )
            self._template_draft = result["nextDraft"]
            self._active_logo_preset_key = None
            self._update_inspectors()
            self._update_dirty_state()
            self._flush_preview_update()
            notify_action(f"Applied pack preset: {item.get('name')}.", tone="success")
            return

        patch = resolve_logo_preset_patch(preset_key)
        if not patch:
            notify_action("Unable to apply that logo preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, **patch}
        self._active_logo_preset_key = preset_key
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()

    def _apply_spectrum_preset(self, preset_key: str) -> None:
        if not self._workspace or not self._template_draft:
            return
        previous = self._active_spectrum_preset_key
        if not is_session_spectrum_preset_key(previous):
            previous = self._spectrum_inspector.previous_preset_key()
        if is_session_spectrum_preset_key(previous) and previous != preset_key:
            capture_session_spectrum_preset(previous, self._template_draft, self._spectrum_layers)

        pack_selection = parse_pack_preset_key(preset_key)
        if pack_selection:
            item = self._resolve_effect_pack_catalog_item(
                "spectrum",
                f"{pack_selection['packId']}::{pack_selection['version']}",
            )
            if not item:
                notify_action("Selected spectrum pack is unavailable.", tone="warning")
                return
            result = apply_spectrum_pack_as_preset(
                current_draft=self._template_draft,
                current_template=dict(self._workspace.template),
                logo_path=self._workspace.logo_path,
                item=item,
            )
            self._template_draft = result["nextDraft"]
            next_layers = result.get("nextLayers")
            if isinstance(next_layers, list):
                self._spectrum_layers = clone_layer_records(next_layers)
            self._selected_spectrum_layer_index = 0
            self._active_spectrum_preset_key = None
            self._commit_spectrum_preset_to_preview()
            notify_action(f"Applied pack preset: {item.get('name')}.", tone="success")
            return

        session = get_session_spectrum_preset(preset_key)
        if session is not None:
            self._template_draft = {**self._template_draft, **session["draft"]}
            layers = clone_layer_records(session["layers"])
            style_key = normalize_spectrum_preset_key_for_apply(
                str(self._template_draft.get("style") or preset_key)
            )
            if style_key in STYLE_PRESET_PATCHES:
                layers = align_spectrum_layers_to_style_geometry(layers, style_key)
            self._spectrum_layers = layers
            self._selected_spectrum_layer_index = min(
                max(0, self._selected_spectrum_layer_index),
                max(0, len(self._spectrum_layers) - 1),
            )
            self._active_spectrum_preset_key = preset_key
            self._commit_spectrum_preset_to_preview()
            return

        base_template = {**dict(self._workspace.template), **self._template_draft, "layers": self._spectrum_layers}
        # Single styles replace the whole stack (python_app look); avoids ring+horizontal leftovers.
        patched = build_spectrum_preset_template(base_template, preset_key, replace_stack=True)
        self._template_draft = {**self._template_draft, "style": patched.get("style", preset_key)}
        self._spectrum_layers = clone_layer_records(patched.get("layers"))
        self._selected_spectrum_layer_index = 0
        self._active_spectrum_preset_key = preset_key
        self._commit_spectrum_preset_to_preview()

    def _apply_stacked_spectrum_preset(self, preset_key: str) -> None:
        if not self._workspace or not self._template_draft:
            return
        previous = self._active_spectrum_preset_key
        if not is_session_spectrum_preset_key(previous):
            previous = self._spectrum_inspector.previous_preset_key()
        if is_session_spectrum_preset_key(previous) and previous != preset_key:
            capture_session_spectrum_preset(previous, self._template_draft, self._spectrum_layers)

        session = get_session_spectrum_preset(preset_key)
        if session is not None:
            self._template_draft = {**self._template_draft, **session["draft"]}
            layers = clone_layer_records(session["layers"])
            style_key = normalize_spectrum_preset_key_for_apply(
                str(self._template_draft.get("style") or session["draft"].get("style") or "ignition-flare")
            )
            layers = align_spectrum_layers_to_style_geometry(layers, style_key)
            self._spectrum_layers = layers
            self._selected_spectrum_layer_index = 0
            self._active_spectrum_preset_key = preset_key
            self._commit_spectrum_preset_to_preview()
            notify_action(f"Restored stacked preset: {preset_key.replace('-', ' ').title()}.", tone="success")
            return

        base_template = {**dict(self._workspace.template), **self._template_draft}
        patched = build_stacked_spectrum_preset_template(base_template, preset_key)
        if not patched:
            notify_action("Unable to apply that stacked spectrum preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, "style": patched.get("style", preset_key)}
        self._spectrum_layers = clone_layer_records(patched.get("layers"))
        self._selected_spectrum_layer_index = 0
        self._active_spectrum_preset_key = preset_key
        self._commit_spectrum_preset_to_preview()
        notify_action(f"Applied stacked preset: {preset_key.replace('-', ' ').title()}.", tone="success")

    def _clear_stacked_spectrum_preset(self) -> None:
        if not self._workspace:
            return
        if len(self._spectrum_layers) > 1:
            self._spectrum_layers = [dict(self._spectrum_layers[0])]
        else:
            base_template = {**dict(self._workspace.template), **(self._template_draft or {})}
            patched = build_spectrum_preset_template(
                base_template,
                str((self._template_draft or {}).get("style") or "orbit-spikes"),
            )
            if patched and isinstance(patched.get("layers"), list) and patched["layers"]:
                self._spectrum_layers = clone_layer_records(patched["layers"][:1])
        self._selected_spectrum_layer_index = 0
        self._commit_spectrum_preset_to_preview()
        notify_action("Cleared stacked spectrum layers.", tone="success")

    def _restore_particle_preset(self) -> None:
        if not self._template_draft:
            return
        key = self._active_particle_preset_key
        if not is_builtin_particle_preset_key(key):
            key = self._particles_inspector.selected_preset_key()
        if not is_builtin_particle_preset_key(key):
            notify_action("No active particle preset to restore.", tone="warning")
            return
        patch = restore_particle_preset_to_factory(key)
        if not patch:
            notify_action("Unable to restore that particle preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, **patch}
        self._active_particle_preset_key = key
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()
        notify_action(f"Restored particle preset '{key}' to factory defaults.", tone="success")

    def _restore_spectrum_preset(self) -> None:
        if not self._workspace or not self._template_draft:
            return
        key = self._active_spectrum_preset_key
        if not is_session_spectrum_preset_key(key):
            key = self._spectrum_inspector.selected_preset_key()
        if not is_session_spectrum_preset_key(key):
            notify_action("No active spectrum preset to restore.", tone="warning")
            return
        restore_spectrum_preset_to_factory(key)
        base_template = {**dict(self._workspace.template), **self._template_draft, "layers": self._spectrum_layers}
        if key in STACKED_LAYER_PRESETS:
            patched = build_stacked_spectrum_preset_template(base_template, key)
            if not patched:
                notify_action("Unable to restore that stacked spectrum preset.", tone="error")
                return
        else:
            patched = build_spectrum_preset_template(base_template, key, replace_stack=True)
        self._template_draft = {**self._template_draft, "style": patched.get("style", key)}
        self._spectrum_layers = clone_layer_records(patched.get("layers"))
        self._selected_spectrum_layer_index = 0
        self._active_spectrum_preset_key = key
        self._commit_spectrum_preset_to_preview()
        notify_action(f"Restored spectrum preset '{key}' to factory defaults.", tone="success")

    def _restore_background_preset(self) -> None:
        if not self._template_draft:
            return
        key = self._active_background_preset_key
        if not is_builtin_background_preset_key(key):
            key = self._background_inspector.selected_preset_key()
        if not is_builtin_background_preset_key(key):
            notify_action("No active background preset to restore.", tone="warning")
            return
        patch = restore_background_preset_to_factory(key)
        if not patch:
            notify_action("Unable to restore that background preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, **patch}
        self._active_background_preset_key = key
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()
        notify_action(f"Restored background preset '{key}' to factory defaults.", tone="success")

    def _restore_logo_preset(self) -> None:
        if not self._template_draft:
            return
        key = self._active_logo_preset_key
        if not is_builtin_logo_preset_key(key):
            key = self._logo_inspector.selected_preset_key()
        if not is_builtin_logo_preset_key(key):
            notify_action("No active logo preset to restore.", tone="warning")
            return
        patch = restore_logo_preset_to_factory(key)
        if not patch:
            notify_action("Unable to restore that logo preset.", tone="error")
            return
        self._template_draft = {**self._template_draft, **patch}
        self._active_logo_preset_key = key
        self._update_inspectors()
        self._update_dirty_state()
        self._flush_preview_update()
        notify_action(f"Restored logo preset '{key}' to factory defaults.", tone="success")

    def _restore_text_preset(self) -> None:
        """Restore the active text preset to factory. Call if a text inspector emits preset_restore_requested."""
        if not self._template_draft:
            return
        key = self._active_text_preset_key
        if not is_builtin_text_preset_key(key):
            notify_action("No active text preset to restore.", tone="warning")
            return
        restore_text_preset_to_factory(key)
        overlays = self._text_overlays()
        index = resolve_selected_text_overlay_index(overlays, str(self._selected_text_overlay_index))
        next_overlays, next_index = apply_resolved_text_preset(overlays, key, selected_index=index)
        self._set_text_overlays(next_overlays, selected_index=next_index)
        notify_action(f"Restored text preset '{key}' to factory defaults.", tone="success")

    def _persisted_draft(self) -> dict | None:
        if not self._workspace:
            return None
        return build_video_template_draft(dict(self._workspace.template), logo_path=self._workspace.logo_path, background_path=self._workspace.background_path)

    def _workspace_dirty(self) -> bool:
        if not self._template_draft:
            return False
        name_dirty = self._template_name_draft.strip() != str(self._workspace.template_name if self._workspace else "").strip()
        draft_dirty = draft_snapshot(self._template_draft) != self._persisted_draft_snapshot
        layers = clone_layer_records(self._workspace.template.get("layers") if self._workspace else [])
        layers_dirty = json.dumps(self._spectrum_layers, sort_keys=True) != json.dumps(layers, sort_keys=True)
        lightning_layers = clone_layer_records(
            self._workspace.template.get("lightningLayers") if self._workspace else []
        )
        lightning_layers_dirty = json.dumps(self._lightning_layers, sort_keys=True) != json.dumps(
            lightning_layers, sort_keys=True
        )
        return name_dirty or draft_dirty or layers_dirty or lightning_layers_dirty

    def _update_dirty_state(self) -> None:
        persisted = self._persisted_draft()
        dirty_map = build_draft_dirty_state(
            self._template_draft,
            persisted,
            spectrum_dirty=json.dumps(self._spectrum_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("layers") if self._workspace else []), sort_keys=True),
            lightning_dirty=json.dumps(self._lightning_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("lightningLayers") if self._workspace else []), sort_keys=True),
        )
        tab_dirty = bool(dirty_map.get(self._active_domain_tab, False))
        workspace_dirty = self._workspace_dirty()
        self._left_rail.set_dirty_state(
            workspace_dirty=workspace_dirty,
            active_tab=self._active_domain_tab,
            tab_dirty=tab_dirty,
        )
        self._left_rail.set_save_enabled(workspace_dirty and bool(self._template_name_draft.strip()) and not self._saving)
        self._left_rail.set_busy(saving=self._saving, deleting=self._deleting)
        self._schedule_local_draft_persist()

    def _on_diagnostics_panel_toggled(self, expanded: bool) -> None:
        if self._diagnostics_timer is None:
            return
        if expanded:
            self._update_diagnostics_panel()
            if not self._diagnostics_timer.isActive():
                self._diagnostics_timer.start()
            return
        self._diagnostics_timer.stop()

    def _update_diagnostics_panel(self) -> None:
        if self._diagnostics_panel is None or not self._diagnostics_panel.isChecked():
            return
        persisted = self._persisted_draft()
        spectrum_dirty = json.dumps(self._spectrum_layers, sort_keys=True) != json.dumps(
            clone_layer_records(self._workspace.template.get("layers") if self._workspace else []),
            sort_keys=True,
        )
        dirty_map = build_draft_dirty_state(
            self._template_draft,
            persisted,
            spectrum_dirty=spectrum_dirty,
            lightning_dirty=json.dumps(self._lightning_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("lightningLayers") if self._workspace else []), sort_keys=True),
        )
        workspace_dirty = self._workspace_dirty()
        selected_row = self._selected_pipeline_row()
        branch = "reel" if self._selected_pipeline_branch == "reel" else "long"
        pipeline_inputs = resolve_video_pipeline_inputs(selected_row, branch) if selected_row else None
        lifecycle = self._stage.preview_lifecycle_snapshot()
        if not self._stage.gpu_preview_available():
            lifecycle = {
                "status": "unsupported",
                "message": "GPU preview dependencies are not available in this environment.",
            }
        diagnostics = build_video_workspace_diagnostics(
            workspace=self._workspace,
            template_name_draft=self._template_name_draft,
            workspace_dirty=workspace_dirty,
            draft_dirty_map=dirty_map,
            active_domain_tab=self._active_domain_tab,
            saving=self._saving,
            playback=self._workspace.playback if self._workspace else None,
            preview_track_path=str(self._workspace.selected_mp3_path if self._workspace else ""),
            pipeline_branch=self._selected_pipeline_branch,
            pipeline_inputs=pipeline_inputs,
            preview_lifecycle_status=str(lifecycle.get("status") or "running"),
            preview_lifecycle_message=str(lifecycle.get("message") or ""),
            preview_remount_pending=self._preview_remount_pending,
            gpu_preview_available=self._stage.gpu_preview_available(),
            performance=self._stage.performance_snapshot(),
            export_gate_active=int(export_gate.active),
            export_gate_limit=int(export_gate.limit),
        )
        self._diagnostics_panel.bind(diagnostics)
        self._diagnostics_payload = build_video_workspace_diagnostics_payload(
            workspace=self._workspace,
            template_name_draft=self._template_name_draft,
            active_domain_tab=self._active_domain_tab,
            workspace_dirty=workspace_dirty,
            draft_dirty_map=dirty_map,
            playback=self._workspace.playback if self._workspace else None,
            preview_track_path=str(self._workspace.selected_mp3_path if self._workspace else ""),
            pipeline_branch=self._selected_pipeline_branch,
            pipeline_inputs=pipeline_inputs,
            preview_runtime_nonce=self._stage.preview_runtime_nonce(),
            preview_lifecycle_status=str(lifecycle.get("status") or "running"),
            preview_lifecycle_message=str(lifecycle.get("message") or ""),
            performance=self._stage.performance_snapshot(),
            export_gate_active=int(export_gate.active),
            export_gate_limit=int(export_gate.limit),
            diagnostics=diagnostics,
        )

    def _remount_preview(self) -> None:
        self._preview_remount_pending = True
        if SHOW_VIDEO_WORKSPACE_DIAGNOSTICS:
            self._update_diagnostics_panel()
        self._stage.remount_preview()
        self._update_preview()
        self._preview_remount_pending = False
        if SHOW_VIDEO_WORKSPACE_DIAGNOSTICS:
            self._update_diagnostics_panel()
        notify_action("Remounted the GPU preview surface.", tone="success")

    def _refresh_workspace_from_diagnostics(self) -> None:
        self.refresh_data(force=True)
        notify_action("Video workspace diagnostics refreshed.")

    def _reset_local_draft(self) -> None:
        if not self._workspace_dirty():
            return
        confirm = QMessageBox.question(
            self,
            "Reset local draft",
            "Discard unsaved local draft changes and restore the saved template?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        template_id = str(self._workspace.template_id or "")
        if template_id:
            clear_video_workspace_draft_snapshot(template_id)
        self._hydrated_template_id = ""
        self._hydrate_draft_from_workspace(force_from_saved=True)
        self._persist_local_draft_snapshot()
        self._render_workspace()
        notify_action("Reset the local Video workspace draft back to the saved template.", tone="success")

    def _restore_template_to_original(self) -> None:
        if not self._workspace or self._saving or self._deleting:
            return
        confirm = QMessageBox.question(
            self,
            "Restore original template",
            "Replace the saved template with its original snapshot? Unsaved session edits will be discarded.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        template_id = str(self._workspace.template_id or "")
        if template_id:
            clear_video_workspace_draft_snapshot(template_id)
        workspace = self._store.restore_template_to_original(template_id, settings=self._settings)
        if workspace is None:
            notify_action("Unable to restore the original template snapshot.", tone="error")
            return
        self._workspace = workspace
        self._hydrated_template_id = ""
        self._hydrate_draft_from_workspace(force_from_saved=True)
        self._persist_local_draft_snapshot()
        self._render_workspace()
        self._update_preview()
        if self._cache is not None:
            self._cache.apply_video_workspace(self._workspace, self._settings)
        emit_video_template_catalog_changed()
        notify_action("Restored the selected template to its original snapshot.", tone="success")

    def _copy_diagnostics(self) -> None:
        payload = getattr(self, "_diagnostics_payload", None)
        if not isinstance(payload, dict):
            self._update_diagnostics_panel()
            payload = getattr(self, "_diagnostics_payload", {})
        text = serialize_diagnostics_payload(payload if isinstance(payload, dict) else {})
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            notify_action("Clipboard access is not available.", tone="warning")
            return
        clipboard.setText(text)
        notify_action("Copied Video diagnostics to the clipboard.", tone="success")

    def _on_template_name_changed(self, value: str) -> None:
        self._template_name_draft = value
        self._update_dirty_state()

    def _on_domain_tab_changed(self, tab_key: str) -> None:
        self._active_domain_tab = tab_key
        self._preview_edit_focus = "domain"
        self._flush_preview_update()
        self._schedule_dirty_state_update()

    def _on_template_selected(self, template_id: str) -> None:
        if not self._workspace or template_id == self._workspace.template_id or self._saving:
            return
        if self._workspace_dirty():
            confirm = QMessageBox.question(
                self,
                "Switch template",
                "You have unsaved changes. Switch template anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                self._left_rail.set_templates(
                    [(item.id, item.name) for item in self._workspace.templates],
                    self._workspace.template_id,
                )
                return
        self._workspace = self._store.set_template(template_id)
        self._hydrated_template_id = ""
        self._hydrate_draft_from_workspace()
        self._render_workspace()
        notify_action("Applied the selected template.", tone="success")

    def _create_blank_template(self) -> None:
        if self._saving or self._deleting:
            return
        if self._workspace and self._workspace_dirty():
            confirm = QMessageBox.question(
                self,
                "Create new template",
                "You have unsaved changes. Create a new blank template anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        name = self._template_name_draft.strip() or "Untitled Template"
        if self._workspace and any(item.name == name for item in self._workspace.templates):
            name = f"{name} copy"
        self._workspace = self._store.create_blank_template(name=name, settings=self._settings)
        self._hydrated_template_id = ""
        self._hydrate_draft_from_workspace(force_from_saved=True)
        self._render_workspace()
        self._update_preview()
        if self._cache is not None and self._workspace is not None:
            self._cache.apply_video_workspace(self._workspace, self._settings)
        emit_video_template_catalog_changed()
        notify_action(f"Created blank template: {self._workspace.template_name}.", tone="success")

    def _save_template(self) -> None:
        if not self._workspace or not self._template_draft or self._patch_worker is not None:
            return
        name = self._template_name_draft.strip()
        if not name:
            notify_action("Template name is required before saving.", tone="warning")
            return
        if not self._workspace.template_id:
            # Keep the in-memory draft the user already edited; only create the catalog row.
            draft = dict(self._template_draft)
            layers = list(self._spectrum_layers)
            lightning = list(self._lightning_layers)
            instances = list(self._spectrum_instances)
            selected_instance = int(self._selected_spectrum_instance_index)
            self._workspace = self._store.create_blank_template(name=name, settings=self._settings)
            self._template_draft = draft
            self._spectrum_layers = layers
            self._lightning_layers = lightning
            self._spectrum_instances = instances
            self._selected_spectrum_instance_index = selected_instance
            self._template_name_draft = name
        self._flush_active_spectrum_instance_layers()
        patch = build_video_workspace_template_save_patch(
            template=dict(self._workspace.template),
            draft=self._template_draft,
            template_name=name,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
            spectrum_instances=self._spectrum_instances,
        )
        self._saving = True
        self._update_dirty_state()
        notify_action("Saving template…", tone="neutral")
        worker = VideoPatchTemplateWorker(self._store, patch, settings=self._settings, parent=self)
        worker.succeeded.connect(self._on_save_succeeded)
        worker.failed.connect(self._on_save_failed)
        worker.finished.connect(self._on_patch_worker_finished)
        self._patch_worker = worker
        worker.start()

    def _on_save_succeeded(self, workspace: object) -> None:
        if isinstance(workspace, VideoWorkspaceState):
            self._workspace = workspace
            self._hydrated_template_id = ""
            self._hydrate_draft_from_workspace(force_from_saved=True)
            self._persist_local_draft_snapshot()
            self._render_workspace()
            self._schedule_template_server_sync()
            if self._cache is not None:
                self._cache.apply_video_workspace(self._workspace, self._settings)
            emit_video_template_catalog_changed()
        self._saving = False
        self._update_dirty_state()
        notify_action("Saved the current workspace draft into the selected template.", tone="success")

    def _schedule_template_server_sync(self) -> None:
        if not self._workspace or self._template_sync_worker is not None:
            return
        self._flush_active_spectrum_instance_layers()
        patch = build_video_workspace_template_save_patch(
            template=dict(self._workspace.template),
            draft=self._template_draft or {},
            template_name=self._template_name_draft.strip(),
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
            spectrum_instances=self._spectrum_instances,
        )
        profiles: list = []
        if self._cache is not None:
            _me, profiles, _settings, _descriptions, _structures, _moods = self._cache.snapshot_core()
        worker = VideoTemplateSyncWorker(
            self._api,
            workspace=self._workspace,
            save_patch=patch,
            profiles=[item for item in profiles if isinstance(item, dict) or hasattr(item, "id")],
            parent=self,
        )
        worker.succeeded.connect(self._on_template_sync_succeeded)
        worker.failed.connect(self._on_template_sync_failed)
        worker.finished.connect(self._on_template_sync_finished)
        self._template_sync_worker = worker
        worker.start()

    def _on_template_sync_succeeded(self, message: str) -> None:
        if message.strip():
            notify_action(message, tone="success")

    def _on_template_sync_failed(self, message: str) -> None:
        notify_action(message or "Saved locally; server sync failed.", tone="warning")

    def _on_template_sync_finished(self) -> None:
        self._template_sync_worker = None

    def _on_save_failed(self, message: str) -> None:
        self._saving = False
        self._update_dirty_state()
        notify_action(message or "Unable to save template.", tone="error")

    def _on_patch_worker_finished(self) -> None:
        self._patch_worker = None

    def _delete_template(self) -> None:
        if not self._workspace or not self._workspace.template_id or self._deleting:
            return
        template_name = self._workspace.template_name
        confirm = QMessageBox.warning(
            self,
            "Delete template",
            f"Delete “{template_name}”? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._deleting = True
        self._update_dirty_state()
        self._workspace = self._store.delete_template(self._workspace.template_id)
        self._hydrate_draft_from_workspace()
        self._render_workspace()
        self._deleting = False
        self._update_dirty_state()
        if self._cache is not None and self._workspace is not None:
            self._cache.apply_video_workspace(self._workspace, self._settings)
        emit_video_template_catalog_changed()
        notify_action(f"Deleted {template_name}.", tone="success")

    # ─── Export for Marketplace (admin-only) ──────────────────────────────

    _MARKETPLACE_ADMIN_EMAIL = "somvannda@gmail.com"

    def _update_export_button_visibility(self) -> None:
        """Show the Export button only if the logged-in user is the marketplace admin."""
        email = ""
        if self._cache and self._cache.me:
            email = str(self._cache.me.email or "").strip().lower()
        self._left_rail.set_export_visible(email == self._MARKETPLACE_ADMIN_EMAIL)

    def _export_template_for_marketplace(self) -> None:
        """Export the current template as a marketplace-ready zip bundle.

        Creates a zip containing:
        - manifest.json (name, description, version, author, kind, tags)
        - template.json (the full template payload)
        - preview.png (placeholder or captured preview)
        """
        import io
        import json
        import zipfile
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QInputDialog

        if not self._workspace or not self._workspace.template:
            notify_action("No template loaded to export.", tone="warning")
            return

        template_name = self._workspace.template_name or "Untitled"
        template_json = dict(self._workspace.template)

        # Prompt for version
        version, ok = QInputDialog.getText(
            self, "Export Template", "Version:", text="1.0.0"
        )
        if not ok or not version.strip():
            return
        version = version.strip()

        # Prompt for description
        description, ok = QInputDialog.getText(
            self, "Export Template", "Description:", text=f"{template_name} video template"
        )
        if not ok:
            return
        description = description.strip() or f"{template_name} video template"

        # Prompt for kind
        kind_options = ["video", "reel"]
        kind, ok = QInputDialog.getItem(
            self, "Export Template", "Kind:", kind_options, 0, False
        )
        if not ok:
            return

        # Ask for save location
        default_filename = f"{template_name.replace(' ', '_').lower()}_{version}.zip"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Marketplace Bundle",
            default_filename,
            "Zip Files (*.zip)",
        )
        if not save_path:
            return

        # Build manifest
        manifest = {
            "name": template_name,
            "description": description,
            "version": version,
            "author": "Camxora",
            "kind": kind,
            "tags": [],
        }

        # Build the zip in memory then write to disk
        try:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
                zf.writestr("template.json", json.dumps(template_json, indent=2, ensure_ascii=False))
                # Generate a minimal 1x1 PNG as placeholder preview
                zf.writestr("preview.png", _minimal_png())

            Path(save_path).write_bytes(buf.getvalue())
            notify_action(f"Exported marketplace bundle → {Path(save_path).name}", tone="success")
        except Exception as exc:
            notify_action(f"Export failed: {exc}", tone="error")


def _minimal_png() -> bytes:
    """Return a valid 1x1 transparent PNG for placeholder preview."""
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_pixels = b"\x00" + b"\x00\x00\x00\x00"  # filter byte + 1 RGBA pixel (transparent)
    idat = _chunk(b"IDAT", zlib.compress(raw_pixels))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend
