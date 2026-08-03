"""Admin Pipeline Ops board WebSocket invalidate pings (P4.6)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

PIPELINE_BOARD_CHANGED_EVENT = "admin:pipeline.board.changed"
_DEBOUNCE_SECONDS = 2


async def notify_pipeline_board_changed(
    *,
    batch_id: str | None = None,
    reason: str = "batch_status",
) -> None:
    """Fan out a lightweight board-changed ping to connected admins.

    Debounced globally (~2s) so chatty status updates do not spam sockets.
    Ephemeral: not queued for offline admins.
    """
    try:
        from platform_api.dependencies import get_db_pool, get_notification_service

        redis = None
        try:
            from platform_api.dependencies import get_redis

            redis = get_redis()
        except Exception:
            redis = None

        debounce_key = "pipeline:board:changed:debounce"
        if redis is not None:
            try:
                acquired = await redis.set(
                    debounce_key,
                    "1",
                    ex=_DEBOUNCE_SECONDS,
                    nx=True,
                )
                if not acquired:
                    return
            except Exception:
                logger.debug("Pipeline board debounce unavailable", exc_info=True)

        pool = get_db_pool()
        rows = await pool.fetch("SELECT id FROM users WHERE role = 'admin'")
        admin_ids = [str(row["id"]) for row in rows]
        if not admin_ids:
            return

        payload: dict[str, Any] = {
            "batch_id": batch_id,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        service = get_notification_service()
        # Live-only: NotificationService.push queues when offline — skip by
        # checking live connections when available.
        push_live = getattr(service, "push_live", None)
        for admin_id in admin_ids:
            try:
                if callable(push_live):
                    await push_live(admin_id, PIPELINE_BOARD_CHANGED_EVENT, payload)
                else:
                    await service.push(admin_id, PIPELINE_BOARD_CHANGED_EVENT, payload)
            except Exception:
                logger.debug(
                    "Failed pipeline board ping for admin %s",
                    admin_id,
                    exc_info=True,
                )
    except Exception:
        logger.debug("notify_pipeline_board_changed failed", exc_info=True)
