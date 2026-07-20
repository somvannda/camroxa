"""Tests for launch-time window centering."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from shared.lib.window_chrome import center_window_on_screen


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_center_window_on_screen_uses_available_geometry(qapp: QApplication) -> None:
    screen = qapp.primaryScreen()
    assert screen is not None
    geo = screen.availableGeometry()

    window = QWidget()
    window.resize(800, 600)
    center_window_on_screen(window)

    expected = QRect(
        geo.x() + max(0, (geo.width() - 800) // 2),
        geo.y() + max(0, (geo.height() - 600) // 2),
        800,
        600,
    )
    assert window.geometry().topLeft() == expected.topLeft()
    window.close()
