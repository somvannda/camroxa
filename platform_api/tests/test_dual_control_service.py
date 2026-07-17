"""Phase 3 dual-control credit adjust queue tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import ForbiddenError
from platform_api.services.credit_units import credits_to_units
from platform_api.services.dual_control_service import DualControlService


class FakePool:
    def __init__(self) -> None:
        self.rows: dict[UUID, dict[str, Any]] = {}
        self.execute = AsyncMock(side_effect=self._execute)
        self.fetch = AsyncMock(side_effect=self._fetch)
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)

    async def _execute(self, query: str, *args: Any) -> str:
        if "INSERT INTO admin_pending_ops" in query:
            pending_id, op_type, admin_id, user_id, payload_json, reason = args
            self.rows[pending_id] = {
                "id": pending_id,
                "op_type": op_type,
                "status": "pending",
                "requested_by": admin_id,
                "target_user_id": user_id,
                "payload": json.loads(payload_json),
                "reason": reason,
                "created_at": None,
            }
        elif "UPDATE admin_pending_ops" in query and "approved" in query:
            pending_id, admin_id, note = args
            row = self.rows[pending_id]
            row["status"] = "approved"
            row["approved_by"] = admin_id
            row["decision_note"] = note
        elif "UPDATE admin_pending_ops" in query and "rejected" in query:
            pending_id, admin_id, note = args
            row = self.rows[pending_id]
            row["status"] = "rejected"
            row["rejected_by"] = admin_id
            row["decision_note"] = note
        return "OK"

    async def _fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return [r for r in self.rows.values() if r["status"] == "pending"]

    async def _fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        pending_id = args[0]
        return self.rows.get(pending_id)


@pytest.mark.asyncio
async def test_small_adjust_applies_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS", "1000")
    from platform_api.config import get_settings

    get_settings.cache_clear()

    credit_service = AsyncMock()
    credit_service.admin_adjust = AsyncMock(return_value=credits_to_units(50))
    dual = DualControlService(pool=FakePool(), credit_service=credit_service)
    result = await dual.request_or_apply_credit_adjust(
        admin_id=str(uuid4()),
        user_id=str(uuid4()),
        amount_display=100,
        reason="small grant",
    )
    assert result["status"] == "applied"
    assert result["requires_approval"] is False
    credit_service.admin_adjust.assert_awaited_once()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_large_adjust_queues_and_requires_second_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS", "1000")
    from platform_api.config import get_settings

    get_settings.cache_clear()

    pool = FakePool()
    credit_service = AsyncMock()
    credit_service.admin_adjust = AsyncMock(return_value=credits_to_units(5000))
    dual = DualControlService(pool=pool, credit_service=credit_service)
    admin_a = str(uuid4())
    user_id = str(uuid4())

    queued = await dual.request_or_apply_credit_adjust(
        admin_id=admin_a,
        user_id=user_id,
        amount_display=2500,
        reason="large grant",
    )
    assert queued["status"] == "pending"
    assert queued["requires_approval"] is True
    credit_service.admin_adjust.assert_not_awaited()

    pending_id = UUID(queued["pending_id"])
    with pytest.raises(ForbiddenError):
        await dual.approve(pending_id=pending_id, admin_id=admin_a)

    approved = await dual.approve(pending_id=pending_id, admin_id=str(uuid4()))
    assert approved["status"] == "approved"
    credit_service.admin_adjust.assert_awaited_once()
    get_settings.cache_clear()
