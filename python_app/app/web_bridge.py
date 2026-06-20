"""QWebChannel bridge for React ↔ Python communication.

Exposes Python methods to JavaScript via QWebChannel and emits signals
from Python to React. This is the sole IPC layer between the web UI
and the Python backend.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow


class WebBridge(QObject):
    """Expose Python methods to React via QWebChannel.

    Signals → Python emits to React:
        progress_updated(str): JSON payload with progress data
        music_event(str): JSON payload with music event data
        export_event(str): JSON payload with export event data
        notification(str, str): (title, message) notification
        page_changed(str): page key when navigation changes
        log_update(str): JSON payload with log lines
    """

    # Outgoing signals (Python → React)
    progress_updated = pyqtSignal(str)
    music_event = pyqtSignal(str)
    export_event = pyqtSignal(str)
    notification = pyqtSignal(str, str)
    page_changed = pyqtSignal(str)
    log_update = pyqtSignal(str)

    def __init__(self, host: "MainWindow") -> None:
        super().__init__()
        self._host = host
        self._log = host._log

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    @pyqtSlot()
    def minimize_window(self) -> None:
        self._host.showMinimized()

    @pyqtSlot()
    def maximize_window(self) -> None:
        if self._host.isMaximized():
            self._host.showNormal()
        else:
            self._host.showMaximized()

    @pyqtSlot()
    def close_window(self) -> None:
        self._host.close()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def navigate(self, page: str) -> None:
        """Navigate to a page. Called from React."""
        self._host._set_primary_page(page)
        self.page_changed.emit(page)

    def navigate_to_page(self, page: str) -> None:
        """Notify React about a page change initiated from Python sidebar."""
        self.page_changed.emit(page)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_dashboard_data(self) -> str:
        """Return dashboard stats as JSON."""
        try:
            coord = getattr(self._host, "progress_coordinator", None)
            if coord and hasattr(coord, "build_dashboard_stats"):
                data = coord.build_dashboard_stats(self._host.db_cfg)
                return json.dumps(data)
            return json.dumps({
                "activeBatches": 0,
                "failedItems": 0,
                "songs": 0,
                "images": 0,
                "mp4": 0,
                "merged": 0,
                "youtube": 0,
                "credits": 0,
            })
        except Exception as exc:
            self._log(f"[WebBridge] get_dashboard_data error: {exc}")
            return json.dumps({})

    @pyqtSlot()
    def refresh_dashboard(self) -> None:
        """Trigger dashboard refresh."""
        try:
            self._host._dashboard_controller.refresh_dashboard_async(force=True)
        except Exception as exc:
            self._log(f"[WebBridge] refresh_dashboard error: {exc}")

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    @pyqtSlot(str, result=str)
    def generate_music(self, params_json: str) -> str:
        """Generate music with the given parameters."""
        try:
            params = json.loads(params_json)
            self._log(f"[WebBridge] generate_music: {params}")
            # Delegate to existing music generation flow
            self._host._submit_music_song_to_suno()
            return json.dumps({"status": "started"})
        except Exception as exc:
            self._log(f"[WebBridge] generate_music error: {exc}")
            return json.dumps({"error": str(exc)})

    @pyqtSlot()
    def cancel_generation(self) -> None:
        """Cancel ongoing music generation."""
        try:
            if hasattr(self._host, "_music_cancel_requested"):
                self._host._music_cancel_requested = True
        except Exception as exc:
            self._log(f"[WebBridge] cancel_generation error: {exc}")

    @pyqtSlot(result=str)
    def get_music_data(self) -> str:
        """Return music data (songs, profiles, etc.)."""
        try:
            data = self._host.music_data
            return json.dumps(data or {})
        except Exception as exc:
            self._log(f"[WebBridge] get_music_data error: {exc}")
            return json.dumps({})

    @pyqtSlot(result=str)
    def get_music_history(self) -> str:
        """Return music generation history."""
        try:
            rows = getattr(self._host, "music_history_rows", [])
            return json.dumps(rows or [])
        except Exception as exc:
            self._log(f"[WebBridge] get_music_history error: {exc}")
            return json.dumps([])

    @pyqtSlot(result=str)
    def get_music_profiles(self) -> str:
        """Return music profiles."""
        try:
            profiles = self._host._music_profiles()
            return json.dumps(profiles or [])
        except Exception as exc:
            self._log(f"[WebBridge] get_music_profiles error: {exc}")
            return json.dumps([])

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_video_templates(self) -> str:
        """Return video templates."""
        try:
            from ..database.persistence import db_list_video_templates
            templates = db_list_video_templates(self._host.db_cfg)
            return json.dumps(templates or [])
        except Exception as exc:
            self._log(f"[WebBridge] get_video_templates error: {exc}")
            return json.dumps([])

    @pyqtSlot(str, result=str)
    def set_video_template(self, template_json: str) -> str:
        """Apply a video template."""
        try:
            template = json.loads(template_json)
            self._host.template = template
            preview = getattr(self._host, "preview", None)
            if preview and hasattr(preview, "set_template"):
                preview.set_template(template)
            return json.dumps({"status": "ok"})
        except Exception as exc:
            self._log(f"[WebBridge] set_video_template error: {exc}")
            return json.dumps({"error": str(exc)})

    @pyqtSlot(result=str)
    def get_template(self) -> str:
        """Return current template."""
        try:
            return json.dumps(self._host.template or {})
        except Exception as exc:
            return json.dumps({})

    @pyqtSlot(str, str)
    def update_template_setting(self, key: str, value: str) -> None:
        """Update a single template setting."""
        try:
            if self._host.template is None:
                self._host.template = {}
            self._host.template[key] = value
            preview = getattr(self._host, "preview", None)
            if preview and hasattr(preview, "set_template"):
                preview.set_template(self._host.template)
        except Exception as exc:
            self._log(f"[WebBridge] update_template_setting error: {exc}")

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_workflow_runs(self) -> str:
        """Return workflow runs."""
        try:
            # Placeholder - will be wired to actual workflow data
            return json.dumps([])
        except Exception as exc:
            self._log(f"[WebBridge] get_workflow_runs error: {exc}")
            return json.dumps([])

    @pyqtSlot()
    def generate_workflow(self) -> None:
        """Start workflow generation."""
        try:
            if hasattr(self._host, "workflow_generate_button"):
                self._host.workflow_generate_button.click()
        except Exception as exc:
            self._log(f"[WebBridge] generate_workflow error: {exc}")

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_image_jobs(self) -> str:
        """Return image generation jobs."""
        try:
            from ..database.image_db import get_ready_background_output
            # Placeholder - will be wired to actual image data
            return json.dumps([])
        except Exception as exc:
            self._log(f"[WebBridge] get_image_jobs error: {exc}")
            return json.dumps([])

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_progress_data(self) -> str:
        """Return progress data."""
        try:
            coord = getattr(self._host, "progress_coordinator", None)
            if coord and hasattr(coord, "get_all_rows"):
                rows = coord.get_all_rows(self._host.db_cfg)
                return json.dumps(rows or [])
            return json.dumps([])
        except Exception as exc:
            self._log(f"[WebBridge] get_progress_data error: {exc}")
            return json.dumps([])

    @pyqtSlot(str)
    def cancel_progress_row(self, batch_id: str) -> None:
        """Cancel a progress row."""
        try:
            self._host._progress_cancel_row(batch_id)
        except Exception as exc:
            self._log(f"[WebBridge] cancel_progress_row error: {exc}")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_settings(self) -> str:
        """Return app settings."""
        try:
            settings = self._host.e_settings or {}
            return json.dumps(settings)
        except Exception as exc:
            self._log(f"[WebBridge] get_settings error: {exc}")
            return json.dumps({})

    @pyqtSlot(str)
    def save_settings(self, settings_json: str) -> None:
        """Save app settings."""
        try:
            settings = json.loads(settings_json)
            self._host.e_settings.update(settings)
            self._host._persist_setting_patch(settings)
        except Exception as exc:
            self._log(f"[WebBridge] save_settings error: {exc}")

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    @pyqtSlot(result=str)
    def get_log(self) -> str:
        """Return application log."""
        try:
            log_widget = getattr(self._host, "log_text_widget", None)
            if log_widget and hasattr(log_widget, "toPlainText"):
                return log_widget.toPlainText()
            return ""
        except Exception as exc:
            self._log(f"[WebBridge] get_log error: {exc}")
            return ""

    @pyqtSlot()
    def clear_log(self) -> None:
        """Clear application log."""
        try:
            log_widget = getattr(self._host, "log_text_widget", None)
            if log_widget and hasattr(log_widget, "clear"):
                log_widget.clear()
        except Exception as exc:
            self._log(f"[WebBridge] clear_log error: {exc}")

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    @pyqtSlot(str, str, result=str)
    def login(self, email: str, password: str) -> str:
        """Authenticate user."""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            auth_client = app.property("auth_client") if app else None
            token_store = app.property("token_store") if app else None
            license_gate = app.property("license_gate") if app else None

            if not auth_client or not token_store:
                return json.dumps({"error": "Auth services not available"})

            tokens = auth_client.login(email, password)
            token_store.save(tokens.access_token, tokens.refresh_token)

            if license_gate:
                license_gate.validate(tokens.access_token)

            return json.dumps({"status": "ok", "token": tokens.access_token})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @pyqtSlot(str, str, str, result=str)
    def register(self, email: str, password: str, display_name: str) -> str:
        """Register new user."""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            auth_client = app.property("auth_client") if app else None

            if not auth_client:
                return json.dumps({"error": "Auth services not available"})

            auth_client.register(email, password, display_name)
            return json.dumps({"status": "ok"})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    @pyqtSlot()
    def start_export(self) -> None:
        """Start video export."""
        try:
            if hasattr(self._host, "btn_export"):
                self._host.btn_export.click()
        except Exception as exc:
            self._log(f"[WebBridge] start_export error: {exc}")

    @pyqtSlot()
    def stop_export(self) -> None:
        """Stop video export."""
        try:
            self._host.export_coordinator.stop_export()
        except Exception as exc:
            self._log(f"[WebBridge] stop_export error: {exc}")

    # ------------------------------------------------------------------
    # Audio playback
    # ------------------------------------------------------------------

    @pyqtSlot()
    def play_audio(self) -> None:
        """Start audio playback."""
        try:
            self._host._audio_controller.play()
        except Exception as exc:
            self._log(f"[WebBridge] play_audio error: {exc}")

    @pyqtSlot()
    def stop_audio(self) -> None:
        """Stop audio playback."""
        try:
            self._host._audio_controller.stop()
        except Exception as exc:
            self._log(f"[WebBridge] stop_audio error: {exc}")

    @pyqtSlot(int)
    def seek_audio(self, position: int) -> None:
        """Seek audio to position (0-1000)."""
        try:
            self._host._audio_controller.seek(position / 1000.0)
        except Exception as exc:
            self._log(f"[WebBridge] seek_audio error: {exc}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def log_from_react(self, message: str) -> None:
        """Log a message from React."""
        self._log(f"[React] {message}")

    @pyqtSlot(str, str)
    def emit_notification(self, title: str, message: str) -> None:
        """Emit a notification to React."""
        self.notification.emit(title, message)
