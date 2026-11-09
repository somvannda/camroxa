"""PublishService charge/refund and payload tests with in-memory fakes."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from platform_api.exceptions import ExternalServiceError, InsufficientCreditsError
from platform_api.repositories.publish_repo import PublishJobRecord
from platform_api.services.publish_service import PublishService


def _job(**overrides: Any) -> PublishJobRecord:
    now = datetime.now(timezone.utc)
    base = PublishJobRecord(
        id=str(uuid4()),
        user_id=str(uuid4()),
        song_id=None,
        job_uid=str(uuid4()),
        batch_id=None,
        profile_id=str(uuid4()),
        role="OK",
        file_path=None,
        title="Song One",
        description="A description",
        tags="tag1,tag2",
        privacy_status="private",
        youtube_video_id=None,
        youtube_url=None,
        status="pending_upload",
        attempt_count=0,
        error_message=None,
        provider="postforme",
        platform="youtube",
        social_account_id="spc_123",
        postforme_post_id=None,
        postforme_result_id=None,
        media_url="https://cdn.example/video.mp4",
        upload_url="https://storage.example/put",
        upload_expires_at=now + timedelta(minutes=20),
        file_size_bytes=123,
        file_checksum=None,
        thumbnail_path=None,
        thumbnail_media_url=None,
        profile_config={"category": "10", "made_for_kids": False, "contains_synthetic_media": True},
        credits_charged_units=0,
        credit_ref_id=None,
        error_code=None,
        scheduled_at=None,
        result_payload={},
        created_at=now,
        updated_at=now,
    )
    return replace(base, **overrides)


class FakeBilling:
    def __init__(self, *, insufficient: bool = False) -> None:
        self.insufficient = insufficient
        self.charges: list[dict[str, Any]] = []
        self.refunds: list[dict[str, Any]] = []

    async def quote(self, *, op: str, user_id=None, **_kwargs):
        class Q:
            amount_units = 50_000
            amount_credits = 5.0

        Q.op = op
        return Q()

    async def wallet_view(self, _user_id):
        return {"balance_units": 100_000}

    async def charge(self, *, user_id, op, ref_id=None, **_kwargs):
        if self.insufficient:
            raise InsufficientCreditsError("Insufficient credits for this operation.")
        self.charges.append({"user_id": str(user_id), "op": op, "ref_id": ref_id})
        return {"amount_units": 50_000, "amount_credits": 5.0}

    async def refund(self, *, user_id, op, amount_credits=None, ref_id=None, **_kwargs):
        self.refunds.append(
            {
                "user_id": str(user_id),
                "op": op,
                "amount_credits": amount_credits,
                "ref_id": ref_id,
            }
        )
        return {}


class FakeClient:
    def __init__(self, *, fail_post: bool = False) -> None:
        self.fail_post = fail_post
        self.post_payload: dict[str, Any] | None = None

    async def create_media_upload_url(self):
        return {"upload_url": "https://storage.example/put", "media_url": "https://cdn.example/v.mp4"}

    async def create_social_post(self, payload):
        self.post_payload = payload
        if self.fail_post:
            raise ExternalServiceError("platform rejected")
        return {"id": "post_1", "status": "processing"}

    async def list_social_post_results(self, _post_id):
        return []


class FakeRepo:
    def __init__(self, job: PublishJobRecord) -> None:
        self.job = job
        self.results: list[dict[str, Any]] = []

    async def get_job(self, _user_id, _job_uid):
        return self.job

    async def set_job_status(self, _job_id, *, status, error_code=None, error_message=None):
        self.job = replace(
            self.job,
            status=status,
            error_code=error_code,
            error_message=error_message,
        )

    async def mark_job_charged(
        self, _job_id, *, credits_charged_units, credit_ref_id, status
    ):
        self.job = replace(
            self.job,
            credits_charged_units=credits_charged_units,
            credit_ref_id=credit_ref_id,
            status=status,
        )

    async def mark_job_posted(self, _job_id, *, postforme_post_id, status, attempt_count=None):
        self.job = replace(
            self.job,
            postforme_post_id=postforme_post_id,
            status=status,
            attempt_count=attempt_count if attempt_count is not None else self.job.attempt_count,
        )

    async def mark_job_refunded(
        self, _job_id, *, credits_charged_units, error_code, error_message, status="failed"
    ):
        self.job = replace(
            self.job,
            credits_charged_units=credits_charged_units,
            error_code=error_code,
            error_message=error_message,
            status=status,
        )

    async def upsert_result(self, **_kwargs):
        self.results.append(dict(_kwargs))

    async def count_results(self, _job_id):
        succeeded = sum(1 for item in self.results if item.get("success"))
        return (len(self.results), succeeded)

    async def mark_job_success(self, _job_id, *, platform_post_id, platform_url, result_payload=None):
        self.job = replace(
            self.job,
            status="success",
            youtube_video_id=platform_post_id,
            youtube_url=platform_url,
            result_payload=result_payload or {},
        )


@pytest.mark.asyncio
async def test_a_repeat_click_reuses_the_job_already_in_flight() -> None:
    """No second transfer, charge, or YouTube post for the same slot."""
    job = replace(_job(), status="processing", file_size_bytes=2_600_000_000)
    repo = FakeRepo(job)
    service = _service(repo, FakeBilling(), FakeClient())

    reused = await service._reuse_or_retire_job(job, size_bytes=2_600_000_000)

    assert reused is not None
    assert reused["existing"] is True
    assert reused["job_uid"] == job.job_uid
    assert reused["status"] == "processing"
    assert reused["upload_url"] is None


@pytest.mark.asyncio
async def test_a_successful_job_is_reported_instead_of_publishing_again() -> None:
    job = replace(_job(), status="success", file_size_bytes=100)
    service = _service(FakeRepo(job), FakeBilling(), FakeClient())

    reused = await service._reuse_or_retire_job(job, size_bytes=100)

    assert reused is not None and reused["existing"] is True


@pytest.mark.asyncio
async def test_a_remerged_file_may_be_published_again() -> None:
    job = replace(_job(), status="success", file_size_bytes=100)
    service = _service(FakeRepo(job), FakeBilling(), FakeClient())

    assert await service._reuse_or_retire_job(job, size_bytes=200) is None


@pytest.mark.asyncio
async def test_a_stale_pending_upload_is_retired_instead_of_blocking() -> None:
    """Older clients left these at pending_upload; Progress showed them forever."""
    job = replace(
        _job(),
        status="pending_upload",
        media_url="https://cdn.example/v.mp4",
        file_size_bytes=100,
    )
    repo = FakeRepo(job)
    service = _service(repo, FakeBilling(), FakeClient())

    assert await service._reuse_or_retire_job(job, size_bytes=100) is None
    assert repo.job.status == "failed"
    assert repo.job.error_code == "UPLOAD_SUPERSEDED"


@pytest.mark.asyncio
async def test_a_real_client_upload_in_progress_is_not_retired() -> None:
    job = replace(_job(), status="pending_upload", media_url=None, file_size_bytes=100)
    repo = FakeRepo(job)
    service = _service(repo, FakeBilling(), FakeClient())

    assert await service._reuse_or_retire_job(job, size_bytes=100) is None
    assert repo.job.status == "pending_upload"

def _service(repo: FakeRepo, billing: FakeBilling, client: FakeClient) -> PublishService:
    return PublishService(
        db=None,
        repo=repo,
        client=client,
        billing=billing,
        enabled=True,
        webhook_secret="secret",
    )


@pytest.mark.asyncio
async def test_complete_charges_five_credits_and_creates_post() -> None:
    job = _job()
    repo = FakeRepo(job)
    billing = FakeBilling()
    client = FakeClient()

    result = await _service(repo, billing, client).complete_job(
        user_id=job.user_id, job_uid=job.job_uid
    )

    assert billing.charges == [
        {"user_id": job.user_id, "op": "publish", "ref_id": job.job_uid}
    ]
    assert repo.job.credits_charged_units == 50_000
    assert repo.job.status == "processing"
    assert repo.job.postforme_post_id == "post_1"
    assert result["status"] == "processing"
    assert client.post_payload is not None
    config = client.post_payload["account_configurations"][0]["configuration"]
    assert config["privacy_status"] == "private"
    assert config["category_id"] == "10"
    assert config["tags"] == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_post_creation_failure_refunds_and_fails_job() -> None:
    job = _job()
    repo = FakeRepo(job)
    billing = FakeBilling()
    client = FakeClient(fail_post=True)

    with pytest.raises(ExternalServiceError):
        await _service(repo, billing, client).complete_job(
            user_id=job.user_id, job_uid=job.job_uid
        )

    assert len(billing.refunds) == 1
    assert billing.refunds[0]["amount_credits"] == 5.0
    assert billing.refunds[0]["ref_id"] == job.job_uid
    assert repo.job.credits_charged_units == 0
    assert repo.job.status == "failed"


@pytest.mark.asyncio
async def test_insufficient_credits_leaves_job_pending_payment() -> None:
    job = _job()
    repo = FakeRepo(job)
    billing = FakeBilling(insufficient=True)
    client = FakeClient()

    with pytest.raises(InsufficientCreditsError):
        await _service(repo, billing, client).complete_job(
            user_id=job.user_id, job_uid=job.job_uid
        )

    assert repo.job.status == "pending_payment"
    assert repo.job.credits_charged_units == 0
    assert client.post_payload is None


@pytest.mark.asyncio
async def test_scheduled_visibility_adds_publish_at() -> None:
    scheduled = datetime.now(timezone.utc) + timedelta(days=1)
    job = _job(privacy_status="private", scheduled_at=scheduled)
    repo = FakeRepo(job)
    billing = FakeBilling()
    client = FakeClient()

    await _service(repo, billing, client).complete_job(
        user_id=job.user_id, job_uid=job.job_uid
    )

    config = client.post_payload["account_configurations"][0]["configuration"]
    assert config["publish_at"].endswith("Z")
    assert client.post_payload["caption"] == "A description"
    assert client.post_payload["media"][0]["skip_processing"] is True


def test_webhook_secret_fails_closed_and_compares_constant_time() -> None:
    service = _service(FakeRepo(_job()), FakeBilling(), FakeClient())
    assert service.verify_webhook_secret("secret") is True
    assert service.verify_webhook_secret("nope") is False
    assert service.verify_webhook_secret(None) is False

    unset = PublishService(
        db=None,
        repo=FakeRepo(_job()),
        client=FakeClient(),
        billing=FakeBilling(),
        enabled=True,
        webhook_secret="",
    )
    assert unset.verify_webhook_secret("") is False


@pytest.mark.asyncio
async def test_hhmm_schedule_uses_batch_planned_date() -> None:
    from datetime import date

    class FakeDb:
        async def fetchrow(self, _query, *_args):
            return {"planned_from_date": date(2030, 1, 2)}

    service = PublishService(
        db=FakeDb(),
        repo=FakeRepo(_job()),
        client=FakeClient(),
        billing=FakeBilling(),
        enabled=True,
        webhook_secret="secret",
    )
    scheduled = await service._resolve_scheduled_at("14:35", "batch-1")
    assert scheduled is not None
    assert scheduled.year == 2030
    assert scheduled.month == 1
    assert scheduled.day == 2
    assert scheduled.hour == 14
    assert scheduled.minute == 35
