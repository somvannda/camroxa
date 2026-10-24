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


def test_notify_provider_capacity_failure_is_debounced(monkeypatch) -> None:
    from platform_api.services import telegram_ops_alert_service as svc

    sent: list[str] = []
    monkeypatch.setattr(
        svc, "schedule_ops_message", lambda text, **kwargs: sent.append(text)
    )
    svc._provider_capacity_alert_last.clear()
    try:
        svc.notify_provider_capacity_failure(
            failure_type="provider_capacity",
            error_message="No paid Suno account is available for this model.",
            batch_id="b1",
            song_id="s1",
        )
        # Same failure type within the cooldown window must not send again.
        svc.notify_provider_capacity_failure(
            failure_type="provider_capacity",
            error_message="No paid Suno account is available for this model.",
            batch_id="b1",
            song_id="s2",
        )
        assert len(sent) == 1
        assert "SUNO PROVIDER UNAVAILABLE" in sent[0]
        assert "No paid Suno account" in sent[0]

        # A distinct failure type is tracked separately.
        svc.notify_provider_capacity_failure(failure_type="provider_capacity_credits")
        assert len(sent) == 2
    finally:
        svc._provider_capacity_alert_last.clear()


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


def test_format_spend_shows_model_version() -> None:
    text = format_ops_message(
        kind="spend",
        env_label="Production",
        account_status="FREE",
        activity="music",
        model="V6_WILD",
        credits_label="10",
        pool="web music",
        reason="v3_music",
        user_id="abc",
    )
    assert "model: <b>v6 wild</b>" in text
    assert "pool: web music" in text

    from platform_api.services.telegram_ops_alert_service import _model_label

    assert _model_label("V6") == "v6 pro"
    assert _model_label("V6_MINI") == "v6 mini"


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


def test_chunk_text_keeps_every_line() -> None:
    from platform_api.services.telegram_ops_alert_service import _chunk_text

    body = "\n".join(f"line {i} " + "x" * 120 for i in range(80))
    chunks = _chunk_text(body)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4000 for chunk in chunks)
    assert "".join(chunks) == body


@pytest.mark.asyncio
async def test_send_html_retries_429(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.services import telegram_ops_alert_service as mod

    class _Resp:
        def __init__(self, status: int, body: str = "") -> None:
            self.status_code = status
            self.text = body

        def json(self):  # type: ignore[no-untyped-def]
            return {"ok": False, "parameters": {"retry_after": 1}}

    async def _enabled() -> bool:
        return True

    async def _no_sleep(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(mod, "_runtime_enabled", _enabled)
    monkeypatch.setattr(mod.asyncio, "sleep", _no_sleep)
    client = AsyncMock()
    client.post = AsyncMock(side_effect=[_Resp(429, "rate limited"), _Resp(200, "ok")])
    service = mod.TelegramOpsAlertService(
        bot_token="123:abc",
        chat_id="-1001",
        enabled=True,
        env_label="Production",
        http_client=client,
    )
    assert await service.send_html("hello") is True
    assert client.post.await_count == 2


@pytest.mark.asyncio
async def test_send_html_records_delivery_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import telegram_ops_alert_service as mod

    class _Resp:
        status_code = 200
        text = "ok"

    async def _enabled() -> bool:
        return True

    logged: list[tuple[str, str, int | None]] = []

    async def _log(chat_id, *, kind, text, status, http_status=None):  # type: ignore[no-untyped-def]
        logged.append((kind, status, http_status))

    monkeypatch.setattr(mod, "_runtime_enabled", _enabled)
    monkeypatch.setattr(mod, "_log_delivery", _log)
    client = AsyncMock()
    client.post = AsyncMock(return_value=_Resp())
    service = mod.TelegramOpsAlertService(
        bot_token="123:abc",
        chat_id="-1001",
        enabled=True,
        env_label="Production",
        http_client=client,
    )
    assert await service.send_html("hello", kind="spend") is True
    assert logged == [("spend", "sent", 200)]


def test_install_telegram_ops_hooks_is_idempotent() -> None:
    from platform_api.services.telegram_ops_alert_service import install_telegram_ops_hooks

    install_telegram_ops_hooks()
    install_telegram_ops_hooks()


def test_get_telegram_ops_service_is_production_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sandbox/staging reuse production's bot/chat, so delivery is gated."""
    from platform_api.services import telegram_ops_alert_service as mod

    monkeypatch.setenv("PLATFORM_TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("PLATFORM_TELEGRAM_CHAT_ID", "-1001")
    monkeypatch.setenv("PLATFORM_TELEGRAM_OPS_ENABLED", "true")

    monkeypatch.setattr(mod, "is_production", lambda: False)
    assert mod.get_telegram_ops_service() is None

    monkeypatch.setattr(mod, "is_production", lambda: True)
    assert mod.get_telegram_ops_service() is not None


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


def test_burn_sql_proves_web_attribution_and_scales_v3_units() -> None:
    from platform_api.services.telegram_ops_commands import _BURN_SQL

    compact = " ".join(_BURN_SQL.split())
    # Web music is proven by the ref_id -> suno_tasks join, not by reason text.
    assert "suno_tasks t" in compact
    assert "v3_" in compact
    assert "ABS(ct.amount)" in compact
    assert "per_credit" in compact
    assert "10000.0" in compact
    assert "consumed_web_music%" in compact
    assert "metadata->>'product'" in compact


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
async def test_fetch_burncredit_stats_uses_proven_families() -> None:
    from platform_api.services.telegram_ops_commands import fetch_burncredit_stats

    class FakePool:
        async def fetchrow(self, query: str, *args: object) -> dict[str, int]:
            if "source = 'web_music'" in query:
                return {"today": 10, "yesterday": 5, "d7": 20, "d30": 40}
            assert "COALESCE(source, 'studio')" in query
            return {"today": 2, "yesterday": 1, "d7": 8, "d30": 16}

        async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
            assert "GROUP BY family" in query
            return [
                {"family": "web", "today": 930, "yesterday": 10, "d7": 3490, "d30": 5000},
                {"family": "studio", "today": 28, "yesterday": 4, "d7": 6050, "d30": 9000},
                {"family": "unattributed", "today": 12, "yesterday": 3, "d7": 2380, "d30": 3000},
            ]

    stats = await fetch_burncredit_stats(FakePool())
    assert stats["web"]["songs"]["today"] == 10
    assert stats["web"]["credits"]["today"] == 930.0
    assert stats["studio"]["credits"]["today"] == 28.0
    # "Both" is web + studio only; shared infrastructure stays separate.
    assert stats["both"]["credits"]["today"] == 958.0
    assert stats["unattributed"]["credits"]["d7"] == 2380.0
    assert stats["both"]["songs"]["today"] == 12


def test_format_burncredit_message_shows_shared_bucket() -> None:
    from platform_api.services.telegram_ops_commands import format_burncredit_message

    empty = {"today": 0, "yesterday": 0, "d7": 0, "d30": 0}
    text = format_burncredit_message(
        env_label="Production",
        scope="both",
        web_songs=empty,
        web_credits={"today": 930, "yesterday": 0, "d7": 3490, "d30": 0},
        studio_songs=empty,
        studio_credits={"today": 28, "yesterday": 0, "d7": 6050, "d30": 0},
        both_songs=empty,
        both_credits={"today": 958, "yesterday": 0, "d7": 9540, "d30": 0},
        unattributed_credits={"today": 12, "yesterday": 0, "d7": 2380, "d30": 0},
    )
    assert "Shared (image/lyric/title" in text
    assert "Today 12 cr" in text
    assert "2380" in text


@pytest.mark.asyncio
async def test_fetch_platform_revenue_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.services import telegram_ops_commands as mod

    calls: list[tuple[object, object]] = []

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            pass

        async def sum_fulfilled_subscription_revenue(
            self, *, user_id=None, from_date=None, to_date=None
        ) -> dict[str, int]:
            calls.append((from_date, to_date))
            return {
                "subscription_revenue_cents": 1250 if len(calls) == 1 else 5000,
                "credit_pack_revenue_cents": 300,
            }

    monkeypatch.setattr(
        "platform_api.repositories.credit_repo.CreditRepository", _FakeRepo
    )
    revenue = await mod.fetch_platform_revenue(object())
    assert revenue["today_cents"] == 1250.0
    assert revenue["d7_cents"] == 5000.0
    assert revenue["pack_today_cents"] == 300.0
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_fetch_musicapi_revenue_groups_by_currency() -> None:
    from platform_api.services import telegram_ops_commands as mod

    captured: dict[str, object] = {}

    class FakeConn:
        async def fetch(self, query: str, *args: object):
            assert "payment_transactions" in query
            captured["args"] = args
            return [
                {"currency": "khr", "today": 12000, "d7": 40000},
                {"currency": "usd", "today": 3.5, "d7": 10},
            ]

        async def close(self) -> None:
            captured["closed"] = True

    async def fake_connect(dsn: str):
        captured["dsn"] = dsn
        return FakeConn()

    revenue = await mod.fetch_musicapi_revenue(
        dsn="postgresql+asyncpg://u:p@localhost/sunoapi",
        connect=fake_connect,
    )
    assert captured["dsn"] == "postgresql://u:p@localhost/sunoapi"
    assert captured["closed"] is True
    assert revenue["KHR"] == {"today": 12000.0, "d7": 40000.0}
    assert revenue["USD"]["today"] == 3.5


@pytest.mark.asyncio
async def test_fetch_musicapi_revenue_is_optional_and_safe() -> None:
    from platform_api.services import telegram_ops_commands as mod

    assert await mod.fetch_musicapi_revenue(dsn="") == {}

    async def failing_connect(dsn: str):
        raise RuntimeError("musicapi db down")

    assert (
        await mod.fetch_musicapi_revenue(
            dsn="postgresql://x", connect=failing_connect
        )
        == {}
    )


def test_format_revenue_line_includes_both_products() -> None:
    from platform_api.services.telegram_ops_commands import format_revenue_line

    line = format_revenue_line(
        {"today_cents": 1250, "d7_cents": 5000},
        {
            "KHR": {"today": 12000, "d7": 40000},
            "USD": {"today": 3.5, "d7": 10},
        },
    )
    assert "platform <b>$12.50</b> (7d $50.00)" in line
    assert "musicapi <b>KHR 12,000</b> (7d 40,000)" in line
    assert "musicapi <b>$3.50</b> (7d $10.00)" in line


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


class _FakeRedis:
    """Minimal async redis surface used by the daily-report claim."""

    def __init__(self, store: dict[str, str] | None = None) -> None:
        self.store = dict(store or {})
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(
        self, key: str, value: str, *, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.store.pop(key, None)


def _fixed_2200(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime

    from platform_api.services.billing_calendar import BILLING_TIMEZONE
    from platform_api.services import telegram_ops_commands as mod

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return datetime(2026, 10, 20, 22, 30, tzinfo=BILLING_TIMEZONE)

    monkeypatch.setattr(mod, "datetime", FixedDatetime)


@pytest.mark.asyncio
async def test_daily_report_marks_sent_only_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import telegram_ops_commands as mod

    sent: list[int] = []

    async def _send() -> None:
        sent.append(1)

    redis = _FakeRedis()
    monkeypatch.setattr(mod, "_try_redis", lambda: redis)
    monkeypatch.setattr(mod, "_send_daily_burncredit", _send)
    _fixed_2200(monkeypatch)

    assert await mod._maybe_send_daily_burncredit() is True
    assert sent == [1]
    assert redis.store[mod._daily_key("2026-10-20")] == "1"

    # A completed day is a no-op, not a second post.
    assert await mod._maybe_send_daily_burncredit() is True
    assert sent == [1]


@pytest.mark.asyncio
async def test_daily_report_failure_clears_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import telegram_ops_commands as mod

    async def _boom() -> None:
        raise RuntimeError("telegram down")

    redis = _FakeRedis()
    monkeypatch.setattr(mod, "_try_redis", lambda: redis)
    monkeypatch.setattr(mod, "_send_daily_burncredit", _boom)
    _fixed_2200(monkeypatch)

    with pytest.raises(RuntimeError):
        await mod._maybe_send_daily_burncredit()
    assert mod._daily_key("2026-10-20") not in redis.store


@pytest.mark.asyncio
async def test_daily_report_in_progress_claim_retries_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import telegram_ops_commands as mod

    async def _send() -> None:  # pragma: no cover - must not be called
        raise AssertionError("another worker owns the in-progress claim")

    redis = _FakeRedis({mod._daily_key("2026-10-20"): "sending"})
    monkeypatch.setattr(mod, "_try_redis", lambda: redis)
    monkeypatch.setattr(mod, "_send_daily_burncredit", _send)
    _fixed_2200(monkeypatch)

    assert await mod._daily_sent_date(redis) is None
    assert await mod._maybe_send_daily_burncredit() is False

