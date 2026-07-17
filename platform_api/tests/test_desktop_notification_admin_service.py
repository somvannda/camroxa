from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from platform_api.services.desktop_notification_admin_service import (
    NOTIFICATION_MESSAGE_EVENT,
    SOFTWARE_UPDATE_VERSION_KEY,
    get_software_update_config,
    publish_software_update,
    save_software_update_config,
    send_push_notification,
)


class _FakePool:
    def __init__(self, settings: dict[str, str] | None = None) -> None:
        self.settings = dict(settings or {})
        self.executed: list[tuple] = []

    async def fetchrow(self, query: str, key: str):
        value = self.settings.get(key)
        if value is None:
            return None
        return {"value": value}

    async def fetch(self, query: str):
        if "FROM users" in query:
            return [{"user_id": "user-1"}, {"user_id": "user-2"}]
        return []

    async def execute(self, query: str, *args):
        self.executed.append((query, args))
        if "INSERT INTO system_settings" in query and len(args) >= 2:
            self.settings[str(args[0])] = str(args[1])


@pytest.mark.asyncio
async def test_get_software_update_config_reads_settings() -> None:
    pool = _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "2.5.0",
            "desktop.software_update.download_url": "https://example.com/app.exe",
            "desktop.software_update.mandatory": "true",
            "desktop.software_update.release_notes": "Bug fixes",
        }
    )
    config = await get_software_update_config(pool)
    assert config.version == "2.5.0"
    assert config.download_url.endswith("app.exe")
    assert config.mandatory is True
    assert config.release_notes == "Bug fixes"


@pytest.mark.asyncio
async def test_save_software_update_config_persists_values() -> None:
    pool = _FakePool()
    config = await save_software_update_config(
        pool,
        version="3.0.0",
        download_url="https://example.com/v3",
        mandatory=False,
        release_notes="Initial release",
    )
    assert config.version == "3.0.0"
    assert pool.settings[SOFTWARE_UPDATE_VERSION_KEY] == "3.0.0"


@pytest.mark.asyncio
async def test_publish_software_update_requires_version() -> None:
    pool = _FakePool()
    with pytest.raises(ValueError, match="version is required"):
        await publish_software_update(pool)


@pytest.mark.asyncio
async def test_publish_software_update_broadcasts_to_users() -> None:
    pool = _FakePool({SOFTWARE_UPDATE_VERSION_KEY: "2.5.0"})
    with patch(
        "platform_api.services.desktop_notification_admin_service.notify_software_update_available",
        new=AsyncMock(),
    ) as notify_mock:
        config, recipients = await publish_software_update(pool)
    assert recipients == 2
    assert config.version == "2.5.0"
    assert notify_mock.await_count == 2


@pytest.mark.asyncio
async def test_send_push_notification_broadcasts_message_event() -> None:
    pool = _FakePool()
    notification_service = AsyncMock()
    notification_service.push = AsyncMock()

    with patch(
        "platform_api.dependencies.get_notification_service",
        return_value=notification_service,
    ):
        history_item, recipients = await send_push_notification(
            pool,
            title="Maintenance",
            message="Desktop app will restart at midnight.",
        )

    assert recipients == 2
    assert history_item.title == "Maintenance"
    notification_service.push.assert_awaited()
    first_call = notification_service.push.await_args_list[0]
    assert first_call.args[1] == NOTIFICATION_MESSAGE_EVENT
    assert first_call.args[2]["title"] == "Maintenance"
