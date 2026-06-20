"""Quick action card and grid layout components for the design system.

Provides clickable cards with centered icon and label (QuickActionCard) and a
configurable grid container (QuickActionGrid) for rendering multiple actions.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.icon import Icon

logger = logging.getLogger(__name__)

# Token-based styling constants
_BG_COLOR = DEFAULT_DARK_THEME.colors.surface_elevated  # #1e2548
_BORDER_COLOR = DEFAULT_DARK_THEME.colors.border_glass  # #ffffff1a
_ACCENT_COLOR = DEFAULT_DARK_THEME.colors.accent  # #00d4ff
_TEXT_COLOR = DEFAULT_DARK_THEME.colors.text_primary
_BORDER_RADIUS = DEFAULT_DARK_THEME.shape.radius_lg  # 12
_PADDING = DEFAULT_DARK_THEME.spacing.padding_md  # 12

# Hover border: accent color at reduced opacity (~30%)
_BORDER_HOVER_COLOR = _ACCENT_COLOR + "4d"  # ~30% opacity


class QuickActionCard(QWidget):
    """Clickable card with centered icon above a text label.

    Uses glass-card styling: rounded corners, semi-transparent border,
    and subtle background differentiation. Emits ``action_triggered``
    with the action key string when clicked.

    Parameters
    ----------
    key : str
        Unique action identifier emitted in the ``action_triggered`` signal.
    icon_name : str
        Name of the SVG icon to display (loaded from assets/icons/).
    label : str
        Text label displayed below the icon.
    parent : QWidget | None
        Optional parent widget.
    """

    action_triggered = pyqtSignal(str)

    def __init__(
        self,
        key: str,
        icon_name: str,
        label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._key = key

        # Apply glass-card styling
        self._apply_stylesheet(_BORDER_COLOR)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Layout: centered icon above label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(_PADDING, _PADDING, _PADDING, _PADDING)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon (centered)
        self._icon = Icon(name=icon_name, size="large", color=_ACCENT_COLOR)
        layout.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignCenter)

        # Label (centered)
        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            f"color: {_TEXT_COLOR}; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignCenter)

    @property
    def key(self) -> str:
        """Return the action key identifier."""
        return self._key

    @property
    def label_text(self) -> str:
        """Return the label text."""
        return self._label.text()

    # ------------------------------------------------------------------
    # Event overrides
    # ------------------------------------------------------------------

    def enterEvent(self, event: QEnterEvent | None) -> None:  # type: ignore[override]
        """Show accent-colored border highlight on hover."""
        self._apply_stylesheet(_BORDER_HOVER_COLOR)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:  # type: ignore[override]
        """Restore default border on leave."""
        self._apply_stylesheet(_BORDER_COLOR)
        super().leaveEvent(event)  # type: ignore[arg-type]

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # type: ignore[override]
        """Emit action_triggered signal with this card's key."""
        self.action_triggered.emit(self._key)
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_stylesheet(self, border_color: str) -> None:
        """Apply glass-card QSS with the given border color."""
        self.setStyleSheet(
            f"QuickActionCard {{"
            f"  background: {_BG_COLOR};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: {_BORDER_RADIUS}px;"
            f"}}"
        )


class QuickActionGrid(QWidget):
    """Grid layout container for QuickActionCard items.

    Arranges cards in a QGridLayout with configurable column count and gap
    spacing. Accepts a list of action descriptors and renders one
    QuickActionCard per item. Forwards ``action_triggered`` signals from
    child cards.

    Parameters
    ----------
    actions : list[dict]
        List of action descriptors. Each must contain at minimum a "key"
        field. Expected shape: ``{"key": str, "icon_name": str, "label": str}``.
    columns : int
        Number of columns in the grid. Values < 1 are clamped to 1 with
        a warning log.
    gap : int
        Spacing between cards in pixels.
    parent : QWidget | None
        Optional parent widget.

    Raises
    ------
    ValueError
        If any action descriptor is missing the required "key" field.
    """

    action_triggered = pyqtSignal(str)

    def __init__(
        self,
        actions: list[dict],
        columns: int = 4,
        gap: int = 12,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Validate action descriptors
        self._validate_actions(actions)

        # Clamp columns
        if columns < 1:
            logger.warning(
                "QuickActionGrid column count %d is less than 1; clamping to 1.",
                columns,
            )
            columns = 1

        self._columns = columns
        self._cards: list[QuickActionCard] = []

        # Grid layout
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(gap)

        # Create and place cards
        for index, descriptor in enumerate(actions):
            key = descriptor["key"]
            icon_name = descriptor.get("icon_name", "circle")
            label = descriptor.get("label", "")

            card = QuickActionCard(
                key=key,
                icon_name=icon_name,
                label=label,
                parent=self,
            )

            # Forward signal
            card.action_triggered.connect(self.action_triggered)

            row = index // columns
            col = index % columns
            grid.addWidget(card, row, col)
            self._cards.append(card)

    @property
    def cards(self) -> list[QuickActionCard]:
        """Return the list of child QuickActionCard widgets."""
        return list(self._cards)

    @staticmethod
    def _validate_actions(actions: list[dict]) -> None:
        """Validate that all action descriptors have the required 'key' field.

        Raises
        ------
        ValueError
            If any descriptor is missing the "key" field, listing the
            malformed descriptor.
        """
        malformed: list[dict] = []
        for descriptor in actions:
            if "key" not in descriptor:
                malformed.append(descriptor)

        if malformed:
            raise ValueError(
                f"Action descriptors missing required 'key' field: {malformed}"
            )
