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


@pytest.mark.asyncio
async def test_run_pending_jobs_prompt_only_thumbnail_skips_style_sample(tmp_path) -> None:
    user_id = uuid4()
    batch_id = uuid4()
    profile_id = uuid4()
    source_job_id = uuid4()

    background_output = tmp_path / "background.png"
    Image.new("RGB", (1920, 1080), (20, 40, 120)).save(background_output)

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
        style_reference_path=None,
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
            "imageThumbnailSourceMode": "prompt_only",
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
    rotation.pick_sample_path = AsyncMock(return_value="/should/not/be/used.png")

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
    rotation.pick_sample_path.assert_not_awaited()
    generation_request = generation_service.submit_image_outcome.await_args.args[1]
    assert "no style reference" in generation_request.prompt.lower() or "There is no style reference" in generation_request.prompt
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


@pytest.mark.asyncio
async def test_archive_image_output_to_storage_uploads_and_persists_key(monkeypatch) -> None:
    """A successful image job's bytes must be archived to Backblaze (durable — avoids
    paying the AI provider again to regenerate a background/thumbnail) when streaming
    storage is configured, and the returned key persisted on the job row."""
    user_id = uuid4()
    batch_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        status=TaskStatus.SUCCESS,
    )
    repo = AsyncMock()
    service = ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )

    config = SimpleNamespace(configured=True)
    monkeypatch.setattr(
        "platform_api.services.streaming_config_service.resolve_streaming_storage_config",
        AsyncMock(return_value=config),
    )
    storage = AsyncMock()
    storage.upload_bytes = AsyncMock(return_value="images/whatever.png")
    monkeypatch.setattr(
        "platform_api.services.storage_service.StorageService.from_config",
        lambda _config: storage,
    )
    monkeypatch.setattr(service, "_pool_for_storage", lambda: object())

    await service._archive_image_output_to_storage(job=job, user_id=user_id, image_bytes=b"png-bytes")

    storage.upload_bytes.assert_awaited_once()
    kwargs = storage.upload_bytes.await_args.kwargs
    assert kwargs["data"] == b"png-bytes"
    assert kwargs["content_type"] == "image/png"
    expected_key = f"images/{user_id}/{batch_id}/background-ok-{job.id}.png"
    assert kwargs["key"] == expected_key
    repo.update_image_job_storage_key.assert_awaited_once_with(job.id, user_id, storage_key=expected_key)


@pytest.mark.asyncio
async def test_archive_image_output_to_storage_noop_when_not_configured(monkeypatch) -> None:
    """Must never raise or attempt an upload when streaming storage isn't configured
    for this environment — this is a durability bonus, not a hard dependency."""
    user_id = uuid4()
    job = ImageJob(id=uuid4(), user_id=user_id, kind=ImageKind.THUMBNAIL, status=TaskStatus.SUCCESS)
    repo = AsyncMock()
    service = ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )
    monkeypatch.setattr(
        "platform_api.services.streaming_config_service.resolve_streaming_storage_config",
        AsyncMock(return_value=SimpleNamespace(configured=False)),
    )
    monkeypatch.setattr(service, "_pool_for_storage", lambda: object())

    await service._archive_image_output_to_storage(job=job, user_id=user_id, image_bytes=b"png-bytes")

    repo.update_image_job_storage_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_job_output_bytes_falls_back_to_backblaze_when_cache_missing(tmp_path, monkeypatch) -> None:
    """If the local server cache AND the client-path copy are both gone (disk wipe,
    VPS migration, redeploy to a fresh disk), fall back to the durable Backblaze
    archive instead of surfacing a 404 that forces an expensive AI regeneration."""
    user_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        kind=ImageKind.BACKGROUND,
        status=TaskStatus.SUCCESS,
        output_image_path=str(tmp_path / "gone" / "background-16x9.png"),
        storage_key="images/whatever/adhoc/background-ok-job.png",
    )
    repo = AsyncMock()
    repo.get_image_job_by_id = AsyncMock(return_value=job)
    service = ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )
    monkeypatch.setattr(
        service, "_server_image_cache_path", lambda _job_id: tmp_path / "cache" / f"{job.id}.png"
    )
    monkeypatch.setattr(
        service, "_read_archived_image_bytes", AsyncMock(return_value=b"archived-png-bytes")
    )

    data, content_type = await service.read_job_output_bytes(job.id, user_id)

    assert data == b"archived-png-bytes"
    assert content_type == "image/png"
    # Cache should be repopulated so the next read is fast and doesn't hit Backblaze again.
    assert (tmp_path / "cache" / f"{job.id}.png").read_bytes() == b"archived-png-bytes"


@pytest.mark.asyncio
async def test_read_job_output_bytes_raises_when_no_cache_no_client_path_no_archive(
    tmp_path, monkeypatch
) -> None:
    user_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        kind=ImageKind.BACKGROUND,
        status=TaskStatus.SUCCESS,
        output_image_path=str(tmp_path / "gone" / "background-16x9.png"),
        storage_key=None,
    )
    repo = AsyncMock()
    repo.get_image_job_by_id = AsyncMock(return_value=job)
    service = ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )
    monkeypatch.setattr(
        service, "_server_image_cache_path", lambda _job_id: tmp_path / "cache" / f"{job.id}.png"
    )

    from platform_api.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await service.read_job_output_bytes(job.id, user_id)

@pytest.mark.asyncio
async def test_resolve_runtime_sample_path_null_input_falls_through_to_rotation(tmp_path) -> None:
    """Force-regen clears input_image_path; None must not become path literal 'None'."""
    sample = tmp_path / "pack.png"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(sample)
    user_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=uuid4(),
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        input_image_path=None,
        status=TaskStatus.PENDING,
    )
    rotation = AsyncMock()
    rotation.pick_sample_path = AsyncMock(return_value=str(sample))
    repo = AsyncMock()
    repo.get_image_jobs_for_user = AsyncMock(return_value=[])
    service = ImageJobService(
        repo=repo,
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
        image_sample_rotation=rotation,
    )
    path = await service._resolve_runtime_sample_path(
        job=job,
        settings={"imageBackgroundSourceMode": "category"},
        user_id=user_id,
    )
    assert path == str(sample)
    rotation.pick_sample_path.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_base_image_bytes_null_input_uses_rotated_sample(tmp_path) -> None:
    sample = tmp_path / "pack.png"
    Image.new("RGB", (32, 32), (9, 8, 7)).save(sample)
    user_id = uuid4()
    job = ImageJob(
        id=uuid4(),
        user_id=user_id,
        batch_id=uuid4(),
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        input_image_path=None,
        status=TaskStatus.PENDING,
    )
    rotation = AsyncMock()
    rotation.pick_sample_path = AsyncMock(return_value=str(sample))
    service = ImageJobService(
        repo=AsyncMock(get_image_jobs_for_user=AsyncMock(return_value=[])),
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
        image_sample_rotation=rotation,
    )
    data = await service._resolve_base_image_bytes(
        user_id=user_id,
        job=job,
        settings={"imageBackgroundSourceMode": "category"},
    )
    assert data == sample.read_bytes()
