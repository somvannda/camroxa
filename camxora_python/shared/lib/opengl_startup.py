"""Prime OpenGL before the main window is shown.

Video workspace prewarm mounts a ``QOpenGLWidget``. On Windows, the first
OpenGL widget parented into a live top-level HWND often recreates that window,
which looks like Camxora closed and reopened during the splash screen.

Call ``configure_opengl_before_qapplication()`` before ``QApplication(...)``,
then ``prime_opengl_on_window()`` on ``RootWindow`` before the first ``show()``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QWidget

OPENGL_PRIME_OBJECT_NAME = "opengl_startup_prime"


def configure_opengl_before_qapplication() -> None:
    """Enable shared contexts + a stable default surface format.

    Must run before ``QApplication`` is constructed. ``AA_ShareOpenGLContexts``
    is Qt's recommended setting for apps that use ``QOpenGLWidget``.
    """
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setVersion(3, 3)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)


def prime_opengl_on_window(window: QWidget) -> bool:
    """Attach a tiny hidden ``QOpenGLWidget`` before the first ``show()``.

    Returns True when a prime widget is present (created or already attached).
    Failures are best-effort: machines without a usable GL stack still start,
    and the Video page has its own GPU-preview fallback.
    """
    try:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
    except Exception:
        return False

    existing = window.findChild(QOpenGLWidget, OPENGL_PRIME_OBJECT_NAME)
    if existing is not None:
        return True

    try:

        class _StartupOpenGLPrime(QOpenGLWidget):
            def initializeGL(self) -> None:  # noqa: N802 - Qt API
                return

            def paintGL(self) -> None:  # noqa: N802 - Qt API
                return

            def resizeGL(self, _w: int, _h: int) -> None:  # noqa: N802 - Qt API
                return

        prime = _StartupOpenGLPrime(window)
        prime.setObjectName(OPENGL_PRIME_OBJECT_NAME)
        prime.setFixedSize(1, 1)
        prime.move(0, 0)
        prime.hide()
        return True
    except Exception as exc:
        try:
            from shared.services.app_logger import log_error

            log_error("OpenGL startup prime failed", category="startup", exc=exc)
        except Exception:
            pass
        return False
