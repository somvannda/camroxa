"""Stat card layout components for the design system.

Provides StatCard — a key-value metric display with optional icon,
and StatCardGroup — a horizontal/vertical arrangement of StatCards
with subtle separators between items.
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.icon import Icon
from python_app.design_system.widgets.labels import TypedLabel

logger = logging.getLogger(__name__)

# Token defaults
_PADDING = DEFAULT_DARK_THEME.spacing.padding_md  # 8
_GAP = DEFAULT_DARK_THEME.spacing.gap_md  # 8
_ACCENT_COLOR = DEFAULT_DARK_THEME.colors.accent  # #00d4ff
_SEPARATOR_COLOR = DEFAULT_DARK_THEME.colors.separator  # #27354b
_BG_COLOR = DEFAULT_DARK_THEME.colors.surface_elevated  # #1e2548
_BORDER_COLOR = DEFAULT_DARK_THEME.colors.border_glass  # #ffffff1a
_RADIUS = DEFAULT_DARK_THEME.shape.radius_md  # 8


class StatCard(QWidget):
    """Key-value metric display with optional icon.

    Displays a metric label (muted, caption size) above a metric value
    (primary text, bold weight). Optionally renders an accent-colored icon
    to the left of the label/value pair.

    Parameters
    ----------
    label : str
        The metric label text displayed in muted caption style.
    value : str
        The metric value text displayed in primary bold style.
    icon_name : str | None
        Optional icon name to render to the left of the label/value pair.
        Uses the accent color at "small" or "medium" size.
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        label: str,
        value: str,
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Apply compact card styling
        self.setStyleSheet(
            f"StatCard {{"
            f"  background: {_BG_COLOR};"
            f"  border: 1px solid {_BORDER_COLOR};"
            f"  border-radius: {_RADIUS}px;"
            f"}}"
        )

        # Main horizontal layout (icon | text)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(_PADDING, _PADDING, _PADDING, _PADDING)
        main_layout.setSpacing(_GAP)

        # Optional icon
        self._icon: Icon | None = None
        if icon_name is not None:
            self._icon = Icon(
                name=icon_name,
                size="medium",
                color=_ACCENT_COLOR,
                parent=self,
            )
            main_layout.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Vertical text layout (label above value)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        # Label: muted, caption size
        self._label = TypedLabel(label, level="muted")
        self._label.setProperty("uiRole", "caption")
        self._label.setStyleSheet(
            f"color: {DEFAULT_DARK_THEME.colors.text_muted};"
            f"font-size: {DEFAULT_DARK_THEME.typography.size_caption}px;"
        )
        text_layout.addWidget(self._label)

        # Value: primary text, bold
        self._value_label = TypedLabel(value, level="body")
        self._value_label.setStyleSheet(
            f"color: {DEFAULT_DARK_THEME.colors.text_primary};"
            f"font-weight: {DEFAULT_DARK_THEME.typography.weight_bold};"
            f"font-size: {DEFAULT_DARK_THEME.typography.size_body}px;"
        )
        text_layout.addWidget(self._value_label)

        main_layout.addLayout(text_layout)
        main_layout.addStretch()

    @property
    def label_text(self) -> str:
        """Return the current label text."""
        return self._label.text()

    @property
    def value_text(self) -> str:
        """Return the current value text."""
        return self._value_label.text()

    def setValue(self, value: str) -> None:
        """Update the displayed value without recreating the widget.

        Parameters
        ----------
        value : str
            The new value text. If None is passed, displays an empty string.
        """
        if value is None:
            value = ""
        self._value_label.setText(value)


class StatCardGroup(QWidget):
    """Horizontal or vertical arrangement of StatCards with separators.

    Accepts a list of stat descriptors and renders one StatCard per item,
    separated by subtle divider lines.

    Parameters
    ----------
    stats : list[dict]
        List of stat descriptors. Each descriptor should contain:
        - "label" (str): The metric label
        - "value" (str): The metric value
        - "icon_name" (str | None, optional): Optional icon name
    orientation : str
        "horizontal" or "vertical". Defaults to "horizontal".
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        stats: list[dict[str, Any]],
        orientation: str = "horizontal",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._orientation = orientation
        self._cards: list[StatCard] = []

        # Choose layout direction
        if orientation == "vertical":
            layout: QHBoxLayout | QVBoxLayout = QVBoxLayout(self)
        else:
            layout = QHBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Render one StatCard per descriptor with separators between
        for i, stat in enumerate(stats):
            label = stat.get("label", "")
            value = stat.get("value", "")
            icon_name = stat.get("icon_name", None)

            card = StatCard(
                label=label,
                value=value,
                icon_name=icon_name,
                parent=self,
            )
            self._cards.append(card)
            layout.addWidget(card)

            # Add separator between items (not after the last one)
            if i < len(stats) - 1:
                separator = self._create_separator()
                layout.addWidget(separator)

    @property
    def cards(self) -> list[StatCard]:
        """Return the list of StatCard children."""
        return list(self._cards)

    def _create_separator(self) -> QFrame:
        """Create a subtle separator line between stat cards."""
        separator = QFrame(self)
        if self._orientation == "vertical":
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(
                f"color: {_SEPARATOR_COLOR};"
                f"background: {_SEPARATOR_COLOR};"
                f"max-height: 1px;"
            )
        else:
            separator.setFrameShape(QFrame.Shape.VLine)
            separator.setStyleSheet(
                f"color: {_SEPARATOR_COLOR};"
                f"background: {_SEPARATOR_COLOR};"
                f"max-width: 1px;"
            )
        separator.setFrameShadow(QFrame.Shadow.Plain)
        return separator
