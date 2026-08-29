"""UI tests for Marketplace Installed button state and catalog installed marking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from features.create.widgets.create_header import CreateHeader
from features.marketplace.coordinator import CatalogItem, CatalogResponse, InstallResult
from features.marketplace.views.marketplace_page_controller import MarketplacePageController
from features.marketplace.views.marketplace_view import MarketplaceView


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _item(item_id: str = "item-1", name: str = "Thunder Bass") -> CatalogItem:
    return CatalogItem(
        id=item_id,
        name=name,
        description="Bass drop",
        version="1.0.0",
        author="Admin",
        kind="video",
        tags=["bass"],
        status="enabled",
        price=0.0,
        preview_url="",
        created_at="",
    )


def _install_button(view: MarketplaceView, item_id: str) -> QPushButton:
    card = view._cards[item_id]
    return card._install_btn


def test_marketplace_uses_studio_chrome(qapp: QApplication) -> None:
    view = MarketplaceView()
    header = view.findChild(CreateHeader)
    assert view.objectName() == "marketplace_workspace"
    assert header is not None
    assert {button.text() for button in view._filter_buttons.values()} == {"All", "Video", "Reel"}
    assert view._search_input.objectName() == "MarketplaceSearch"


def test_set_catalog_marks_installed_button(qapp: QApplication) -> None:
    view = MarketplaceView()
    view.set_catalog(
        [_item("a"), _item("b", name="Other")],
        total=2,
        page=1,
        page_size=20,
        installed_ids={"a"},
    )

    assert _install_button(view, "a").text() == "Installed"
    assert _install_button(view, "b").text() == "Install"
    assert view._cards["a"].is_installed is True
    assert view._cards["b"].is_installed is False


def test_set_item_installed_updates_button_after_success(qapp: QApplication) -> None:
    view = MarketplaceView()
    view.set_catalog([_item("a")], total=1, page=1, page_size=20)

    assert _install_button(view, "a").text() == "Install"
    view.set_item_installed("a", True)
    assert _install_button(view, "a").text() == "Installed"
    assert view._cards["a"].is_installed is True


def test_set_installing_restores_installed_label(qapp: QApplication) -> None:
    view = MarketplaceView()
    view.set_catalog(
        [_item("a")],
        total=1,
        page=1,
        page_size=20,
        installed_ids={"a"},
    )
    view.set_install_progress("a", True)
    assert _install_button(view, "a").text() == "…"
    view.set_install_progress("a", False)
    assert _install_button(view, "a").text() == "Installed"


def test_catalog_ready_passes_installed_ids(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = MarketplaceView()
    coordinator = MagicMock()
    coordinator.is_installed.side_effect = lambda item_id: item_id == "installed-1"

    monkeypatch.setattr(MarketplacePageController, "_refresh_catalog", lambda self: None)
    controller = MarketplacePageController(view=view, coordinator=coordinator)

    response = CatalogResponse(
        items=[_item("installed-1"), _item("fresh-2", name="Fresh")],
        total=2,
        page=1,
        page_size=20,
    )
    controller._on_catalog_ready(controller._refresh_seq, response)

    assert _install_button(view, "installed-1").text() == "Installed"
    assert _install_button(view, "fresh-2").text() == "Install"
    assert coordinator.is_installed.call_count == 2


def test_install_ready_marks_installed_and_notifies(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = MarketplaceView()
    view.set_catalog([_item("item-1")], total=1, page=1, page_size=20)
    coordinator = MagicMock()
    changed: list[bool] = []

    monkeypatch.setattr(MarketplacePageController, "_refresh_catalog", lambda self: None)
    controller = MarketplacePageController(
        view=view,
        coordinator=coordinator,
        on_templates_changed=lambda: changed.append(True),
    )
    monkeypatch.setattr(controller, "_show_success_notification", lambda _msg: None)

    controller._on_install_ready("item-1", InstallResult(uid="local-uid-1"))

    assert _install_button(view, "item-1").text() == "Installed"
    assert changed == [True]
