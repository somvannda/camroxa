"""Web-music renewal reminder email + scheduling helpers."""

from __future__ import annotations

import pytest

from platform_api.services.email_service import _build_renewal_reminder_email
from platform_api.services.renewal_reminder_service import (
    _format_price,
    run_renewal_reminders,
)


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


class _FakeConn:
    def __init__(self, acquired: bool) -> None:
        self._acquired = acquired

    async def fetchval(self, query, *args):
        if "pg_try_advisory_lock" in query:
            return self._acquired
        return None


class _FakeAcquire:
    def __init__(self, conn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, acquired: bool) -> None:
        self._conn = _FakeConn(acquired)

    def acquire(self):
        return _FakeAcquire(self._conn)


@pytest.mark.asyncio
async def test_run_renewal_reminders_skips_when_lock_not_acquired() -> None:
    # Another worker holds the advisory lock -> no sweep, no duplicate sends.
    sent = await run_renewal_reminders(_FakePool(acquired=False))
    assert sent == 0
