from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from platform_api.models.domain import ChannelProfile
from platform_api.repositories.profile_repo import ProfileRepository


class FakePool:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object):
        self.fetchrow_calls.append((query, args))
        return {
            "id": args[0] if len(args) > 0 else uuid4(),
            "user_id": args[1] if len(args) > 1 else uuid4(),
            "name": args[2] if len(args) > 2 else "Profile",
            "folder_name": args[3] if len(args) > 3 else None,
            "run_prefix": args[4] if len(args) > 4 else None,
            "logo_path": args[5] if len(args) > 5 else None,
            "video_template_id": args[6] if len(args) > 6 else None,
            "reel_template_id": args[7] if len(args) > 7 else None,
            "output_resolution": args[8] if len(args) > 8 else "1920x1080",
            "image_config": args[9] if len(args) > 9 else "{}",
            "youtube_config": args[10] if len(args) > 10 else "{}",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }


@pytest.mark.asyncio
async def test_create_serializes_jsonb_fields() -> None:
    pool = FakePool()
    repo = ProfileRepository(pool)
    profile = ChannelProfile(
      id=uuid4(),
      user_id=uuid4(),
      name="Debug Profile",
      image_config={"palette": "sunset"},
      youtube_config={"visibility": "unlisted"},
    )

    await repo.create(profile)

    query, args = pool.fetchrow_calls[0]
    assert "$10::jsonb" in query
    assert "$11::jsonb" in query
    assert json.loads(args[9]) == {"palette": "sunset"}
    assert json.loads(args[10]) == {"visibility": "unlisted"}


@pytest.mark.asyncio
async def test_update_serializes_jsonb_fields() -> None:
    pool = FakePool()
    repo = ProfileRepository(pool)
    profile_id = uuid4()
    user_id = uuid4()

    await repo.update(
        profile_id,
        user_id,
        image_config={"theme": "dark"},
        youtube_config={"category": "10"},
        name="Updated Profile",
    )

    query, args = pool.fetchrow_calls[0]
    assert "image_config = $1::jsonb" in query
    assert "youtube_config = $2::jsonb" in query
    assert "name = $3" in query
    assert json.loads(args[0]) == {"theme": "dark"}
    assert json.loads(args[1]) == {"category": "10"}
    assert args[2] == "Updated Profile"
