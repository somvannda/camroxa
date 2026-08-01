"""Application bootstrap — entry point for the PySide6 desktop client."""

from __future__ import annotations

import os
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


def _install_global_excepthook() -> None:
    """Log otherwise-invisible crashes in windowed (console=False) builds.

    Without this, an unhandled exception raised inside a Qt slot (e.g. a
    QTimer callback during startup) is swallowed silently because
    sys.stdout/sys.stderr are None in the packaged build — the app just
    freezes on whatever screen was last drawn instead of crashing or
    logging anything.
    """
    import threading

    from shared.services.app_logger import log_error

    def _handle(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        try:
            log_error("Unhandled exception (main thread)", category="crash", exc=exc_value)
        except Exception:
            pass

    def _handle_thread(args) -> None:
        try:
            log_error(
                f"Unhandled exception (thread={args.thread.name if args.thread else '?'})",
                category="crash",
                exc=args.exc_value,
            )
        except Exception:
            pass

    sys.excepthook = _handle
    threading.excepthook = _handle_thread


def run() -> int:
    from shared.lib.app_install import get_or_seed_install_datetime
    from shared.lib.env_loader import load_desktop_env

    # Local dev convenience:
    #   python main.py sandbox
    #   python main.py production
    # Sets the same CAMXORA_* vars the bundled installers target, so
    # env loading doesn't fall back to .env.production.
    env_arg: str | None = None
    if len(sys.argv) > 1:
        candidate = str(sys.argv[1]).strip().lower()
        if candidate in {"sandbox", "production"}:
            env_arg = candidate
            sys.argv = [sys.argv[0], *sys.argv[2:]]

    if env_arg == "sandbox":
        os.environ["CAMXORA_BUILD_ENV"] = "sandbox"
        os.environ["CAMXORA_API_BASE_URL"] = "https://api.sandbox.camxora.com/api/v1"
        os.environ["CAMXORA_PORTAL_BASE_URL"] = "https://app.sandbox.camxora.com"
    elif env_arg == "production":
        os.environ["CAMXORA_BUILD_ENV"] = "production"
        os.environ["CAMXORA_API_BASE_URL"] = "https://api.camxora.com/api/v1"
        os.environ["CAMXORA_PORTAL_BASE_URL"] = "https://app.camxora.com"

    load_desktop_env()
    get_or_seed_install_datetime()
    _set_windows_app_id()
    _install_global_excepthook()

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
