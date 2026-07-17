"""Stop the mouse wheel from editing controls while scrolling a panel.

Controls (sliders, combo boxes, spin boxes) normally react to any wheel event
under the cursor, so scrolling a settings panel accidentally changes values.
The guard makes a control respond to the wheel only when it has keyboard focus
(i.e. the user clicked it first); otherwise the event is forwarded to the
parent so the surrounding scroll area keeps scrolling.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QSlider, QWidget

_GUARDED_TYPES = (QSlider, QComboBox, QAbstractSpinBox)


class _WheelGuard(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel and isinstance(obj, QWidget) and not obj.hasFocus():
            parent = obj.parentWidget()
            if parent is not None:
                QApplication.sendEvent(parent, event)
            return True
        return False


_shared_guard: _WheelGuard | None = None


def _guard_instance() -> _WheelGuard:
    global _shared_guard
    if _shared_guard is None:
        _shared_guard = _WheelGuard()
    return _shared_guard


def guard_wheel(widget: QWidget) -> None:
    """Require focus before the widget reacts to wheel events."""
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.installEventFilter(_guard_instance())


def guard_page_wheel_controls(page: QWidget) -> int:
    """Apply the wheel guard to every slider/combo/spin box under ``page``."""
    count = 0
    for widget in page.findChildren(QWidget):
        if isinstance(widget, _GUARDED_TYPES):
            guard_wheel(widget)
            count += 1
    return count
