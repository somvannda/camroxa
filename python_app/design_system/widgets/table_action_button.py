"""Compact table action button widget for table action columns.

Provides a styled QPushButton with ghost, outlined, and launch variants,
supporting icon-only and icon-with-text modes with compact rounded styling
appropriate for use inside table cells.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import QPushButton, QWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

logger = logging.getLogger(__name__)

_VALID_VARIANTS = frozenset({"ghost", "outlined", "launch"})
_ASSETS_DIR: Path = Path(__file__).parent.parent / "assets" / "icons"


class TableActionButton(QPushButton):
    """Compact button for table action columns.

    Supports three visual variants and two content modes:

    Variants:
        - "ghost": transparent background, text only
        - "outlined": transparent background, accent border
        - "launch": primary accent color background

    Modes:
        - icon-only: no text set, reduced padding (4px all around)
        - icon-with-text: icon to the left of text, normal padding

    The button uses the ``uiRole`` dynamic property for QSS styling,
    with roles: "tableActionGhost", "tableActionOutlined", "tableActionLaunch".

    Parameters
    ----------
    text : str
        Button label text. If empty, icon-only mode is used.
    icon_name : str | None
        Optional icon name to load from the design system assets.
    variant : str
        Visual variant: "ghost", "outlined", or "launch". Defaults to
        "ghost". Invalid values fall back to "ghost" with a warning.
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        text: str = "",
        icon_name: str | None = None,
        variant: str = "ghost",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)

        # Validate variant
        if variant not in _VALID_VARIANTS:
            logger.warning(
                "Unknown TableActionButton variant '%s', falling back to 'ghost'.",
                variant,
            )
            variant = "ghost"

        self._variant: str = variant
        self._icon_name: str | None = icon_name
        self._icon_only: bool = not text

        # Set the uiRole for QSS styling
        role = f"tableAction{variant.capitalize()}"
        self.setProperty("uiRole", role)

        # Apply icon if provided
        if icon_name:
            self._apply_icon(icon_name)

        # Apply compact styling
        self._apply_compact_style()

    @property
    def variant(self) -> str:
        """Return the current variant."""
        return self._variant

    @property
    def icon_name(self) -> str | None:
        """Return the icon name."""
        return self._icon_name

    @property
    def icon_only(self) -> bool:
        """Return whether the button is in icon-only mode."""
        return self._icon_only

    def _apply_icon(self, icon_name: str) -> None:
        """Load and apply the icon to the button."""
        icon_path = Path(icon_name)
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            # Try from design system assets directory
            svg_path = _ASSETS_DIR / f"{icon_name}.svg"
            if svg_path.exists():
                self.setIcon(QIcon(str(svg_path)))
            else:
                logger.warning(
                    "TableActionButton icon '%s' not found, rendering without icon.",
                    icon_name,
                )
                return
        self.setIconSize(QSize(16, 16))

    def _apply_compact_style(self) -> None:
        """Apply compact rounded styling appropriate for table cells.

        Icon-only mode uses reduced padding (4px). Icon-with-text mode
        uses slightly larger padding for readability.
        """
        if self._icon_only:
            # Reduced padding for icon-only mode
            self.setStyleSheet(
                self.styleSheet()
                + "QPushButton { padding: 4px; min-width: 24px; min-height: 24px; }"
            )
        else:
            # Normal compact padding for icon-with-text
            self.setStyleSheet(
                self.styleSheet()
                + "QPushButton { padding: 4px 8px; min-height: 24px; }"
            )
