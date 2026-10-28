"""Dependency gate for chained (thumbnail) image jobs.

Thumbnails are chained to a background image through ``source_job_id``. Before
this gate the batch runner claimed them while the background was still running,
charged the wallet, waited 10s, then refunded as ``image_generation_deferred``
and reset the job to ``pending`` — a charge/refund pair per sweep for work that
could not have run. These tests pin both layers of the fix:

* ``claim_image_jobs_for_run`` must not select a child whose source is still
  running.
* ``_ensure_dependency_ready`` must run before the wallet hold, so a not-ready
  dependency never debits (and therefore never refunds).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.models.domain import Batch, ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.repositories.batch_repo import BatchRepository
from platform_api.services.image_job_service import (
    DependencyPendingError,
    ImageJobService,
)
from platform_api.exceptions import ValidationError


def _thumbnail_job(*, user_id, batch_id, source_job_id) -> ImageJob:
    return ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=uuid4(),
        kind=ImageKind.THUMBNAIL,
        channel_role=ChannelRole.OK,
        prompt="thumbnail",
        resolution="1920x1080",
        style_strength=0.5,
        source_job_id=source_job_id,
        status=TaskStatus.RUNNING,
        attempt_count=0,
    )


def _source_job(*, user_id, batch_id, job_id, status, output_path=None) -> ImageJob:
    return ImageJob(
        id=job_id,
        user_id=user_id,
        batch_id=batch_id,
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="background",
        status=status,
        output_image_path=output_path,
    )


def _build_service(*, repo, enforcement_service=None) -> ImageJobService:
    routing_service = AsyncMock()
    routing_service.resolve_image_chain = AsyncMock(
        return_value=[SimpleNamespace(provider="slai", sub_model="flux")]
    )
    return ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=routing_service,
        enforcement_service=enforcement_service or AsyncMock(),
        generation_service=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_claim_skips_child_while_source_is_running() -> None:
    captured: dict[str, object] = {}

    class _Conn:
        async def fetch(self, sql, *args):
            captured["sql"] = sql
            captured["args"] = args
            return []

        @asynccontextmanager
        async def transaction(self):
            yield self

    class _Pool:
        @asynccontextmanager
        async def acquire(self):
            yield _Conn()

    repo = BatchRepository(_Pool())
    await repo.claim_image_jobs_for_run(uuid4(), batch_id=None, statuses=["pending"], limit=5)

    sql = " ".join(str(captured["sql"]).split())
    assert "source_job_id IS NULL" in sql
    assert "source_job.status IN ('success', 'failed')" in sql
    # The guard must be part of the candidate CTE, not applied after the claim.
    assert sql.index("source_job.status IN") < sql.index("FOR UPDATE SKIP LOCKED")


@pytest.mark.asyncio
async def test_pending_dependency_never_debits_and_returns_job_to_pending() -> None:
    user_id = uuid4()
    batch_id = uuid4()
    source_id = uuid4()
    job = _thumbnail_job(user_id=user_id, batch_id=batch_id, source_job_id=source_id)

    repo = AsyncMock()
    repo.get_batch_for_user = AsyncMock(return_value=Batch(id=batch_id, user_id=user_id))
    repo.get_image_job_by_id = AsyncMock(
        return_value=_source_job(
            user_id=user_id,
            batch_id=batch_id,
            job_id=source_id,
            status=TaskStatus.RUNNING,
        )
    )
    repo.update_image_job_status = AsyncMock()

    enforcement = AsyncMock()
    enforcement.resolve_max_credits = AsyncMock(return_value=5)
    enforcement.preflight_quotas_and_balance = AsyncMock()
    enforcement.reserve_and_hold_before_provider = AsyncMock()
    enforcement.release_operation_quota = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()

    service = _build_service(repo=repo, enforcement_service=enforcement)

    ok = await service._run_one_job(
        user_id=user_id,
        job=job,
        settings={"perfImageWorkers": 1},
        semaphore=asyncio.Semaphore(1),
        slai_retry_attempts=1,
    )

    assert ok is False
    enforcement.reserve_and_hold_before_provider.assert_not_awaited()
    enforcement.refund_failed_operation.assert_not_awaited()
    enforcement.release_operation_quota.assert_not_awaited()

    repo.update_image_job_status.assert_awaited()
    kwargs = repo.update_image_job_status.await_args.kwargs
    assert kwargs["status"] == TaskStatus.PENDING
    assert "Waiting for background image output" in kwargs["error"]


@pytest.mark.asyncio
async def test_failed_source_fails_fast_without_billing() -> None:
    user_id = uuid4()
    batch_id = uuid4()
    source_id = uuid4()
    job = _thumbnail_job(user_id=user_id, batch_id=batch_id, source_job_id=source_id)

    repo = AsyncMock()
    repo.get_batch_for_user = AsyncMock(return_value=Batch(id=batch_id, user_id=user_id))
    repo.get_image_job_by_id = AsyncMock(
        return_value=_source_job(
            user_id=user_id,
            batch_id=batch_id,
            job_id=source_id,
            status=TaskStatus.FAILED,
        )
    )
    repo.update_image_job_status = AsyncMock()

    enforcement = AsyncMock()
    enforcement.reserve_and_hold_before_provider = AsyncMock()

    service = _build_service(repo=repo, enforcement_service=enforcement)

    ok = await service._run_one_job(
        user_id=user_id,
        job=job,
        settings={"perfImageWorkers": 1},
        semaphore=asyncio.Semaphore(1),
        slai_retry_attempts=1,
    )

    assert ok is False
    enforcement.reserve_and_hold_before_provider.assert_not_awaited()
    kwargs = repo.update_image_job_status.await_args.kwargs
    assert kwargs["status"] == TaskStatus.FAILED
    assert "source background job failed" in kwargs["error"]


@pytest.mark.asyncio
async def test_ready_source_passes_the_gate() -> None:
    user_id = uuid4()
    batch_id = uuid4()
    source_id = uuid4()
    job = _thumbnail_job(user_id=user_id, batch_id=batch_id, source_job_id=source_id)

    repo = AsyncMock()
    repo.get_image_job_by_id = AsyncMock(
        return_value=_source_job(
            user_id=user_id,
            batch_id=batch_id,
            job_id=source_id,
            status=TaskStatus.SUCCESS,
            output_path="/tmp/background.png",
        )
    )

    service = _build_service(repo=repo)
    await service._ensure_dependency_ready(user_id=user_id, job=job)


@pytest.mark.asyncio
async def test_unfinished_success_raises_pending() -> None:
    user_id = uuid4()
    batch_id = uuid4()
    source_id = uuid4()
    job = _thumbnail_job(user_id=user_id, batch_id=batch_id, source_job_id=source_id)

    repo = AsyncMock()
    repo.get_image_job_by_id = AsyncMock(
        return_value=_source_job(
            user_id=user_id,
            batch_id=batch_id,
            job_id=source_id,
            status=TaskStatus.SUCCESS,
            output_path=None,
        )
    )

    service = _build_service(repo=repo)
    with pytest.raises(DependencyPendingError):
        await service._ensure_dependency_ready(user_id=user_id, job=job)


@pytest.mark.asyncio
async def test_missing_source_is_a_validation_error() -> None:
    user_id = uuid4()
    job = _thumbnail_job(user_id=user_id, batch_id=uuid4(), source_job_id=uuid4())

    repo = AsyncMock()
    repo.get_image_job_by_id = AsyncMock(return_value=None)

    service = _build_service(repo=repo)
    with pytest.raises(ValidationError):
        await service._ensure_dependency_ready(user_id=user_id, job=job)
