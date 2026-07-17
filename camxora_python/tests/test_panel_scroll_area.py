"""Panel scroll helper matches Video thin scrollbar styling path."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

from shared.themes.deep_blue import (
    MAIN_STYLESHEET,
    PANEL_SCROLL_AREA_ID,
    PANEL_SCROLL_CONTENT_ID,
    PANEL_SCROLLBAR_HANDLE,
    PANEL_SCROLLBAR_HANDLE_HOVER,
    PANEL_SCROLLBAR_WIDTH_PX,
)
from shared.widgets.settings_ui import make_panel_scroll_area, make_scrollable_tab_page


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_make_panel_scroll_area_object_name(qapp: QApplication) -> None:
    scroll = make_panel_scroll_area()
    assert scroll.objectName() == PANEL_SCROLL_AREA_ID


def test_make_scrollable_tab_page_uses_panel_scroll(qapp: QApplication) -> None:
    page = make_scrollable_tab_page(QLabel("body"))
    scrolls = page.findChildren(QScrollArea)
    assert any(child.objectName() == PANEL_SCROLL_AREA_ID for child in scrolls)
    contents = page.findChildren(QWidget)
    assert any(child.objectName() == PANEL_SCROLL_CONTENT_ID for child in contents)


def test_theme_defines_thin_panel_scrollbar() -> None:
    assert PANEL_SCROLLBAR_WIDTH_PX == 6
    assert PANEL_SCROLLBAR_HANDLE == "#2a4a6c"
    assert PANEL_SCROLLBAR_HANDLE_HOVER == "#4ac0ff"
    assert f"QScrollArea#{PANEL_SCROLL_AREA_ID} QScrollBar:vertical" in MAIN_STYLESHEET
    assert f"width: {PANEL_SCROLLBAR_WIDTH_PX}px;" in MAIN_STYLESHEET
    assert "background: transparent;" in MAIN_STYLESHEET
