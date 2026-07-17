from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.image_job_service import ImageJobService


@pytest.mark.asyncio
async def test_retry_jobs_rejects_invalid_batch_id() -> None:
    service = ImageJobService(
        repo=AsyncMock(),
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )

    with pytest.raises(ValidationError):
        await service.retry_jobs(str(uuid4()), batch_id="not-a-uuid")


@pytest.mark.asyncio
async def test_retry_jobs_rejects_empty_job_id() -> None:
    service = ImageJobService(
        repo=AsyncMock(),
        settings_service=AsyncMock(),
        routing_service=AsyncMock(),
        enforcement_service=AsyncMock(),
        generation_service=AsyncMock(),
    )

    with pytest.raises(ValidationError):
        await service.retry_jobs(str(uuid4()), job_ids=[""])
