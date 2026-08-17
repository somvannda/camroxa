"""Guards for music-web checkout payment ids, URLs, and amounts."""

from __future__ import annotations

import pytest

from platform_api.services.v2.payment_security import (
    extract_paid_amount_cents,
    is_allowed_cutluy_checkout_url,
    paid_amount_matches,
    require_cutluy_checkout_url,
    sanitize_music_web_return_url,
    validate_payment_id,
    webhook_user_matches,
)


def test_validate_payment_id_accepts_cutluy_ids() -> None:
    assert validate_payment_id("pay_abc-DEF.123") == "pay_abc-DEF.123"


@pytest.mark.parametrize(
    "value",
    ["", "ab", "../etc/passwd", "https://evil.test/x", "pay/../../secret", "a" * 200],
)
def test_validate_payment_id_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_payment_id(value)


def test_checkout_url_allowlist() -> None:
    assert is_allowed_cutluy_checkout_url("https://cutluy.com/pay/abc")
    assert is_allowed_cutluy_checkout_url("https://pay.cutluy.com/x")
    assert not is_allowed_cutluy_checkout_url("https://evil.com/cutluy.com")
    assert not is_allowed_cutluy_checkout_url("javascript:alert(1)")
    assert not is_allowed_cutluy_checkout_url("http://cutluy.com/pay/abc")
    with pytest.raises(ValueError):
        require_cutluy_checkout_url("https://example.com/pay")


def test_sanitize_return_url_keeps_music_web_only() -> None:
    assert (
        sanitize_music_web_return_url("https://music.sandbox.camxora.com/create")
        == "https://music.sandbox.camxora.com/create"
    )
    assert (
        sanitize_music_web_return_url("https://evil.example/phish")
        == "https://music.camxora.com/create"
    )
    assert sanitize_music_web_return_url("http://localhost:3000/create").startswith(
        "http://localhost:3000/"
    )


def test_paid_amount_matches_dollars_and_cents() -> None:
    assert extract_paid_amount_cents({"amount": 9.0}) == 900
    assert extract_paid_amount_cents({"amount_cents": 900}) == 900
    assert paid_amount_matches(900, {"amount": 9.0})
    assert paid_amount_matches(900, {"status": "paid"})
    assert not paid_amount_matches(2900, {"amount": 9.0})


def test_webhook_user_match() -> None:
    assert webhook_user_matches("user-1", {"metadata": {"user_id": "user-1"}})
    assert webhook_user_matches("user-1", {"metadata": {}})
    assert not webhook_user_matches("user-1", {"metadata": {"user_id": "user-2"}})
