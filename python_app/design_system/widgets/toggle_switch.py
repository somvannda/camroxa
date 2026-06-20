"""Toggle switch widget with animated knob and custom painting.

Provides a modern on/off toggle control that replaces native checkboxes
with a visually polished sliding switch.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    pyqtProperty,
    QRectF,
)
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel


class ToggleSwitch(QWidget):
    """A toggle switch widget with animated knob transition.

    Renders a rounded track with a circular knob that slides between
    off (left) and on (right) positions. Emits ``toggled(bool)`` on
    state change.

    Parameters
    ----------
    label : str
        Optional text label displayed beside the switch.
    label_position : str
        Position of the label relative to the switch: "left" or "right".
    parent : QWidget | None
        Parent widget.
    """

    toggled = pyqtSignal(bool)

    # Track dimensions
    _TRACK_WIDTH = 40
    _TRACK_HEIGHT = 20
    _KNOB_MARGIN = 2
    _KNOB_DIAMETER = _TRACK_HEIGHT - 2 * _KNOB_MARGIN

    # Colors
    _OFF_TRACK_COLOR = QColor("#31435d")  # border_strong
    _ON_TRACK_COLOR = QColor("#00d4ff")  # accent
    _OFF_KNOB_COLOR = QColor("#8ea4c7")  # text_muted
    _ON_KNOB_COLOR = QColor("#ffffff")  # white

    def __init__(
        self,
        label: str = "",
        label_position: str = "right",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._checked = False
        self._knob_position_value: float = float(self._KNOB_MARGIN)

        # Animation for knob slide
        self._animation = QPropertyAnimation(self, b"knob_position")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Focus policy for keyboard navigation
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        # Build layout with optional label
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._switch_area = _SwitchCanvas(self)
        self._label_widget: QLabel | None = None

        if label:
            self._label_widget = QLabel(label)
            self._label_widget.setStyleSheet("color: #eef4ff;")
            if label_position == "left":
                layout.addWidget(self._label_widget)
                layout.addWidget(self._switch_area)
            else:
                layout.addWidget(self._switch_area)
                layout.addWidget(self._label_widget)
        else:
            layout.addWidget(self._switch_area)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def isChecked(self) -> bool:
        """Return whether the switch is in the on state."""
        return self._checked

    def setChecked(self, checked: bool) -> None:
        """Set the switch state programmatically with animation."""
        if checked == self._checked:
            return
        self._checked = checked
        self._animate_knob()
        self.toggled.emit(self._checked)

    # ------------------------------------------------------------------
    # Qt property for animation
    # ------------------------------------------------------------------

    def _get_knob_position(self) -> float:
        return self._knob_position_value

    def _set_knob_position(self, pos: float) -> None:
        self._knob_position_value = pos
        self._switch_area.update()

    knob_position = pyqtProperty(float, _get_knob_position, _set_knob_position)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Toggle state on mouse click."""
        self._toggle()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802
        """Toggle state on Space key press."""
        if event and event.key() == Qt.Key.Key_Space:
            self._toggle()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _toggle(self) -> None:
        """Toggle the checked state with animation."""
        self._checked = not self._checked
        self._animate_knob()
        self.toggled.emit(self._checked)

    def _animate_knob(self) -> None:
        """Start the knob slide animation to the target position."""
        self._animation.stop()
        self._animation.setStartValue(self._knob_position_value)
        end = (
            self._TRACK_WIDTH - self._KNOB_DIAMETER - self._KNOB_MARGIN
            if self._checked
            else float(self._KNOB_MARGIN)
        )
        self._animation.setEndValue(end)
        self._animation.start()


class _SwitchCanvas(QWidget):
    """Internal widget that handles the custom painting of the toggle track and knob."""

    def __init__(self, toggle: ToggleSwitch) -> None:
        super().__init__(toggle)
        self._toggle = toggle
        self.setFixedSize(ToggleSwitch._TRACK_WIDTH, ToggleSwitch._TRACK_HEIGHT)

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the rounded track and circular knob."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        toggle = self._toggle
        checked = toggle._checked
        knob_x = toggle._knob_position_value

        # -- Draw track (pill shape) --
        track_color = (
            ToggleSwitch._ON_TRACK_COLOR if checked else ToggleSwitch._OFF_TRACK_COLOR
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        track_rect = QRectF(0, 0, ToggleSwitch._TRACK_WIDTH, ToggleSwitch._TRACK_HEIGHT)
        painter.drawRoundedRect(
            track_rect,
            ToggleSwitch._TRACK_HEIGHT / 2,
            ToggleSwitch._TRACK_HEIGHT / 2,
        )

        # -- Draw knob (circle) --
        knob_color = (
            ToggleSwitch._ON_KNOB_COLOR if checked else ToggleSwitch._OFF_KNOB_COLOR
        )
        painter.setBrush(knob_color)
        knob_y = float(ToggleSwitch._KNOB_MARGIN)
        painter.drawEllipse(
            QRectF(knob_x, knob_y, ToggleSwitch._KNOB_DIAMETER, ToggleSwitch._KNOB_DIAMETER)
        )

        painter.end()
