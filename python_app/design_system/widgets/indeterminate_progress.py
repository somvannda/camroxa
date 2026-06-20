"""Indeterminate progress bar widget.

Animated horizontal bar indicating a loading state, using QPropertyAnimation
on an internal position property to sweep an accent-colored segment
left-to-right continuously.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget

from python_app.design_system.tokens import DEFAULT_DARK_THEME

# Token values
_ACCENT = DEFAULT_DARK_THEME.colors.accent  # #00d4ff
_SURFACE_SUNKEN = DEFAULT_DARK_THEME.colors.surface_sunken  # #070b1e

# Dimensions
_BAR_HEIGHT = 6
_SEGMENT_WIDTH_RATIO = 0.3  # Segment is 30% of bar width
_BORDER_RADIUS = _BAR_HEIGHT / 2  # Fully rounded endpoints

# Animation
_ANIMATION_DURATION_MS = 1400


class IndeterminateProgress(QWidget):
    """Animated horizontal bar indicating loading state.

    Uses QPropertyAnimation on an internal position property (0.0 to 1.0)
    to sweep an accent-colored segment left-to-right continuously.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._position: float = 0.0

        # Fixed height, expand horizontally
        self.setFixedHeight(_BAR_HEIGHT)
        self.setMinimumWidth(60)

        # Setup animation on the _position property
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(_ANIMATION_DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.setLoopCount(-1)  # Loop indefinitely

    # --- Qt property for animation ---

    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float) -> None:
        self._position = value
        self.update()

    position = pyqtProperty(float, fget=_get_position, fset=_set_position)

    # --- Public API ---

    def start(self) -> None:
        """Begin the animation loop."""
        self._animation.start()

    def stop(self) -> None:
        """Stop the animation and reset position."""
        self._animation.stop()
        self._position = 0.0
        self.update()

    @property
    def is_running(self) -> bool:
        """Return whether the animation is currently running."""
        return self._animation.state() == QPropertyAnimation.State.Running

    # --- Painting ---

    def paintEvent(self, event: object) -> None:
        """Render the track and animated accent segment."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = float(self.width())
        height = float(self.height())

        # Draw track (sunken background with rounded endpoints)
        track_rect = QRectF(0, 0, width, height)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, _BORDER_RADIUS, _BORDER_RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_SURFACE_SUNKEN))
        painter.drawPath(track_path)

        # Draw animated segment (accent color)
        segment_width = width * _SEGMENT_WIDTH_RATIO
        # Position maps 0.0..1.0 to the segment sweeping fully across the bar
        # At position=0.0, segment left edge is at -segment_width (hidden left)
        # At position=1.0, segment left edge is at width (hidden right)
        total_travel = width + segment_width
        segment_x = -segment_width + (self._position * total_travel)

        # Clip to bar bounds
        segment_rect = QRectF(segment_x, 0, segment_width, height)
        segment_path = QPainterPath()
        segment_path.addRoundedRect(segment_rect, _BORDER_RADIUS, _BORDER_RADIUS)

        # Intersect with track to clip at bar edges
        clipped_path = track_path.intersected(segment_path)

        painter.setBrush(QColor(_ACCENT))
        painter.drawPath(clipped_path)

        painter.end()
