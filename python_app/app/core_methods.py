"""Relocated CoreMethodsMixin methods (task 11.3 shell reduction).

These methods were moved verbatim from ``MainWindow`` into this mixin so the
``MainWindow`` class body stays a thin shell (Requirement 9.1). ``MainWindow``
inherits this mixin, so ``self.<method>()`` resolves unchanged via the MRO.
"""
from __future__ import annotations

from ..database.persistence import (
    DbCfg,
    db_get_profile_image_config,
    db_list_video_templates,
    db_upsert_video_template,
    read_local_templates,
    write_local_templates,
)
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox,
    QFileDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton,
    QSlider, QToolButton, QWidget,
)
from PyQt6.QtCore import Qt, QDate, QEvent, QObject, QPoint, QSize, QTimer
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
from ..design_system.tokens import TokenRegistry
from ..database.image_db import (
    cancel_all_pending_image_jobs,
    get_ready_background_output,
    upsert_image_job,
)
from ..features.youtube.db import (
    db_cancel_all_pending_youtube_jobs,
)
from .resources import icon_path, lucide_icon_path
from .logging import log_line
import os
import re
import time


class CoreMethodsMixin:
    @staticmethod
    def _logo_size_slider_to_real_size(slider_value: int) -> int:
        return int(max(1, min(10, int(slider_value)))) * 100

    @staticmethod
    def _logo_real_size_to_slider_value(real_size: float) -> int:
        return int(max(1, min(10, round(float(real_size) / 100.0))))

    def _build_ui_tokens(self) -> dict[str, str]:
        return TokenRegistry().as_dict()

    def _build_app_stylesheet(self) -> str:
        # Legacy stylesheet building is no longer needed — the global QSS is
        # applied via design_system.bootstrap.apply_theme() at startup.
        return ""

    def _refresh_widget_style(self, widget: QWidget) -> None:
        _sh_refresh_widget_style(widget)

    def _set_widget_property(self, widget: QWidget, name: str, value: str) -> None:
        _sh_set_widget_property(widget, name, value)

    def _set_label_role(self, label: QLabel, role: str) -> None:
        _sh_set_label_role(label, role)

    def _set_button_role(self, button: QPushButton, role: str) -> None:
        _sh_set_button_role(button, role)

    def _set_field_role(self, widget: QWidget, role: str) -> None:
        _sh_set_field_role(widget, role)

    def _apply_card_field(self, widget: QWidget) -> None:
        _sh_apply_card_field(widget)

    def _current_selected_mp3_path(self) -> str:
        return self.workspace_coordinator.current_selected_mp3_path()

    def _iter_mp3_paths(self) -> list[str]:
        return self.workspace_coordinator.iter_mp3_paths()

    def _sync_toggle_button(self, toggle: QPushButton, checked: bool) -> None:
        toggle.setText("ON" if checked else "OFF")

    @staticmethod
    def _normalize_music_match_key(value: str) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _parse_music_date_ymd(value: str) -> QDate | None:
        text = str(value or "").strip()
        if not text:
            return None
        parsed = QDate.fromString(text, "yyyy-MM-dd")
        return parsed if parsed.isValid() else None

    def _refresh_footer(self) -> None:
        template_name = str(self.template.get("templateName", "New Template") or "New Template").strip()
        current_mp3 = self._current_selected_mp3_path()
        output_dir = str(getattr(self, "_output_dir", "") or "").strip()
        self._refresh_footer_status()
        if hasattr(self, "footer_center_label"):
            center_text = f"Template: {template_name}"
            if current_mp3:
                center_text += f" | Track: {Path(current_mp3).name}"
            self.footer_center_label.setText(center_text)
        if hasattr(self, "footer_right_label"):
            if output_dir:
                self.footer_right_label.setText(f"Output: {output_dir}")
            else:
                self.footer_right_label.setText("Output: Not selected")

    def _refresh_footer_status(self) -> None:
        self._footer.refresh()

    def _log(self, msg: str) -> None:
        log_line(msg)
        # Also append to in-app log viewer (thread-safe via signal)
        try:
            if hasattr(self, "bus") and hasattr(self, "log_text_widget"):
                self.bus.ui_invoke.emit(lambda m=msg: self._append_log_line(m))
        except Exception:
            pass

    def _project_icon_path(self, icon_name: str) -> str:
        return icon_path(icon_name)

    def _resolve_display_user_name(self) -> str:
        return str(
            os.environ.get("MG_USER_NAME")
            or os.environ.get("USERNAME")
            or os.environ.get("USER")
            or "Boss"
        ).strip()

    def _lucide_icon_path(self, icon_name: str) -> str:
        return lucide_icon_path(icon_name)

    def _render_svg_icon(self, path: str, size: int, color: str):
        cache = getattr(self, "_svg_icon_cache", None)
        if cache is None:
            cache = {}
            self._svg_icon_cache = cache
        return _sh_render_svg_icon(path, size, color, cache=cache)

    def _set_lucide_icon(self, button: QToolButton, icon_name: str, size: int = 22, color: str | None = None) -> None:
        cache = getattr(self, "_svg_icon_cache", None)
        if cache is None:
            cache = {}
            self._svg_icon_cache = cache
        button.setIcon(_sh_render_svg_icon(self._lucide_icon_path(icon_name), size, color or self.ui["text_soft"], cache=cache))
        button.setIconSize(QSize(int(size), int(size)))

    def _time_now(self) -> str:
        return time.strftime('%H:%M:%S')

    def _init_database_impl(self) -> None:
        return self.persistence_coordinator.initialize_database()

    def _load_persisted_data_impl(self) -> None:
        return self.persistence_coordinator.load_persisted_data()

    def _reload_music_db_collections(self) -> None:
        return self.persistence_coordinator.reload_music_db_collections()

    def _apply_settings_patch_to_database(self, patch: dict) -> dict:
        return self.persistence_coordinator.apply_settings_patch(patch)

    def _set_db_cfg(self, cfg: DbCfg | None) -> None:
        """Update db_cfg and propagate to all coordinators after reconnection."""
        self.db_cfg = cfg
        if hasattr(self, '_music_coordinator'):
            self._music_coordinator.update_db_cfg(cfg)
        if hasattr(self, '_image_coordinator'):
            self._image_coordinator.update_db_cfg(cfg)
        if hasattr(self, 'youtube_coordinator'):
            self.youtube_coordinator.update_db_cfg(cfg)
        if hasattr(self, 'export_coordinator') and hasattr(self.export_coordinator, 'update_db_cfg'):
            self.export_coordinator.update_db_cfg(cfg)

    def _cancel_unfinished_background_jobs(self, *, reason: str, cancel_image_jobs: bool = True, cancel_youtube_jobs: bool = True, stop_youtube_runtime: bool = True) -> dict:
        summary = {"image": 0, "youtube": 0, "youtube_runtime": 0, "errors": []}
        if stop_youtube_runtime:
            cancelled, errors = self.youtube_coordinator.cancel_runtime_jobs(stop_timer=True, clear_running=True)
            summary["youtube_runtime"] = int(cancelled or 0)
            if errors:
                summary["errors"].extend(errors)
        if not self.db_cfg:
            return summary
        if cancel_image_jobs:
            try:
                summary["image"] = int(cancel_all_pending_image_jobs(self.db_cfg, reason=reason) or 0)
            except Exception as exc:
                summary["errors"].append(f"image db cancel: {exc}")
        if cancel_youtube_jobs:
            try:
                summary["youtube"] = int(db_cancel_all_pending_youtube_jobs(self.db_cfg, reason=reason) or 0)
            except Exception as exc:
                summary["errors"].append(f"youtube db cancel: {exc}")
        return summary

    def _set_image_status(self, text: str) -> None:
        message = str(text or "").strip() or "Ready"
        self._image_status_message = message
        if hasattr(self, "image_status_label"):
            self.image_status_label.setText(message)
        self._set_global_status(message, source="Image")

    def _set_global_status(self, text: str, *, source: str = "") -> None:
        msg = str(text or "").strip()
        if not msg:
            return
        src = str(source or "").strip()
        if src:
            low_msg = msg.lower()
            low_src = src.lower()
            if not low_msg.startswith(low_src):
                if not re.match(r"^[a-zA-Z0-9_ -]+:", msg):
                    msg = f"{src}: {msg}"
        self._footer.set_status(msg, source=source)

    def _sync_auto_video_timer(self) -> None:
        """Sync auto-video timer via TimerRegistry."""
        if not hasattr(self, '_timer_registry'):
            return
        settings = self._music_settings()
        enabled = bool(settings.get("autoVideoAfterSuno", False)) and bool(self.db_cfg)
        self._timer_registry.sync("auto_video", enabled=enabled)

    def _handle_image_poll_started(self, event: dict) -> None:
        self._image_coordinator.start_live_refresh()
        if self._current_primary_page == "image":
            self._refresh_image_jobs_table()

    def _handle_progress(self, event: dict) -> None:
        message = str(event.get("message", "")).strip()
        if message:
            self._set_music_status(message)

    def _handle_status(self, event: dict) -> None:
        message = str(event.get("message", "")).strip()
        if message:
            self._set_music_status(message)

    def _handle_done(self, event: dict) -> None:
        self._music_coordinator.handle_done_event(event)

    def _mask_client_id(self, text: str) -> str:
        s = str(text or "").strip()
        if not s:
            return ""
        if len(s) <= 14:
            return s
        return f"{s[:6]}…{s[-6:]}"

    def _browse_music_profile_logo(self) -> None:
        if not hasattr(self, "music_settings_profile_logo"):
            return
        self._music_browse_file_into(self.music_settings_profile_logo, "Select logo image", "Images (*.png *.jpg *.jpeg)")

    def _show_logout_placeholder(self) -> None:
        """Perform logout: revoke tokens server-side, clear local store, navigate to Login View."""
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        app = QApplication.instance()
        if app is None:
            return

        token_store = app.property("token_store")
        auth_client = app.property("auth_client")
        login_view = app.property("login_view")

        # Best-effort server-side logout (ignore errors)
        if token_store is not None and auth_client is not None:
            tokens = token_store.load()
            if tokens is not None:
                try:
                    auth_client.logout(tokens.access_token, tokens.refresh_token)
                except Exception:
                    pass

        # Clear the local token store
        if token_store is not None:
            token_store.clear()

        # Navigate back to the Login screen (two-window approach: hide main, show login)
        auth_stack = getattr(self, "_auth_stack", None)
        if auth_stack is not None:
            # Legacy stacked-widget flow (kept for compat if still wired)
            auth_stack.setCurrentIndex(0)
            shell = app.property("shell")
            if shell is not None:
                shell.setWindowTitle("Music Generator — Sign In")
            title_bar = app.property("title_bar")
            if title_bar is not None:
                title_bar.set_title("Music Generator — Sign In")
            login_view = app.property("login_view")
            if login_view is not None:
                login_view.setFocus()
        else:
            # Two-window flow: hide main window, show login at same position
            login_view = app.property("login_view")
            if login_view is not None:
                login_view.move(self.pos())
                login_view.resize(self.size())
                self.hide()
                login_view.show()
                login_view.setFocus()

    def _persist_setting_patch(self, patch: dict) -> None:
        if not patch:
            return
        try:
            self._apply_settings_patch_to_database(patch)
        except Exception as exc:
            self._log(f"[{time.strftime('%H:%M:%S')}] Settings persistence failed: {exc}")

    def _on_perf_music_workers_changed(self, value: int) -> None:
        workers = max(1, min(5, int(value or 1)))
        self._persist_setting_patch({"perfMusicWorkers": workers})

    def _on_perf_image_workers_changed(self, value: int) -> None:
        workers = max(1, min(8, int(value or 1)))
        self._persist_setting_patch({"perfImageWorkers": workers})

    def _on_perf_export_workers_changed(self, value: int) -> None:
        self._on_export_workers_changed(int(value or 1))

    def _on_perf_merge_workers_changed(self, value: int) -> None:
        workers = max(1, min(2, int(value or 1)))
        self._persist_setting_patch({"perfMergeWorkers": workers})

    def _apply_phase1_ux_tuning(self) -> None:
        for btn in self.findChildren(QPushButton):
            if btn in {
                getattr(self, "btn_back10", None),
                getattr(self, "btn_play", None),
                getattr(self, "btn_stop", None),
                getattr(self, "btn_fwd10", None),
            }:
                continue
            btn.setMinimumHeight(max(30, btn.minimumHeight()))
        for field in self.findChildren(QLineEdit):
            field.setMinimumHeight(max(30, field.minimumHeight()))
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(max(30, combo.minimumHeight()))
        for list_widget in self.findChildren(QListWidget):
            list_widget.setMinimumHeight(max(140, list_widget.minimumHeight()))
        for slider in self.findChildren(QSlider):
            slider.setFixedHeight(18)
        for cb in self.findChildren(QCheckBox):
            cb.setMinimumHeight(max(18, cb.minimumHeight()))
