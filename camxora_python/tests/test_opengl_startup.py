"""Regression tests for OpenGL HWND priming during desktop startup."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QWidget

from app.root_window import RootWindow
from shared.lib.opengl_startup import (
    OPENGL_PRIME_OBJECT_NAME,
    configure_opengl_before_qapplication,
    prime_opengl_on_window,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_configure_opengl_sets_default_surface_format(qapp: QApplication) -> None:
    configure_opengl_before_qapplication()
    fmt = QSurfaceFormat.defaultFormat()
    assert fmt.renderableType() == QSurfaceFormat.RenderableType.OpenGL
    assert fmt.majorVersion() == 3
    assert fmt.minorVersion() == 3
    assert fmt.profile() == QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile


def test_prime_opengl_on_window_attaches_hidden_widget(qapp: QApplication) -> None:
    host = QWidget()
    assert prime_opengl_on_window(host) is True
    prime = host.findChild(QOpenGLWidget, OPENGL_PRIME_OBJECT_NAME)
    assert prime is not None
    assert prime.isHidden()
    assert prime.width() == 1
    assert prime.height() == 1
    # Idempotent — second call keeps a single prime widget.
    assert prime_opengl_on_window(host) is True
    assert host.findChildren(QOpenGLWidget, OPENGL_PRIME_OBJECT_NAME) == [prime]


def test_root_window_primes_opengl_before_show(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shared.services.secure_storage import SecureStorage
    from shared.services.session_service import SessionService

    class _MemoryStorage(SecureStorage):
        def __init__(self) -> None:
            self._data: dict[str, str] = {}
            self._api_base_url = "http://localhost:8000/api/v3"

        def get(self, key: str) -> str | None:
            return self._data.get(key)

        def set(self, key: str, value: str) -> None:
            self._data[key] = value

        def remove(self, key: str) -> None:
            self._data.pop(key, None)

        def get_api_base_url(self) -> str:
            return self._api_base_url

        def set_api_base_url(self, url: str) -> None:
            self._api_base_url = url

    monkeypatch.setattr(RootWindow, "_start_bootstrap", lambda self: None)
    session = SessionService(storage=_MemoryStorage())
    session.hydrate()
    window = RootWindow(session=session)

    prime = window.findChild(QOpenGLWidget, OPENGL_PRIME_OBJECT_NAME)
    assert prime is not None
    assert prime.isHidden()
    assert not window.isVisible()
