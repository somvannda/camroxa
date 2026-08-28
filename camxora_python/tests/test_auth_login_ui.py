"""Smoke tests for the restyled desktop login card."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from features.account.views.auth_view import REMEMBER_EMAIL_KEY, AuthView
from shared.services.account_token_store import remember_account
from shared.services.secure_storage import SecureStorage


class _MemoryStorage(SecureStorage):
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._api_base_url = "http://localhost:8000/api/v3"

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def remove(self, key: str) -> None:
        self._data.pop(key, None)

    def get_api_base_url(self) -> str:
        return self._api_base_url

    def set_api_base_url(self, url: str) -> None:
        self._api_base_url = url


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_login_card_matches_studio_chrome(qapp: QApplication) -> None:
    view = AuthView(storage=_MemoryStorage())
    assert view.objectName() == "auth_page"
    assert view.findChild(QPushButton, "login_primary_button") is not None
    social = [btn.text() for btn in view.findChildren(QPushButton) if btn.text() in {"G", "MS", "Apple"}]
    assert social == []
    assert view._login_email.objectName() == "auth_input"
    assert view._footer_bar.parentWidget() is view
    brand = view.findChild(QLabel, "auth_brand_title")
    welcome = view.findChild(QLabel, "auth_welcome")
    assert brand is not None and brand.font().pixelSize() == 15
    assert welcome is not None and welcome.font().pixelSize() == 28


def test_remembered_email_prefills(qapp: QApplication) -> None:
    storage = _MemoryStorage()
    storage.set(REMEMBER_EMAIL_KEY, "somvannda@gmail.com")
    view = AuthView(storage=storage)
    assert view._login_email.text() == "somvannda@gmail.com"
    assert view._remember.isChecked()


def test_recent_account_fills_email_and_emits_switch(qapp: QApplication) -> None:
    storage = _MemoryStorage()
    remember_account(
        storage,
        user_id="user-1",
        email="duke@example.com",
        display_name="Duke",
        tokens_json="{}",
    )
    view = AuthView(storage=storage)
    captured: list[str] = []
    view.switch_account_requested.connect(captured.append)
    assert view._saved_accounts_layout.count() == 1
    card = view._saved_accounts_layout.itemAt(0).widget()
    card.selected.emit("user-1", "duke@example.com")
    assert view._login_email.text() == "duke@example.com"
    assert captured == ["user-1"]
