"""Application bootstrap — entry point for the PySide6 desktop client."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.root_window import RootWindow
from shared.lib.app_icon import load_app_icon
from shared.lib.single_instance import SingleInstanceGuard, notify_already_running
from shared.themes import apply_theme


def _set_windows_app_id() -> None:
    """Give Windows a stable AppUserModelID so the taskbar uses our icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Camxora.DesktopStudio")
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
    app.setWindowIcon(load_app_icon())
    apply_theme(app)

    guard = SingleInstanceGuard(app)
    if not guard.try_become_primary():
        notify_already_running()
        return 0

    def _shutdown_child_processes() -> None:
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

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
