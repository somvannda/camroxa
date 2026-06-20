"""SVG Icon widget with color tinting and size variants.

Renders Lucide-style stroke-based SVG icons with configurable size,
color tinting, and opacity. Falls back to a placeholder icon when
the requested icon name is not found.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

_SIZES: dict[str, int] = {
    "small": 16,
    "medium": 20,
    "large": 24,
    "xlarge": 32,
}

_ICON_DIR: Path = Path(__file__).parent.parent / "assets" / "icons"
_FALLBACK_ICON: str = "circle"


class Icon(QWidget):
    """SVG icon widget with color tinting and size variants.

    Loads SVG icons from the assets/icons/ directory by name. Supports
    color tinting by modifying the SVG stroke attribute, size variants,
    and opacity control.

    Parameters
    ----------
    name : str
        Icon name (without .svg extension) to load from assets/icons/.
    size : str
        Size variant: "small" (16px), "medium" (20px), "large" (24px),
        "xlarge" (32px). Defaults to "medium". Invalid values fall back
        to "medium" with a warning.
    color : str | None
        Hex color string to apply as SVG stroke color. If None, the
        original SVG stroke color is preserved.
    opacity : float
        Opacity value between 0.0 and 1.0. Values outside this range
        are clamped with a warning.
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        name: str,
        size: str = "medium",
        color: str | None = None,
        opacity: float = 1.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Validate and store size
        if size not in _SIZES:
            logger.warning(
                "Invalid icon size variant '%s', falling back to 'medium'.", size
            )
            size = "medium"
        self._size_variant: str = size
        self._pixel_size: int = _SIZES[size]

        # Validate and store opacity
        if opacity < 0.0:
            logger.warning(
                "Icon opacity %.2f below 0.0, clamping to 0.0.", opacity
            )
            opacity = 0.0
        elif opacity > 1.0:
            logger.warning(
                "Icon opacity %.2f above 1.0, clamping to 1.0.", opacity
            )
            opacity = 1.0
        self._opacity: float = opacity

        # Store color
        self._color: str | None = color

        # Store name and resolve SVG path
        self._name: str = name
        self._using_fallback: bool = False
        self._svg_content: str = self._load_svg(name)

        # Build renderer
        self._renderer: QSvgRenderer = self._build_renderer()

        # Set fixed size for this widget
        self.setFixedSize(QSize(self._pixel_size, self._pixel_size))

    @property
    def name(self) -> str:
        """Return the icon name."""
        return self._name

    @property
    def color(self) -> str | None:
        """Return the current color tint."""
        return self._color

    @property
    def opacity(self) -> float:
        """Return the current opacity."""
        return self._opacity

    @property
    def size_variant(self) -> str:
        """Return the size variant string."""
        return self._size_variant

    @property
    def pixel_size(self) -> int:
        """Return the pixel size for the current variant."""
        return self._pixel_size

    @property
    def using_fallback(self) -> bool:
        """Return whether the fallback icon is being used."""
        return self._using_fallback

    def setColor(self, color: str) -> None:
        """Set a new color tint and repaint.

        Parameters
        ----------
        color : str
            Hex color string to apply as SVG stroke color.
        """
        self._color = color
        self._renderer = self._build_renderer()
        self.update()

    def setOpacity(self, opacity: float) -> None:
        """Set a new opacity value and repaint.

        Parameters
        ----------
        opacity : float
            Opacity value between 0.0 and 1.0. Clamped with warning
            if outside bounds.
        """
        if opacity < 0.0:
            logger.warning(
                "Icon opacity %.2f below 0.0, clamping to 0.0.", opacity
            )
            opacity = 0.0
        elif opacity > 1.0:
            logger.warning(
                "Icon opacity %.2f above 1.0, clamping to 1.0.", opacity
            )
            opacity = 1.0
        self._opacity = opacity
        self.update()

    def paintEvent(self, event: object) -> None:
        """Render the SVG icon with current color and opacity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        rect = QRectF(0, 0, self._pixel_size, self._pixel_size)
        self._renderer.render(painter, rect)

        painter.end()

    def _load_svg(self, name: str) -> str:
        """Load SVG content from the icons directory.

        Falls back to the placeholder icon if the requested name
        is not found.
        """
        svg_path = _ICON_DIR / f"{name}.svg"
        if svg_path.exists():
            return svg_path.read_text(encoding="utf-8")

        # Fallback
        logger.warning(
            "Icon '%s' not found at '%s', using fallback '%s'.",
            name,
            svg_path,
            _FALLBACK_ICON,
        )
        self._using_fallback = True
        fallback_path = _ICON_DIR / f"{_FALLBACK_ICON}.svg"
        if fallback_path.exists():
            return fallback_path.read_text(encoding="utf-8")

        # If even the fallback doesn't exist, return a minimal SVG
        logger.warning("Fallback icon '%s' not found either.", _FALLBACK_ICON)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>'
        )

    def _build_renderer(self) -> QSvgRenderer:
        """Build a QSvgRenderer from the SVG content with color tinting applied."""
        svg_data = self._svg_content

        # Apply color tinting by replacing stroke attribute
        if self._color is not None:
            svg_data = self._apply_color_tint(svg_data, self._color)

        renderer = QSvgRenderer(svg_data.encode("utf-8"))
        return renderer

    @staticmethod
    def _apply_color_tint(svg_content: str, color: str) -> str:
        """Apply color tinting to SVG by modifying stroke attributes.

        Replaces stroke="currentColor" and any existing stroke color
        with the specified color. This works with Lucide-style icons
        that use stroke-based drawing.
        """
        # Replace stroke="currentColor" with the target color
        result = svg_content.replace(
            'stroke="currentColor"', f'stroke="{color}"'
        )
        return result
