"""Push notifications when workspace-related user data changes."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

WORKSPACE_CHANGED_EVENT = "workspace.changed"
SOFTWARE_UPDATE_AVAILABLE_EVENT = "software_update.available"


async def notify_workspace_changed(
    user_id: str,
    *,
    source: str,
    scope: str | None = None,
    extra: dict | None = None,
) -> None:
    """Notify connected desktop clients that workspace data changed."""
    from platform_api.dependencies import get_notification_service

    payload: dict = {
        "source": source,
        "scope": scope or source,
    }
    if extra:
        payload.update(extra)

    try:
        service = get_notification_service()
        await service.push(user_id, WORKSPACE_CHANGED_EVENT, payload)
    except Exception as exc:
        logger.debug(
            "Failed to push %s for user %s: %s",
            WORKSPACE_CHANGED_EVENT,
            user_id,
            str(exc)[:120],
        )


async def notify_software_update_available(
    user_id: str,
    *,
    version: str,
    download_url: str | None = None,
    mandatory: bool = False,
    release_notes: str | None = None,
) -> None:
    """Push a software-update notification (future desktop auto-update flow)."""
    from platform_api.dependencies import get_notification_service

    payload = {
        "version": version,
        "download_url": download_url,
        "mandatory": mandatory,
        "release_notes": release_notes or "",
    }
    try:
        service = get_notification_service()
        await service.push(user_id, SOFTWARE_UPDATE_AVAILABLE_EVENT, payload)
    except Exception as exc:
        logger.debug(
            "Failed to push %s for user %s: %s",
            SOFTWARE_UPDATE_AVAILABLE_EVENT,
            user_id,
            str(exc)[:120],
        )
