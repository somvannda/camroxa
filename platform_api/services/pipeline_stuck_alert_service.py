"""Scheduled stuck-pipeline detection + admin alert.

See `docs/PLATFORM_WORKERS_REQUIREMENTS.md` §8 ("Pipeline failure detection,
admin alerting, and retry/recovery"): today, "stuck" batches are only visible
if an admin happens to have Pipeline Ops open, because nothing scans for them
proactively. This mirrors the existing `AbuseAlertService` pattern — a Redis
cooldown per batch prevents re-alerting on every scan cycle, and alerts fan
out to every admin user via the same `NotificationService` WebSocket push
already used for `admin:abuse_alert` / `admin:low_balance_alert`.

No dedicated `platform_worker` process exists yet, so this is intended to be
driven by an in-process scheduled loop (see `platform_api/main.py` lifespan)
until that infra lands — the detection/alerting logic itself has no
dependency on how it's scheduled.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class BatchRepoProtocol(Protocol):
    async def list_stuck_batches(self, *, min_age_seconds: int, limit: int) -> list[dict[str, Any]]: ...


class RedisProtocol(Protocol):
    async def get(self, key: str) -> str | bytes | None: ...

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> Any: ...


class NotificationServiceProtocol(Protocol):
    async def push(self, user_id: str, event: str, payload: dict) -> None: ...


class AdminUserProviderProtocol(Protocol):
    async def get_admin_user_ids(self) -> list[str]: ...


class PipelineStuckAlertService:
    """Scan for batches with no pipeline activity for too long and alert admins."""

    def __init__(
        self,
        *,
        batch_repo: BatchRepoProtocol,
        redis: RedisProtocol,
        notification_service: NotificationServiceProtocol | None = None,
        admin_provider: AdminUserProviderProtocol | None = None,
        stuck_threshold_seconds: int = 900,
        alert_cooldown_seconds: int = 1800,
        scan_limit: int = 50,
    ) -> None:
        self._batch_repo = batch_repo
        self._redis = redis
        self._notification_service = notification_service
        self._admin_provider = admin_provider
        self._stuck_threshold_seconds = max(60, stuck_threshold_seconds)
        self._alert_cooldown_seconds = max(60, alert_cooldown_seconds)
        self._scan_limit = max(1, min(200, scan_limit))

    async def scan_and_alert(self) -> list[dict[str, Any]]:
        """Find stuck batches and push a throttled admin alert for each.

        Returns every stuck batch found this scan (alerted or still cooling
        down) so callers/tests can distinguish "found but throttled" from
        "found nothing" — never raises, so a scan failure can't crash the
        scheduling loop that calls this on a timer.
        """
        try:
            stuck_batches = await self._batch_repo.list_stuck_batches(
                min_age_seconds=self._stuck_threshold_seconds,
                limit=self._scan_limit,
            )
        except Exception as exc:
            logger.error("Pipeline stuck-batch scan failed: %s", exc)
            return []

        for row in stuck_batches:
            try:
                await self._maybe_alert(row)
            except Exception as exc:
                logger.warning("Failed to alert for stuck batch %s: %s", row.get("batch_id"), exc)
        return stuck_batches

    async def _maybe_alert(self, row: dict[str, Any]) -> None:
        batch_id = str(row.get("batch_id"))
        cooldown_key = f"pipeline:stuck:cooldown:{batch_id}"

        set_fn = getattr(self._redis, "set", None)
        if set_fn is not None:
            # nx=True → only the first scan cycle to see this batch in the cooldown
            # window actually alerts; later cycles just re-detect it silently.
            try:
                acquired = await set_fn(cooldown_key, "1", ex=self._alert_cooldown_seconds, nx=True)
            except TypeError:
                # Fake redis / limited clients may not support the nx kwarg.
                existing = await self._redis.get(cooldown_key)
                if existing is not None:
                    return
                await self._redis.set(cooldown_key, "1", ex=self._alert_cooldown_seconds)
                acquired = True
            if not acquired:
                return

        age_seconds = int(row.get("age_seconds") or 0)
        user_label = row.get("user_email") or row.get("user_id")
        payload = {
            "kind": "pipeline_stuck",
            "severity": "warning",
            "batch_id": batch_id,
            "user_id": str(row["user_id"]) if row.get("user_id") else None,
            "user_email": row.get("user_email"),
            "status": row.get("status"),
            "age_seconds": age_seconds,
            "message": (
                f"Batch {batch_id} ({user_label}) has had no pipeline activity for "
                f"{age_seconds // 60} min and is not fully complete."
            ),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        logger.warning("Pipeline stuck alert: %s", payload["message"])

        if self._notification_service is None or self._admin_provider is None:
            return
        try:
            admin_ids = await self._admin_provider.get_admin_user_ids()
        except Exception as exc:
            logger.error("Failed to load admin IDs for pipeline stuck alert: %s", exc)
            return

        for admin_id in admin_ids:
            try:
                await self._notification_service.push(admin_id, "admin:pipeline_stuck_alert", payload)
            except Exception as exc:
                logger.warning(
                    "Failed to push pipeline stuck alert to admin %s: %s",
                    admin_id,
                    str(exc)[:100],
                )


# Process-wide optional singleton wired at app startup (mirrors abuse_alert_service.py).
_pipeline_stuck_alert_service: PipelineStuckAlertService | None = None


def set_pipeline_stuck_alert_service(service: PipelineStuckAlertService | None) -> None:
    global _pipeline_stuck_alert_service
    _pipeline_stuck_alert_service = service


def get_pipeline_stuck_alert_service() -> PipelineStuckAlertService | None:
    return _pipeline_stuck_alert_service
