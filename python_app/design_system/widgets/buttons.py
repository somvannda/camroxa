"""Button widget components for the design system.

Provides variant-based button classes that apply Qt dynamic properties
for QSS styling, plus icon and toggle button variants.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import QPushButton, QWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

logger = logging.getLogger(__name__)

_VALID_VARIANTS = frozenset({
    "primary",
    "secondary",
    "danger",
    "success",
    "toggle",
    "transport",
    "transportPrimary",
})


class DesignButton(QPushButton):
    """Base button that applies a Style_Role via the uiRole dynamic property.

    If an unknown variant is provided, falls back to "primary" with a warning.
    """

    def __init__(
        self,
        text: str = "",
        variant: str = "primary",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if variant not in _VALID_VARIANTS:
            logger.warning(
                "Unknown button variant '%s', falling back to 'primary'.", variant
            )
            variant = "primary"
        self.setProperty("uiRole", variant)


class PrimaryButton(DesignButton):
    """Button with primary/accent styling."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, variant="primary", parent=parent)


class SecondaryButton(DesignButton):
    """Button with secondary/outline styling."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, variant="secondary", parent=parent)


class DangerButton(DesignButton):
    """Button with danger/destructive action styling."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, variant="danger", parent=parent)


class SuccessButton(DesignButton):
    """Button with success/positive action styling."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, variant="success", parent=parent)


class IconButton(QPushButton):
    """Button that displays an SVG icon with optional tooltip.

    The icon is loaded from the provided path and displayed at 16x16 default size.
    """

    def __init__(
        self,
        icon_name: str,
        tooltip: str = "",
        icon_size: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("uiRole", "icon")

        # Set icon from SVG path
        icon_path = Path(icon_name)
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            # Try as resource path directly
            self.setIcon(QIcon(icon_name))

        self.setIconSize(QSize(icon_size, icon_size))

        if tooltip:
            self.setToolTip(tooltip)


class ToggleButton(QPushButton):
    """Button with checkable/toggle behavior.

    Uses the 'toggle' uiRole and Qt's built-in checked pseudo-state
    for on/off visual states.
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setProperty("uiRole", "toggle")


class GhostButton(QPushButton):
    """Text-only button with transparent background and accent text.

    Styled via QSS using the ``uiRole`` dynamic property. Supports a
    danger mode that switches to danger token colors.

    Parameters
    ----------
    text : str
        Button label text.
    icon_name : str | None
        Optional icon name. When provided, the icon is loaded from the
        design system assets and displayed to the left of the text.
    danger : bool
        If True, applies danger color variant (uiRole="ghostDanger").
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        text: str = "",
        icon_name: str | None = None,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        role = "ghostDanger" if danger else "ghost"
        self.setProperty("uiRole", role)
        self._danger = danger
        self._icon_name = icon_name

        if icon_name:
            self._apply_icon(icon_name)

    @property
    def danger(self) -> bool:
        """Return whether danger mode is enabled."""
        return self._danger

    @property
    def icon_name(self) -> str | None:
        """Return the icon name."""
        return self._icon_name

    def _apply_icon(self, icon_name: str) -> None:
        """Load and apply the icon to the button."""
        icon_path = Path(icon_name)
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            # Try from design system assets directory
            assets_dir = Path(__file__).parent.parent / "assets" / "icons"
            svg_path = assets_dir / f"{icon_name}.svg"
            if svg_path.exists():
                self.setIcon(QIcon(str(svg_path)))
            else:
                logger.warning(
                    "GhostButton icon '%s' not found, rendering without icon.",
                    icon_name,
                )
                return
        self.setIconSize(QSize(16, 16))


class OutlinedButton(QPushButton):
    """Border-only button with accent border and text.

    Styled via QSS using the ``uiRole`` dynamic property. Supports a
    danger mode that switches to danger token colors.

    Parameters
    ----------
    text : str
        Button label text.
    icon_name : str | None
        Optional icon name. When provided, the icon is loaded from the
        design system assets and displayed to the left of the text.
    danger : bool
        If True, applies danger color variant (uiRole="outlinedDanger").
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        text: str = "",
        icon_name: str | None = None,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        role = "outlinedDanger" if danger else "outlined"
        self.setProperty("uiRole", role)
        self._danger = danger
        self._icon_name = icon_name

        if icon_name:
            self._apply_icon(icon_name)

    @property
    def danger(self) -> bool:
        """Return whether danger mode is enabled."""
        return self._danger

    @property
    def icon_name(self) -> str | None:
        """Return the icon name."""
        return self._icon_name

    def _apply_icon(self, icon_name: str) -> None:
        """Load and apply the icon to the button."""
        icon_path = Path(icon_name)
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            # Try from design system assets directory
            assets_dir = Path(__file__).parent.parent / "assets" / "icons"
            svg_path = assets_dir / f"{icon_name}.svg"
            if svg_path.exists():
                self.setIcon(QIcon(str(svg_path)))
            else:
                logger.warning(
                    "OutlinedButton icon '%s' not found, rendering without icon.",
                    icon_name,
                )
                return
        self.setIconSize(QSize(16, 16))
