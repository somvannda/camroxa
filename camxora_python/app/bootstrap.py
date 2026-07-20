"""Application bootstrap — entry point for the PySide6 desktop client."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.root_window import RootWindow
from shared.lib.app_icon import APP_USER_MODEL_ID, apply_app_window_icon
from shared.lib.single_instance import SingleInstanceGuard, notify_already_running
from shared.themes import apply_theme


def _set_windows_app_id() -> None:
    """Give Windows a stable AppUserModelID so the taskbar uses our icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def run() -> int:
    from shared.lib.app_install import get_or_seed_install_datetime
    from shared.lib.env_loader import load_desktop_env

    load_desktop_env()
    get_or_seed_install_datetime()
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("Camxora")
    app.setOrganizationName("Camxora")
    apply_app_window_icon()
    apply_theme(app)

    guard = SingleInstanceGuard(app)
    if not guard.try_become_primary():
        notify_already_running()
        return 0

    def _shutdown_child_processes() -> None:
        try:
            from shared.services.video_pipeline_activity import set_app_quitting

            set_app_quitting(True)
        except Exception:
            pass
        try:
            from shared.services.app_thread_registry import shutdown_app_threads

            shutdown_app_threads(wait_ms=10_000)
        except Exception:
            pass
        try:
            from shared.services.video_pipeline_activity import shutdown_video_pipeline_threads

            # Belt-and-suspenders after RootWindow.closeEvent: export QThreads use
            # parent=None but still need an explicit cancel+join on app quit.
            shutdown_video_pipeline_threads(wait_ms=12_000)
        except Exception:
            pass
        try:
            from features.video.services.visualizer_daemon import shutdown_visualizer_daemon

            shutdown_visualizer_daemon()
        except Exception:
            pass
        try:
            from shared.lib.subprocess_utils import terminate_job

            terminate_job()
        except Exception:
            pass

    app.aboutToQuit.connect(_shutdown_child_processes)

    try:
        from shared.services.app_logger import log_info

        log_info("Camxora desktop starting", category="app")
    except Exception:
        pass

    window = RootWindow()
    guard.set_activate_handler(window.bring_to_front)
    window.show()
    # Window hwnd exists only after show; native taskbar branding needs a second pass.
    apply_app_window_icon(window)
    QTimer.singleShot(0, lambda: apply_app_window_icon(window))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
