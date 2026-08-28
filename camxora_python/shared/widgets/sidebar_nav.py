"""Sidebar navigation matching Electron AppShellLayout sections."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shared.constants.navigation import (
    ShellRouteKey,
    ShellRouteMeta,
    get_utility_routes,
    get_workspace_routes,
)
from shared.icons.lucide_icons import (
    LOGOUT_ICON_COLOR,
    NAV_ICON_ACTIVE_COLOR,
    NAV_ICON_COLOR,
    SIDEBAR_ICON_BY_ROUTE,
    lucide_pixmap,
)
from shared.lib.settings_workspace import get_profile_initials
from shared.lib.ui_font import studio_font


class _ShellAvatar(QWidget):
    """Circular initials badge for the sidebar account card."""

    def __init__(self, initials: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._initials = initials
        self.setFixedSize(36, 36)

    def set_initials(self, initials: str) -> None:
        self._initials = initials or "P"
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#6335D9"))
        painter.drawEllipse(self.rect())
        painter.setPen(QColor("#E5EDF7"))
        painter.setFont(studio_font(12, QFont.Weight.DemiBold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._initials)


class SidebarNav(QFrame):
    """Left sidebar with account summary, workspace nav, system nav, and logout."""

    route_selected = Signal(str)
    logout_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shell_sidebar")
        self.setFixedWidth(192)
        self.setFont(studio_font(12))
        self._nav_buttons: dict[ShellRouteKey, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self._account_card = self._build_account_card()
        layout.addWidget(self._account_card)

        workspace_label = QLabel("WORKSPACE")
        workspace_label.setObjectName("shell_group_label")
        workspace_label.setFont(studio_font(10, QFont.Weight.DemiBold, letter_spacing=110, uppercase=True))
        workspace_label.setContentsMargins(8, 14, 8, 6)
        layout.addWidget(workspace_label)
        layout.addWidget(self._build_nav_section(get_workspace_routes()))

        system_label = QLabel("SYSTEM")
        system_label.setObjectName("shell_group_label")
        system_label.setFont(studio_font(10, QFont.Weight.DemiBold, letter_spacing=110, uppercase=True))
        system_label.setContentsMargins(8, 14, 8, 6)
        layout.addWidget(system_label)
        layout.addWidget(self._build_nav_section(get_utility_routes()))

        layout.addStretch()

        logout_wrap = QFrame()
        logout_wrap.setObjectName("shell_logout_wrap")
        logout_layout = QVBoxLayout(logout_wrap)
        logout_layout.setContentsMargins(0, 12, 0, 0)
        logout_layout.setSpacing(0)

        self._logout_btn = QPushButton("  Logout")
        self._logout_btn.setObjectName("shell_logout_button")
        self._logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logout_btn.setFont(studio_font(12, QFont.Weight.Medium))
        logout_icon = lucide_pixmap("log-out", size=14, color=LOGOUT_ICON_COLOR)
        self._logout_btn.setIconSize(logout_icon.size())
        self._logout_btn.setIcon(QIcon(logout_icon))
        self._logout_btn.clicked.connect(self.logout_clicked.emit)
        logout_layout.addWidget(self._logout_btn)
        layout.addWidget(logout_wrap)

    def _build_account_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("shell_account_card")
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)

        self._avatar = _ShellAvatar(get_profile_initials("Guest User"))
        row.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(1)

        self._name_label = QLabel("Guest User")
        self._name_label.setObjectName("shell_account_name")
        self._name_label.setFont(studio_font(13, QFont.Weight.DemiBold))
        copy.addWidget(self._name_label)

        self._plan_label = QLabel("Not signed in")
        self._plan_label.setObjectName("shell_account_meta")
        self._plan_label.setFont(studio_font(12))
        copy.addWidget(self._plan_label)

        self._credits_label = QLabel("Credits: --")
        self._credits_label.setObjectName("shell_account_meta")
        self._credits_label.setFont(studio_font(12))
        copy.addWidget(self._credits_label)

        row.addLayout(copy, 1)
        return card

    def _build_nav_section(self, routes: tuple[ShellRouteMeta, ...]) -> QWidget:
        section = QWidget()
        section.setObjectName("shell_nav_section")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        for route in routes:
            button = QPushButton(f"  {route.label}")
            button.setCheckable(True)
            button.setObjectName("nav_button")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFont(studio_font(12, QFont.Weight.Medium))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setFixedHeight(34)
            self._set_nav_button_icon(button, route.key, active=False)
            button.clicked.connect(lambda _checked=False, key=route.key: self._on_nav_clicked(key))
            section_layout.addWidget(button)
            self._nav_buttons[route.key] = button

        return section

    def _on_nav_clicked(self, key: ShellRouteKey) -> None:
        self.select_route(key)
        self.route_selected.emit(key)

    def select_route(self, key: ShellRouteKey) -> None:
        for route_key, button in self._nav_buttons.items():
            button.blockSignals(True)
            is_active = route_key == key
            button.setChecked(is_active)
            self._set_nav_button_icon(button, route_key, active=is_active)
            button.blockSignals(False)

    @staticmethod
    def _set_nav_button_icon(button: QPushButton, route_key: ShellRouteKey, *, active: bool) -> None:
        icon_name = SIDEBAR_ICON_BY_ROUTE.get(route_key)
        if icon_name is None:
            return
        color = NAV_ICON_ACTIVE_COLOR if active else NAV_ICON_COLOR
        pixmap = lucide_pixmap(icon_name, size=14, color=color)
        button.setIconSize(pixmap.size())
        button.setIcon(QIcon(pixmap))

    def set_account_summary(
        self,
        display_name: str,
        plan_label: str | None,
        credits_label: str,
    ) -> None:
        name = display_name.strip() or "Guest User"
        self._name_label.setText(name)
        self._plan_label.setText(plan_label or "Free plan")
        self._credits_label.setText(credits_label)
        self._avatar.set_initials(get_profile_initials(name))
