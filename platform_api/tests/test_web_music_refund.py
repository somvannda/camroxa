"""Web-music failures always refund the 10-credit charge."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from platform_api.models.products import WEB_MUSIC_CREDITS_PER_SONG
from platform_api.services import web_music_refund
from platform_api.services.credit_units import CREDIT_SCALE

USER_ID = uuid4()
TASK_ID = uuid4()


class FakeRepo:
    instances: list["FakeRepo"] = []
    default_applied = True

    def __init__(self, pool) -> None:
        self.pool = pool
        self.calls: list[dict] = []
        self.applied = FakeRepo.default_applied
        FakeRepo.instances.append(self)

    async def refund_once(self, user_id, amount, reason, ref_id=None, metadata=None):
        self.calls.append(
            {
                "user_id": user_id,
                "amount": amount,
                "reason": reason,
                "ref_id": ref_id,
                "metadata": metadata,
            }
        )
        return self.applied


@pytest.fixture
def wired(monkeypatch):
    FakeRepo.instances.clear()
    FakeRepo.default_applied = True
    monkeypatch.setattr(web_music_refund, "CreditRepository", FakeRepo)

    released: list[UUID] = []

    async def fake_release(pool, *, user_id, task_id):
        released.append(task_id)

    monkeypatch.setattr(web_music_refund, "release_web_music_preview", fake_release)
    return released


@pytest.mark.asyncio
async def test_refunds_a_paying_user(wired) -> None:
    """A live pack must not suppress the refund (the old is_pro gate)."""
    applied = await web_music_refund.refund_web_music_generation_on_failure(
        pool=object(), user_id=str(USER_ID), task_id=TASK_ID, prior_status="pending"
    )

    assert applied is True
    repo = FakeRepo.instances[0]
    assert repo.calls == [
        {
            "user_id": USER_ID,
            "amount": WEB_MUSIC_CREDITS_PER_SONG * CREDIT_SCALE,
            "reason": "web_music_generation_failed",
            "ref_id": str(TASK_ID),
            "metadata": {"source": "web_music", "op": "music", "billing": "v3"},
        }
    ]
    assert wired == [TASK_ID]


@pytest.mark.asyncio
async def test_reconcile_path_refunds_without_a_prior_status(wired) -> None:
    """The reconcile sweep has no prior status to pass in."""
    applied = await web_music_refund.refund_web_music_generation_on_failure(
        pool=object(), user_id=str(USER_ID), task_id=TASK_ID
    )

    assert applied is True
    assert FakeRepo.instances[0].calls


@pytest.mark.asyncio
async def test_already_failed_skips_the_write(wired) -> None:
    applied = await web_music_refund.refund_web_music_generation_on_failure(
        pool=object(), user_id=str(USER_ID), task_id=TASK_ID, prior_status="FAILED"
    )

    assert applied is False
    assert FakeRepo.instances == []


@pytest.mark.asyncio
async def test_duplicate_settlement_reports_not_applied(wired, monkeypatch) -> None:
    monkeypatch.setattr(FakeRepo, "default_applied", False)

    applied = await web_music_refund.refund_web_music_generation_on_failure(
        pool=object(), user_id=str(USER_ID), task_id=TASK_ID, prior_status="pending"
    )

    assert applied is False
    assert FakeRepo.instances[0].calls  # it did try, and the ledger said no-op
