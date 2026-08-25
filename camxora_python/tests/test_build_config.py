"""Tests for build-time API URL locking."""

from __future__ import annotations

import pytest

from shared.services import build_config
from shared.services.secure_storage import SecureStorage


@pytest.fixture(autouse=True)
def _clear_build_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_BUILD_ENV", raising=False)
    monkeypatch.delenv("CAMXORA_API_BASE_URL", raising=False)
    monkeypatch.delenv("CAMXORA_PORTAL_BASE_URL", raising=False)
    monkeypatch.setattr(build_config, "is_frozen_runtime", lambda: False)


def test_development_allows_user_api_override(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "development")
    storage = SecureStorage(store_path=tmp_path / "store.json")
    storage.set_api_base_url("http://127.0.0.1:9000/api/v3")
    assert storage.get_api_base_url() == "http://127.0.0.1:9000/api/v3"
    assert not storage.is_api_url_locked()


def test_sandbox_locks_api_url(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "sandbox")
    monkeypatch.setenv("CAMXORA_API_BASE_URL", "https://api.sandbox.camxora.com/api/v3")
    storage = SecureStorage(store_path=tmp_path / "store.json")
    storage.set_api_base_url("http://127.0.0.1:9000/api/v3")
    assert storage.get_api_base_url() == "https://api.sandbox.camxora.com/api/v3"
    assert storage.is_api_url_locked()


def test_portal_url_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "sandbox")
    assert build_config.get_portal_base_url() == "https://app.sandbox.camxora.com"
    assert build_config.get_onboarding_url().endswith("/onboarding")


def test_footer_badge_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "production")
    monkeypatch.setenv("CAMXORA_API_BASE_URL", "https://api.camxora.com/api/v3")
    assert not build_config.should_show_api_environment_badge()
    label, _ = build_config.footer_environment_badge()
    assert label is None


def test_footer_badge_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "sandbox")
    monkeypatch.setenv("CAMXORA_API_BASE_URL", "https://api.sandbox.camxora.com/api/v3")
    label, tooltip = build_config.footer_environment_badge()
    assert label == "Sandbox API"
    assert "sandbox.camxora.com" in tooltip


def test_footer_badge_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "development")
    monkeypatch.setenv("CAMXORA_API_BASE_URL", "http://localhost:8000/api/v3")
    label, tooltip = build_config.footer_environment_badge()
    assert label == "Local API"
    assert "localhost" in tooltip


def test_footer_version_badge() -> None:
    label, tooltip = build_config.footer_version_badge()
    assert label.startswith("v")
    assert label[1:] in tooltip
    assert "Camxora desktop" in tooltip
