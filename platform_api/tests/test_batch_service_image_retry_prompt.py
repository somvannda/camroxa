from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.models.domain import ImageJob, Song
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.services.batch_service import BatchService


@pytest.mark.asyncio
async def test_refresh_image_job_prompts_for_retry_updates_job_prompt() -> None:
    user_id = uuid4()
    job_id = uuid4()
    song_id = uuid4()
    profile_id = uuid4()
    batch_id = uuid4()

    song = Song(
        id=song_id,
        batch_id=batch_id,
        user_id=user_id,
        title="Chrome Veins",
        album="Bass Drive",
        status=TaskStatus.SUCCESS,
    )
    profile = type(
        "Profile",
        (),
        {
            "image_config": {
                "background_prompt": "profile bg",
                "thumbnail_prompt": "profile th",
            }
        },
    )()
    job = ImageJob(
        id=job_id,
        song_id=song_id,
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt=None,
        status=TaskStatus.FAILED,
    )

    batch_repo = AsyncMock()
    batch_repo.get_image_jobs_for_user = AsyncMock(return_value=[job])
    batch_repo.get_song_by_id = AsyncMock(return_value=song)
    batch_repo.update_image_job_prompt = AsyncMock()

    profile_repo = AsyncMock()
    profile_repo.get_by_id = AsyncMock(return_value=profile)

    settings_service = AsyncMock()
    settings_service.get_merged_settings = AsyncMock(
        return_value={"imageBackgroundPrompt": "user bg prompt"}
    )

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=profile_repo,
        ai_routing_service=AsyncMock(),
        prompt_service=AsyncMock(),
        settings_service=settings_service,
        enforcement_service=AsyncMock(),
    )

    refreshed = await service.refresh_image_job_prompts_for_retry(
        user_id=str(user_id),
        job_ids=[str(job_id)],
    )

    assert refreshed == 1
    batch_repo.update_image_job_prompt.assert_awaited_once()
    assert "user bg prompt" in batch_repo.update_image_job_prompt.await_args.kwargs["prompt"]
