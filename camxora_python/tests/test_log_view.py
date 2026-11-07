"""Tests for the support-only Diagnostics log console."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.logs.views.log_view import MAX_CONSOLE_LINES, LogView
from shared.services.app_logger import LogLevel, get_app_logger


@pytest.fixture(autouse=True)
def _clean_logger():
    logger = get_app_logger()
    logger.clear()
    logger.set_min_level(LogLevel.DEBUG)
    yield logger
    logger.clear()


def test_log_view_seeds_from_buffer_and_follows_new_lines(qapp: QApplication) -> None:
    logger = get_app_logger()
    logger.info("seed line", category="test")

    view = LogView()

    assert "seed line" in view._console.toPlainText()
    logger.warn("live warning", category="test")
    assert "live warning" in view._console.toPlainText()


def test_log_view_level_filter_hides_lower_levels(qapp: QApplication) -> None:
    logger = get_app_logger()
    logger.debug("debug noise", category="test")
    logger.error("hard failure", category="test")

    view = LogView()
    assert "debug noise" in view._console.toPlainText()

    # "Warnings and above"
    view._level_combo.setCurrentIndex(2)
    text = view._console.toPlainText()
    assert "debug noise" not in text
    assert "hard failure" in text

    logger.debug("more noise", category="test")
    assert "more noise" not in view._console.toPlainText()


def test_log_view_pause_buffers_then_flushes(qapp: QApplication) -> None:
    logger = get_app_logger()
    view = LogView()

    view._pause_btn.setChecked(True)
    logger.info("while paused", category="test")
    assert "while paused" not in view._console.toPlainText()

    view._pause_btn.setChecked(False)
    assert "while paused" in view._console.toPlainText()


def test_log_view_clear_empties_console(qapp: QApplication) -> None:
    logger = get_app_logger()
    logger.info("to be cleared", category="test")
    view = LogView()
    assert view._console.toPlainText()

    logger.clear()

    assert view._console.toPlainText() == ""
    assert view._shown_count == 0


def test_log_view_caps_console_lines(qapp: QApplication) -> None:
    logger = get_app_logger()
    view = LogView()
    for index in range(MAX_CONSOLE_LINES + 50):
        logger.info(f"line {index}", category="test")

    assert view._console.blockCount() <= MAX_CONSOLE_LINES
    assert "line 2049" in view._console.toPlainText()
