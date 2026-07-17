"""C2: prepaid (auto_gen_image) path must bill like plan_allowance / wallet."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from PIL import Image

from platform_api.models.domain import Batch, ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.services.image_job_service import ImageJobService


def _png_bytes() -> bytes:
    from io import BytesIO

    image = Image.new("RGB", (64, 64), (10, 20, 30))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_auto_gen_image_batch_still_deducts_wallet_or_plan_ledger(tmp_path) -> None:
    """auto_gen_image=True must NOT skip preflight or deduct_wallet (C2)."""
    user_id = uuid4()
    batch_id = uuid4()
    profile_id = uuid4()

    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="Cover art",
        resolution="1920x1080",
        status=TaskStatus.RUNNING,
    )

    repo = AsyncMock()
    repo.claim_image_jobs_for_run = AsyncMock(return_value=[job])
    repo.get_batch_for_user = AsyncMock(
        return_value=Batch(id=batch_id, user_id=user_id, auto_gen_image=True)
    )
    repo.update_image_job_status = AsyncMock()

    settings_service = AsyncMock()
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "perfImageWorkers": 1,
            "imageOutputDir": str(tmp_path / "outputs"),
            "thumbnailReferenceMode": "composite",
        }
    )
    routing_service = AsyncMock()
    routing_service.resolve_image_chain = AsyncMock(
        return_value=[SimpleNamespace(provider="fal", sub_model="flux")]
    )
    enforcement_service = AsyncMock()
    enforcement_service.resolve_max_credits = AsyncMock(return_value=10)
    enforcement_service.preflight_quotas_and_balance = AsyncMock()
    hold = SimpleNamespace(held_units=0, plan_covered=True)
    enforcement_service.reserve_and_hold_before_provider = AsyncMock(return_value=hold)
    enforcement_service.finalize_held_operation = AsyncMock(return_value=0)

    generation_service = AsyncMock()
    generation_service.submit_image_outcome = AsyncMock(
        return_value=SimpleNamespace(
            image_bytes=_png_bytes(),
            provider="fal",
            sub_model="flux",
        )
    )

    service = ImageJobService(
        repo=repo,
        settings_service=settings_service,
        routing_service=routing_service,
        enforcement_service=enforcement_service,
        generation_service=generation_service,
    )
    service._resolve_base_image_bytes = AsyncMock(return_value=None)  # type: ignore[method-assign]

    completed = await service.run_pending_jobs(str(user_id), batch_id=str(batch_id), limit=1)

    assert completed == 1
    enforcement_service.preflight_quotas_and_balance.assert_awaited()
    enforcement_service.reserve_and_hold_before_provider.assert_awaited()
    enforcement_service.finalize_held_operation.assert_awaited_once()


@pytest.mark.asyncio
async def test_image_provider_failure_refunds_even_when_prepaid_batch(tmp_path) -> None:
    user_id = uuid4()
    batch_id = uuid4()
    profile_id = uuid4()

    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="Cover art",
        resolution="1920x1080",
        status=TaskStatus.RUNNING,
    )

    repo = AsyncMock()
    repo.claim_image_jobs_for_run = AsyncMock(return_value=[job])
    repo.get_batch_for_user = AsyncMock(
        return_value=Batch(id=batch_id, user_id=user_id, auto_gen_image=True)
    )
    repo.update_image_job_status = AsyncMock()

    settings_service = AsyncMock()
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "perfImageWorkers": 1,
            "imageOutputDir": str(tmp_path / "outputs"),
        }
    )
    routing_service = AsyncMock()
    routing_service.resolve_image_chain = AsyncMock(
        return_value=[SimpleNamespace(provider="fal", sub_model="flux")]
    )
    enforcement_service = AsyncMock()
    enforcement_service.resolve_max_credits = AsyncMock(return_value=10)
    enforcement_service.preflight_quotas_and_balance = AsyncMock()
    hold = SimpleNamespace(held_units=10, plan_covered=False)
    enforcement_service.reserve_and_hold_before_provider = AsyncMock(return_value=hold)
    enforcement_service.refund_failed_operation = AsyncMock()
    enforcement_service.release_operation_quota = AsyncMock()

    generation_service = AsyncMock()
    generation_service.submit_image_outcome = AsyncMock(
        side_effect=RuntimeError("provider boom")
    )

    service = ImageJobService(
        repo=repo,
        settings_service=settings_service,
        routing_service=routing_service,
        enforcement_service=enforcement_service,
        generation_service=generation_service,
    )
    service._resolve_base_image_bytes = AsyncMock(return_value=None)  # type: ignore[method-assign]

    completed = await service.run_pending_jobs(str(user_id), batch_id=str(batch_id), limit=1)

    assert completed == 0
    enforcement_service.refund_failed_operation.assert_awaited()
    call_kwargs = enforcement_service.refund_failed_operation.await_args.kwargs
    assert call_kwargs["prior_ledger_recorded"] is True
    assert call_kwargs["charged_credit_units"] == 10
