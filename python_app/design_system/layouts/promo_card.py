"""Gradient-background promotional CTA card for sidebar areas.

Renders a promotional card with custom QPainter QLinearGradient background
(purple-to-blue by default), title, description, optional icon, and an
action button that emits `action_clicked` when clicked.
"""

from __future__ import annotations

import logging
import re

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.icon import Icon
from python_app.design_system.widgets.labels import TypedLabel

logger = logging.getLogger(__name__)

# Defaults
_DEFAULT_GRADIENT_START = "#7c3aed"  # Purple
_DEFAULT_GRADIENT_END = "#3b82f6"  # Blue
_BORDER_RADIUS = DEFAULT_DARK_THEME.shape.radius_lg  # 12px
_PADDING = DEFAULT_DARK_THEME.spacing.padding_lg  # 16px
_GAP = DEFAULT_DARK_THEME.spacing.gap_md  # 8px

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


class PromoCard(QWidget):
    """Gradient-background promotional CTA card for sidebar areas.

    Uses custom paintEvent with QLinearGradient for the gradient background.
    Contains a title (bold, white), description (muted/light), optional icon
    alongside the title, and an action button.

    Parameters
    ----------
    title : str
        Title text displayed bold and white.
    description : str
        Description text displayed in muted/light styling.
    button_text : str
        Text for the action button. If empty, the button is hidden.
    icon_name : str | None
        Optional icon name rendered alongside the title using the Icon widget.
    gradient_start : str
        Hex color for the gradient start (left/top). Defaults to purple (#7c3aed).
        Falls back to default if invalid.
    gradient_end : str
        Hex color for the gradient end (right/bottom). Defaults to blue (#3b82f6).
        Falls back to default if invalid.
    parent : QWidget | None
        Optional parent widget.
    """

    action_clicked = pyqtSignal()

    def __init__(
        self,
        title: str,
        description: str = "",
        button_text: str = "",
        icon_name: str | None = None,
        gradient_start: str = _DEFAULT_GRADIENT_START,
        gradient_end: str = _DEFAULT_GRADIENT_END,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Validate gradient colors
        self._gradient_start = self._validate_color(
            gradient_start, "gradient_start", _DEFAULT_GRADIENT_START
        )
        self._gradient_end = self._validate_color(
            gradient_end, "gradient_end", _DEFAULT_GRADIENT_END
        )

        # Store references
        self._title_text = title
        self._description_text = description
        self._icon_name = icon_name

        # Set minimum height for comfortable sizing
        self.setMinimumHeight(80)

        # Ensure transparent background so paintEvent handles everything
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent;")

        # Build internal layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(_PADDING, _PADDING, _PADDING, _PADDING)
        self._layout.setSpacing(_GAP)

        # Title row (icon + title)
        self._title_row = QHBoxLayout()
        self._title_row.setContentsMargins(0, 0, 0, 0)
        self._title_row.setSpacing(_GAP)

        # Optional icon
        self._icon_widget: Icon | None = None
        if icon_name:
            self._icon_widget = Icon(
                name=icon_name,
                size="medium",
                color="#ffffff",
                parent=self,
            )
            self._title_row.addWidget(self._icon_widget)

        # Title label (bold, white)
        self._title_label = TypedLabel(title, level="section_title")
        self._title_label.setStyleSheet(
            "background: transparent; color: #ffffff; font-weight: bold;"
        )
        self._title_row.addWidget(self._title_label)
        self._title_row.addStretch()

        self._layout.addLayout(self._title_row)

        # Description label (muted/light)
        self._description_label = TypedLabel(description, level="muted")
        self._description_label.setStyleSheet(
            "background: transparent; color: #b4c6e0;"
        )
        self._description_label.setWordWrap(True)
        if description:
            self._description_label.setVisible(True)
        else:
            self._description_label.setVisible(False)
        self._layout.addWidget(self._description_label)

        # Action button
        self._action_button = QPushButton(button_text, self)
        self._action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_button.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255, 255, 255, 0.2);"
            "  color: #ffffff;"
            "  border: 1px solid rgba(255, 255, 255, 0.3);"
            f"  border-radius: {DEFAULT_DARK_THEME.shape.radius_md}px;"
            "  padding: 6px 16px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 255, 255, 0.3);"
            "}"
        )
        if button_text:
            self._action_button.setVisible(True)
        else:
            self._action_button.setVisible(False)
        self._action_button.clicked.connect(self.action_clicked.emit)
        self._layout.addWidget(self._action_button)

    @property
    def gradient_start(self) -> str:
        """Return the validated gradient start color."""
        return self._gradient_start

    @property
    def gradient_end(self) -> str:
        """Return the validated gradient end color."""
        return self._gradient_end

    @property
    def title_label(self) -> TypedLabel:
        """Return the title label widget."""
        return self._title_label

    @property
    def description_label(self) -> TypedLabel:
        """Return the description label widget."""
        return self._description_label

    @property
    def action_button(self) -> QPushButton:
        """Return the action button widget."""
        return self._action_button

    @property
    def icon_widget(self) -> Icon | None:
        """Return the icon widget, or None if no icon was provided."""
        return self._icon_widget

    def paintEvent(self, event: object) -> None:
        """Custom paint with linear gradient background and rounded corners."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        # Create linear gradient (top-left to bottom-right)
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0.0, QColor(self._gradient_start))
        gradient.setColorAt(1.0, QColor(self._gradient_end))

        # Draw rounded rect with gradient
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        path = QPainterPath()
        path.addRoundedRect(rect, _BORDER_RADIUS, _BORDER_RADIUS)
        painter.drawPath(path)

        painter.end()

    @staticmethod
    def _validate_color(
        color: str, param_name: str, default: str
    ) -> str:
        """Validate a hex color string, falling back to default if invalid.

        Parameters
        ----------
        color : str
            The color string to validate.
        param_name : str
            Parameter name for the warning log message.
        default : str
            Default color to use if validation fails.

        Returns
        -------
        str
            The validated color, or the default if invalid.
        """
        if _HEX_COLOR_RE.match(color):
            return color
        logger.warning(
            "PromoCard %s '%s' is not a valid hex color; "
            "falling back to default '%s'.",
            param_name,
            color,
            default,
        )
        return default
