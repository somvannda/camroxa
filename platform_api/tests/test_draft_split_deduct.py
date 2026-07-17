"""Phase 2: shared split draft deduct used by batch + /generation/draft."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.draft_billing import (
    deduct_split_draft_billing,
    draft_billing_slots,
)


def _routing(*, forced_title: bool = False, forced_album: bool = False):
    del forced_title, forced_album
    slot = lambda name: SimpleNamespace(provider=f"p-{name}", sub_model=f"m-{name}")
    return SimpleNamespace(lyric=slot("lyric"), title=slot("title"), album=slot("album"))


def test_draft_billing_slots_respect_forced_fields() -> None:
    routing = _routing()
    assert [s[0] for s in draft_billing_slots(routing)] == ["lyric", "title", "album"]
    assert [s[0] for s in draft_billing_slots(routing, include_title=False)] == [
        "lyric",
        "album",
    ]
    assert [s[0] for s in draft_billing_slots(routing, include_album=False)] == [
        "lyric",
        "title",
    ]


@pytest.mark.asyncio
async def test_deduct_split_draft_billing_charges_each_slot() -> None:
    enforcement = AsyncMock()
    enforcement.deduct_for_operation = AsyncMock(side_effect=[10, 20, 30])
    charged, listed = await deduct_split_draft_billing(
        enforcement,
        user_id=uuid4(),
        channel_profile_id=None,
        draft_routing=_routing(),
    )
    assert charged == 60
    assert listed == 60
    assert enforcement.deduct_for_operation.await_count == 3
    ops = [c.args[2] for c in enforcement.deduct_for_operation.await_args_list]
    assert ops == ["lyric", "title", "album"]


@pytest.mark.asyncio
async def test_deduct_split_draft_billing_refunds_partial_failure() -> None:
    enforcement = AsyncMock()
    enforcement.deduct_for_operation = AsyncMock(
        side_effect=[5, RuntimeError("no title pricing")]
    )
    enforcement.refund_failed_operation = AsyncMock()

    with pytest.raises(RuntimeError):
        await deduct_split_draft_billing(
            enforcement,
            user_id=uuid4(),
            channel_profile_id=None,
            draft_routing=_routing(),
        )

    enforcement.refund_failed_operation.assert_awaited_once()
    assert enforcement.refund_failed_operation.await_args.kwargs["count"] == 1
    assert enforcement.refund_failed_operation.await_args.kwargs["charged_credit_units"] == 5
