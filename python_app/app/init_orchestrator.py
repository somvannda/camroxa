from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import Qt, QPoint, QTimer, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

# QWebEngineView imports (lazy - only loaded when hybrid mode is enabled)
HAS_WEB_ENGINE = None  # resolved lazily on first check

from .audio_controller import AudioController
from .logging import log_line
from .resources import assets_dir
from .signal_router import SignalRouter
from ..design_system.tokens import TokenRegistry
from .timer_registry import TimerRegistry
from .ui_bus import UiBus
from ..database.music_db import (
    list_pending_suno_tasks,
    list_songs_by_batch_id as music_list_songs_by_batch_id,
    upsert_suno_task,
)
from ..features import (
    ExportCoordinator,
    ImagePromptPresetCoordinator,
    MusicHistoryCoordinator,
    MusicProfileManagementCoordinator,
    MusicSettingsCoordinator,
    PersistenceCoordinator,
    ProfileCoordinator,
    ProgressCoordinator,
    TemplateManagementCoordinator,
    VideoTemplateCoordinator,
    VideoWorkspaceStateCoordinator,
    YouTubeCoordinator,
)
from ..features.auto_video.coordinator import AutoVideoCoordinator
from ..features.image.coordinator import ImageGenerationCoordinator
from ..features.merge.worker import MergeWorker
from ..features.music.coordinator import MusicGenerationCoordinator
from ..views.music_page_controller import MusicPageController
from ..views.dashboard_page_controller import DashboardPageController
from ..views.progress_page_controller import ProgressPageController
from ..features.video_export.coordinator import ExportBatchCoordinator
from ..features.video_export.video_page_controller import VideoPageController
from ..features.youtube.oauth_controller import YouTubeOAuthController
from ..models.music_model import default_music_app_data
from ..models.spectrum_model import default_template, normalize_template
from ..services.music_callback import CallbackServerManager
from ..views.helpers.qt_ui_adapter import (
    make_confirm_fn,
    make_confirm_question_fn,
    make_defer_call_fn,
    make_dir_dialog_fn,
    make_file_dialog_fn,
    make_input_fn,
    make_list_items_fn,
    make_list_populate_fn,
    make_process_events_fn,
    make_table_populate_fn,
    make_timer_factory,
    make_warning_fn,
)
from ..services.music_ngrok import NgrokManager
from ..services.music_suno import poll_and_download_pending_suno
from ..views.helpers.footer_controller import FooterController
from ..views.helpers.style_helper import set_panel_role as _sh_set_panel_role

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .main_window import MainWindow


class _UiBusAdapter:
    """Adapter bridging ``EventBusPort.emit(name, payload)`` to a signal-based ``UiBus``."""

    def __init__(self, bus: "UiBus") -> None:
        self._bus = bus

    def emit(self, event_name: str, payload: dict) -> None:
        try:
            signal = getattr(self._bus, event_name, None)
            if signal is not None:
                signal.emit(payload)
        except RuntimeError:
            # Qt object already deleted during shutdown — ignore safely
            pass


class _MainWindowLoggerAdapter:
    """Adapter bridging ``MainWindow._log`` to the ``LoggerPort`` interface."""

    def __init__(self, host: "MainWindow") -> None:
        self._host = host

    def info(self, msg: str) -> None:
        self._host._log(msg)

    def error(self, msg: str) -> None:
        self._host._log(msg)

    def warning(self, msg: str) -> None:
        self._host._log(msg)


class InitOrchestrator:
    """Executes ``MainWindow.__init__`` in four deterministic phases.

    The orchestrator replaces the previously ad-hoc, ordering-sensitive body of
    ``MainWindow.__init__`` with four explicitly named phases. Each phase is
    bracketed by ``log_line`` calls and wrapped in a try/except that records the
    failing phase before re-raising, so initialization failures are diagnosable
    from the startup log alone.

    Phases (executed strictly in order):

    * **Phase A — state defaults**: assign every plain-data attribute that later
      phases (and the coordinators they build) read. After Phase A the host has
      a fully-populated set of default attributes and is safe to wire.
    * **Phase B — coordinators**: construct all coordinators / controllers in a
      defined order. Each coordinator may read only attributes assigned in
      Phase A (or by an earlier coordinator in Phase B).
    * **Phase C — UI build**: invoke the view-mixin ``_build_*`` page methods and
      assemble the primary navigation stack. All widget references stored on the
      host are assigned here.
    * **Phase D — timers & restore**: register timers with ``TimerRegistry``,
      apply persisted settings to the UI, restore runtime state, and start the
      polling timers.

    Phase-dependency contract
    -------------------------
    **Any attribute read in Phase N must be assigned in Phase N-1 or earlier.**

    When a new attribute dependency is introduced, assign it in the earliest
    phase that precedes every read. Concretely: a value read by a coordinator
    constructor (Phase B) must be assigned in Phase A; a value read while
    building widgets (Phase C) must be assigned in Phase A or B; and a value read
    by a timer callback (which only fires after Phase D starts the timers) may be
    assigned in any of Phase A, B, or C.

    The orchestrator is single-use: calling :meth:`run` more than once raises
    ``RuntimeError`` to prevent re-entrant / double initialization.
    """

    # Attributes that Phase A guarantees to assign before any coordinator runs.
    # Kept as a class-level contract list so tests and future phases can assert
    # against it without re-deriving the set.
    PHASE_A_ATTRIBUTES: tuple[str, ...] = (
        "db_cfg",
        "bus",
        "music_data",
        "e_settings",
        "template",
        "ui",
        "_footer",
        "_timer_registry",
        "_ffmpeg_path",
        "_output_dir",
        "_app_closing",
        "_primary_page_index",
        "_audio_paused",
        "_seek_dragging",
    )

    def __init__(self, host: "MainWindow") -> None:
        self._host = host
        self._has_run = False

    def run(self) -> None:
        """Execute all four phases in order.

        Raises:
            RuntimeError: if called more than once on the same instance.
            Exception: re-raises (unchanged) any exception raised within a phase
                after logging the failing phase name and exception message.
        """
        if self._has_run:
            raise RuntimeError("InitOrchestrator.run() called more than once")
        self._has_run = True

        phases: list[tuple[Callable[[], None], str]] = [
            (self._phase_a_state_defaults, "Phase A"),
            (self._phase_b_coordinators, "Phase B"),
            (self._phase_c_ui_build, "Phase C"),
            (self._phase_d_timers_and_restore, "Phase D"),
        ]
        for phase_fn, phase_name in phases:
            log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] {phase_name}: Begin")
            try:
                phase_fn()
            except Exception as exc:
                log_line(
                    f"[{time.strftime('%H:%M:%S')}] [STARTUP] {phase_name}: "
                    f"FAILED \u2014 {type(exc).__name__}: {exc}"
                )
                raise
            log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] {phase_name}: Complete")

    # ------------------------------------------------------------------
    # Phase A — state defaults
    # ------------------------------------------------------------------
    def _phase_a_state_defaults(self) -> None:
        """Assign every default-valued attribute later phases depend on.

        Reads nothing on the host other than the host object itself; every value
        assigned here is derived from module-level constants/factories. This is
        the foundation of the phase-dependency contract: coordinators built in
        Phase B may rely on any attribute set here.
        """
        host = self._host

        # Plain state defaults.
        host.db_cfg = None
        host.bus = UiBus()
        host.music_data = default_music_app_data()
        host.e_settings = dict(host.music_data.get("settings") or {})
        host.template = normalize_template(default_template())
        host.ui = TokenRegistry().as_dict()
        host._footer = FooterController(lambda: getattr(host, "footer_left_label", None))
        host._timer_registry = TimerRegistry(parent=host)
        host._ffmpeg_path = ""
        host._output_dir = ""
        host._app_closing = False
        host._primary_page_index = {}
        host._audio_paused = False
        host._seek_dragging = False

        # Host-specific Phase A work: window chrome + UiBus signal wiring. The
        # core defaults above remain the single source of truth for the Phase A
        # contract; the work below only assigns attributes the contract does not
        # cover and wires bus signals to host handlers. Host methods
        # (``_project_icon_path``, ``_build_app_stylesheet``) and handlers live on
        # the ``MainWindow`` mixins, so they are always present.
        host.setWindowTitle("CAMXORA")
        host.setWindowIcon(QIcon(host._project_icon_path("app.ico")))
        host.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Single source of truth for the app window size (see window_config.py).
        from .window_config import apply_fixed_window_size
        apply_fixed_window_size(host)

        # DWM rounded corners are applied in MainWindow.showEvent() after
        # the window is mapped and the HWND is valid.

        a = assets_dir()
        host._combo_arrow_url = (a / "combo-arrow.svg").as_posix()
        host._spin_up_arrow_url = (a / "spin-up-arrow.svg").as_posix()
        host._spin_down_arrow_url = (a / "spin-down-arrow.svg").as_posix()
        # Global QSS is now applied at QApplication level via design_system.bootstrap.apply_theme()
        # The legacy host.setStyleSheet() call has been removed.
        host.bus.export_event.connect(host._on_export_event)
        host.bus.export_done.connect(host._on_export_done)
        host.bus.music_event.connect(lambda ev: host._signal_router._on_music_event(ev))
        host.bus.ui_invoke.connect(lambda fn: fn() if callable(fn) else None)

    # ------------------------------------------------------------------
    # Phase B — coordinator construction
    # ------------------------------------------------------------------
    def _phase_b_coordinators(self) -> None:
        """Construct all coordinators / controllers in dependency order.

        Each coordinator may read only attributes assigned in Phase A (or by an
        earlier coordinator in this phase).

        :meth:`_construct_feature_coordinators` builds the *existing* feature
        coordinators (music/image/export/youtube/progress/...). Once it returns,
        :meth:`_construct_decomposition_controllers` constructs the *new*
        decomposition controllers (``AudioController``, ``VideoPageController``,
        ``SignalRouter`` and the page controllers) — they depend on the
        coordinators built first, so they must follow.

        The page controllers receive lazy ``Callable`` accessors rather than a
        ``MainWindow`` reference. Widgets are not built until Phase C, but every
        accessor is a deferred ``getattr``/lambda, so constructing the
        controllers now is safe — the accessors are only evaluated later when a
        controller method runs.
        """
        self._construct_feature_coordinators()
        self._construct_decomposition_controllers()

    # ------------------------------------------------------------------
    # Phase B — existing feature coordinator construction
    # ------------------------------------------------------------------
    def _construct_feature_coordinators(self) -> None:
        """Construct the existing feature coordinators and restore persisted data.

        Migrated verbatim (task 11.3) from the former
        ``MainWindow._io_phase_b_coordinators`` host hook so the heavy
        construction logic lives on the orchestrator rather than the shell. Each
        coordinator reads only Phase A attributes (or coordinators built earlier
        in this method). Runs before :meth:`_construct_decomposition_controllers`
        so the new controllers can depend on the coordinators built here.
        """
        host = self._host
        host._music_coordinator = MusicGenerationCoordinator(
            db=host,
            service=host,
            bus=host.bus,
            settings_accessor=host._music_settings,
            db_cfg_accessor=lambda: host.db_cfg,
            logger=_MainWindowLoggerAdapter(host),
            db_cfg=host.db_cfg,
            poll_pending_suno=poll_and_download_pending_suno,
            list_pending_suno_tasks=list_pending_suno_tasks,
            upsert_suno_task=upsert_suno_task,
            list_songs_by_batch_id=music_list_songs_by_batch_id,
            ui_delegate=host,
            warning_fn=make_warning_fn(host),
            defer_call_fn=make_defer_call_fn(),
        )
        host.music_controller = host._music_coordinator
        host._image_coordinator = ImageGenerationCoordinator(
            db=host,
            service=host,
            bus=_UiBusAdapter(host.bus),
            settings_accessor=host._music_settings,
            db_cfg_accessor=lambda: host.db_cfg,
            logger=_MainWindowLoggerAdapter(host),
            profile_accessor=host._music_profile_by_id,
            status_callback=host._set_image_status,
            db_cfg=host.db_cfg,
        )
        host.image_controller = host._image_coordinator
        host.image_prompt_preset_coordinator = ImagePromptPresetCoordinator(host)
        host.profile_mgmt_coordinator = MusicProfileManagementCoordinator(
            host,
            confirm_question_fn=make_confirm_question_fn(host),
            warning_fn=make_warning_fn(host),
            list_populate_fn=lambda items: make_list_populate_fn(host.music_settings_profile_list)(items),
        )
        host.profile_coordinator = ProfileCoordinator(
            refresh_list_fn=lambda: host.profile_mgmt_coordinator.refresh_list(),
            selected_profile_fn=lambda: host.profile_mgmt_coordinator.selected_profile(),
            save_profile_fn=lambda: host.profile_mgmt_coordinator.save_profile_details(),
        )
        host.template_mgmt_coordinator = TemplateManagementCoordinator(host, confirm_question_fn=make_confirm_question_fn(host))
        host.template_coordinator = VideoTemplateCoordinator(
            refresh_template_list_fn=lambda: host.refresh_templates_impl(),
            load_template_fn=lambda tpl_id: host.template_mgmt_coordinator.load_template_impl(tpl_id),
            save_template_fn=lambda: host.template_mgmt_coordinator.save_template_impl(),
        )
        host.workspace_coordinator = VideoWorkspaceStateCoordinator(
            host=host,
            file_dialog_fn=make_file_dialog_fn(host),
            dir_dialog_fn=make_dir_dialog_fn(host),
            list_items_fn=lambda: make_list_items_fn(host.mp3_list)(),
        )
        host._export_batches = {}  # per-batch state, keyed by unique batch_key
        host._export_workers = 1
        host._export_merge_running = False
        host._export_merge_last_output = ""
        host._export_merge_cancel_requested = False
        host._export_merge_proc = None
        host._current_export_mp3 = ""
        host._current_export_done = False
        host._current_export_progress_ratio = 0.0
        host._current_export_stage = ""
        host._current_export_frame = 0
        host._current_export_total_frames = 0
        host._last_export_path = ""
        host.export_coordinator = ExportCoordinator(
            bus=_UiBusAdapter(host.bus),
            settings_accessor=host._music_settings,
            export_batches_accessor=lambda: host._export_batches,
            export_batches_setter=lambda v: setattr(host, '_export_batches', v),
            export_workers_accessor=lambda: host._export_workers,
            export_workers_setter=lambda v: setattr(host, '_export_workers', v),
            template_accessor=lambda: getattr(host, 'template', {}),
            resolved_output_resolution_fn=lambda: host._resolved_output_resolution(),
            ffmpeg_path_accessor=lambda: getattr(host, '_ffmpeg_path', ''),
            iter_mp3_paths_fn=lambda: host._iter_mp3_paths(),
            pick_ffmpeg_fn=lambda: host.pick_ffmpeg(),
            prompt_output_dir_fn=lambda: host._prompt_output_dir_for_export(),
            preview_bg_path_accessor=lambda: getattr(host.preview, 'bg_path', '') if hasattr(host, 'preview') else '',
            preview_logo_path_accessor=lambda: getattr(host.preview, 'logo_path', '') if hasattr(host, 'preview') else '',
            set_export_status_fn=lambda msg: host._set_export_status_message(msg),
            refresh_export_output_label_fn=lambda: host._refresh_export_output_label(),
            update_export_overall_progress_fn=lambda: host._update_export_overall_progress(),
            refresh_export_detail_fn=lambda: host._refresh_export_detail(),
            normalize_export_stage_message_fn=lambda msg: host._normalize_export_stage_message(msg),
            format_export_percent_fn=lambda ratio: host._format_export_percent(ratio),
            export_auto_merge_enabled_fn=lambda: host._export_auto_merge_enabled(),
            export_worker_limit_fn=lambda: host._export_worker_limit(),
            set_last_export_path_fn=lambda p: setattr(host, '_last_export_path', p),
            get_export_merge_state_fn=lambda: {"running": host._export_merge_running, "cancel_requested": host._export_merge_cancel_requested, "proc": host._export_merge_proc},
            set_export_merge_state_fn=lambda s: (setattr(host, '_export_merge_running', s.get('running', host._export_merge_running)), setattr(host, '_export_merge_cancel_requested', s.get('cancel_requested', host._export_merge_cancel_requested)), setattr(host, '_export_merge_proc', s.get('proc', host._export_merge_proc))),
            export_detail_label_set_fn=lambda txt: (host.export_detail_label.setText(txt) if hasattr(host, 'export_detail_label') else None),
            export_merge_progress_set_fn=lambda vis, val, fmt: (setattr(host.export_merge_progress, 'visible', vis) if hasattr(host, 'export_merge_progress') else None, host.export_merge_progress.setVisible(vis) if hasattr(host, 'export_merge_progress') else None, host.export_merge_progress.setValue(val) if hasattr(host, 'export_merge_progress') and vis else None, host.export_merge_progress.setFormat(fmt) if hasattr(host, 'export_merge_progress') and vis and fmt else None),
            btn_export_merge_stop_set_fn=lambda vis: (host.btn_export_merge_stop.setVisible(vis) if hasattr(host, 'btn_export_merge_stop') else None),
            auto_video_coordinator_accessor=lambda: host.auto_video_coordinator,
        )
        host.export_batch_coordinator = ExportBatchCoordinator(
            ffmpeg_path=getattr(host, '_ffmpeg_path', ''),
            output_dir=getattr(host, '_output_dir', ''),
            bg_path=getattr(host.preview, 'bg_path', '') if hasattr(host, 'preview') else '',
            logo_path=getattr(host.preview, 'logo_path', '') if hasattr(host, 'preview') else '',
            bus=host.bus,
            db_cfg=host.db_cfg,
        )
        host.persistence_coordinator = PersistenceCoordinator(
            db_cfg_accessor=lambda: host.db_cfg,
            db_cfg_setter=host._set_db_cfg,
            settings_accessor=host._music_settings,
            music_data_accessor=lambda: host.music_data,
            music_data_setter=lambda data: setattr(host, 'music_data', data),
            settings_setter=lambda s: setattr(host, 'e_settings', s),
            restore_music_runtime_state_fn=lambda: host._restore_music_runtime_state(),
            restore_runtime_state_fn=lambda: host._restore_runtime_state(),
            logger=_MainWindowLoggerAdapter(host),
            bus=_UiBusAdapter(host.bus),
            db_cfg=host.db_cfg,
        )
        host.progress_coordinator = ProgressCoordinator(
            host=host,
            confirm_question_fn=make_confirm_question_fn(host),
            warning_fn=make_warning_fn(host),
            table_populate_fn=lambda rows: make_table_populate_fn(host.progress_table)(rows),
            process_events_fn=make_process_events_fn(),
        )
        host.youtube_coordinator = YouTubeCoordinator(
            host=host,
            db_cfg=host.db_cfg,
            bus=_UiBusAdapter(host.bus),
            settings_accessor=host._music_settings,
            db_cfg_accessor=lambda: host.db_cfg,
            logger=_MainWindowLoggerAdapter(host),
            confirm_fn=make_confirm_fn(host),
            input_fn=make_input_fn(host),
            timer_factory=make_timer_factory(host),
        )
        host.auto_video_coordinator = AutoVideoCoordinator(
            db_cfg_accessor=lambda: host.db_cfg,
            settings_accessor=host._music_settings,
            profile_accessor=lambda pid: host._music_profile_by_id(pid) or {},
            get_video_template_fn=lambda tpl_id: host._get_saved_video_template(tpl_id),
            resolved_output_resolution_fn=lambda profile: host._resolved_output_resolution(profile=profile),
            auto_video_batches_accessor=lambda: getattr(host, '_auto_video_batches', {}) or {},
            ffmpeg_path_accessor=lambda: getattr(host, '_ffmpeg_path', ''),
            export_batch_state_accessor=lambda: {},
        )
        host.music_settings_coordinator = MusicSettingsCoordinator(
            host,
            table_populate_fn=lambda rows: make_table_populate_fn(host.music_pools_table)(rows),
            warning_fn=make_warning_fn(host),
            confirm_question_fn=make_confirm_question_fn(host),
            file_dialog_fn=make_file_dialog_fn(host),
        )
        host.music_history_coordinator = MusicHistoryCoordinator()
        host.merge_worker = MergeWorker(
            on_status=lambda msg: host.bus.music_event.emit({"type": "auto_video_status", "message": msg}),
        )
        log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase A: Coordinators initialized")
        host._popout = None
        host.current_template_id = None
        host._suno_rate_lock = threading.Lock()
        host._suno_generate_times = deque()
        host._suno_credits_cache = {"credits": None, "checkedAt": 0.0}
        # music_heartbeat timer (formerly _suno_credits_timer) is now registered
        # via TimerRegistry after UI build.
        host._music_suno_auto_poll_enabled = False
        host._image_poll_running = False
        host._image_cancel_requested = False
        host._image_status_message = "Ready"
        host._youtube_progress_by_job_uid = {}
        host.image_from_date = ""
        host.image_to_date = ""
        host._image_prompt_text = ""
        host._image_preview_mode = ""
        host._selected_layer_index = 0

        host.user_data_dir = None
        host._db_startup_message = ""
        host.persistence_coordinator.initialize_database()
        if host._db_startup_message:
            host._log(f"[{host._time_now()}] DB startup issue: {host._db_startup_message}")
            host._footer.set_music_status(f"DB: {host._db_startup_message}")
        host.persistence_coordinator.load_persisted_data()
        host._sanitize_startup_youtube_auto_upload()
        host._music_ui_loading = False
        host.music_current_description = ""
        host.music_current_structure = ""
        host.music_current_song_id = None
        host.music_run_from_date = ""
        host.music_run_to_date = ""
        host.music_last_batch_only = False
        host._footer.set_music_status("Ready")
        host._footer.set_suno_status("")
        host._music_batch_album_by_batch = {}
        host._music_generating = False
        host._music_cancel_requested = False
        host._music_suno_poll_running = False
        host._music_pool_stats = {}
        host._music_pools_rows = []
        host._music_pools_page = 0
        host._music_pools_page_size = 100
        host._music_pools_generate_count = 10000
        host._music_pools_selected_id = ""
        host._music_settings_selected_profile_id = None
        # The MusicPageController (which owns ``on_music_suno_callback_received``)
        # is built later in ``_construct_decomposition_controllers``; the callback
        # only fires at runtime, so a deferred lambda resolves it safely then.
        host._music_callback_server = CallbackServerManager(
            on_callback=lambda payload: host._music_controller.on_music_suno_callback_received(payload)
        )
        host._music_ngrok_manager = NgrokManager()
        host._music_generation_thread = None

    # ------------------------------------------------------------------
    # Phase B — new controller construction (task 12.1)
    # ------------------------------------------------------------------
    def _construct_decomposition_controllers(self) -> None:
        """Construct and assign the extracted controllers onto the host.

        Runs at the tail of Phase B, after the existing coordinators exist.
        Each controller is wired with lazy accessors so it never holds a
        ``MainWindow`` reference (see the Controller Dependency Matrix in
        design.md).
        """
        host = self._host

        def attr(name: str) -> Callable[[], object]:
            """Lazy zero-arg accessor returning ``host.<name>`` (``None`` if absent)."""
            return lambda: getattr(host, name, None)

        def setter(name: str) -> Callable[..., None]:
            """Return a one-arg setter that assigns ``host.<name> = value``."""
            return lambda value: setattr(host, name, value)

        db_cfg_accessor: Callable[[], object] = lambda: getattr(host, "db_cfg", None)
        settings_accessor = host._music_settings

        # --- AudioController -------------------------------------------------
        # preview_accessor -> the visualizer preview widget (built in Phase C).
        # ui_update_fn -> host helper that refreshes the seek label/slider.
        host._audio_controller = AudioController(
            preview_accessor=attr("preview"),
            ui_update_fn=lambda cur, dur: host._audio_ui_update(cur, dur),
        )

        # --- VideoPageController --------------------------------------------
        # template_accessor/mutator read & push the live template to the
        # preview. persist_fn matches the pre-decomposition behaviour: per-slider
        # updates push to the live preview only (explicit template save persists
        # to the DB), so it is a documented no-op here.
        def video_template_mutator(template: dict) -> None:
            host.template = template
            preview = getattr(host, "preview", None)
            if preview is not None and hasattr(preview, "set_template"):
                preview.set_template(template)

        def video_persist(_template: dict) -> None:
            # Parity with MainWindow._update_* methods: slider/combo edits update
            # the live preview but are not auto-persisted per change. Explicit
            # template save (save_template) handles persistence.
            return None

        host._video_controller = VideoPageController(
            template_accessor=lambda: getattr(host, "template", {}) or {},
            template_mutator=video_template_mutator,
            preview_accessor=attr("preview"),
            persist_fn=video_persist,
            widget_accessors=self._video_widget_accessors(attr),
        )

        # --- SignalRouter ----------------------------------------------------
        # Built with the full event-routing map (design.md "Event Routing Map").
        # Double-dispatch avoidance: Phase A (_phase_a_state_defaults) connects
        # host.bus.music_event / host.bus.export_event directly to the host
        # handlers, so to prevent events being handled twice the router is bound
        # to a dedicated, inert UiBus rather than host.bus. The router and its
        # handler map are fully assembled and assigned to the host; a follow-up
        # pass removes the host's _on_music_event/_on_export_event connections
        # and rebinds the router to host.bus as the sole dispatcher.
        router_bus = UiBus()
        host._signal_router = SignalRouter(
            bus=router_bus,
            handlers=self._signal_router_handlers(),
        )
        # Keep the dedicated bus alive (SignalRouter does not retain it) so its
        # connections are not garbage-collected.
        host._signal_router_bus = router_bus

        # --- DashboardPageController ----------------------------------------
        host._dashboard_controller = DashboardPageController(
            db_cfg_accessor=db_cfg_accessor,
            bus=host.bus,
            settings_accessor=settings_accessor,
            widget_accessors=self._dashboard_widget_accessors(attr),
            stats_builder=self._dashboard_stats_builder(),
        )

        # --- ProgressPageController -----------------------------------------
        host._progress_controller = ProgressPageController(
            db_cfg_accessor=db_cfg_accessor,
            bus=host.bus,
            settings_accessor=settings_accessor,
            merge_worker=host.merge_worker,
            widget_accessors=self._progress_widget_accessors(attr),
        )

        # --- MusicPageController --------------------------------------------
        host._music_controller = MusicPageController(
            music_coordinator=host._music_coordinator,
            db_cfg_accessor=db_cfg_accessor,
            bus=host.bus,
            settings_accessor=settings_accessor,
            footer=host._footer,
            widget_accessors=self._music_widget_accessors(attr, setter),
        )

        # --- YouTubeOAuthController -----------------------------------------
        host._youtube_oauth_controller = YouTubeOAuthController(
            db_cfg_accessor=db_cfg_accessor,
            youtube_coordinator=host.youtube_coordinator,
            settings_accessor=settings_accessor,
            widget_accessors=self._youtube_oauth_widget_accessors(attr),
            persist_fn=host._persist_setting_patch,
            warning_fn=make_warning_fn(host),
            confirm_question_fn=make_confirm_question_fn(host),
            table_populate_fn=lambda rows: make_table_populate_fn(host.youtube_oauth_apps_table)(rows),
        )

        log_line(
            f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase B: "
            "Decomposition controllers constructed"
        )

    # ------------------------------------------------------------------
    # Phase B helpers — handler map & widget-accessor registries
    # ------------------------------------------------------------------
    def _host_accessor(self) -> Callable[[], object]:
        """Return a zero-arg accessor that resolves to the host itself."""
        host = self._host
        return lambda: host

    def _signal_router_handlers(self) -> dict:
        """Build the SignalRouter handlers map (design.md "Event Routing Map").

        Maps each ``event["type"]`` to the host handler method. The host
        ``_handle_*`` / coordinator-delegating methods always exist on the
        ``MainWindow`` mixins, so binding them now is safe.
        """
        host = self._host
        return {
            # music_event types
            "song": host._handle_song,
            "progress": host._handle_progress,
            "status": host._handle_status,
            "lyrics_polished": host._handle_lyrics_polished,
            "suno_result": host._handle_suno_result,
            "suno_poll_result": host._handle_suno_poll_result,
            "suno_schedule_poll": host._handle_suno_schedule_poll,
            "done": host._handle_done,
            "image_poll_started": host._handle_image_poll_started,
            # present in MainWindow._on_music_event today; kept for fidelity when
            # the router becomes the sole dispatcher (task 11.2).
            "image_poll_result": host._handle_image_poll_result,
            "auto_video_status": host._handle_auto_video_status,
            "auto_video_done": host._handle_auto_video_done,
            "youtube_connect_select_channel": host._handle_youtube_connect_select_channel,
            "youtube_connect_done": host._handle_youtube_connect_done,
            "youtube_playlists_loaded": host._handle_youtube_playlists_loaded,
            "youtube_upload_status": host._handle_youtube_upload_status,
            "youtube_upload_progress": host._handle_youtube_upload_progress,
            "youtube_upload_done": host._handle_youtube_upload_done,
            # export_event types
            "started": host._handle_export_started,
            "stage_changed": host._handle_export_stage_changed,
            "completed": host._handle_export_completed,
            "failed": host._handle_export_failed,
        }

    def _dashboard_stats_builder(self) -> Callable[..., dict] | None:
        """Return the dashboard stats builder (delegates to ProgressCoordinator)."""
        host = self._host

        def build(db_cfg, **kwargs) -> dict:
            coord = getattr(host, "progress_coordinator", None)
            if coord is None or not hasattr(coord, "build_dashboard_stats"):
                return {}
            return coord.build_dashboard_stats(db_cfg, **kwargs)

        return build

    @staticmethod
    def _video_widget_accessors(attr: Callable[[str], Callable[[], object]]) -> dict:
        """Widget accessors for VideoPageController.

        Keys mirror the controller's documented ``widget_accessors`` keys and
        resolve to the identically-named ``MainWindow`` widget attributes.
        """
        names = (
            # collaborator
            "template_mgmt_coordinator",
            # style / audio / position
            "style_combo", "spectrum_enabled", "sens_slider", "sens_label",
            "smooth_slider", "smooth_label", "anchor_combo", "x_slider", "x_label",
            "y_slider", "y_label",
            # background
            "bg_fit_mode_combo", "bg_user_scale_slider", "bg_user_scale_label",
            "bg_edit_mode", "bg_brightness_slider", "bg_brightness_label",
            "bg_reactivity_slider", "bg_reactivity_label", "bg_smoothing_slider",
            "bg_smoothing_label", "bg_motion_mode_combo", "bg_motion_zoom_slider",
            "bg_motion_zoom_label", "bg_motion_vibrate_slider",
            "bg_motion_vibrate_label",
            # particles
            "particles_enabled", "particles_controls", "p_max_slider", "p_max_label",
            "p_spawn_slider", "p_spawn_label", "p_life_slider", "p_life_label",
            "p_speed_slider", "p_speed_label", "p_react_slider", "p_react_label",
            "p_smoothing_slider", "p_smoothing_label", "p_size_slider", "p_size_label",
            "p_opacity_slider", "p_opacity_label", "p_color_input",
            "p_spawn_mode_combo", "p_spawn_trigger_combo", "p_spawn_threshold_slider",
            "p_spawn_threshold_label", "p_style_combo", "p_react_color_input",
            "p_react_strength_slider", "p_react_strength_label", "p_variant_combo",
            "p_spawn_area_combo", "p_size_jitter_slider", "p_size_jitter_label",
            "p_drift_slider", "p_drift_label", "p_swirl_slider", "p_swirl_label",
            # vignette
            "vignette_enabled", "vignette_controls", "vignette_strength_slider",
            "vignette_strength_label", "vignette_feather_slider",
            "vignette_feather_label", "vignette_opacity_slider",
            "vignette_opacity_label", "vignette_color_input",
            # smoke
            "smoke_enabled", "smoke_controls", "smoke_strength_slider",
            "smoke_strength_label", "smoke_blur_slider", "smoke_blur_label",
            "smoke_noise_slider", "smoke_noise_label", "smoke_speed_slider",
            "smoke_speed_label", "smoke_opacity_slider", "smoke_opacity_label",
            "smoke_color_input",
            # logo
            "logo_enabled", "logo_controls", "logo_shape_combo", "logo_size_slider",
            "logo_size_label", "logo_opacity_slider", "logo_opacity_label",
            "logo_reactivity_slider", "logo_reactivity_label", "logo_smoothing_slider",
            "logo_smoothing_label", "logo_spin_enabled", "logo_spin_controls",
            "logo_spin_direction_combo", "logo_spin_speed_slider",
            "logo_spin_speed_label",
            # text overlays
            "text_overlay_enabled", "text_overlay_controls", "text_overlay_text",
            "text_overlay_anchor", "text_overlay_anim", "text_overlay_color",
            "text_overlay_duration", "text_overlay_start", "text_overlay_shadow_slider",
            "text_overlay_shadow_label", "text_overlay_size_slider",
            "text_overlay_size_label", "text_overlay_stroke_color",
            "text_overlay_stroke_slider", "text_overlay_stroke_label",
            "text_overlay_x_slider", "text_overlay_x_label", "text_overlay_y_slider",
            "text_overlay_y_label",
            # layers
            "layer_selector", "btn_remove_layer", "layer_name_input",
            "layer_barwidth_slider", "layer_barwidth_label", "layer_blend_combo",
            "layer_blur_slider", "layer_blur_label", "layer_color_mode",
            "layer_curved_cb", "layer_editing", "layer_fill_cb", "layer_glow_slider",
            "layer_glow_label", "layer_grad_dir", "layer_grad_preset",
            "layer_grad_widget", "layer_gravity_combo", "layer_mirrored_cb",
            "layer_opacity_slider", "layer_opacity_label", "layer_radius_slider",
            "layer_radius_label", "layer_solid_input", "layer_solid_widget",
            "layer_thickness_slider", "layer_thickness_label", "template_name_input",
        )
        return {name: attr(name) for name in names}

    def _dashboard_widget_accessors(self, attr: Callable[[str], Callable[[], object]]) -> dict:
        """Widget/collaborator/callback accessors for DashboardPageController."""
        # key (controller-side) -> host attribute / method name
        mapping = {
            "status_label": "dashboard_status_label",
            "summary_label": "dashboard_summary_label",
            "kpi_labels": "dashboard_kpi_labels",
            "stage_bars": "dashboard_stage_bars",
            "failures_table": "dashboard_failures_table",
            "activity_table": "dashboard_activity_table",
            "from_date": "dashboard_from_date",
            "to_date": "dashboard_to_date",
            "profile_combo": "dashboard_profile_combo",
            "active_only": "dashboard_active_only",
            "music_data": "music_data",
            "app_closing": "_app_closing",
            "log": "_log",
            "set_global_status": "_set_global_status",
            "progress_cancel_row": "_progress_cancel_row",
            "progress_restart_images": "_progress_restart_images",
            "progress_restart_converter": "_progress_restart_converter",
            "progress_restart_merge_only": "_progress_restart_merge_only",
        }
        accessors = {key: attr(name) for key, name in mapping.items()}
        # window -> the MainWindow host itself (dialog parent for menus).
        accessors["window"] = self._host_accessor()
        # suno_credits -> the cached Suno credit count (int) or None.
        host = self._host
        accessors["suno_credits"] = lambda: (
            (getattr(host, "_suno_credits_cache", {}) or {}).get("credits")
        )
        # token_store -> for API stats calls
        app = QApplication.instance()
        accessors["token_store"] = lambda: (app.property("token_store") if app else None)
        # donut charts
        accessors["donut_credits"] = lambda: getattr(host, "dashboard_donut_credits", None)
        accessors["donut_songs"] = lambda: getattr(host, "dashboard_donut_songs", None)
        accessors["donut_images"] = lambda: getattr(host, "dashboard_donut_images", None)
        # line chart
        accessors["line_chart"] = lambda: getattr(host, "dashboard_line_chart", None)
        return accessors

    def _progress_widget_accessors(self, attr: Callable[[str], Callable[[], object]]) -> dict:
        """Widget/collaborator/state/callback accessors for ProgressPageController."""
        mapping = {
            "progress_table": "progress_table",
            "progress_status_label": "progress_status_label",
            "progress_summary_label": "progress_summary_label",
            "progress_from_date": "progress_from_date",
            "progress_to_date": "progress_to_date",
            "progress_limit_combo": "progress_limit_combo",
            "progress_active_only": "progress_active_only",
            "music_data": "music_data",
            "youtube_coordinator": "youtube_coordinator",
            "image_coordinator": "_image_coordinator",
            "footer": "_footer",
            "app_closing": "_app_closing",
            "ffmpeg_path": "_ffmpeg_path",
            "image_status_message": "_image_status_message",
            "auto_video_batches": "_auto_video_batches",
            "auto_video_done": "_auto_video_done",
            "auto_video_merging_dirs": "_auto_video_merging_dirs",
            "auto_video_active_channels": "_auto_video_active_channels",
            "auto_video_running": "_auto_video_running",
            "export_batches": "_export_batches",
            "export_merge_running": "_export_merge_running",
            "youtube_progress_by_job_uid": "_youtube_progress_by_job_uid",
            "log": "_log",
            "set_global_status": "_set_global_status",
            "set_music_status": "_set_music_status",
            "music_profile_by_id": "_music_profile_by_id",
            "get_saved_video_template": "_get_saved_video_template",
            "try_start_auto_video_channel": "_try_start_auto_video_channel",
            "cancel_unfinished_background_jobs": "_cancel_unfinished_background_jobs",
            "safe_batch_suffix": "_safe_batch_suffix",
            "enqueue_youtube_upload_for_merge": "_enqueue_youtube_upload_for_merge",
            "youtube_upload_tick": "_youtube_upload_tick",
            "youtube_is_mp4_ready_for_upload": "_youtube_is_mp4_ready_for_upload",
            "refresh_history_rows": "_refresh_history_rows",
        }
        accessors = {key: attr(name) for key, name in mapping.items()}
        accessors["window"] = self._host_accessor()
        accessors["generation_proxy"] = attr("_generation_proxy")
        return accessors

    def _music_widget_accessors(
        self,
        attr: Callable[[str], Callable[[], object]],
        setter: Callable[[str], Callable[..., None]],
    ) -> dict:
        """Widget/collaborator/state/callback accessors for MusicPageController."""
        mapping = {
            # widgets / state
            "music_draft_title": "music_draft_title",
            "music_draft_album": "music_draft_album",
            "music_song_lyrics_editor": "music_song_lyrics_editor",
            "music_description_editor": "music_description_editor",
            "music_structure_editor": "music_structure_editor",
            "music_settings_profile_list": "music_settings_profile_list",
            "music_history_table": "music_history_table",
            "music_history_rows": "music_history_rows",
            "music_suno_ngrok_status": "music_suno_ngrok_status",
            "music_data": "music_data",
            "music_ui_loading": "_music_ui_loading",
            "music_suno_auto_poll_enabled": "_music_suno_auto_poll_enabled",
            # collaborators
            "music_settings_coordinator": "music_settings_coordinator",
            "youtube_coordinator": "youtube_coordinator",
            "profile_coordinator": "profile_coordinator",
            "music_ngrok_manager": "_music_ngrok_manager",
            # host-helper callables
            "log": "_log",
            "current_music_song": "_current_music_song",
            "submit_music_song_to_suno": "_submit_music_song_to_suno",
            "on_music_history_row_selected": "_on_music_history_row_selected",
            "on_music_open_song_folder_clicked": "_on_music_open_song_folder_clicked",
            "on_music_open_song_channel_folder_clicked": "_on_music_open_song_channel_folder_clicked",
            "refresh_music_ui": "_refresh_music_ui",
            "refresh_music_history_table": "_refresh_music_history_table",
            "refresh_music_profile_lists": "_refresh_music_profile_lists",
            "refresh_music_match_structure_options": "_refresh_music_match_structure_options",
            "refresh_music_saved_text_list": "_refresh_music_saved_text_list",
            "save_music_draft_state": "_save_music_draft_state",
            "persist_music_runtime_state": "_persist_music_runtime_state",
            "load_music_settings_profile_details": "_load_music_settings_profile_details",
            "update_music_credit_cost_label": "_update_music_credit_cost_label",
            "start_suno_credits_refresh_async": "_start_suno_credits_refresh_async",
            "trigger_music_suno_poll": "_trigger_music_suno_poll",
        }
        accessors = {key: attr(name) for key, name in mapping.items()}
        accessors["window"] = self._host_accessor()
        # Setters that assign back to host state (controller invokes with a value).
        accessors["set_music_current_description"] = lambda: setter("music_current_description")
        accessors["set_music_current_structure"] = lambda: setter("music_current_structure")
        accessors["set_music_last_batch_only"] = lambda: setter("music_last_batch_only")
        accessors["set_music_settings_selected_profile_id"] = lambda: setter("_music_settings_selected_profile_id")
        return accessors

    def _youtube_oauth_widget_accessors(self, attr: Callable[[str], Callable[[], object]]) -> dict:
        """Widget/callback accessors for YouTubeOAuthController."""
        mapping = {
            "current_primary_page": "_current_primary_page",
            "music_settings_tabs": "music_settings_tabs",
            "youtube_oauth_apps_table": "youtube_oauth_apps_table",
            "youtube_oauth_app_name": "youtube_oauth_app_name",
            "youtube_oauth_app_client_id": "youtube_oauth_app_client_id",
            "youtube_oauth_app_client_secret": "youtube_oauth_app_client_secret",
            "load_music_settings_profile_details": "_load_music_settings_profile_details",
            "log": "_log",
            "music_profile_by_id": "_music_profile_by_id",
            "set_music_status": "_set_music_status",
        }
        accessors = {key: attr(name) for key, name in mapping.items()}
        accessors["dialog_parent"] = self._host_accessor()
        return accessors

    # ------------------------------------------------------------------
    # Phase C — UI build
    # ------------------------------------------------------------------
    def _phase_c_ui_build(self) -> None:
        """Build the UI layer.

        When MUSIC_GEN_WEB_UI=1, the content area (where primary_stack normally
        lives) is replaced with a QWebEngineView that renders the React app.
        The sidebar, header, and footer remain as PyQt6 widgets.

        All widget references stored on the host are assigned during this phase.
        """
        host = self._host

        if self._should_use_web_ui():
            host._use_web_ui = True
            self._phase_c_hybrid_ui_build(host)
        else:
            host._use_web_ui = False
            self._phase_c_widget_ui_build(host)

    def _should_use_web_ui(self) -> bool:
        """Check if hybrid web UI should be used.

        Currently disabled — always uses native widget UI.
        """
        return False

    def _phase_c_hybrid_ui_build(self, host: "MainWindow") -> None:
        """Build hybrid UI: PyQt6 titlebar + QWebEngineView for sidebar/content/footer.

        The QWebEngineView creation is deferred via QTimer so the window shows
        immediately with just the titlebar while Chromium initializes in the background.
        """
        from .web_bridge import WebBridge

        # --- Root layout ---
        main_widget = QWidget()
        _sh_set_panel_role(main_widget, "appRoot")
        host.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- PyQt6 titlebar (window controls) ---
        host.app_header = self._build_title_bar(host)
        root_layout.addWidget(host.app_header)
        QTimer.singleShot(0, lambda: host._start_suno_credits_refresh_async(force=False))

        # --- Placeholder while QWebEngineView loads ---
        from PyQt6.QtWidgets import QLabel
        placeholder = QLabel("Loading web UI...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("background: #080c24; color: #8ea4c7; font-size: 14px;")
        root_layout.addWidget(placeholder, 1)

        # --- primary_stack not used in hybrid mode ---
        host.primary_stack = None
        host.primary_nav = None
        host.global_footer = None
        host.footer_left_label = None

        # --- QWebChannel bridge (can be created now, it's lightweight) ---
        from PyQt6.QtWebChannel import QWebChannel
        host.web_bridge = WebBridge(host)
        host.web_channel = QWebChannel()
        host.web_channel.registerObject("python", host.web_bridge)

        # --- Wire bus signals to web bridge ---
        self._wire_web_bridge_signals(host)

        # --- Defer QWebEngineView creation (Chromium import is very heavy, ~10s) ---
        # Show window first so user sees titlebar + "Loading..." during the import
        def _create_web_view():
            try:
                from PyQt6.QtWebEngineWidgets import QWebEngineView as _QWebEngineView

                root_layout.removeWidget(placeholder)
                placeholder.deleteLater()

                host.web_view = _QWebEngineView()
                root_layout.addWidget(host.web_view, 1)
                host.web_view.page().setWebChannel(host.web_channel)

                web_dist = Path(__file__).parent.parent / "web" / "dist" / "index.html"
                if web_dist.exists():
                    host.web_view.setUrl(QUrl.fromLocalFile(str(web_dist)))
                    log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase C: Hybrid — React loading")
                else:
                    host.web_view.setHtml(self._placeholder_html())
                    log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase C: Hybrid — web/dist not found")
            except Exception as exc:
                log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase C: Hybrid FAILED — {exc}")
                placeholder.setText(f"Failed to load web UI: {exc}")

        # Show window immediately, then load QWebEngineView
        QTimer.singleShot(0, _create_web_view)

    def _placeholder_html(self) -> str:
        """Generate placeholder HTML when web dist is not available."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { margin: 0; background: #0a0e27; color: #eef4ff; font-family: Segoe UI, sans-serif;
                       display: flex; align-items: center; justify-content: center; height: 100vh; }
                .container { text-align: center; }
                h1 { color: #00d4ff; }
                p { color: #8ea4c7; }
                code { background: #1e2548; padding: 2px 8px; border-radius: 4px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Music Generator - Web UI</h1>
                <p>React app not built yet.</p>
                <p>Run <code>cd python_app/web && npm run build</code> to build the UI.</p>
                <p>Or run <code>npm run dev</code> in the web directory for development.</p>
            </div>
        </body>
        </html>
        """

    def _wire_web_bridge_signals(self, host: "MainWindow") -> None:
        """Wire web bridge signals to existing coordinators."""
        # Connect bus events to web bridge for forwarding to React
        def _on_music_event(ev):
            try:
                import json
                host.web_bridge.music_event.emit(json.dumps(ev))
            except Exception:
                pass

        def _on_export_event(ev):
            try:
                import json
                host.web_bridge.export_event.emit(json.dumps(ev))
            except Exception:
                pass

        # Connect signals
        host.bus.music_event.connect(_on_music_event)
        host.bus.export_event.connect(_on_export_event)

    def _phase_c_widget_ui_build(self, host: "MainWindow") -> None:
        """Build traditional widget-based UI (original implementation)."""
        main_widget = QWidget()
        _sh_set_panel_role(main_widget, "appRoot")
        host.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Window dragging support (no titlebar needed) ---
        host._window_dragging = False
        host._window_drag_pos = QPoint()

        def _win_press(event):
            if event and event.button() == Qt.MouseButton.LeftButton:
                host._window_dragging = True
                host._window_drag_pos = event.globalPosition().toPoint() - host.frameGeometry().topLeft()
                event.accept()

        def _win_move(event):
            if event and host._window_dragging:
                if host.isMaximized():
                    host.showNormal()
                host.move(event.globalPosition().toPoint() - host._window_drag_pos)
                event.accept()

        def _win_release(event):
            host._window_dragging = False

        def _win_double_click(event):
            if host.isMaximized():
                host.showNormal()
            else:
                host.showMaximized()

        # Apply drag to the main widget
        QTimer.singleShot(0, lambda: (
            setattr(host.centralWidget(), 'mousePressEvent', _win_press),
            setattr(host.centralWidget(), 'mouseMoveEvent', _win_move),
            setattr(host.centralWidget(), 'mouseReleaseEvent', _win_release),
            setattr(host.centralWidget(), 'mouseDoubleClickEvent', _win_double_click),
        ))

        # --- Layout: header full width on top, then sidebar + content below ---
        top_vbox = QVBoxLayout()
        top_vbox.setContentsMargins(0, 0, 0, 0)
        top_vbox.setSpacing(0)
        root_layout.addLayout(top_vbox, 1)

        # Top: header spanning full width (logo + CAMXORA left, bell + controls right)
        header_bar = self._build_header_bar(host)
        top_vbox.addWidget(header_bar)

        # Below header: sidebar (left) + stacked pages (right)
        shell_layout = QHBoxLayout()
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        top_vbox.addLayout(shell_layout, 1)

        # Left: sidebar (full height below header)
        host.primary_nav = host._build_primary_navigation_shell()
        shell_layout.addWidget(host.primary_nav)

        # Right: stacked pages
        host.primary_stack = QStackedWidget()
        shell_layout.addWidget(host.primary_stack, 1)

        primary_pages = [
            ("home", host._build_dashboard_workspace_page()),
            ("workflow", host._build_workflow_workspace_page()),
            ("progress", host._build_progress_workspace_page()),
            ("music", host._build_music_workspace_page()),
            ("image", host._build_image_workspace_page()),
            ("video", host._build_video_workspace_page()),
            ("merger", host._build_primary_placeholder_page("Merger", "Merger page is reserved for future development.")),
            ("settings", host._build_music_settings_tab()),
            ("log", host._build_log_workspace_page()),
        ]
        for idx, (page_key, page_widget) in enumerate(primary_pages):
            host.primary_stack.addWidget(page_widget)
            host._primary_page_index[page_key] = idx

        host.global_footer = host._build_global_footer()
        root_layout.addWidget(host.global_footer)

        # Update sidebar with license info + credit balance after UI is visible
        QTimer.singleShot(0, lambda: self._update_sidebar_license_info(host))

    def _update_sidebar_license_info(self, host: "MainWindow") -> None:
        """Read cached license status and update sidebar labels."""
        from PyQt6.QtWidgets import QApplication
        import logging
        _log = logging.getLogger("CAMXORA.sidebar")

        app = QApplication.instance()
        license_gate = app.property("license_gate") if app else None
        token_store = app.property("token_store") if app else None

        _log.info("sidebar update: license_gate=%s, token_store=%s", license_gate, token_store)

        plan_name = None
        expires_at = None
        credit_balance = None

        if license_gate is not None:
            status = license_gate.get_cached_status()
            _log.info("sidebar update: cached_status=%s", status)
            # If cache is empty (validate hasn't run yet), do a synchronous call
            if status is None and token_store is not None:
                try:
                    tokens = token_store.load()
                    _log.info("sidebar update: calling validate synchronously")
                    status = license_gate.validate(tokens.access_token)
                    _log.info("sidebar update: validate returned=%s", status)
                except Exception as exc:
                    _log.warning("sidebar update: validate failed: %s", exc)
            if status is not None:
                plan_name = status.plan_name
                expires_at = status.expires_at
                credit_balance = status.wallet_balance

        _log.info("sidebar update: plan=%s, expires=%s, credits=%s", plan_name, expires_at, credit_balance)
        host.update_sidebar_license(plan_name, expires_at, credit_balance)

    # ------------------------------------------------------------------
    # Title bar builder (used in Phase C)
    # ------------------------------------------------------------------
    def _build_title_bar(self, host: "MainWindow") -> QWidget:
        """Build a custom draggable title bar with brand, notification bell, and window controls.

        Height: 40px, styled via property selectors (no inline QSS). Supports
        drag-to-move and double-click-to-maximize.
        """
        from PyQt6.QtCore import QPoint, QSize
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton

        from .resources import icon_path as _icon_path, lucide_icon_path as _lucide_path
        from ..views.helpers.style_helper import (
            render_svg_icon as _render_icon,
            set_panel_role,
            set_button_role,
            set_label_role,
        )
        from ..design_system.tokens import DEFAULT_DARK_THEME

        _colors = DEFAULT_DARK_THEME.colors

        title_bar = QWidget(host)
        title_bar.setFixedHeight(40)
        set_panel_role(title_bar, "titleBar")

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(0)

        # --- Left side: logo SVG + app name ---
        _cache: dict = {}

        logo_btn = QToolButton()
        logo_btn.setFixedSize(QSize(24, 24))
        logo_btn.setIcon(_render_icon(_icon_path("app-logo.svg"), 20, _colors.text_primary, cache=_cache))
        logo_btn.setIconSize(QSize(20, 20))
        set_button_role(logo_btn, "windowControl")
        layout.addWidget(logo_btn)
        layout.addSpacing(8)

        app_name_label = QLabel("CAMXORA")
        set_label_role(app_name_label, "appTitle")
        layout.addWidget(app_name_label)

        layout.addStretch(1)

        # --- Right side: notification bell + window controls ---

        # Notification bell icon (placeholder)
        bell_btn = QToolButton()
        bell_btn.setFixedSize(QSize(32, 28))
        bell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bell_btn.setToolTip("Notifications")
        bell_btn.setIcon(_render_icon(_lucide_path("bell"), 16, _colors.text_muted, cache=_cache))
        bell_btn.setIconSize(QSize(16, 16))
        set_button_role(bell_btn, "windowControl")
        layout.addWidget(bell_btn)
        layout.addSpacing(8)

        # Hidden credits label — still exists as host attribute for credits refresh code
        host.header_suno_credits_label = QLabel("Credits: \u2014")
        host.header_suno_credits_label.setVisible(False)

        # Window control buttons
        def _make_ctrl_btn(icon_name: str, color: str) -> QToolButton:
            btn = QToolButton()
            btn.setFixedSize(QSize(32, 28))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(_render_icon(_lucide_path(icon_name), 16, color, cache=_cache))
            btn.setIconSize(QSize(16, 16))
            set_button_role(btn, "windowControl")
            return btn

        btn_min = _make_ctrl_btn("minus", _colors.text_muted)
        btn_max = _make_ctrl_btn("maximize-2", _colors.text_muted)
        btn_close = _make_ctrl_btn("x", "#ef4444")
        set_button_role(btn_close, "windowClose")

        from .window_config import toggle_maximize as _toggle_maximize
        btn_min.clicked.connect(lambda: host.showMinimized())
        btn_max.clicked.connect(lambda: _toggle_maximize(host))
        btn_close.clicked.connect(lambda: host.close())

        layout.addWidget(btn_min)
        layout.addWidget(btn_max)
        layout.addWidget(btn_close)

        # --- Dragging support ---
        title_bar._dragging = False  # type: ignore[attr-defined]
        title_bar._drag_pos = QPoint()  # type: ignore[attr-defined]

        def _on_press(event: QMouseEvent | None) -> None:
            if event and event.button() == Qt.MouseButton.LeftButton:
                title_bar._dragging = True  # type: ignore[attr-defined]
                title_bar._drag_pos = event.globalPosition().toPoint() - host.frameGeometry().topLeft()  # type: ignore[attr-defined]
                event.accept()

        def _on_move(event: QMouseEvent | None) -> None:
            if event and title_bar._dragging:  # type: ignore[attr-defined]
                if host.isMaximized():
                    from PyQt6.QtCore import QRect
                    prev = host.property("_pre_maximize_geo")
                    if isinstance(prev, QRect) and prev.isValid():
                        ratio = event.position().x() / max(host.width(), 1)
                        new_x = int(event.globalPosition().x() - ratio * prev.width())
                        new_y = int(event.globalPosition().y() - event.position().y())
                        host.setGeometry(new_x, new_y, prev.width(), prev.height())
                        host.setProperty("_pre_maximize_geo", None)
                    else:
                        host.showNormal()
                    title_bar._drag_pos = event.globalPosition().toPoint() - host.frameGeometry().topLeft()  # type: ignore[attr-defined]
                host.move(event.globalPosition().toPoint() - title_bar._drag_pos)  # type: ignore[attr-defined]
                event.accept()

        def _on_release(event: QMouseEvent | None) -> None:
            title_bar._dragging = False  # type: ignore[attr-defined]

        def _on_double_click(event: QMouseEvent | None) -> None:
            _toggle_maximize(host)

        title_bar.mousePressEvent = _on_press  # type: ignore[assignment]
        title_bar.mouseMoveEvent = _on_move  # type: ignore[assignment]
        title_bar.mouseReleaseEvent = _on_release  # type: ignore[assignment]
        title_bar.mouseDoubleClickEvent = _on_double_click  # type: ignore[assignment]

        return title_bar

    # ------------------------------------------------------------------
    # Header bar (right of sidebar, window controls only)
    # ------------------------------------------------------------------
    def _build_header_bar(self, host: "MainWindow") -> QWidget:
        """Build a slim 48px header bar spanning full width.

        Left: small logo + CAMXORA. Right: bell + window controls.
        """
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QPixmap, QPainter
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton

        from .resources import icon_path as _icon_path, lucide_icon_path as _lucide_path
        from ..views.helpers.style_helper import (
            render_svg_icon as _render_icon,
            set_panel_role,
            set_button_role,
            set_label_role,
        )
        from ..design_system.tokens import DEFAULT_DARK_THEME

        _colors = DEFAULT_DARK_THEME.colors
        _cache: dict = {}

        bar = QWidget()
        bar.setFixedHeight(48)
        set_panel_role(bar, "headerBar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(0)

        # Left: small logo + CAMXORA
        logo_label = QLabel()
        logo_label.setFixedSize(QSize(28, 28))
        logo_pixmap = QPixmap(28, 28)
        logo_pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(_icon_path("app-logo.svg"))
        painter = QPainter(logo_pixmap)
        renderer.render(painter)
        painter.end()
        logo_label.setPixmap(logo_pixmap)
        layout.addWidget(logo_label)
        layout.addSpacing(10)

        brand_label = QLabel("CAMXORA")
        set_label_role(brand_label, "headerBrandTitle")
        _bf = brand_label.font()
        _bf.setBold(True)
        brand_label.setFont(_bf)
        layout.addWidget(brand_label)

        layout.addStretch(1)

        # Right: bell + window controls
        bell_btn = QToolButton()
        bell_btn.setFixedSize(QSize(36, 36))
        bell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bell_btn.setToolTip("Notifications")
        bell_btn.setIcon(_render_icon(_lucide_path("bell"), 18, _colors.text_muted, cache=_cache))
        bell_btn.setIconSize(QSize(18, 18))
        set_button_role(bell_btn, "windowControl")
        layout.addWidget(bell_btn)
        layout.addSpacing(8)

        host.header_suno_credits_label = QLabel("Credits: \u2014")
        host.header_suno_credits_label.setVisible(False)

        def _make_ctrl_btn(icon_name: str, color: str) -> QToolButton:
            btn = QToolButton()
            btn.setFixedSize(QSize(36, 36))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(_render_icon(_lucide_path(icon_name), 18, color, cache=_cache))
            btn.setIconSize(QSize(18, 18))
            set_button_role(btn, "windowControl")
            return btn

        btn_min = _make_ctrl_btn("minus", _colors.text_muted)
        btn_max = _make_ctrl_btn("maximize-2", _colors.text_muted)
        btn_close = _make_ctrl_btn("x", "#ef4444")
        set_button_role(btn_close, "windowClose")

        from .window_config import toggle_maximize as _toggle_maximize_2
        btn_min.clicked.connect(lambda: host.showMinimized())
        btn_max.clicked.connect(lambda: _toggle_maximize_2(host))
        btn_close.clicked.connect(lambda: host.close())

        layout.addWidget(btn_min)
        layout.addSpacing(4)
        layout.addWidget(btn_max)
        layout.addSpacing(4)
        layout.addWidget(btn_close)

        return bar

    # ------------------------------------------------------------------
    # Phase D — timers & state restoration
    # ------------------------------------------------------------------
    def _phase_d_timers_and_restore(self) -> None:
        """Register timers, apply settings, restore runtime state, start polling.

        Timer callbacks registered here only reference attributes assigned in
        Phase A, B, or C (all of which have completed before the timers start).
        Migrated (task 11.3) from the former
        ``MainWindow._io_phase_d_timers_and_restore`` host hook.
        """
        host = self._host

        # Skip widget-dependent operations when using web UI
        if not getattr(host, '_use_web_ui', False):
            host._apply_settings_to_ui()
            host.refresh_templates()
            host._restore_runtime_state()
            host._restore_music_runtime_state()
            host._refresh_music_ui()
            host._set_primary_page("home")
        else:
            # Web UI: apply settings and restore state without widget references
            try:
                host._restore_runtime_state()
            except Exception:
                pass
            try:
                host._restore_music_runtime_state()
            except Exception:
                pass
            # Send initial page to React
            try:
                if hasattr(host, 'web_bridge') and host.web_bridge:
                    host.web_bridge.navigate_to_page("home")
            except Exception:
                pass

        log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase C: UI pages built")
        # --- TimerRegistry: register all nine timers ---
        # (host._timer_registry is created by InitOrchestrator Phase A)
        host._timer_registry.register(
            "image_auto_poll", 30_000,
            lambda: host._image_coordinator.trigger_image_poll(manual=False, max_jobs=10) if host._image_coordinator else None,
        )
        host._timer_registry.register(
            "image_live_refresh", 1_500,
            host._refresh_image_jobs_table,
            page_gate="image",
        )
        host._timer_registry.register(
            "auto_video", 30_000,
            host._auto_video_tick,
        )
        host._timer_registry.register(
            "progress_live_refresh", 2_500,
            lambda: host._progress_controller._refresh_progress_table_async(),
            page_gate="progress",
        )
        host._timer_registry.register(
            "dashboard_live_refresh", 4_500,
            lambda: host._dashboard_controller.refresh_dashboard_async(),
            page_gate="home",
        )
        host._timer_registry.register(
            "youtube_auto_poll", 30_000,
            host._youtube_upload_tick,
        )
        host._music_suno_poll_timer = host._timer_registry.register(
            "music_suno_poll", 30_000,
            lambda: host._trigger_music_suno_poll(manual=False, max_tasks=10),
        )
        host._timer_registry.register(
            "music_render", 200,
            host._tick_ui,
        )
        host._timer_registry.register(
            "music_heartbeat", 60_000,
            lambda: host._start_suno_credits_refresh_async(force=False),
        )
        # Start music_suno_poll via coordinator (preserves existing behaviour)
        host._music_coordinator.start_polling(host._music_suno_poll_timer)
        # Pass timer references to coordinators for backward compatibility
        host._image_auto_poll_timer = host._timer_registry._timers["image_auto_poll"]
        host._image_live_refresh_timer = host._timer_registry._timers["image_live_refresh"]
        host._youtube_auto_poll_timer = host._timer_registry._timers["youtube_auto_poll"]
        host._image_coordinator.start_polling(host._image_auto_poll_timer, host._image_live_refresh_timer)
        # Start the music_render timer immediately (was: self.ui_timer.start(200))
        host._timer_registry.sync("music_render", enabled=True)
        # Start the music_heartbeat timer immediately (was: self._suno_credits_timer.start())
        host._timer_registry.sync("music_heartbeat", enabled=True)
        log_line(f"[{time.strftime('%H:%M:%S')}] [STARTUP] Phase B: Timers registered")

        # Apply license-based UI gating if a cached license status exists
        # (e.g., from auto-login before the main window is shown)
        host.apply_license_gating()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _invoke_host_hook(self, name: str) -> None:
        """Call ``host.<name>()`` when present.

        Provides the integration seam used while ``MainWindow`` is incrementally
        reduced to a thin shell (tasks 11 and 12). When the host does not yet
        define the hook, the phase is a no-op so the orchestrator can be
        exercised in isolation.
        """
        hook = getattr(self._host, name, None)
        if callable(hook):
            hook()
