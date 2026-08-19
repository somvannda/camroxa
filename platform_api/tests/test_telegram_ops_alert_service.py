"""Unit tests for the Telegram ops activity feed."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.services.telegram_ops_alert_service import (
    TelegramOpsAlertService,
    classify_activity,
    format_ops_message,
)


def test_classify_activity_prefers_lyric_over_music() -> None:
    assert classify_activity("web_music_lyrics") == "lyric"
    assert classify_activity("draft via slai") == "lyric"


def test_classify_activity_music_and_image() -> None:
    assert classify_activity("web_music_generation") == "music"
    assert classify_activity("music via suno") == "music"
    assert classify_activity("background_image via fal") == "image"
    assert classify_activity("video_manual via slai") == "video"


def test_format_login_message() -> None:
    text = format_ops_message(
        kind="login",
        env_label="Production",
        email="user@example.com",
        display_name="Ada",
        activity="login",
        account_status="FREE",
        user_id="abc-123",
    )
    assert "LOGIN" in text
    assert "user@example.com" in text
    assert "Production" in text


def test_format_signup_message_escapes_html() -> None:
    text = format_ops_message(
        kind="signup",
        env_label="Sandbox",
        email="a<b>@x.com",
        display_name="Ann & Bob",
        product="music_web",
        user_id="11111111-2222-3333-4444-555555555555",
        account_status="FREE",
    )
    assert "🆕" in text
    assert "SIGNUP" in text
    assert "a&lt;b&gt;@x.com" in text
    assert "Ann &amp; Bob" in text
    assert "<code>11111111-2222-3333-4444-555555555555</code>" in text


def test_format_spend_highlights_free_status() -> None:
    text = format_ops_message(
        kind="spend",
        env_label="Sandbox",
        account_status="FREE",
        activity="music",
        credits_label="10",
        pool="web music",
        reason="web_music_generation",
        user_id="abc",
    )
    assert "🔥" in text
    assert "<b>FREE</b>" in text
    assert "activity: <b>music</b>" in text


@pytest.mark.asyncio
async def test_send_html_noops_when_not_configured() -> None:
    client = AsyncMock()
    service = TelegramOpsAlertService(
        bot_token="",
        chat_id="-1001",
        enabled=True,
        env_label="Sandbox",
        http_client=client,
    )
    assert service.configured is False
    assert await service.send_html("hello") is False
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_send_html_posts_to_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _enabled() -> bool:
        return True

    monkeypatch.setattr(
        "platform_api.services.telegram_ops_alert_service._runtime_enabled",
        _enabled,
    )
    client = AsyncMock()
    client.post = AsyncMock(return_value=type("Resp", (), {"status_code": 200, "text": "ok"})())
    service = TelegramOpsAlertService(
        bot_token="123:abc",
        chat_id="-1001",
        enabled=True,
        env_label="Sandbox",
        http_client=client,
    )
    assert await service.send_html("<b>hi</b>") is True
    client.post.assert_awaited_once()
    kwargs = client.post.await_args.kwargs
    assert kwargs["json"]["chat_id"] == "-1001"
    assert kwargs["json"]["parse_mode"] == "HTML"


def test_install_telegram_ops_hooks_is_idempotent() -> None:
    from platform_api.services.telegram_ops_alert_service import install_telegram_ops_hooks

    install_telegram_ops_hooks()
    install_telegram_ops_hooks()


def test_is_stats_command() -> None:
    from platform_api.services.telegram_ops_commands import is_stats_command

    assert is_stats_command("/stats")
    assert is_stats_command("/stats@CamxoraBot")
    assert is_stats_command("stats")
    assert is_stats_command("/report")
    assert not is_stats_command("/login")
    assert not is_stats_command("hello")


def test_format_ops_stats_message() -> None:
    from platform_api.services.telegram_ops_commands import format_ops_stats_message

    text = format_ops_stats_message(
        env_label="Production",
        users={"today": 2, "yesterday": 1, "d7": 9, "d30": 40},
        songs={"today": 15, "yesterday": 8, "d7": 80, "d30": 300},
    )
    assert "STATS" in text
    assert "<b>Users</b>" in text
    assert "<b>Songs generated</b>" in text
    assert "Today: <b>2</b>" in text
    assert "Yesterday" in text
    assert "Last 7 Days" in text
    assert "Last 30 Days" in text
    assert "<pre>" not in text
    assert "2" in text
    assert "15" in text
    assert "40" in text
    assert "300" in text
    assert "10d" not in text


@pytest.mark.asyncio
async def test_fetch_ops_stats_reads_user_and_suno_windows() -> None:
    from platform_api.services.telegram_ops_commands import fetch_ops_stats

    class FakePool:
        async def fetchrow(self, query: str, *args: object) -> dict[str, int]:
            assert "AS yesterday" in query
            assert "d10" not in query
            if "FROM users" in query:
                return {"today": 1, "yesterday": 0, "d7": 2, "d30": 4}
            assert "FROM suno_tasks" in query
            return {"today": 5, "yesterday": 3, "d7": 6, "d30": 8}

    stats = await fetch_ops_stats(FakePool())
    assert stats["users"]["today"] == 1
    assert stats["users"]["yesterday"] == 0
    assert stats["users"]["d30"] == 4
    assert stats["songs"]["today"] == 5
    assert stats["songs"]["yesterday"] == 3
    assert "d10" not in stats["songs"]


def test_web_credit_sql_attaches_filter_to_sum() -> None:
    from platform_api.services.telegram_ops_commands import _WEB_CREDIT_SQL

    compact = " ".join(_WEB_CREDIT_SQL.split())
    assert "SUM(-amount) FILTER" in compact
    assert "COALESCE(SUM(-amount), 0) FILTER" not in compact


def test_parse_ops_command_burncredit() -> None:
    from platform_api.services.telegram_ops_commands import parse_ops_command

    assert parse_ops_command("/stats") == ("stats", "")
    assert parse_ops_command("/burncredit") == ("burncredit", "all")
    assert parse_ops_command("/burncredit@CamxoraBot web") == ("burncredit", "web")
    assert parse_ops_command("/burncredit studio") == ("burncredit", "studio")
    assert parse_ops_command("/burncredit desktop") == ("burncredit", "studio")
    assert parse_ops_command("/burncredit both") == ("burncredit", "both")
    assert parse_ops_command("burncredit web") == ("burncredit", "web")
    assert parse_ops_command("/burncredit nope") == ("burncredit", "help")
    assert parse_ops_command("hello") is None


def test_format_burn_table_has_songs_credits_and_usd() -> None:
    from platform_api.services.telegram_ops_commands import format_burn_table

    text = format_burn_table(
        "Web music",
        {"today": 10, "yesterday": 4, "d7": 20, "d30": 40},
        {"today": 50, "yesterday": 20, "d7": 100, "d30": 200},
    )
    assert "<b>Web music</b>" in text
    assert "<b>Today</b>" in text
    assert "10 songs · 50 cr" in text
    assert "$0.60" in text
    assert "$2.40" in text  # 40 songs * 0.06
    assert "<pre>" not in text


def test_format_burncredit_message_scopes() -> None:
    from platform_api.services.telegram_ops_commands import format_burncredit_message

    empty = {"today": 0, "yesterday": 0, "d7": 0, "d30": 0}
    kwargs = dict(
        env_label="Production",
        web_songs=empty,
        web_credits=empty,
        studio_songs=empty,
        studio_credits=empty,
        both_songs=empty,
        both_credits=empty,
    )
    web = format_burncredit_message(scope="web", **kwargs)
    assert "Web music" in web
    assert "Desktop studio" not in web
    assert "Both" not in web
    all_tables = format_burncredit_message(scope="all", **kwargs)
    assert "Web music" in all_tables
    assert "Desktop studio" in all_tables
    assert "Both" in all_tables
    daily = format_burncredit_message(
        scope="all",
        headline="Daily 10:00 PM report (Asia/Phnom_Penh)",
        **kwargs,
    )
    assert "Daily 10:00 PM report" in daily


@pytest.mark.asyncio
async def test_fetch_burncredit_stats_splits_web_and_studio() -> None:
    from platform_api.services.telegram_ops_commands import fetch_burncredit_stats

    class FakePool:
        async def fetchrow(self, query: str, *args: object) -> dict[str, int]:
            if "FROM suno_tasks" in query and "source = 'web_music'" in query:
                return {"today": 10, "yesterday": 5, "d7": 20, "d30": 40}
            if "FROM suno_tasks" in query:
                return {"today": 2, "yesterday": 1, "d7": 8, "d30": 16}
            if "SUM(-amount)" in query:
                return {"today": 50, "yesterday": 20, "d7": 100, "d30": 200}
            return {"today": 10000, "yesterday": 20000, "d7": 30000, "d30": 40000}

    stats = await fetch_burncredit_stats(FakePool())
    assert stats["web"]["songs"]["today"] == 10
    assert stats["web"]["credits"]["today"] == 50
    assert stats["studio"]["songs"]["today"] == 2
    assert stats["studio"]["credits"]["today"] == 1.0
    assert stats["both"]["songs"]["today"] == 12
    assert stats["both"]["credits"]["today"] == 51.0


def test_daily_burncredit_schedule() -> None:
    from datetime import datetime

    from platform_api.services.billing_calendar import BILLING_TIMEZONE
    from platform_api.services.telegram_ops_commands import (
        daily_burncredit_should_send,
        next_daily_burncredit_at,
        seconds_until_daily_burncredit_check,
    )

    at_2159 = datetime(2026, 8, 19, 21, 59, tzinfo=BILLING_TIMEZONE)
    at_2200 = datetime(2026, 8, 19, 22, 0, tzinfo=BILLING_TIMEZONE)
    assert daily_burncredit_should_send(at_2159, None) is False
    assert daily_burncredit_should_send(at_2200, None) is True
    assert daily_burncredit_should_send(at_2200, "2026-08-19") is False
    assert daily_burncredit_should_send(at_2200, "2026-08-18") is True
    nxt = next_daily_burncredit_at(at_2159)
    assert nxt.hour == 22 and nxt.date().isoformat() == "2026-08-19"
    nxt_after = next_daily_burncredit_at(at_2200)
    assert nxt_after.date().isoformat() == "2026-08-20"
    assert seconds_until_daily_burncredit_check(at_2200, last_sent_date=None) == 1.0
    assert seconds_until_daily_burncredit_check(at_2200, last_sent_date="2026-08-19") > 60

