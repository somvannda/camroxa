import os
import random
import re
import signal
import time
import uuid
from pathlib import Path

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None
from PyQt6.QtCore import Qt, QDate, QEvent, QObject, QPoint, QSize, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox,
    QFileDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton,
    QSlider, QToolButton, QWidget,
)

from .auto_video_handlers import AutoVideoHandlersMixin
from .image_ui_handlers import ImageUiHandlersMixin
from .init_orchestrator import InitOrchestrator
from .video_methods import VideoMethodsMixin
from .core_methods import CoreMethodsMixin
from .logging import log_line
from .music_ui_handlers import MusicUiHandlersMixin
from .resources import icon_path, lucide_icon_path
from .widgets import PopoutPreviewWindow
from .youtube_upload_handlers import YouTubeUploadHandlersMixin
from ..database.image_db import (
    cancel_all_pending_image_jobs,
    get_ready_background_output,
    upsert_image_job,
)
from ..database.music_db import (
    find_batch_by_output_dir,
)
from ..database.persistence import (
    DbCfg,
    db_get_profile_image_config,
    db_list_video_templates,
    db_upsert_video_template,
    read_local_templates,
    write_local_templates,
)
from ..database.preset_db import list_text_style_presets
from ..views.progress_view import ProgressViewMixin
from ..features.text_presets.coordinator import TextPresetManagerCoordinator
from ..views.video_view import VideoViewMixin
from ..features.youtube.db import (
    db_cancel_all_pending_youtube_jobs,
)
from ..models.music_model import normalize_music_app_data
from ..models.spectrum_model import VideoTemplate, default_template, normalize_template
from ..utils.subprocess_utils import terminate_job
from ..visualizer.contracts import PreviewConfig
from ..views.components import _fmt_time, STACKED_LAYER_PRESETS
from ..views.core_view import CoreViewMixin
from ..views.dashboard_view import DashboardViewMixin
from ..views.helpers import widget_factory
from ..views.helpers.style_helper import (
    apply_card_field as _sh_apply_card_field,
    apply_cta_button as _sh_apply_cta_button,
    refresh_widget_style as _sh_refresh_widget_style,
    render_svg_icon as _sh_render_svg_icon,
    set_button_role as _sh_set_button_role,
    set_field_role as _sh_set_field_role,
    set_label_role as _sh_set_label_role,
    set_widget_property as _sh_set_widget_property,
)
from ..views.image_view import ImageViewMixin
from ..views.log_view import LogViewMixin
from ..views.music_view import MusicViewMixin
from ..views.preset_manager_dialog import PresetManagerDialog
from ..views.settings_view import SettingsViewMixin
from ..views.workflow_view import WorkflowViewMixin


# deprecated: import from features.video_export.export_batch
from ..features.video_export.export_batch import ExportBatch  # noqa: F401


class MainWindow(QMainWindow, DashboardViewMixin, WorkflowViewMixin, MusicViewMixin, MusicUiHandlersMixin, ImageViewMixin, ImageUiHandlersMixin, VideoViewMixin, ProgressViewMixin, SettingsViewMixin, CoreViewMixin, LogViewMixin, AutoVideoHandlersMixin, YouTubeUploadHandlersMixin, VideoMethodsMixin, CoreMethodsMixin):


    # YouTube upload job execution is in YouTubeUploadHandlersMixin (app/youtube_upload_handlers.py)

    # Auto-video pipeline methods are in AutoVideoHandlersMixin (app/auto_video_handlers.py)


    def _set_primary_page(self, page_key: str) -> None:
        key = str(page_key or "").strip().lower() or "video"

        idx = self._primary_page_index.get(key, self._primary_page_index.get("video", 0))
        self.primary_stack.setCurrentIndex(idx)
        self._current_primary_page = key if key in self._primary_page_index else "video"
        self._update_nav_buttons()
        # ... rest of widget-mode logic
        if hasattr(self, '_timer_registry'):
            self._timer_registry.set_active_page(self._current_primary_page)
        if self._current_primary_page != "progress":
            if hasattr(self, '_timer_registry'):
                self._timer_registry.sync("progress_live_refresh", enabled=False)
        if self._current_primary_page != "home":
            if hasattr(self, '_timer_registry'):
                self._timer_registry.sync("dashboard_live_refresh", enabled=False)
        t_workflow = getattr(self, "_workflow_live_refresh_timer", None)
        if t_workflow is not None and t_workflow.isActive() and self._current_primary_page != "workflow":
            t_workflow.stop()
        self._update_nav_buttons()
        self._refresh_footer()
        if self._current_primary_page == "music" and getattr(self, "_music_history_dirty", False):
            if not getattr(self, "_music_history_refresh_scheduled", False):
                self._music_history_refresh_scheduled = True
                QTimer.singleShot(
                    0,
                    lambda: (
                        setattr(self, "_music_history_refresh_scheduled", False),
                        self._refresh_music_history_table(force=True),
                    ),
                )
        if self._current_primary_page == "image" and (getattr(self, "_image_dirty", False) or not getattr(self, "_image_initialized", False)):
            setattr(self, "_image_initialized", True)
            QTimer.singleShot(0, lambda: self._refresh_image_ui(force=True))
        if self._current_primary_page == "settings" and getattr(self, "_music_pools_dirty", False):
            if hasattr(self, "music_settings_tabs") and str(self.music_settings_tabs.tabText(self.music_settings_tabs.currentIndex()) or "").strip().lower() == "pools":
                self._music_pools_dirty = False
                self._music_controller.refresh_music_pool_stats(force=True)
                self._music_controller.refresh_music_pool_table(force=True)
        if self._current_primary_page == "video" and bool(getattr(self, "_pending_video_bg_path", "") or getattr(self, "_pending_video_logo_path", "") or getattr(self, "_pending_video_mp3_dir", "") or getattr(self, "_pending_video_template_id", "")):
            if not getattr(self, "_pending_video_restore_scheduled", False):
                self._pending_video_restore_scheduled = True
                QTimer.singleShot(
                    0,
                    lambda: (
                        setattr(self, "_pending_video_restore_scheduled", False),
                        self._apply_pending_video_restore(),
                    ),
                )
        if self._current_primary_page == "progress":
            if hasattr(self, '_timer_registry'):
                self._timer_registry.sync("progress_live_refresh", enabled=True)
            QTimer.singleShot(0, lambda: self._progress_controller._refresh_progress_table_async(force=True))
        if self._current_primary_page == "workflow":
            self._ensure_workflow_timers()
            t = getattr(self, "_workflow_live_refresh_timer", None)
            if t is not None and not t.isActive():
                t.start()
            QTimer.singleShot(0, lambda: self._refresh_workflow_async(force=True))
        if self._current_primary_page == "home":
            if hasattr(self, '_timer_registry'):
                self._timer_registry.sync("dashboard_live_refresh", enabled=True)
            QTimer.singleShot(0, lambda: self._dashboard_controller.refresh_dashboard_async(force=True))
        self._log(f"[{time.strftime('%H:%M:%S')}] Primary page changed: {self._current_primary_page}")

    def _update_nav_buttons(self) -> None:
        """Update sidebar nav button styling based on current page."""
        nav_buttons = getattr(self, '_primary_nav_buttons', None)
        if not nav_buttons:
            return
        for nav_key, button in nav_buttons.items():
            is_active = nav_key == self._current_primary_page
            icon_name = str(button.property("lucideName") or "").strip()
            icon_cache = getattr(button, "_icon_cache", None) or {}
            if is_active:
                _sh_set_button_role(button, "navItemActive")
                if icon_name:
                    from python_app.app.resources import lucide_icon_path as _lip
                    icon = _sh_render_svg_icon(_lip(icon_name), 20, "#ffffff", cache=icon_cache)
                    button.setIcon(icon)
                    button.setIconSize(QSize(20, 20))
            else:
                _sh_set_button_role(button, "navItem")
                if icon_name:
                    from python_app.app.resources import lucide_icon_path as _lip
                    icon = _sh_render_svg_icon(_lip(icon_name), 20, self.ui["text_muted"], cache=icon_cache)
                    button.setIcon(icon)
                    button.setIconSize(QSize(20, 20))


    def __init__(self) -> None:
        super().__init__()
        InitOrchestrator(self).run()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_dwm_corners_applied', False):
            self._dwm_corners_applied = True
            import sys
            if sys.platform == "win32":
                try:
                    import ctypes
                    DWMWA_WINDOW_CORNER_PREFERENCE = 33
                    DWMWCP_ROUND = 2
                    hwnd = int(self.winId())
                    preference = ctypes.c_int(DWMWCP_ROUND)
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                        ctypes.byref(preference), ctypes.sizeof(preference),
                    )
                except Exception:
                    pass

    def closeEvent(self, ev: QCloseEvent) -> None:
        try:
            self._app_closing = True
        except Exception:
            pass
        # 1. Cancel YouTube runtime jobs first
        try:
            self.youtube_coordinator.cancel_runtime_jobs(stop_timer=True, clear_running=True)
        except Exception:
            pass
        # 2. Stop all active export converter subprocesses (ffmpeg/visualizer)
        try:
            self.export_coordinator.stop_export()
        except Exception:
            pass
        # 3. Stop export merge ffmpeg process
        try:
            self.export_coordinator.stop_export_merge()
        except Exception:
            pass
        # 4. Kill any merge-only ffmpeg processes by setting cancel flag
        try:
            self._export_merge_cancel_requested = True
            proc = getattr(self, '_export_merge_proc', None)
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass
        # 5. Clear the merge-only queue so no new merges start
        try:
            self._merge_only_queue = []
        except Exception:
            pass
        # 6. Cancel remaining background jobs (image/youtube DB-level)
        try:
            summary = self._cancel_unfinished_background_jobs(reason="Cancelled during application shutdown", stop_youtube_runtime=False)
            self._log(
                f"[{time.strftime('%H:%M:%S')}] Shutdown cleanup: images={int(summary.get('image', 0) or 0)} youtube={int(summary.get('youtube', 0) or 0)}"
            )
            errors = summary.get("errors") if isinstance(summary, dict) else []
            if errors:
                self._log(f"[{time.strftime('%H:%M:%S')}] Shutdown cleanup warnings: {'; '.join(str(x) for x in errors if str(x).strip())}")
        except Exception as exc:
            self._log(f"[{time.strftime('%H:%M:%S')}] Shutdown cleanup failed: {exc}")
        try:
            self._music_coordinator.stop_polling()
        except Exception:
            pass
        try:
            self._image_coordinator.stop_polling()
        except Exception:
            pass
        # 7. Stop all registered timers via TimerRegistry
        try:
            self._timer_registry.stop_all()
        except Exception:
            pass
        # Preserve cancellation-token increments
        try:
            self._progress_refresh_token = int(getattr(self, "_progress_refresh_token", 0) or 0) + 1
        except Exception:
            pass
        try:
            self._dashboard_refresh_token = int(getattr(self, "_dashboard_refresh_token", 0) or 0) + 1
        except Exception:
            pass
        # 8. Force-kill any remaining child processes (converter subprocesses, ffmpeg)
        try:
            terminate_job()
        except Exception:
            pass
        if psutil is not None:
            try:
                current = psutil.Process()
                children = current.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                # Give them 2 seconds then kill
                _, alive = psutil.wait_procs(children, timeout=2)
                for child in alive:
                    try:
                        child.kill()
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            # psutil not available — terminate via subprocess tree on Windows
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                pass
        # 9. Call super to complete the close
        super().closeEvent(ev)


        


        


    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(watched, QSlider) and event.type() == QEvent.Type.Wheel:
            step = int(watched.property("_wheelStep") or watched.singleStep() or 1)
            delta = event.angleDelta().y()
            if delta:
                direction = 1 if delta > 0 else -1
                watched.setValue(max(watched.minimum(), min(watched.maximum(), watched.value() + (direction * step))))
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _tick_ui(self) -> None:
        cur, dur = self._audio_controller.tick()
        if hasattr(self, "seek_label"):
            self.seek_label.setText(f"{_fmt_time(cur)} / {_fmt_time(dur)}")
        if hasattr(self, "seek_slider") and dur > 0 and not self._seek_dragging:
            v = int(max(0.0, min(1.0, cur / dur)) * 1000.0)
            self.seek_slider.setValue(v)
        if hasattr(self, "btn_play") and hasattr(self, "preview"):
            self.btn_play.setEnabled(bool(getattr(self.preview, "audio_ready", False)))
            self._sync_play_button_state()
        if hasattr(self, "preview") and getattr(self.preview, "analysis_loading", False) and not self._export_batches:
            self._set_export_status_message("Analyzing audio for spectrum...")

    def _audio_ui_update(self, current_time: float, duration: float) -> None:
        # AudioController.ui_update_fn hook (task 12.1): refresh the seek label
        # and slider from controller-reported (current_time, duration).
        # TODO: remove after view mixin / AudioController wiring (task 11.2)
        if hasattr(self, "seek_label"):
            self.seek_label.setText(f"{_fmt_time(current_time)} / {_fmt_time(duration)}")
        if hasattr(self, "seek_slider") and duration > 0 and not self._seek_dragging:
            v = int(max(0.0, min(1.0, current_time / duration)) * 1000.0)
            self.seek_slider.setValue(v)

    # ------------------------------------------------------------------
    # Backward-compat forwarding methods (task 11.3)
    # ------------------------------------------------------------------
    # These thin forwarders bridge external coordinators, lazy widget-accessor
    # wiring, and not-yet-updated view mixins to the extracted controllers.
    # They preserve the pre-decomposition ``host._<name>(...)`` contract that
    # callers in features/* and app/* still rely on.
    # TODO: remove once every caller is updated to use the controllers directly.
    def _apply_resolved_template_settings(self, *args, **kwargs):
        return self._video_controller.apply_resolved_template_settings(*args, **kwargs)

    def _apply_dashboard_model(self, *args, **kwargs):
        return self._dashboard_controller.apply_dashboard_model(*args, **kwargs)

    def _dashboard_selected_profile_id(self, *args, **kwargs):
        return self._dashboard_controller.dashboard_selected_profile_id(*args, **kwargs)

    def _dashboard_sync_profile_combo(self, *args, **kwargs):
        return self._dashboard_controller.dashboard_sync_profile_combo(*args, **kwargs)

    def _enqueue_youtube_upload_for_merge(self, *args, **kwargs):
        return self._youtube_oauth_controller.enqueue_youtube_upload_for_merge(*args, **kwargs)

    def _resolve_youtube_oauth_client(self, *args, **kwargs):
        return self._youtube_oauth_controller.resolve_youtube_oauth_client(*args, **kwargs)

    def _youtube_scan_for_merged_outputs(self, *args, **kwargs):
        return self._youtube_oauth_controller.youtube_scan_for_merged_outputs(*args, **kwargs)

    def _progress_row_meta_at(self, *args, **kwargs):
        return self._progress_controller._progress_row_meta_at(*args, **kwargs)

    def _progress_cancel_row(self, *args, **kwargs):
        return self._progress_controller._progress_cancel_row(*args, **kwargs)

    def _progress_restart_converter(self, *args, **kwargs):
        return self._progress_controller._progress_restart_converter(*args, **kwargs)

    def _progress_restart_images(self, *args, **kwargs):
        return self._progress_controller._progress_restart_images(*args, **kwargs)

    def _progress_restart_merge_only(self, *args, **kwargs):
        return self._progress_controller._progress_restart_merge_only(*args, **kwargs)

    def _refresh_music_ngrok_status(self, *args, **kwargs):
        return self._music_controller.refresh_music_ngrok_status(*args, **kwargs)

    def _refresh_music_settings_profile_list(self, *args, **kwargs):
        return self._music_controller.refresh_music_settings_profile_list(*args, **kwargs)

    def _music_profiles(self, *args, **kwargs):
        return self.profile_mgmt_coordinator.music_profiles(*args, **kwargs)

    def _refresh_history_rows(self, *args, **kwargs):
        return self._refresh_music_history_table(*args, **kwargs)

    # ------------------------------------------------------------------
    # License-based UI gating (task 10.2)
    # ------------------------------------------------------------------

    def update_generation_controls(self, is_allowed: bool) -> None:
        """Enable or disable generation controls based on license status.

        When *is_allowed* is False, draft/Suno generation, image generation,
        and workflow generation buttons are disabled and a status message is
        shown in the footer. Non-generation features (video export, YouTube
        upload, settings, profiles) remain enabled.

        This method is safe to call at any point after the UI has been built
        (Phase C of InitOrchestrator).

        Args:
            is_allowed: True to enable all generation controls, False to
                disable them and show a license-required notification.
        """
        # Generation control widgets (may not exist if UI hasn't been built yet)
        generation_widgets: list[QWidget | None] = [
            getattr(self, "music_generate_button", None),
            getattr(self, "workflow_generate_button", None),
            getattr(self, "image_generate_now_button", None),
            getattr(self, "image_gen_thumbs_button", None),
        ]

        for widget in generation_widgets:
            if widget is not None:
                widget.setEnabled(is_allowed)

        # Update the footer status label with a license notification
        footer_label = getattr(self, "footer_left_label", None)
        if footer_label is not None:
            if not is_allowed:
                footer_label.setText(
                    "\u26a0 Active license required for generation features."
                )
            else:
                footer_label.setText("Ready")

    def apply_license_gating(self) -> None:
        """Read the license gate from the app instance and apply UI gating.

        Convenience method that retrieves the LicenseGate stored on the
        QApplication instance (set by bootstrap.py) and calls
        ``update_generation_controls()`` with the cached permission.
        """
        app = QApplication.instance()
        if app is None:
            return
        license_gate = app.property("license_gate")
        if license_gate is None:
            return
        is_allowed = license_gate.is_generation_allowed()
        self.update_generation_controls(is_allowed)


