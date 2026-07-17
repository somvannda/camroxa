"""Sidebar navigation matching Electron AppShellLayout sections."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
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
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class SidebarNav(QFrame):
    """Left sidebar with account summary, workspace nav, system nav, and logout."""

    route_selected = Signal(str)
    logout_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shell_sidebar")
        self.setFixedWidth(220)
        self._nav_buttons: dict[ShellRouteKey, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        self._account_card = self._build_account_card()
        layout.addWidget(self._account_card)

        workspace_label = QLabel("WORKSPACE")
        workspace_label.setObjectName(SUBTITLE_LABEL_ID)
        workspace_label.setContentsMargins(8, 16, 8, 0)
        layout.addWidget(workspace_label)
        layout.addWidget(self._build_nav_section(get_workspace_routes()))

        system_label = QLabel("SYSTEM")
        system_label.setObjectName(SUBTITLE_LABEL_ID)
        system_label.setContentsMargins(8, 18, 8, 0)
        layout.addWidget(system_label)
        layout.addWidget(self._build_nav_section(get_utility_routes()))

        layout.addStretch()

        logout_wrap = QFrame()
        logout_wrap.setObjectName("shell_logout_wrap")
        logout_layout = QVBoxLayout(logout_wrap)
        logout_layout.setContentsMargins(0, 12, 0, 0)
        logout_layout.setSpacing(0)

        self._logout_btn = QPushButton("Logout")
        self._logout_btn.setObjectName("shell_logout_button")
        self._logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_icon = lucide_pixmap("log-out", size=16, color=LOGOUT_ICON_COLOR)
        self._logout_btn.setIconSize(logout_icon.size())
        self._logout_btn.setIcon(QIcon(logout_icon))
        self._logout_btn.clicked.connect(self.logout_clicked.emit)
        logout_layout.addWidget(self._logout_btn)
        layout.addWidget(logout_wrap)

    def _build_account_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("account_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(4)

        name = QLabel("Guest User")
        name.setObjectName(TITLE_LABEL_ID)
        card_layout.addWidget(name)

        plan = QLabel("Not signed in")
        plan.setObjectName(SUBTITLE_LABEL_ID)
        card_layout.addWidget(plan)

        credits = QLabel("Credits: --")
        credits.setObjectName(SUBTITLE_LABEL_ID)
        card_layout.addWidget(credits)

        return card

    def _build_nav_section(self, routes: tuple[ShellRouteMeta, ...]) -> QWidget:
        section = QWidget()
        section.setObjectName("shell_nav_section")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 10, 0, 0)
        section_layout.setSpacing(6)

        for route in routes:
            button = QPushButton(route.label)
            button.setCheckable(True)
            button.setObjectName("nav_button")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        pixmap = lucide_pixmap(icon_name, size=16, color=color)
        button.setIconSize(pixmap.size())
        button.setIcon(QIcon(pixmap))

    def set_account_summary(
        self,
        display_name: str,
        plan_label: str | None,
        credits_label: str,
    ) -> None:
        card_layout = self._account_card.layout()
        if not isinstance(card_layout, QVBoxLayout):
            return
        name_label = card_layout.itemAt(0).widget()
        plan_label_widget = card_layout.itemAt(1).widget()
        credits_label_widget = card_layout.itemAt(2).widget()
        if isinstance(name_label, QLabel):
            name_label.setText(display_name)
        if isinstance(plan_label_widget, QLabel):
            plan_label_widget.setText(plan_label or "Free plan")
        if isinstance(credits_label_widget, QLabel):
            credits_label_widget.setText(credits_label)
