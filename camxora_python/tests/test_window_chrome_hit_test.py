"""Tests for hit-test-safe rounded window chrome."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from shared.lib.window_chrome import (
    WINDOW_CORNER_RADIUS,
    configure_rounded_window,
    sync_rounded_window_shape,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _shell_window() -> QMainWindow:
    window = QMainWindow()
    surface = QWidget(window)
    surface.setObjectName("window_surface")
    window.setCentralWidget(surface)
    window.resize(800, 600)
    return window


def test_configure_rounded_window_keeps_opaque_unmasked_shell(qapp: QApplication) -> None:
    window = _shell_window()
    configure_rounded_window(window)

    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is False
    assert window.mask().isEmpty()
    surface = window.centralWidget()
    assert surface is not None
    assert surface.property("roundedCorners") is True
    assert int(surface.property("cornerRadius") or 0) == WINDOW_CORNER_RADIUS
    window.close()


def test_sync_clears_mask_in_windowed_and_maximized(qapp: QApplication) -> None:
    window = _shell_window()
    configure_rounded_window(window)
    assert window.mask().isEmpty()

    window.showMaximized()
    qapp.processEvents()
    sync_rounded_window_shape(window)
    assert window.mask().isEmpty()
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is False
    surface = window.centralWidget()
    assert surface is not None
    assert surface.property("roundedCorners") is False

    window.showNormal()
    qapp.processEvents()
    sync_rounded_window_shape(window)
    assert window.mask().isEmpty()
    assert surface.property("roundedCorners") is True
    window.close()
