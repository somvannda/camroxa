"""Unified notification items for the header notification panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from shared.lib.app_install import get_or_seed_install_datetime
from shared.lib.music_readiness import SECTION_ICON_BY_NAME, ReadinessItem
from shared.models.push_events import NOTIFICATION_MESSAGE, SOFTWARE_UPDATE_AVAILABLE
from shared.services.push_notification_hub import PushInboxItem


@dataclass(slots=True)
class NotificationItem:
    id: str
    kind: str
    title: str
    message: str
    icon: str
    created_at: datetime
    event: str = ""
    can_dismiss: bool = True
    primary_action: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def setup_notification_id(item: ReadinessItem) -> str:
    return f"setup:{item.section}:{item.label}"


def notification_item_from_setup(item: ReadinessItem) -> NotificationItem:
    # Setup checklist items are long-lived; stamp them with first-launch time
    # (never the old hardcoded 2000-01-01 placeholder).
    return NotificationItem(
        id=setup_notification_id(item),
        kind="setup",
        title=item.label,
        message=item.hint or f"Open {item.section} to complete this setup step.",
        icon=SECTION_ICON_BY_NAME.get(item.section, "settings"),
        created_at=get_or_seed_install_datetime(),
    )


def notification_item_from_push(item: PushInboxItem) -> NotificationItem:
    if item.event == SOFTWARE_UPDATE_AVAILABLE:
        mandatory = bool(item.payload.get("mandatory"))
        return NotificationItem(
            id=item.id,
            kind="push",
            title=item.title,
            message=item.message,
            icon="download",
            created_at=item.created_at,
            event=item.event,
            can_dismiss=not mandatory,
            primary_action="Install update",
            payload=dict(item.payload),
        )
    icon = "bell" if item.event == NOTIFICATION_MESSAGE else "activity"
    return NotificationItem(
        id=item.id,
        kind="push",
        title=item.title,
        message=item.message,
        icon=icon,
        created_at=item.created_at,
        event=item.event,
        payload=dict(item.payload),
    )


def notification_sort_key(item: NotificationItem) -> tuple[int, float]:
    kind_rank = 0 if item.kind == "push" else 1
    return (kind_rank, -item.created_at.timestamp())


def _local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone()


def format_notification_timestamp(value: datetime) -> str:
    local = _local_datetime(value)
    hour = local.strftime("%I:%M %p").lstrip("0")
    return f"{local.day} {local.strftime('%B, %Y')} • {hour}"


def notification_group_label(value: datetime) -> str:
    local = _local_datetime(value)
    item_date = local.date()
    today = date.today()
    if item_date == today:
        return "Today"
    if item_date == today - timedelta(days=1):
        return "Yesterday"
    return local.strftime("%B %d, %Y")


def group_notifications(items: Iterable[NotificationItem]) -> list[tuple[str, list[NotificationItem]]]:
    buckets: dict[str, list[NotificationItem]] = {}
    order: list[str] = []
    for item in sorted(items, key=notification_sort_key):
        label = notification_group_label(item.created_at)
        if label not in buckets:
            buckets[label] = []
            order.append(label)
        buckets[label].append(item)
    return [(label, buckets[label]) for label in order]
