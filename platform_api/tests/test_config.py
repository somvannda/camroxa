from __future__ import annotations

from platform_api.config import Settings


def test_short_jwt_secret_is_stretched_to_safe_length() -> None:
    settings = Settings(jwt_secret="short-secret")

    assert len(settings.jwt_secret) >= 32
    assert settings.jwt_secret != "short-secret"


def test_long_jwt_secret_is_preserved() -> None:
    strong_secret = "this-is-already-a-strong-jwt-secret-123456"
    settings = Settings(jwt_secret=strong_secret)

    assert settings.jwt_secret == strong_secret
