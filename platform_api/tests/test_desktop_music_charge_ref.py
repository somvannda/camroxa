"""Desktop music debits must carry a reference so they can be reconciled.

Refunds are keyed by ``ref_id=song_id`` but the debit itself had no ``ref_id``,
so a charged-but-failed desktop generation could never be matched back to its
song. ``deduct_for_operation`` now forwards the reference to the v3 charge and
tags it with the provider that actually ran.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.usage_enforcement_service import UsageEnforcementService


@pytest.mark.asyncio
async def test_deduct_for_operation_forwards_ref_id() -> None:
    service = UsageEnforcementService.__new__(UsageEnforcementService)
    service._v3_op_if_enabled = AsyncMock(return_value="music")  # type: ignore[method-assign]
    service.enforce_fail_absorb_budget = AsyncMock()  # type: ignore[method-assign]
    service._charge_via_v3 = AsyncMock(return_value=100_000)  # type: ignore[method-assign]

    user_id = uuid4()
    charged = await service.deduct_for_operation(
        user_id,
        None,
        "music",
        "suno",
        sub_model="V6",
        ref_id="song-1",
    )

    assert charged == 100_000
    service._charge_via_v3.assert_awaited_once_with(
        user_id,
        "music",
        ref_id="song-1",
        model="V6",
        provider="suno",
    )


@pytest.mark.asyncio
async def test_deduct_without_ref_id_stays_unkeyed() -> None:
    service = UsageEnforcementService.__new__(UsageEnforcementService)
    service._v3_op_if_enabled = AsyncMock(return_value="music")  # type: ignore[method-assign]
    service.enforce_fail_absorb_budget = AsyncMock()  # type: ignore[method-assign]
    service._charge_via_v3 = AsyncMock(return_value=0)  # type: ignore[method-assign]

    await service.deduct_for_operation(uuid4(), None, "music", "suno")

    _, kwargs = service._charge_via_v3.await_args
    assert kwargs["ref_id"] is None
