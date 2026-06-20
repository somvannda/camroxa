"""Glass-morphism card layout component for the design system.

Provides a frosted-glass style card with semi-transparent background, subtle border,
hover state border brightness increase, optional clickable mode, and configurable
padding/border-radius.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.labels import TypedLabel

logger = logging.getLogger(__name__)

# Token defaults
_BG_COLOR = DEFAULT_DARK_THEME.colors.surface_elevated  # #1e2548
_BORDER_COLOR = DEFAULT_DARK_THEME.colors.border_glass  # #ffffff1a
_BORDER_HOVER_COLOR = "#ffffff33"  # ~20% white opacity on hover
_PADDING_DEFAULT = DEFAULT_DARK_THEME.spacing.padding_lg  # 16
_RADIUS_DEFAULT = DEFAULT_DARK_THEME.shape.radius_lg  # 12
_GAP_DEFAULT = DEFAULT_DARK_THEME.spacing.gap_md  # 8

_PADDING_MIN = 0
_PADDING_MAX = 64
_RADIUS_MIN = 0
_RADIUS_MAX = 32


class GlassCard(QWidget):
    """Glass-morphism card with semi-transparent background and frosted border.

    The GlassCard provides an elevated surface with rounded corners,
    a semi-transparent background, and a subtle glass-morphism border.
    On hover the border brightens to indicate interactivity.

    Parameters
    ----------
    title : str
        Optional title rendered with section_title styling (bold 14-16px white).
    subtitle : str
        Optional subtitle rendered with muted text styling below the title.
    clickable : bool
        If True, emits the `clicked` signal on mouse press and shows a
        pointing-hand cursor on hover.
    padding : int
        Internal padding on all sides in pixels. Clamped to 0–64 range.
        Defaults to 16px (spacing.padding_lg token).
    border_radius : int
        Corner radius in pixels. Clamped to 0–32 range.
        Defaults to 12px (shape.radius_lg token).
    parent : QWidget | None
        Optional parent widget.
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        clickable: bool = False,
        padding: int = _PADDING_DEFAULT,
        border_radius: int = _RADIUS_DEFAULT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._clickable = clickable
        self._padding = self._clamp(padding, _PADDING_MIN, _PADDING_MAX, "padding")
        self._border_radius = self._clamp(
            border_radius, _RADIUS_MIN, _RADIUS_MAX, "border_radius"
        )

        # Apply base stylesheet
        self._apply_stylesheet(_BORDER_COLOR)

        # Cursor for clickable mode
        if self._clickable:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Internal layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            self._padding, self._padding, self._padding, self._padding
        )
        self._layout.setSpacing(_GAP_DEFAULT)

        # Title label
        self._title_label = TypedLabel("", level="section_title")
        self._title_label.setVisible(False)
        self._layout.addWidget(self._title_label)

        # Subtitle label
        self._subtitle_label = TypedLabel("", level="muted")
        self._subtitle_label.setVisible(False)
        self._layout.addWidget(self._subtitle_label)

        # Set initial title/subtitle if provided
        if title:
            self.setTitle(title)
        if subtitle:
            self.setSubtitle(subtitle)

    def setTitle(self, title: str) -> None:
        """Set or update the card title.

        Parameters
        ----------
        title : str
            The title text. If empty, the title label is hidden.
        """
        if title:
            self._title_label.setText(title)
            self._title_label.setVisible(True)
        else:
            self._title_label.setText("")
            self._title_label.setVisible(False)

    def setSubtitle(self, subtitle: str) -> None:
        """Set or update the card subtitle.

        Parameters
        ----------
        subtitle : str
            The subtitle text. If empty, the subtitle label is hidden.
        """
        if subtitle:
            self._subtitle_label.setText(subtitle)
            self._subtitle_label.setVisible(True)
        else:
            self._subtitle_label.setText("")
            self._subtitle_label.setVisible(False)

    def addWidget(self, widget: QWidget) -> None:
        """Add a child widget to the card's content area.

        Parameters
        ----------
        widget : QWidget
            The widget to add below existing content.
        """
        self._layout.addWidget(widget)

    # ------------------------------------------------------------------
    # Event overrides for hover and click
    # ------------------------------------------------------------------

    def enterEvent(self, event: QEnterEvent | None) -> None:  # type: ignore[override]
        """Brighten border on hover."""
        self._apply_stylesheet(_BORDER_HOVER_COLOR)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:  # type: ignore[override]
        """Restore default border on leave."""
        self._apply_stylesheet(_BORDER_COLOR)
        super().leaveEvent(event)  # type: ignore[arg-type]

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # type: ignore[override]
        """Emit clicked signal if in clickable mode."""
        if self._clickable:
            self.clicked.emit()
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_stylesheet(self, border_color: str) -> None:
        """Apply the QSS stylesheet with the given border color."""
        self.setStyleSheet(
            f"GlassCard {{"
            f"  background: {_BG_COLOR};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: {self._border_radius}px;"
            f"}}"
        )

    @staticmethod
    def _clamp(value: int, minimum: int, maximum: int, name: str) -> int:
        """Clamp a value to [minimum, maximum], logging a warning if out of bounds."""
        if value < minimum:
            logger.warning(
                "GlassCard %s %d is below minimum (%d); clamping to %d.",
                name,
                value,
                minimum,
                minimum,
            )
            return minimum
        if value > maximum:
            logger.warning(
                "GlassCard %s %d exceeds maximum (%d); clamping to %d.",
                name,
                value,
                maximum,
                maximum,
            )
            return maximum
        return value
