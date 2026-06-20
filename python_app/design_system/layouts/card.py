"""Card layout component for the design system.

Provides a rounded-corner container with configurable title, padding,
and internal spacing between child widgets.
"""

import logging

from PyQt6.QtWidgets import QWidget, QVBoxLayout

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.labels import TypedLabel

logger = logging.getLogger(__name__)

# Token defaults
_PADDING_DEFAULT = DEFAULT_DARK_THEME.spacing.padding_lg  # 16
_GAP_DEFAULT = DEFAULT_DARK_THEME.spacing.gap_md  # 8
_RADIUS = DEFAULT_DARK_THEME.shape.radius_md  # 8
_BG_COLOR = DEFAULT_DARK_THEME.colors.surface_raised  # #141d2c

_PADDING_MIN = 0
_PADDING_MAX = 64


class Card(QWidget):
    """A rounded-corner card container with optional title and configurable padding.

    The Card provides subtle background differentiation from the page surface,
    rounded corners, and consistent internal spacing between child widgets.

    Parameters
    ----------
    title : str
        Optional title string rendered at the top with section_title styling.
    padding : int | None
        Padding on all sides in pixels. Clamped to 0–64 range.
        Defaults to the spacing.padding_lg token (16px).
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self, title: str = "", padding: int | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        # Resolve and clamp padding
        if padding is None:
            padding = _PADDING_DEFAULT
        padding = self._clamp_padding(padding)

        self._padding = padding

        # Apply visual styling: rounded corners + raised surface background
        self.setStyleSheet(
            f"Card {{ background: {_BG_COLOR}; border-radius: {_RADIUS}px; }}"
        )
        self.setObjectName("Card")

        # Internal layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(_GAP_DEFAULT)

        # Title label (hidden if no title provided)
        self._title_label = TypedLabel("", level="section_title")
        self._title_label.setVisible(False)
        self._layout.addWidget(self._title_label)

        if title:
            self.setTitle(title)

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

    def addWidget(self, widget: QWidget) -> None:
        """Add a child widget to the card's content area.

        Parameters
        ----------
        widget : QWidget
            The widget to add below existing content.
        """
        self._layout.addWidget(widget)

    @staticmethod
    def _clamp_padding(value: int) -> int:
        """Clamp padding to valid range [0, 64], logging a warning if out of bounds."""
        if value < _PADDING_MIN:
            logger.warning(
                "Card padding %d is below minimum (%d); clamping to %d.",
                value,
                _PADDING_MIN,
                _PADDING_MIN,
            )
            return _PADDING_MIN
        if value > _PADDING_MAX:
            logger.warning(
                "Card padding %d exceeds maximum (%d); clamping to %d.",
                value,
                _PADDING_MAX,
                _PADDING_MAX,
            )
            return _PADDING_MAX
        return value
