"""StatusBadge widget for displaying colored status indicators.

Provides pill-shaped badges with text labels and dot-mode indicators
for item status (active, inactive, premium, warning). Maps variants
to status token colors from the design system token registry.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from python_app.design_system.tokens import DEFAULT_DARK_THEME

logger = logging.getLogger(__name__)

# Variant → (background_color_token_value, text_color)
_VARIANT_MAP: dict[str, tuple[str, str]] = {
    "active": (DEFAULT_DARK_THEME.colors.status_active, "#ffffff"),
    "inactive": (DEFAULT_DARK_THEME.colors.status_inactive, "#ffffff"),
    "premium": (DEFAULT_DARK_THEME.colors.status_premium, "#ffffff"),
    "warning": (DEFAULT_DARK_THEME.colors.status_warning, "#ffffff"),
}

_DOT_DIAMETER: int = 8
_PILL_H_PADDING: int = 6
_PILL_V_PADDING: int = 2


class StatusBadge(QWidget):
    """Colored pill badge or dot indicator for item status.

    In pill mode, renders a rounded-full pill with text label and
    colored background. In dot mode, renders an 8px diameter circle
    without text.

    Parameters
    ----------
    text : str
        Text label to display in pill mode. Ignored in dot mode.
    variant : str
        Predefined color variant: "active", "inactive", "premium", "warning".
        Unknown variants fall back to "inactive" with a warning log.
    dot_mode : bool
        If True, renders as a small colored dot instead of a pill.
    background_color : str | None
        Custom background color override (hex string). Overrides variant color.
    text_color : str | None
        Custom text color override (hex string). Overrides variant text color.
    parent : QWidget | None
        Optional parent widget.
    """

    VARIANTS: set[str] = {"active", "inactive", "premium", "warning"}

    def __init__(
        self,
        text: str = "",
        variant: str = "active",
        dot_mode: bool = False,
        background_color: str | None = None,
        text_color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._text: str = text
        self._dot_mode: bool = dot_mode
        self._custom_bg: str | None = background_color
        self._custom_text_color: str | None = text_color

        # Validate and resolve variant
        self._variant: str = self._resolve_variant(variant)

        # Resolve final colors
        self._bg_color: str = ""
        self._text_color_value: str = ""
        self._resolve_colors()

        # Configure widget size
        self._configure_size()

    @property
    def variant(self) -> str:
        """Return the current variant string."""
        return self._variant

    @property
    def background_color(self) -> str:
        """Return the resolved background color."""
        return self._bg_color

    @property
    def text_color(self) -> str:
        """Return the resolved text color."""
        return self._text_color_value

    @property
    def dot_mode(self) -> bool:
        """Return whether dot mode is active."""
        return self._dot_mode

    @property
    def text(self) -> str:
        """Return the badge text."""
        return self._text

    def setVariant(self, variant: str) -> None:
        """Set a new variant and repaint.

        Parameters
        ----------
        variant : str
            Predefined color variant. Unknown variants fall back to "inactive".
        """
        self._variant = self._resolve_variant(variant)
        self._resolve_colors()
        self._configure_size()
        self.update()

    def paintEvent(self, event: object) -> None:
        """Render the status badge (pill or dot)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = QColor(self._bg_color)

        if self._dot_mode:
            self._paint_dot(painter, bg_color)
        else:
            self._paint_pill(painter, bg_color)

        painter.end()

    def _paint_dot(self, painter: QPainter, bg_color: QColor) -> None:
        """Paint the dot mode (8px circle)."""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)

        # Center the dot within the widget
        x = (self.width() - _DOT_DIAMETER) / 2
        y = (self.height() - _DOT_DIAMETER) / 2
        painter.drawEllipse(int(x), int(y), _DOT_DIAMETER, _DOT_DIAMETER)

    def _paint_pill(self, painter: QPainter, bg_color: QColor) -> None:
        """Paint the pill mode (rounded rectangle with text)."""
        rect = self.rect()

        # Draw rounded-full background (radius = half height for pill shape)
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, radius, radius)

        # Draw text
        text_color = QColor(self._text_color_value)
        painter.setPen(QPen(text_color))

        font = QFont(DEFAULT_DARK_THEME.typography.font_family)
        font.setPixelSize(DEFAULT_DARK_THEME.typography.size_caption)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)

        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)

    def _resolve_variant(self, variant: str) -> str:
        """Validate variant, falling back to 'inactive' for unknown strings."""
        if variant not in self.VARIANTS:
            logger.warning(
                "Unknown StatusBadge variant '%s', falling back to 'inactive'.",
                variant,
            )
            return "inactive"
        return variant

    def _resolve_colors(self) -> None:
        """Resolve the final background and text colors from variant + overrides."""
        variant_bg, variant_text = _VARIANT_MAP[self._variant]

        # Apply custom overrides if provided
        self._bg_color = self._custom_bg if self._custom_bg is not None else variant_bg
        self._text_color_value = (
            self._custom_text_color
            if self._custom_text_color is not None
            else variant_text
        )

    def _configure_size(self) -> None:
        """Set the widget's fixed size based on mode."""
        if self._dot_mode:
            self.setFixedSize(QSize(_DOT_DIAMETER, _DOT_DIAMETER))
        else:
            # Calculate pill size based on text
            font = QFont(DEFAULT_DARK_THEME.typography.font_family)
            font.setPixelSize(DEFAULT_DARK_THEME.typography.size_caption)
            font.setWeight(QFont.Weight.Medium)

            from PyQt6.QtGui import QFontMetrics

            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(self._text)
            text_height = metrics.height()

            width = text_width + (_PILL_H_PADDING * 2)
            height = text_height + (_PILL_V_PADDING * 2)

            self.setFixedSize(QSize(max(width, height), height))
