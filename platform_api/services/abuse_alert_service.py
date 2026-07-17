"""Abuse / anomaly alerts pushed to Admin WebSockets (Phase 3).

Tracks absorb spikes, polish-probe storms, rapid redeem bursts, and
zero-dollar fulfillment attempts. Uses Redis counters with cooldown so
admins are not spammed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_COOLDOWN_SECONDS = 300


class RedisProtocol(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> Any: ...

    async def get(self, key: str) -> str | bytes | None: ...

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> Any: ...


class NotificationServiceProtocol(Protocol):
    async def push(self, user_id: str, event: str, payload: dict) -> None: ...


class AdminUserProviderProtocol(Protocol):
    async def get_admin_user_ids(self) -> list[str]: ...


class AbuseAlertService:
    """Record abuse signals and fan out throttled admin alerts."""

    def __init__(
        self,
        *,
        redis: RedisProtocol,
        notification_service: NotificationServiceProtocol | None = None,
        admin_provider: AdminUserProviderProtocol | None = None,
        absorb_alert_threshold: int = 20,
        polish_probe_threshold: int = 10,
        redeem_burst_threshold: int = 5,
        redeem_burst_window_seconds: int = 300,
    ) -> None:
        self._redis = redis
        self._notification_service = notification_service
        self._admin_provider = admin_provider
        self._absorb_alert_threshold = max(1, absorb_alert_threshold)
        self._polish_probe_threshold = max(1, polish_probe_threshold)
        self._redeem_burst_threshold = max(1, redeem_burst_threshold)
        self._redeem_burst_window = max(60, redeem_burst_window_seconds)

    async def note_absorb(self, *, user_id: str, count: int, budget: int) -> None:
        """Alert when absorb count approaches or exceeds the daily budget."""
        if budget <= 0:
            return
        warn_at = max(1, int(budget * 0.8))
        if count < warn_at and count < self._absorb_alert_threshold:
            return
        severity = "critical" if count >= budget else "warning"
        await self._emit(
            kind="absorb_spike",
            severity=severity,
            message=(
                f"Platform absorb count for user {user_id}: {count}/{budget} "
                f"(alert threshold {self._absorb_alert_threshold})."
            ),
            metadata={"user_id": user_id, "count": count, "budget": budget},
            cooldown_key=f"abuse:cooldown:absorb:{user_id}",
        )

    async def note_polish_probe(self, *, user_id: str | None = None) -> None:
        """Count polish 403 probes; alert on storm."""
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        key = f"abuse:polish_probe:{day}"
        count = await self._incr(key, ttl_seconds=86_400)
        if count < self._polish_probe_threshold:
            return
        await self._emit(
            kind="polish_probe_storm",
            severity="warning",
            message=(
                f"Polish endpoint probe storm: {count} POLISH_DISABLED hits today "
                f"(threshold {self._polish_probe_threshold})."
            ),
            metadata={"count": count, "user_id": user_id},
            cooldown_key="abuse:cooldown:polish_probe",
        )

    async def note_redeem(self, *, user_id: str) -> None:
        """Alert on rapid credit-code redeem bursts per user."""
        key = f"abuse:redeem_burst:{user_id}"
        count = await self._incr(key, ttl_seconds=self._redeem_burst_window)
        if count < self._redeem_burst_threshold:
            return
        await self._emit(
            kind="redeem_burst",
            severity="warning",
            message=(
                f"Rapid redeem burst for user {user_id}: {count} in "
                f"{self._redeem_burst_window}s "
                f"(threshold {self._redeem_burst_threshold})."
            ),
            metadata={"user_id": user_id, "count": count},
            cooldown_key=f"abuse:cooldown:redeem:{user_id}",
        )

    async def note_zero_dollar_fulfill(
        self,
        *,
        payment_id: str,
        external_payment_id: str | None = None,
        amount_cents: int | None = None,
    ) -> None:
        """Alert when a paid fulfill path would grant value for $0."""
        await self._emit(
            kind="zero_dollar_fulfill",
            severity="critical",
            message=(
                f"Zero-dollar fulfill attempt for payment {payment_id} "
                f"(external={external_payment_id}, amount_cents={amount_cents})."
            ),
            metadata={
                "payment_id": payment_id,
                "external_payment_id": external_payment_id,
                "amount_cents": amount_cents,
            },
            cooldown_key=f"abuse:cooldown:zero_dollar:{payment_id}",
        )

    async def _incr(self, key: str, *, ttl_seconds: int) -> int:
        incr = getattr(self._redis, "incr", None)
        if incr is not None:
            count = int(await incr(key))
            expire = getattr(self._redis, "expire", None)
            if expire is not None:
                await expire(key, ttl_seconds)
            return count
        raw = await self._redis.get(key)
        try:
            count = int(raw or 0) + 1
        except (TypeError, ValueError):
            count = 1
        await self._redis.set(key, str(count), ex=ttl_seconds)
        return count

    async def _emit(
        self,
        *,
        kind: str,
        severity: str,
        message: str,
        metadata: dict[str, Any],
        cooldown_key: str,
    ) -> None:
        set_fn = getattr(self._redis, "set", None)
        if set_fn is not None:
            # nx=True → only first writer in the cooldown window alerts
            try:
                acquired = await set_fn(cooldown_key, "1", ex=_COOLDOWN_SECONDS, nx=True)
            except TypeError:
                # Fake redis / limited clients may not support nx kwargs
                existing = await self._redis.get(cooldown_key)
                if existing is not None:
                    return
                await self._redis.set(cooldown_key, "1", ex=_COOLDOWN_SECONDS)
                acquired = True
            if not acquired:
                return

        payload = {
            "kind": kind,
            "severity": severity,
            "message": message,
            "metadata": metadata,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        logger.warning("Abuse alert [%s/%s]: %s", severity, kind, message)

        if self._notification_service is None or self._admin_provider is None:
            return
        try:
            admin_ids = await self._admin_provider.get_admin_user_ids()
        except Exception as exc:
            logger.error("Failed to load admin IDs for abuse alert: %s", exc)
            return

        for admin_id in admin_ids:
            try:
                await self._notification_service.push(admin_id, "admin:abuse_alert", payload)
            except Exception as exc:
                logger.warning(
                    "Failed to push abuse alert to admin %s: %s",
                    admin_id,
                    str(exc)[:100],
                )


# Process-wide optional singleton wired at app startup.
_abuse_alert_service: AbuseAlertService | None = None


def set_abuse_alert_service(service: AbuseAlertService | None) -> None:
    global _abuse_alert_service
    _abuse_alert_service = service


def get_abuse_alert_service() -> AbuseAlertService | None:
    return _abuse_alert_service


async def maybe_note_absorb(*, user_id: str, count: int, budget: int) -> None:
    service = get_abuse_alert_service()
    if service is None:
        return
    try:
        await service.note_absorb(user_id=user_id, count=count, budget=budget)
    except Exception as exc:
        logger.debug("Absorb abuse alert skipped: %s", exc)


async def maybe_note_polish_probe(*, user_id: str | None = None) -> None:
    service = get_abuse_alert_service()
    if service is None:
        return
    try:
        await service.note_polish_probe(user_id=user_id)
    except Exception as exc:
        logger.debug("Polish probe alert skipped: %s", exc)


async def maybe_note_redeem(*, user_id: str) -> None:
    service = get_abuse_alert_service()
    if service is None:
        return
    try:
        await service.note_redeem(user_id=user_id)
    except Exception as exc:
        logger.debug("Redeem abuse alert skipped: %s", exc)


async def maybe_note_zero_dollar_fulfill(
    *,
    payment_id: str,
    external_payment_id: str | None = None,
    amount_cents: int | None = None,
) -> None:
    service = get_abuse_alert_service()
    if service is None:
        return
    try:
        await service.note_zero_dollar_fulfill(
            payment_id=payment_id,
            external_payment_id=external_payment_id,
            amount_cents=amount_cents,
        )
    except Exception as exc:
        logger.debug("Zero-dollar fulfill alert skipped: %s", exc)


def dump_alert_payload(payload: dict[str, Any]) -> str:
    """Test helper — stable JSON for assertions."""
    return json.dumps(payload, sort_keys=True)
