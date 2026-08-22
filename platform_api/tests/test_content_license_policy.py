"""Policy tests for content license play vs export."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ForbiddenError
from platform_api.services.content_license_service import ContentLicenseService, decrypt_module_hash


@pytest.mark.asyncio
async def test_assert_play_access_allows_published_catalog() -> None:
    pool = AsyncMock()
    track_id = uuid4()
    user_id = uuid4()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": track_id,
            "user_id": uuid4(),
            "publish_status": "published",
            "package_status": "ready",
            "content_key_id": uuid4(),
            "packaged_storage_key": "a.cxa",
            "packaged_storage_key_b": None,
            "variant": "ok",
        }
    )
    service = ContentLicenseService(pool)
    result = await service.assert_play_access(
        user_id,
        subject_type="stream_track",
        subject_id=track_id,
        variant="ok",
    )
    assert result["access"] == "play"
    assert result["owner"] is False


@pytest.mark.asyncio
async def test_assert_play_access_rejects_private_suno_task() -> None:
    pool = AsyncMock()
    task_id = uuid4()
    owner_id = uuid4()
    listener_id = uuid4()

    async def fetchrow(query: str, *args):
        del args
        if "FROM suno_tasks" in query:
            return {
                "id": task_id,
                "user_id": owner_id,
                "source": "web_music",
                "package_status_ok": "ready",
                "package_status_alt": "none",
                "content_key_id_ok": uuid4(),
                "content_key_id_alt": None,
                "packaged_storage_key_ok": "a.cxa",
                "packaged_storage_key_alt": None,
                "packaged_storage_key_ok_b": None,
                "packaged_storage_key_alt_b": None,
                "encrypted_original_key_ok": "a.cxo",
                "encrypted_original_key_alt": None,
                "b2_storage_key_ok": "a.mp3",
                "b2_storage_key_alt": None,
            }
        return None

    pool.fetchrow = fetchrow
    service = ContentLicenseService(pool)
    with pytest.raises(ForbiddenError):
        await service.assert_play_access(
            listener_id,
            subject_type="suno_task",
            subject_id=task_id,
            variant="ok",
        )


@pytest.mark.asyncio
async def test_assert_export_access_requires_owner_and_paid() -> None:
    pool = AsyncMock()
    task_id = uuid4()
    owner_id = uuid4()
    other_id = uuid4()
    pool.fetchrow = AsyncMock(
        return_value={"id": task_id, "user_id": owner_id, "source": "web_music"}
    )
    service = ContentLicenseService(pool)
    with pytest.raises(ForbiddenError, match="your own tracks"):
        await service.assert_export_access(other_id, task_id)

    service._active_paid = AsyncMock(return_value=False)
    with pytest.raises(ForbiddenError, match="paid subscription"):
        await service.assert_export_access(owner_id, task_id)

    service._active_paid = AsyncMock(return_value=True)
    row = await service.assert_export_access(owner_id, task_id)
    assert row["id"] == task_id


def test_decrypt_module_hash_is_stable() -> None:
    assert len(decrypt_module_hash()) == 64
    assert decrypt_module_hash() == decrypt_module_hash()
