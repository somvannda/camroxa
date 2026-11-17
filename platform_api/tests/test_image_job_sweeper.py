from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.models.domain import ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.services.image_job_service import ImageJobService


def _job(*, kind=ImageKind.BACKGROUND, attempt_count=0, hold_state="held", hold_units=10, provider_invoked=True) -> ImageJob:
    return ImageJob(
        id=uuid4(),
        user_id=uuid4(),
        batch_id=uuid4(),
        profile_id=uuid4(),
        kind=kind,
        channel_role=ChannelRole.OK,
        prompt="test",
        provider="fal",
        status=TaskStatus.RUNNING if kind == ImageKind.BACKGROUND else TaskStatus.PENDING,
        attempt_count=attempt_count,
        hold_units=hold_units,
        hold_state=hold_state,
        provider_invoked=provider_invoked,
    )


def _service(repo, enforcement):
    return ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=enforcement,
        generation_service=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_sweep_requeues_stale_running_and_refunds_hold() -> None:
    job = _job(attempt_count=0)
    repo = AsyncMock()
    repo.get_stale_running_image_jobs = AsyncMock(return_value=[job])
    repo.get_stale_pending_thumbnail_jobs = AsyncMock(return_value=[])
    repo.update_image_job_billing_state = AsyncMock()
    repo.update_image_job_status = AsyncMock()
    enforcement = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()

    result = await _service(repo, enforcement).sweep_stale_jobs()

    assert result == {"recovered": 1, "failed": 0, "refunded": 1}
    enforcement.refund_failed_operation.assert_awaited_once()
    kwargs = enforcement.refund_failed_operation.await_args.kwargs
    assert kwargs["charged_credit_units"] == 10
    assert kwargs["provider_invoked"] is True
    assert kwargs["ref_id"] == str(job.id)
    repo.update_image_job_billing_state.assert_awaited_with(
        job.id, job.user_id, hold_state="refunded"
    )
    status_kwargs = repo.update_image_job_status.await_args.kwargs
    assert status_kwargs["status"] == TaskStatus.PENDING
    assert status_kwargs["attempt_count"] == 1


@pytest.mark.asyncio
async def test_sweep_fails_stale_running_at_max_attempts() -> None:
    job = _job(attempt_count=3)
    repo = AsyncMock()
    repo.get_stale_running_image_jobs = AsyncMock(return_value=[job])
    repo.get_stale_pending_thumbnail_jobs = AsyncMock(return_value=[])
    repo.update_image_job_billing_state = AsyncMock()
    repo.update_image_job_status = AsyncMock()
    enforcement = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()

    result = await _service(repo, enforcement).sweep_stale_jobs()

    assert result == {"recovered": 0, "failed": 1, "refunded": 1}
    status_kwargs = repo.update_image_job_status.await_args.kwargs
    assert status_kwargs["status"] == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_sweep_fails_stale_dependent_thumbnail() -> None:
    job = _job(kind=ImageKind.THUMBNAIL, hold_state="none", hold_units=0)
    repo = AsyncMock()
    repo.get_stale_running_image_jobs = AsyncMock(return_value=[])
    repo.get_stale_pending_thumbnail_jobs = AsyncMock(return_value=[job])
    repo.update_image_job_billing_state = AsyncMock()
    repo.update_image_job_status = AsyncMock()
    enforcement = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()

    result = await _service(repo, enforcement).sweep_stale_jobs()

    assert result == {"recovered": 0, "failed": 1, "refunded": 0}
    status_kwargs = repo.update_image_job_status.await_args.kwargs
    assert status_kwargs["status"] == TaskStatus.FAILED
    assert "Background image did not finish" in status_kwargs["error"]
