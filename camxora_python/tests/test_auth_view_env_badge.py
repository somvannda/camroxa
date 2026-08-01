"""Login screen must never surface which API/environment a production build hits."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.account.views.auth_view import AuthView


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_view(qapp: QApplication) -> AuthView:
    return AuthView()


def test_login_footer_badge_hidden_for_production_build(qapp: QApplication, monkeypatch) -> None:
    import features.account.views.auth_view as auth_view_module

    monkeypatch.setattr(auth_view_module, "build_environment", lambda: "production")
    view = _make_view(qapp)

    view._refresh_login_footer_badges()

    assert view._footer_bar._env_badge.isHidden()
    assert view._footer_bar._env_badge.text() == ""


@pytest.mark.parametrize("env", ["sandbox", "development"])
def test_login_footer_badge_still_shown_for_non_production_builds(
    qapp: QApplication, monkeypatch, env: str
) -> None:
    import features.account.views.auth_view as auth_view_module

    monkeypatch.setattr(auth_view_module, "build_environment", lambda: env)
    monkeypatch.setattr(auth_view_module, "footer_environment_badge", lambda: (None, ""))
    view = _make_view(qapp)
    view._storage.get_api_base_url = lambda: "https://sandbox.example.com"  # type: ignore[method-assign]

    view._refresh_login_footer_badges()

    assert not view._footer_bar._env_badge.isHidden()
    assert view._footer_bar._env_badge.text() != ""
    assert "Production" not in view._footer_bar._env_badge.text()
