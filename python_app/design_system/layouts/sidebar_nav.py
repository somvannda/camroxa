"""Sidebar navigation layout component for the design system.

Provides a vertical list of navigation items with icon and text label,
active/inactive/hover states, item grouping with headers, separators,
and a dedicated bottom slot for promotional or arbitrary widgets.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QColor

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.icon import Icon

# Token defaults
_ITEM_HEIGHT = 38
_PADDING_MD = DEFAULT_DARK_THEME.spacing.padding_md  # 8
_PADDING_LG = DEFAULT_DARK_THEME.spacing.padding_lg  # 16
_GAP_MD = DEFAULT_DARK_THEME.spacing.gap_md  # 8
_RADIUS_SM = DEFAULT_DARK_THEME.shape.radius_sm  # 4
_RADIUS_MD = DEFAULT_DARK_THEME.shape.radius_md  # 8

# Colors
_ACTIVE_BG = DEFAULT_DARK_THEME.colors.accent + "1a"  # Semi-transparent accent (~10%)
_ACTIVE_TEXT = DEFAULT_DARK_THEME.colors.text_primary  # #eef4ff
_INACTIVE_TEXT = DEFAULT_DARK_THEME.colors.text_muted  # #8ea4c7
_ACCENT = DEFAULT_DARK_THEME.colors.accent  # #00d4ff
_HOVER_BG = DEFAULT_DARK_THEME.colors.surface_overlay  # Subtle hover tint
_SEPARATOR_COLOR = DEFAULT_DARK_THEME.colors.separator  # #27354b
_GROUP_HEADER_COLOR = DEFAULT_DARK_THEME.colors.text_muted  # #8ea4c7

# Typography
_BODY_SIZE = DEFAULT_DARK_THEME.typography.size_body  # 12
_CAPTION_SIZE = DEFAULT_DARK_THEME.typography.size_caption  # 10


class _NavItem(QWidget):
    """Internal clickable navigation item widget with hover/active states."""

    clicked = pyqtSignal(str)

    def __init__(
        self,
        key: str,
        icon: str,
        label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._is_active = False
        self._is_hovered = False

        self.setFixedHeight(_ITEM_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(_PADDING_LG, _PADDING_MD, _PADDING_LG, _PADDING_MD)
        layout.setSpacing(_GAP_MD)

        # Icon widget (20px / medium size)
        self._icon_widget = Icon(
            name=icon if icon else "circle",
            size="medium",
            color=_INACTIVE_TEXT,
        )
        layout.addWidget(self._icon_widget)

        # Text label with body typography
        self._text_label = QLabel(label)
        self._text_label.setStyleSheet(
            f"QLabel {{ font-size: {_BODY_SIZE}px; color: {_INACTIVE_TEXT}; }}"
        )
        layout.addWidget(self._text_label)
        layout.addStretch()

        # Apply initial inactive styling
        self._apply_style()

    @property
    def key(self) -> str:
        """Return the page key associated with this navigation item."""
        return self._key

    @property
    def is_active(self) -> bool:
        """Return whether this item is currently active."""
        return self._is_active

    def set_active(self, active: bool) -> None:
        """Set the active/inactive visual state of this item."""
        self._is_active = active
        self._apply_style()

    def enterEvent(self, event: object) -> None:  # noqa: N802
        """Handle mouse enter to apply hover state."""
        self._is_hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        """Handle mouse leave to remove hover state."""
        self._is_hovered = False
        self._apply_style()
        super().leaveEvent(event)

    def _apply_style(self) -> None:
        """Apply the visual style based on active and hover state."""
        if self._is_active:
            # Active state: semi-transparent accent background + accent icon tint
            self.setStyleSheet(
                f"_NavItem {{ "
                f"background: {_ACTIVE_BG}; "
                f"border-radius: {_RADIUS_SM}px; "
                f"}}"
            )
            self._text_label.setStyleSheet(
                f"QLabel {{ color: {_ACTIVE_TEXT}; font-weight: 500; "
                f"font-size: {_BODY_SIZE}px; }}"
            )
            self._icon_widget.setColor(_ACCENT)
        elif self._is_hovered:
            # Hover state: subtle background tint, icon color stays muted
            self.setStyleSheet(
                f"_NavItem {{ "
                f"background: {_HOVER_BG}; "
                f"border-radius: {_RADIUS_SM}px; "
                f"}}"
            )
            self._text_label.setStyleSheet(
                f"QLabel {{ color: {_INACTIVE_TEXT}; "
                f"font-size: {_BODY_SIZE}px; }}"
            )
            # Icon stays muted on hover (no color change)
            self._icon_widget.setColor(_INACTIVE_TEXT)
        else:
            # Inactive state: icon and label in muted/secondary text color
            self.setStyleSheet(
                f"_NavItem {{ "
                f"background: transparent; "
                f"border-radius: {_RADIUS_SM}px; "
                f"}}"
            )
            self._text_label.setStyleSheet(
                f"QLabel {{ color: {_INACTIVE_TEXT}; "
                f"font-size: {_BODY_SIZE}px; }}"
            )
            self._icon_widget.setColor(_INACTIVE_TEXT)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Emit clicked signal with this item's key on mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


class SidebarNav(QWidget):
    """Sidebar navigation component rendering a vertical list of navigation items.

    Each item is rendered with a 20px Icon widget on the left and a body typography
    text label on the right. The active item has a semi-transparent accent background
    and accent icon tint, while inactive items have muted text and icon colors.
    Inactive items display a subtle background tint on hover without changing icon color.

    Items can be organized into groups with optional uppercase muted header labels,
    and items may have a separator flag to render a horizontal divider line below them.

    A dedicated bottom slot area supports placing a PromoCard or arbitrary widget
    via the ``setBottomWidget()`` method or the ``bottom_widget`` constructor parameter.

    Parameters
    ----------
    items : list[dict]
        A list of navigation item dictionaries. Each dict must contain:
        - "key": str — unique page identifier
        - "icon": str — icon name (e.g., "music") for the Icon widget
        - "label": str — display text

        Optional fields:
        - "group": str | None — group name for item grouping with header labels
        - "separator": bool — if True, renders a horizontal divider below the item

    bottom_widget : QWidget | None
        Optional widget to place in the dedicated bottom slot area (e.g., PromoCard).

    parent : QWidget | None
        Optional parent widget.

    Raises
    ------
    ValueError
        If any item in the list is missing the required "key" field.

    Signals
    -------
    navigation_requested(str)
        Emitted when a navigation item is clicked, with the item's page key.
    """

    navigation_requested = pyqtSignal(str)

    def __init__(
        self,
        items: list[dict],
        bottom_widget: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Validate items
        self._validate_items(items)

        self._items: list[_NavItem] = []
        self._bottom_widget: QWidget | None = None

        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, _PADDING_MD, 0, _PADDING_MD)
        main_layout.setSpacing(0)

        # Navigation items area (scrollable in the future if needed)
        self._nav_container = QWidget()
        self._nav_layout = QVBoxLayout(self._nav_container)
        self._nav_layout.setContentsMargins(0, 0, 0, 0)
        self._nav_layout.setSpacing(2)

        # Build navigation items with grouping
        self._build_items(items)

        main_layout.addWidget(self._nav_container)
        main_layout.addStretch()

        # Bottom slot area
        self._bottom_container = QWidget()
        self._bottom_layout = QVBoxLayout(self._bottom_container)
        self._bottom_layout.setContentsMargins(_PADDING_MD, _PADDING_MD, _PADDING_MD, _PADDING_MD)
        self._bottom_layout.setSpacing(0)
        main_layout.addWidget(self._bottom_container)

        # Set bottom widget if provided
        if bottom_widget is not None:
            self.setBottomWidget(bottom_widget)

        # Activate the first item by default if items exist
        if self._items:
            self._items[0].set_active(True)

    def setBottomWidget(self, widget: QWidget) -> None:  # noqa: N802
        """Set or replace the widget in the dedicated bottom slot area.

        Parameters
        ----------
        widget : QWidget
            The widget to place at the bottom of the sidebar
            (e.g., a PromoCard or arbitrary widget).
        """
        # Remove existing bottom widget if any
        if self._bottom_widget is not None:
            self._bottom_layout.removeWidget(self._bottom_widget)
            self._bottom_widget.setParent(None)

        self._bottom_widget = widget
        self._bottom_layout.addWidget(widget)

    def setActiveItem(self, page_key: str) -> None:  # noqa: N802
        """Programmatically set the active navigation item by page key.

        Parameters
        ----------
        page_key : str
            The key of the item to activate. If no item matches, no change occurs.
        """
        for item in self._items:
            item.set_active(item.key == page_key)

    def _build_items(self, items: list[dict]) -> None:
        """Build navigation items with group headers and separators."""
        current_group: str | None = None

        for item_data in items:
            group = item_data.get("group")
            separator = item_data.get("separator", False)

            # Render group header if this item starts a new group
            if group is not None and group != current_group:
                current_group = group
                self._add_group_header(group)

            # Create navigation item widget
            nav_item = _NavItem(
                key=item_data["key"],
                icon=item_data.get("icon", ""),
                label=item_data.get("label", ""),
            )
            nav_item.clicked.connect(self._on_item_clicked)
            self._items.append(nav_item)
            self._nav_layout.addWidget(nav_item)

            # Render separator if flagged
            if separator:
                self._add_separator()

    def _add_group_header(self, group_name: str) -> None:
        """Add a group header label (uppercase muted caption text)."""
        header = QLabel(group_name.upper())
        header.setStyleSheet(
            f"QLabel {{ "
            f"color: {_GROUP_HEADER_COLOR}; "
            f"font-size: {_CAPTION_SIZE}px; "
            f"font-weight: 600; "
            f"letter-spacing: 1px; "
            f"padding: {_PADDING_MD}px {_PADDING_LG}px 4px {_PADDING_LG}px; "
            f"}}"
        )
        self._nav_layout.addWidget(header)

    def _add_separator(self) -> None:
        """Add a horizontal divider line below a navigation item."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            f"QFrame {{ background: {_SEPARATOR_COLOR}; "
            f"margin: 4px {_PADDING_LG}px; }}"
        )
        self._nav_layout.addWidget(separator)

    def _on_item_clicked(self, key: str) -> None:
        """Handle an item click: activate it and emit the navigation signal."""
        self.setActiveItem(key)
        self.navigation_requested.emit(key)

    @staticmethod
    def _validate_items(items: list[dict]) -> None:
        """Validate that all items have the required 'key' field.

        Raises
        ------
        ValueError
            If any item is missing the "key" field.
        """
        for i, item in enumerate(items):
            if "key" not in item:
                raise ValueError(
                    f"Navigation item at index {i} is missing the required 'key' field: {item!r}"
                )
