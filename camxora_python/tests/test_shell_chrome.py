"""Smoke tests for the restyled desktop shell chrome."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QToolButton

from shared.widgets.shell_footer_bar import ShellFooterBar
from shared.widgets.sidebar_nav import SidebarNav
from shared.widgets.window_title_bar import WindowTitleBar


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_title_bar_has_help_button(qapp: QApplication) -> None:
    bar = WindowTitleBar()
    assert bar.height() == 52
    help_button = bar.findChild(QToolButton, "window_help_button")
    assert help_button is not None
    assert help_button.toolTip() == "Help"


def test_sidebar_is_floating_card(qapp: QApplication) -> None:
    sidebar = SidebarNav()
    assert sidebar.objectName() == "shell_sidebar"
    assert sidebar.width() == 192
    assert sidebar.font().pixelSize() == 12


def test_sidebar_matches_screenshot_chrome(qapp: QApplication) -> None:
    sidebar = SidebarNav()
    assert sidebar.width() == 192
    assert sidebar._account_card.objectName() == "shell_account_card"
    assert sidebar._avatar._initials == "GU"

    sidebar.set_account_summary("Somvannda Kong", "starter_monthly", "2,050.0 credits")
    assert sidebar._name_label.text() == "Somvannda Kong"
    assert sidebar._plan_label.text() == "starter_monthly"
    assert sidebar._credits_label.text() == "2,050.0 credits"
    assert sidebar._avatar._initials == "SK"
    assert sidebar._name_label.font().pixelSize() == 13
    create_btn = sidebar._nav_buttons["create"]
    assert create_btn.font().pixelSize() == 12
    assert create_btn.text().startswith("  ")
    assert sidebar._logout_btn.font().pixelSize() == 12


def test_footer_uses_compact_dividers(qapp: QApplication) -> None:
    footer = ShellFooterBar()
    assert footer.height() == 40
    assert footer._message.font().pixelSize() == 12
    assert footer.layout().alignment() & Qt.AlignmentFlag.AlignVCenter
    assert footer._message.alignment() & Qt.AlignmentFlag.AlignVCenter
    assert footer._credits_divider.isHidden()
    assert not footer._allowance_divider.isHidden()

    footer.set_environment_badge("Sandbox API")
    footer.set_version_badge("v1.3.1")
    assert footer._env_badge.height() == 22
    assert footer._version_badge.height() == 22
    assert footer._env_badge.height() < footer.height()
    assert footer._env_badge.font().pixelSize() == 12
    assert footer._env_divider.isHidden()
    assert not footer._version_divider.isHidden()
    assert not footer._credits_divider.isHidden()
    assert not footer._allowance_divider.isHidden()
