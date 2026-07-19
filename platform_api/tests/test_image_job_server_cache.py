from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from PIL import Image

from platform_api.models.domain import ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.services.image_job_service import ImageJobService


@pytest.mark.asyncio
async def test_resolve_source_background_path_uses_server_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_IMAGE_OUTPUT_CACHE_DIR", str(tmp_path / "cache"))
    from platform_api.config import get_settings

    get_settings.cache_clear()

    user_id = uuid4()
    source_job_id = uuid4()
    cache_path = tmp_path / "cache" / f"{source_job_id}.png"
    cache_path.parent.mkdir(parents=True)
    Image.new("RGB", (64, 64), (10, 20, 30)).save(cache_path)

    source_job = ImageJob(
        id=source_job_id,
        user_id=user_id,
        batch_id=uuid4(),
        profile_id=uuid4(),
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        prompt="Background",
        output_image_path=r"D:\MusicGenerator\outputs\background-16x9.png",
        status=TaskStatus.SUCCESS,
    )

    service = ImageJobService(
        repo=AsyncMock(),
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )

    try:
        resolved = await service._resolve_source_background_path(user_id, source_job)
        assert resolved == str(cache_path.resolve())
    finally:
        get_settings.cache_clear()
