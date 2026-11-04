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
    monkeypatch.delenv("CAMXORA_MUSIC_WEB_BASE_URL", raising=False)
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


def test_bundled_env_ignores_other_environments(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A leftover .env.production must not override a sandbox build's URLs.

    Regression: every ``.env.*`` file in the install dir / _internal / source tree
    was merged in a fixed order, so ``.env.production`` won and a sandbox installer
    pointed at production.
    """
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "sandbox")
    (tmp_path / ".env.production").write_text(
        "CAMXORA_PORTAL_BASE_URL=https://app.camxora.com\n"
        "CAMXORA_MUSIC_WEB_BASE_URL=https://music.camxora.com\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.sandbox").write_text(
        "CAMXORA_PORTAL_BASE_URL=https://app.sandbox.camxora.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_config, "get_install_dir", lambda: tmp_path)

    assert build_config.get_portal_base_url() == "https://app.sandbox.camxora.com"
    assert build_config.get_music_web_base_url() == "https://music.sandbox.camxora.com"


def _isolate_env_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> "object":
    """Point build_config's module dir at an empty package folder.

    ``_load_bundled_env`` also scans the real source tree, which has its own
    ``.env.*`` files; redirecting ``__file__`` keeps these tests hermetic.
    """
    fake = tmp_path / "pkg" / "shared" / "services" / "build_config.py"
    fake.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(build_config, "__file__", str(fake))
    monkeypatch.setattr(build_config, "get_install_dir", lambda: tmp_path)
    return fake.parents[2]


def test_single_bundled_env_file_selects_environment(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A release installer ships one .env.<env> and sets no env var at runtime."""
    pkg = _isolate_env_dir(tmp_path, monkeypatch)
    (pkg / ".env.sandbox").write_text(
        "CAMXORA_BUILD_ENV=sandbox\n"
        "CAMXORA_PORTAL_BASE_URL=https://app.sandbox.camxora.com\n",
        encoding="utf-8",
    )
    assert build_config.build_environment() == "sandbox"
    assert build_config.get_portal_base_url() == "https://app.sandbox.camxora.com"


def test_ambiguous_bundled_env_files_are_not_merged(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two environment files (dev checkout) must not silently pick production."""
    pkg = _isolate_env_dir(tmp_path, monkeypatch)
    (pkg / ".env.sandbox").write_text(
        "CAMXORA_BUILD_ENV=sandbox\nCAMXORA_PORTAL_BASE_URL=https://app.sandbox.camxora.com\n",
        encoding="utf-8",
    )
    (pkg / ".env.production").write_text(
        "CAMXORA_BUILD_ENV=production\nCAMXORA_PORTAL_BASE_URL=https://app.camxora.com\n",
        encoding="utf-8",
    )
    assert build_config.build_environment() == "development"
    assert build_config.get_portal_base_url() == "http://localhost:3001"


def test_portal_url_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "sandbox")
    assert build_config.get_portal_base_url() == "https://app.sandbox.camxora.com"
    assert build_config.get_onboarding_url().endswith("/onboarding")
    assert build_config.get_music_web_base_url() == "https://music.sandbox.camxora.com"
    assert build_config.get_pricing_url(embed=True) == (
        "https://music.sandbox.camxora.com/pricing/embed"
    )


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
