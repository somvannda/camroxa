"""End-to-end seams: refunds, stalled jobs, quota, delivery status.

These cover the failures found in production, not the happy path alone.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from platform_api.repositories.publish_repo import PublishJobRecord
from platform_api.services.publish_service import PublishService



def _job(**overrides: Any) -> PublishJobRecord:
    base = PublishJobRecord(
        id=str(uuid4()),
        user_id=str(uuid4()),
        song_id=None,
        job_uid=str(uuid4()),
        batch_id=str(uuid4()),
        profile_id=str(uuid4()),
        role="OK",
        file_path=None,
        title="A song",
        description=None,
        tags=None,
        privacy_status="private",
        youtube_video_id=None,
        youtube_url=None,
        status="processing",
        attempt_count=0,
        error_message=None,
        provider="postforme",
        platform="youtube",
        social_account_id=None,
        postforme_post_id=None,
        postforme_result_id=None,
        media_url="https://cdn.example/v.mp4",
        upload_url=None,
        upload_expires_at=None,
        file_size_bytes=100,
        file_checksum=None,
        thumbnail_path=None,
        thumbnail_media_url=None,
        profile_config={},
        credits_charged_units=80_000,
        credit_ref_id="ref",
        error_code=None,
        scheduled_at=None,
        result_payload={},
        created_at=datetime.now(timezone.utc) - timedelta(hours=3),
        updated_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    return replace(base, **overrides)


class _Repo:
    def __init__(self, job: PublishJobRecord | None = None, refundable: list | None = None) -> None:
        self.job = job
        self.refundable = refundable or []
        self.statuses: list[tuple[str, str | None]] = []

    async def latest_job_for_slot(self, **_kwargs: Any) -> PublishJobRecord | None:
        return self.job

    async def set_job_status(self, _job_id: str, *, status: str, error_code: str | None = None, error_message: str | None = None) -> None:
        self.statuses.append((status, error_code))

    async def mark_job_refunded(self, _job_id: str, **_kwargs: Any) -> None:
        return None

    async def list_charged_without_video(self) -> list:
        return list(self.refundable)


class _Billing:
    def __init__(self) -> None:
        self.refunds: list[dict[str, Any]] = []

    async def refund(self, *, user_id: Any, op: str, amount_credits: float | None = None, ref_id: str | None = None, **_kw: Any) -> dict:
        self.refunds.append({"op": op, "amount": amount_credits, "ref": ref_id})
        return {}


class _Client:
    pass


def _service(repo: _Repo, billing: _Billing) -> PublishService:
    return PublishService(
        db=None,
        repo=repo,  # type: ignore[arg-type]
        client=_Client(),
        billing=billing,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_a_stalled_provider_job_is_retired_and_refunded() -> None:
    """A charged job with no video must not block retries, and must pay back."""
    job = _job()
    repo = _Repo(job)
    billing = _Billing()

    reused = await _service(repo, billing)._reuse_or_retire_job(job, size_bytes=100)

    assert reused is None, "the retry must be allowed to proceed"
    assert billing.refunds, "the customer must get the credits back"
    assert repo.statuses and repo.statuses[0][1] == "UPLOAD_STALLED"


@pytest.mark.asyncio
async def test_a_fresh_provider_job_is_still_reused() -> None:
    job = _job(updated_at=datetime.now(timezone.utc))
    repo = _Repo(job)
    billing = _Billing()

    reused = await _service(repo, billing)._reuse_or_retire_job(job, size_bytes=100)

    assert reused is not None and reused["existing"] is True
    assert not billing.refunds


@pytest.mark.asyncio
async def test_reconcile_refunds_every_stuck_charge_once() -> None:
    stuck = [_job(), _job()]
    repo = _Repo(refundable=stuck)
    billing = _Billing()

    refunded = await _service(repo, billing).reconcile_refunds()

    assert refunded == 2
    assert len(billing.refunds) == 2


@pytest.mark.asyncio
async def test_reconcile_is_a_noop_without_stuck_charges() -> None:
    billing = _Billing()

    assert await _service(_Repo(refundable=[]), billing).reconcile_refunds() == 0
    assert not billing.refunds


class _QuotaDb:
    def __init__(self, used: int) -> None:
        self.used = used

    async def fetchval(self, _query: str, *_args: Any) -> int:
        return self.used


@pytest.mark.asyncio
async def test_quota_counts_today_and_reports_remaining() -> None:
    from platform_api.services.youtube_connection_service import YouTubeConnectionService

    service = YouTubeConnectionService(
        db=_QuotaDb(used=5), oauth_app_repo=None, connection_repo=None, encryption=None  # type: ignore[arg-type]
    )
    status = await service.quota_status(user_id=uuid4())

    assert status["limit"] >= 1
    assert status["used"] == 5
    assert status["remaining"] == max(0, status["limit"] - 5)


@pytest.mark.asyncio
async def test_quota_exhausted_reports_zero_remaining() -> None:
    from platform_api.services.youtube_connection_service import YouTubeConnectionService

    service = YouTubeConnectionService(
        db=_QuotaDb(used=99), oauth_app_repo=None, connection_repo=None, encryption=None  # type: ignore[arg-type]
    )

    assert (await service.quota_status(user_id=uuid4()))["remaining"] == 0


class _RecordingQuotaDb:
    def __init__(self) -> None:
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetchval(self, query: str, *args: Any) -> int:
        self.query = query
        self.args = args
        return 0


@pytest.mark.asyncio
async def test_quota_counts_a_retry_by_its_latest_attempt() -> None:
    """A re-uploaded old slot must count today, not only on its created_at day."""
    from platform_api.services.youtube_connection_service import YouTubeConnectionService

    db = _RecordingQuotaDb()
    service = YouTubeConnectionService(
        db=db, oauth_app_repo=None, connection_repo=None, encryption=None  # type: ignore[arg-type]
    )

    await service.quota_status(user_id=uuid4())

    assert "created_at" in db.query
    assert "updated_at" in db.query
    assert len(db.args) == 3  # user id + quota day start/end
