from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from PIL import Image

from platform_api.models.domain import Batch, ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.services.image_job_service import ImageJobService


@pytest.mark.asyncio
async def test_run_pending_jobs_uses_composite_thumbnail_pipeline(tmp_path) -> None:
    user_id = uuid4()
    batch_id = uuid4()
    profile_id = uuid4()
    source_job_id = uuid4()

    background_output = tmp_path / "background.png"
    Image.new("RGB", (1920, 1080), (20, 40, 120)).save(background_output)
    style_sample = tmp_path / "style.png"
    Image.new("RGBA", (640, 360), (0, 0, 0, 255)).save(style_sample)

    thumbnail_job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.THUMBNAIL,
        channel_role=ChannelRole.OK,
        prompt="Thumbnail prompt",
        resolution="1920x1080",
        style_strength=0.5,
        source_job_id=source_job_id,
        style_reference_path=str(style_sample),
        status=TaskStatus.RUNNING,
    )
    source_job = ImageJob(
        id=source_job_id,
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="Background prompt",
        output_image_path=str(background_output),
        status=TaskStatus.SUCCESS,
    )

    repo = AsyncMock()
    repo.claim_image_jobs_for_run = AsyncMock(return_value=[thumbnail_job])
    repo.get_batch_for_user = AsyncMock(return_value=Batch(id=batch_id, user_id=user_id, auto_gen_image=True))
    repo.get_image_job_by_id = AsyncMock(return_value=source_job)
    repo.update_image_job_status = AsyncMock()

    settings_service = AsyncMock()
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "perfImageWorkers": 1,
            "imageOutputDir": str(tmp_path / "outputs"),
            "thumbnailReferenceMode": "composite",
            "imageThumbSamples": [str(style_sample)],
        }
    )
    routing_service = AsyncMock()
    routing_service.resolve_image_chain = AsyncMock(
        return_value=[SimpleNamespace(provider="fal", sub_model="flux")]
    )
    enforcement_service = AsyncMock()
    hold = SimpleNamespace(held_units=0, plan_covered=True)
    enforcement_service.resolve_max_credits = AsyncMock(return_value=5)
    enforcement_service.preflight_quotas_and_balance = AsyncMock()
    enforcement_service.reserve_and_hold_before_provider = AsyncMock(return_value=hold)
    enforcement_service.finalize_held_operation = AsyncMock(return_value=0)
    generation_service = AsyncMock()
    generation_service.submit_image_outcome = AsyncMock(
        return_value=SimpleNamespace(
            image_bytes=_solid_overlay_png(),
            provider="fal",
            sub_model="flux",
        )
    )

    rotation = AsyncMock()
    rotation.pick_sample_path = AsyncMock(return_value=str(style_sample))

    service = ImageJobService(
        repo=repo,
        settings_service=settings_service,
        routing_service=routing_service,
        enforcement_service=enforcement_service,
        generation_service=generation_service,
        image_sample_rotation=rotation,
    )

    completed = await service.run_pending_jobs(str(user_id), batch_id=str(batch_id), limit=1)

    assert completed == 1
    routing_service.resolve_image_chain.assert_awaited_with("thumbnail_image")
    generation_request = generation_service.submit_image_outcome.await_args.args[1]
    assert generation_request.prompt.startswith("Thumbnail prompt")
    assert generation_request.base_image is not None
    assert generation_request.base_image != background_output.read_bytes()
    enforcement_service.preflight_quotas_and_balance.assert_awaited()
    enforcement_service.reserve_and_hold_before_provider.assert_awaited()
    enforcement_service.finalize_held_operation.assert_awaited()
    enforcement_service.deduct_for_operation.assert_not_awaited()
    repo.update_image_job_status.assert_awaited()


def _solid_overlay_png() -> bytes:
    from io import BytesIO

    image = Image.new("RGBA", (1920, 1080), (255, 220, 40, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_write_image_output_uses_role_suffix_when_run_dirs_match(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    batch = Batch(
        id=uuid4(),
        user_id=uuid4(),
        ok_run_dir=str(run_dir),
        alt_run_dir=str(run_dir),
    )
    job = ImageJob(
        id=uuid4(),
        user_id=batch.user_id,
        batch_id=batch.id,
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.ALT,
        resolution="1920x1080",
        status=TaskStatus.RUNNING,
    )
    service = ImageJobService(
        repo=AsyncMock(),
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )
    output_path = service._write_image_output(
        image_bytes=b"png-bytes",
        user_id=batch.user_id,
        job=job,
        settings={"imageOutputDir": str(tmp_path / "fallback")},
        batch=batch,
    )
    assert output_path.endswith("background-16x9-alt.png")
    assert (run_dir / "background-16x9-alt.png").read_bytes() == b"png-bytes"


def test_write_image_output_uses_canonical_run_folder_name(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    batch = Batch(
        id=uuid4(),
        user_id=uuid4(),
        ok_run_dir=str(run_dir),
        alt_run_dir=str(run_dir / "alt"),
    )
    job = ImageJob(
        id=uuid4(),
        user_id=batch.user_id,
        batch_id=batch.id,
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        resolution="1920x1080",
        status=TaskStatus.RUNNING,
    )
    service = ImageJobService(
        repo=AsyncMock(),
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )
    output_path = service._write_image_output(
        image_bytes=b"png-bytes",
        user_id=batch.user_id,
        job=job,
        settings={"imageOutputDir": str(tmp_path / "fallback")},
        batch=batch,
    )
    assert output_path.endswith("background-16x9.png")
    assert (run_dir / "background-16x9.png").read_bytes() == b"png-bytes"
