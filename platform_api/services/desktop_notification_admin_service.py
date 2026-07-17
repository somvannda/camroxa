"""Admin-managed desktop push notifications and software update publishing."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from platform_api.services.billing_config_service import load_system_setting
from platform_api.services.workspace_notifications import (
    SOFTWARE_UPDATE_AVAILABLE_EVENT,
    notify_software_update_available,
)

logger = logging.getLogger(__name__)

NOTIFICATION_MESSAGE_EVENT = "notification.message"

SOFTWARE_UPDATE_VERSION_KEY = "desktop.software_update.version"
SOFTWARE_UPDATE_DOWNLOAD_URL_KEY = "desktop.software_update.download_url"
SOFTWARE_UPDATE_MANDATORY_KEY = "desktop.software_update.mandatory"
SOFTWARE_UPDATE_RELEASE_NOTES_KEY = "desktop.software_update.release_notes"
SOFTWARE_UPDATE_PUBLISHED_AT_KEY = "desktop.software_update.published_at"
PUSH_NOTIFICATION_HISTORY_KEY = "desktop.push_notifications.history"

MAX_HISTORY_ITEMS = 25


@dataclass(frozen=True, slots=True)
class SoftwareUpdateConfig:
    version: str
    download_url: str
    mandatory: bool
    release_notes: str
    published_at: str | None


@dataclass(frozen=True, slots=True)
class PushNotificationHistoryItem:
    id: str
    title: str
    message: str
    created_at: str
    recipients: int


def _parse_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def _upsert_system_setting(
    pool: Any,
    *,
    key: str,
    value: str,
    value_type: str = "string",
) -> None:
    await pool.execute(
        """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        key,
        value,
        value_type,
    )


async def list_active_user_ids(pool: Any) -> list[str]:
    rows = await pool.fetch(
        """
        SELECT id::text AS user_id
        FROM users
        WHERE deleted_at IS NULL
          AND status = 'active'
        """
    )
    return [str(row["user_id"]) for row in rows]


async def get_software_update_config(pool: Any) -> SoftwareUpdateConfig:
    version = await load_system_setting(pool, SOFTWARE_UPDATE_VERSION_KEY) or ""
    download_url = await load_system_setting(pool, SOFTWARE_UPDATE_DOWNLOAD_URL_KEY) or ""
    mandatory = _parse_bool(await load_system_setting(pool, SOFTWARE_UPDATE_MANDATORY_KEY))
    release_notes = await load_system_setting(pool, SOFTWARE_UPDATE_RELEASE_NOTES_KEY) or ""
    published_at = await load_system_setting(pool, SOFTWARE_UPDATE_PUBLISHED_AT_KEY)
    return SoftwareUpdateConfig(
        version=version,
        download_url=download_url,
        mandatory=mandatory,
        release_notes=release_notes,
        published_at=published_at,
    )


async def save_software_update_config(
    pool: Any,
    *,
    version: str,
    download_url: str,
    mandatory: bool,
    release_notes: str,
) -> SoftwareUpdateConfig:
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_VERSION_KEY, value=version.strip())
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_DOWNLOAD_URL_KEY, value=download_url.strip())
    await _upsert_system_setting(
        pool,
        key=SOFTWARE_UPDATE_MANDATORY_KEY,
        value="true" if mandatory else "false",
        value_type="boolean",
    )
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_RELEASE_NOTES_KEY, value=release_notes.strip())
    return await get_software_update_config(pool)


async def publish_software_update(pool: Any) -> tuple[SoftwareUpdateConfig, int]:
    config = await get_software_update_config(pool)
    if not config.version.strip():
        raise ValueError("Software update version is required before publishing.")

    published_at = datetime.now(timezone.utc).isoformat()
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_PUBLISHED_AT_KEY, value=published_at)

    user_ids = await list_active_user_ids(pool)
    for user_id in user_ids:
        await notify_software_update_available(
            user_id,
            version=config.version.strip(),
            download_url=config.download_url.strip() or None,
            mandatory=config.mandatory,
            release_notes=config.release_notes.strip() or None,
        )

    published_config = SoftwareUpdateConfig(
        version=config.version,
        download_url=config.download_url,
        mandatory=config.mandatory,
        release_notes=config.release_notes,
        published_at=published_at,
    )
    return published_config, len(user_ids)


async def _load_push_history(pool: Any) -> list[PushNotificationHistoryItem]:
    raw = await load_system_setting(pool, PUSH_NOTIFICATION_HISTORY_KEY)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    items: list[PushNotificationHistoryItem] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        items.append(
            PushNotificationHistoryItem(
                id=str(entry.get("id") or ""),
                title=str(entry.get("title") or ""),
                message=str(entry.get("message") or ""),
                created_at=str(entry.get("created_at") or ""),
                recipients=int(entry.get("recipients") or 0),
            )
        )
    return [item for item in items if item.id and item.title]


async def _save_push_history(pool: Any, items: list[PushNotificationHistoryItem]) -> None:
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "message": item.message,
            "created_at": item.created_at,
            "recipients": item.recipients,
        }
        for item in items[:MAX_HISTORY_ITEMS]
    ]
    await _upsert_system_setting(
        pool,
        key=PUSH_NOTIFICATION_HISTORY_KEY,
        value=json.dumps(payload),
        value_type="json",
    )


async def list_push_notification_history(pool: Any) -> list[PushNotificationHistoryItem]:
    return await _load_push_history(pool)


async def send_push_notification(
    pool: Any,
    *,
    title: str,
    message: str,
) -> tuple[PushNotificationHistoryItem, int]:
    from platform_api.dependencies import get_notification_service

    notification_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "notification_id": notification_id,
        "title": title.strip(),
        "message": message.strip(),
        "created_at": created_at,
    }

    service = get_notification_service()
    user_ids = await list_active_user_ids(pool)
    for user_id in user_ids:
        await service.push(user_id, NOTIFICATION_MESSAGE_EVENT, payload)

    history_item = PushNotificationHistoryItem(
        id=notification_id,
        title=payload["title"],
        message=payload["message"],
        created_at=created_at,
        recipients=len(user_ids),
    )
    history = [history_item, *(await _load_push_history(pool))]
    await _save_push_history(pool, history)
    logger.info(
        "Broadcast %s to %d users (notification_id=%s)",
        NOTIFICATION_MESSAGE_EVENT,
        len(user_ids),
        notification_id,
    )
    return history_item, len(user_ids)
