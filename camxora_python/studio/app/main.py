"""Camxora Studio entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from studio.app.logging_config import install_qt_message_handler, log_file_path, setup_logging
from studio.app.theme import build_qss
from studio.core.project_state import ProjectState
from studio.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def run() -> int:
    setup_logging()
    install_qt_message_handler()
    log_path = log_file_path()
    logger.info("Starting Camxora Studio")
    logger.info("Log file: %s", log_path)
    print(f"[camxora] logging → {log_path}", flush=True)

    app = QApplication(sys.argv)
    app.setApplicationName("Camxora Studio")
    app.setOrganizationName("Camxora")
    app.setStyleSheet(build_qss())

    project_state = ProjectState()
    window = MainWindow(project_state)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
