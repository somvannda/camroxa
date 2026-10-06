"""Web-music renewal reminder email + scheduling helpers."""

from __future__ import annotations

from platform_api.services.email_service import _build_renewal_reminder_email
from platform_api.services.renewal_reminder_service import _format_price


def test_format_price() -> None:
    assert _format_price(500) == "$5.00"
    assert _format_price(2300) == "$23.00"
    assert _format_price(0) == "$0.00"


def _body(msg) -> str:
    return "".join(
        part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        for part in msg.get_payload()
    )


def test_renewal_email_mentions_plan_price_and_link() -> None:
    msg = _build_renewal_reminder_email(
        display_name="Duke",
        plan_name="Starter",
        price_display="$5.00",
        renew_url="https://music.camxora.com/profile",
        days_left=3,
        from_name="CAMXORA",
        from_address="no-reply@camxora.com",
    )
    assert "Starter" in msg["Subject"]
    assert "in 3 days" in msg["Subject"]
    body = _body(msg)
    assert "$5.00" in body
    assert "https://music.camxora.com/profile" in body


def test_renewal_email_subject_today_and_soon() -> None:
    today = _build_renewal_reminder_email(
        display_name="Duke",
        plan_name="Starter",
        price_display="$5.00",
        renew_url="https://music.camxora.com/profile",
        days_left=0,
        from_name="CAMXORA",
        from_address="no-reply@camxora.com",
    )
    assert "today" in today["Subject"]

    soon = _build_renewal_reminder_email(
        display_name="Duke",
        plan_name="Starter",
        price_display="$5.00",
        renew_url="https://music.camxora.com/profile",
        days_left=None,
        from_name="CAMXORA",
        from_address="no-reply@camxora.com",
    )
    assert "soon" in soon["Subject"]
