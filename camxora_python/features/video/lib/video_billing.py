"""Billable gate for local video export / merge via platform_api."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class VideoBillingResult:
    operation_type: str
    billing: str
    charged_credit_units: int
    list_credit_units: int


def consume_video_operation(
    api: Any,
    *,
    operation_type: str,
    count: int = 1,
    channel_profile_id: str | UUID | None = None,
    ref_id: str | None = None,
) -> VideoBillingResult:
    """Charge plan allowance or wallet before local export/merge.

    Raises whatever the platform client raises (quota / credits / auth).
    """
    payload: dict[str, Any] = {
        "operation_type": str(operation_type).strip().lower(),
        "count": max(1, int(count)),
    }
    if channel_profile_id is not None and str(channel_profile_id).strip():
        payload["channel_profile_id"] = str(channel_profile_id)
    if ref_id:
        payload["ref_id"] = str(ref_id)
    data = api.consume_local_video(payload)
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    return VideoBillingResult(
        operation_type=str(data.get("operation_type") or operation_type),
        billing=str(data.get("billing") or "plan_allowance"),
        charged_credit_units=int(data.get("charged_credit_units") or 0),
        list_credit_units=int(data.get("list_credit_units") or 0),
    )


def refund_video_operation(
    api: Any,
    *,
    operation_type: str,
    charged_credit_units: int = 0,
    count: int = 1,
    channel_profile_id: str | UUID | None = None,
    ref_id: str | None = None,
    reason: str = "Local video operation failed",
) -> None:
    payload: dict[str, Any] = {
        "operation_type": str(operation_type).strip().lower(),
        "charged_credit_units": max(0, int(charged_credit_units)),
        "count": max(1, int(count)),
        "reason": reason,
    }
    if channel_profile_id is not None and str(channel_profile_id).strip():
        payload["channel_profile_id"] = str(channel_profile_id)
    if ref_id:
        payload["ref_id"] = str(ref_id)
    api.refund_local_video(payload)
