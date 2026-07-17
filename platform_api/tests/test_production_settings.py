"""Tests for production startup config gates (Phase 0)."""

from __future__ import annotations

import hashlib

import pytest

from platform_api.config import (
    Settings,
    is_production,
    validate_production_settings,
)


def test_is_production_accepts_prod_aliases() -> None:
    assert is_production(Settings(environment="production")) is True
    assert is_production(Settings(environment="prod")) is True
    assert is_production(Settings(environment="development")) is False


def test_validate_production_settings_allows_safe_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_JWT_SECRET", "a" * 32)
    settings = Settings(
        environment="production",
        debug=False,
        jwt_secret="a" * 32,
        suno_callback_hmac_secret="callback-hmac-secret",
    )
    validate_production_settings(settings)


def test_validate_production_settings_rejects_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_JWT_SECRET", "a" * 32)
    settings = Settings(
        environment="production",
        debug=True,
        jwt_secret="a" * 32,
        suno_callback_hmac_secret="callback-hmac-secret",
    )
    with pytest.raises(RuntimeError, match="PLATFORM_DEBUG"):
        validate_production_settings(settings)


def test_validate_production_settings_rejects_default_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLATFORM_JWT_SECRET", raising=False)
    settings = Settings(
        environment="production",
        debug=False,
        jwt_secret="change-me-in-production",
        suno_callback_hmac_secret="callback-hmac-secret",
    )
    with pytest.raises(RuntimeError, match="PLATFORM_JWT_SECRET"):
        validate_production_settings(settings)


def test_validate_production_settings_rejects_stretched_default_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = hashlib.sha256(b"camxora-jwt::change-me-in-production").hexdigest()
    monkeypatch.setenv("PLATFORM_JWT_SECRET", digest)
    settings = Settings(
        environment="production",
        debug=False,
        jwt_secret=digest,
        suno_callback_hmac_secret="callback-hmac-secret",
    )
    with pytest.raises(RuntimeError, match="PLATFORM_JWT_SECRET"):
        validate_production_settings(settings)


def test_validate_production_settings_rejects_missing_callback_hmac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_JWT_SECRET", "a" * 32)
    settings = Settings(
        environment="production",
        debug=False,
        jwt_secret="a" * 32,
        suno_callback_hmac_secret="",
    )
    with pytest.raises(RuntimeError, match="SUNO_CALLBACK_HMAC_SECRET"):
        validate_production_settings(settings)


def test_validate_production_settings_skips_non_production() -> None:
    settings = Settings(
        environment="development",
        debug=True,
        jwt_secret="change-me-in-production",
        suno_callback_hmac_secret="",
    )
    validate_production_settings(settings)
