from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import QuotaExceededError
from platform_api.models.domain import Batch, ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.services.image_job_service import (
    ImageJobService,
    _is_non_retryable_image_error,
)


def test_non_retryable_detects_fail_budget() -> None:
    assert _is_non_retryable_image_error(
        QuotaExceededError(
            "Daily fail/retry budget exceeded. Try again tomorrow.",
            details={"error_code": "FAIL_BUDGET_EXCEEDED"},
        )
    )
    assert _is_non_retryable_image_error(Exception("Daily fail/retry budget exceeded. Try again tomorrow."))
    assert not _is_non_retryable_image_error(Exception("fal timeout after 30s"))


@pytest.mark.asyncio
async def test_run_one_job_auto_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_api.services.image_job_service._image_job_max_attempts",
        lambda: 3,
    )
    user_id = uuid4()
    batch_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="bg",
        status=TaskStatus.RUNNING,
        attempt_count=0,
    )
    repo = AsyncMock()
    repo.get_batch_for_user = AsyncMock(return_value=Batch(id=batch_id, user_id=user_id))
    repo.update_image_job_status = AsyncMock()

    settings_service = AsyncMock()
    routing_service = AsyncMock()
    routing_service.resolve_image_chain = AsyncMock(
        return_value=[SimpleNamespace(provider="fal", sub_model="flux")]
    )
    enforcement_service = AsyncMock()
    hold = SimpleNamespace(held_units=0, plan_covered=True)
    enforcement_service.resolve_max_credits = AsyncMock(return_value=5)
    enforcement_service.preflight_quotas_and_balance = AsyncMock()
    enforcement_service.reserve_and_hold_before_provider = AsyncMock(return_value=hold)
    enforcement_service.release_operation_quota = AsyncMock()

    generation_service = AsyncMock()
    generation_service.submit_image_outcome = AsyncMock(side_effect=RuntimeError("provider timeout"))

    service = ImageJobService(
        repo=repo,
        settings_service=settings_service,
        routing_service=routing_service,
        enforcement_service=enforcement_service,
        generation_service=generation_service,
    )
    monkeypatch.setattr(service, "_resolve_base_image_bytes", AsyncMock(return_value=b"png-bytes"))
    monkeypatch.setattr(service, "_write_image_output", lambda **kwargs: "/tmp/out.png")

    semaphore = __import__("asyncio").Semaphore(1)
    ok = await service._run_one_job(
        user_id=user_id,
        job=job,
        settings={"perfImageWorkers": 1, "imageOutputDir": "/tmp"},
        semaphore=semaphore,
        slai_retry_attempts=1,
    )
    assert ok is False
    repo.update_image_job_status.assert_awaited()
    kwargs = repo.update_image_job_status.await_args.kwargs
    assert kwargs["status"] == TaskStatus.PENDING
    assert kwargs["attempt_count"] == 1


@pytest.mark.asyncio
async def test_run_one_job_no_auto_retry_on_fail_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_api.services.image_job_service._image_job_max_attempts",
        lambda: 3,
    )
    user_id = uuid4()
    batch_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="bg",
        status=TaskStatus.RUNNING,
        attempt_count=0,
    )
    repo = AsyncMock()
    repo.get_batch_for_user = AsyncMock(return_value=Batch(id=batch_id, user_id=user_id))
    repo.update_image_job_status = AsyncMock()

    settings_service = AsyncMock()
    routing_service = AsyncMock()
    routing_service.resolve_image_chain = AsyncMock(
        return_value=[SimpleNamespace(provider="fal", sub_model="flux")]
    )
    enforcement_service = AsyncMock()
    enforcement_service.resolve_max_credits = AsyncMock(return_value=5)
    enforcement_service.preflight_quotas_and_balance = AsyncMock(
        side_effect=QuotaExceededError(
            "Daily fail/retry budget exceeded. Try again tomorrow.",
            details={"error_code": "FAIL_BUDGET_EXCEEDED"},
        )
    )

    service = ImageJobService(
        repo=repo,
        settings_service=settings_service,
        routing_service=routing_service,
        enforcement_service=enforcement_service,
        generation_service=AsyncMock(),
    )
    ok = await service._run_one_job(
        user_id=user_id,
        job=job,
        settings={"perfImageWorkers": 1, "imageOutputDir": "/tmp"},
        semaphore=__import__("asyncio").Semaphore(1),
        slai_retry_attempts=1,
    )
    assert ok is False
    kwargs = repo.update_image_job_status.await_args.kwargs
    assert kwargs["status"] == TaskStatus.FAILED
