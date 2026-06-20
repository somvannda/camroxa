"""Gradient button widget with linear gradient background and glow effect.

Primary CTA button rendered with QPainter QLinearGradient for the background
(since QSS doesn't support linear-gradient on QPushButton) and
QGraphicsDropShadowEffect for the outer glow.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QPushButton,
    QWidget,
)

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.icon import Icon

logger = logging.getLogger(__name__)

# Token values from the default dark theme
_ACCENT = DEFAULT_DARK_THEME.colors.nav_active_gradient_start  # #7466F1 purple
_ACCENT_GLOW = DEFAULT_DARK_THEME.colors.secondary_accent + "66"  # #7466F166
_ACCENT_LIGHTER = DEFAULT_DARK_THEME.colors.nav_active_gradient_end  # #A259FF lighter purple
_MUTED_BG = DEFAULT_DARK_THEME.colors.surface_overlay  # #1a1f3a
_TEXT_MUTED = DEFAULT_DARK_THEME.colors.text_muted  # #8ea4c7

# Glow configuration
_DEFAULT_BLUR_RADIUS = 12
_HOVER_BLUR_RADIUS = 20
_PRESSED_BLUR_RADIUS = 6

# Shape
_BORDER_RADIUS = DEFAULT_DARK_THEME.shape.radius_md  # 8px
_H_PADDING = 20
_V_PADDING = 8
_ICON_SPACING = 8


class GradientButton(QPushButton):
    """Primary CTA button with linear gradient background and glow effect.

    Uses QPainter with QLinearGradient for the background since QSS doesn't
    support linear-gradient on QPushButton. Attaches QGraphicsDropShadowEffect
    for the outer glow using the accent_glow token color.

    Parameters
    ----------
    text : str
        Button label text.
    icon_name : str | None
        Optional icon name to render to the left of the text via the Icon widget.
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        text: str = "",
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)

        self._icon_name: str | None = icon_name
        self._icon_widget: Icon | None = None
        self._hovered: bool = False

        # Setup icon if provided
        if icon_name:
            self._icon_widget = Icon(
                name=icon_name,
                size="small",
                color="#ffffff",
                parent=self,
            )
            # Hide the icon widget from layout; we paint it ourselves
            self._icon_widget.setVisible(False)

        # Setup glow effect
        self._glow_effect = QGraphicsDropShadowEffect(self)
        self._glow_effect.setBlurRadius(_DEFAULT_BLUR_RADIUS)
        self._glow_effect.setColor(QColor(_ACCENT_GLOW))
        self._glow_effect.setOffset(0, 0)
        self.setGraphicsEffect(self._glow_effect)

        # Set minimum size and font
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Transparent background so QPainter draws everything
        self.setStyleSheet("background: transparent; border: none;")

    @property
    def icon_name(self) -> str | None:
        """Return the icon name."""
        return self._icon_name

    @property
    def glow_effect(self) -> QGraphicsDropShadowEffect:
        """Return the glow shadow effect."""
        return self._glow_effect

    def paintEvent(self, event: object) -> None:
        """Custom paint with linear gradient background, rounded rect, and text."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())

        if not self.isEnabled():
            # Disabled: flat muted background
            painter.setBrush(QColor(_MUTED_BG))
            painter.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            path.addRoundedRect(rect, _BORDER_RADIUS, _BORDER_RADIUS)
            painter.drawPath(path)
            # Draw text in muted color
            painter.setPen(QPen(QColor(_TEXT_MUTED)))
            font = self.font()
            font.setBold(True)
            painter.setFont(font)
            self._draw_content(painter, rect, QColor(_TEXT_MUTED))
            painter.end()
            return

        # Determine gradient stops based on state
        if self.isDown():
            # Pressed: darken gradient stops
            start_color = QColor("#5a3dc7")  # Darker purple
            end_color = QColor("#7c4dff")  # Darker lighter purple
        elif self._hovered:
            # Hover: lighten gradient stops
            start_color = QColor("#8b6fff")  # Brighter purple
            end_color = QColor("#b87dff")  # Brighter lighter purple
        else:
            # Normal state
            start_color = QColor(_ACCENT)
            end_color = QColor(_ACCENT_LIGHTER)

        # Create linear gradient (left to right)
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        gradient.setColorAt(0.0, start_color)
        gradient.setColorAt(1.0, end_color)

        # Draw rounded rect with gradient
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        path = QPainterPath()
        path.addRoundedRect(rect, _BORDER_RADIUS, _BORDER_RADIUS)
        painter.drawPath(path)

        # Draw content (icon + text) in white
        text_color = QColor("#ffffff")
        painter.setPen(QPen(text_color))
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        self._draw_content(painter, rect, text_color)

        painter.end()

    def _draw_content(self, painter: QPainter, rect: QRectF, text_color: QColor) -> None:
        """Draw icon and text content centered in the button rect."""
        text = self.text()
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(text)
        text_height = font_metrics.height()

        icon_size = 0
        icon_spacing = 0
        if self._icon_widget and self._icon_name:
            icon_size = self._icon_widget.pixel_size
            icon_spacing = _ICON_SPACING

        total_content_width = icon_size + icon_spacing + text_width
        start_x = (rect.width() - total_content_width) / 2
        center_y = rect.height() / 2

        if self._icon_widget and self._icon_name:
            # Draw icon using the Icon widget's renderer
            icon_rect = QRectF(
                start_x,
                center_y - icon_size / 2,
                icon_size,
                icon_size,
            )
            # Render SVG icon directly
            self._icon_widget._renderer.render(painter, icon_rect)
            start_x += icon_size + icon_spacing

        # Draw text
        text_rect = QRectF(
            start_x,
            center_y - text_height / 2,
            text_width,
            text_height,
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

    def enterEvent(self, event: object) -> None:
        """Intensify glow on hover."""
        self._hovered = True
        if self.isEnabled() and self._glow_effect:
            self._glow_effect.setBlurRadius(_HOVER_BLUR_RADIUS)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        """Restore default glow on leave."""
        self._hovered = False
        if self.isEnabled() and self._glow_effect:
            self._glow_effect.setBlurRadius(_DEFAULT_BLUR_RADIUS)
        self.update()
        super().leaveEvent(event)

    def setEnabled(self, enabled: bool) -> None:
        """Override to manage glow effect on enable/disable."""
        super().setEnabled(enabled)
        if enabled:
            # Restore glow effect
            if self.graphicsEffect() is None:
                self._glow_effect = QGraphicsDropShadowEffect(self)
                self._glow_effect.setBlurRadius(_DEFAULT_BLUR_RADIUS)
                self._glow_effect.setColor(QColor(_ACCENT_GLOW))
                self._glow_effect.setOffset(0, 0)
                self.setGraphicsEffect(self._glow_effect)
        else:
            # Remove glow effect when disabled
            self.setGraphicsEffect(None)
            self._glow_effect = None  # type: ignore[assignment]
        self.update()

    def mousePressEvent(self, event: object) -> None:
        """Reduce glow on press."""
        if self.isEnabled() and self._glow_effect:
            self._glow_effect.setBlurRadius(_PRESSED_BLUR_RADIUS)
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: object) -> None:
        """Restore glow after release."""
        if self.isEnabled() and self._glow_effect:
            blur = _HOVER_BLUR_RADIUS if self._hovered else _DEFAULT_BLUR_RADIUS
            self._glow_effect.setBlurRadius(blur)
        self.update()
        super().mouseReleaseEvent(event)
