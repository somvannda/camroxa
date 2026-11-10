"""Route-level tests for Phase 1 creator identity."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.creator_studio import _get_creator_service as studio_service
from platform_api.routers.creators_public import _get_creator_service as public_service


def _profile_payload(handle: str = "sokha") -> dict:
    return {
        "handle": handle,
        "display_name": "Sokha Chan",
        "tagline": "Khmer pop for the ride home.",
        "bio": "Late-night Khmer pop.",
        "avatar_url": None,
        "banner_url": None,
        "country_code": "KH",
        "city": "Phnom Penh",
        "genres": ["Khmer Pop"],
        "influences": [],
        "links": [],
        "ai_disclosure": "ai_assisted",
        "tier": "creator",
        "badges": [],
        "support_enabled": False,
        "joined_at": datetime.now(timezone.utc),
        "stats": {
            "followers": 0,
            "monthly_listeners": 0,
            "releases": 0,
            "valid_streams": 0,
        },
        "is_following": False,
    }


class _FakeService:
    async def list_public(self, **_kwargs):
        return {"items": [_profile_payload()], "total": 1, "limit": 24, "offset": 0}

    async def get_public(self, handle: str):
        return _profile_payload(handle) if handle == "sokha" else None

    async def get_studio(self, _user_id: str):
        return {
            "profile": {**_profile_payload(), "user_id": str(uuid4())},
            "checklist": {"handle": True, "display_name": True},
        }

    async def claim(self, _user_id: str, _data: dict):
        return {
            "profile": {**_profile_payload(), "user_id": str(uuid4())},
            "checklist": {"handle": True, "display_name": True},
        }

    async def update(self, _user_id: str, _data: dict):
        return await self.get_studio(_user_id)

    async def availability(self, handle: str):
        return {"handle": handle, "available": True, "reason": None, "suggestions": []}


@pytest.fixture()
def app():
    application = create_app()
    fake = _FakeService()
    application.dependency_overrides[public_service] = lambda: fake
    application.dependency_overrides[studio_service] = lambda: fake
    application.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id=str(uuid4()), email="creator@example.com", role="user"
    )
    return application


@pytest.mark.asyncio
async def test_public_creator_routes(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/v3/creators")
        profile = await client.get("/api/v3/creators/sokha")
        missing = await client.get("/api/v3/creators/nobody")

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert profile.status_code == 200
    assert profile.json()["handle"] == "sokha"
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_studio_creator_routes(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        me = await client.get("/api/v3/creator/me")
        claimed = await client.post(
            "/api/v3/creator/claim",
            json={"handle": "sokha", "display_name": "Sokha Chan"},
        )
        available = await client.get("/api/v3/creator/handle-available?handle=sokha")

    assert me.status_code == 200
    assert me.json()["profile"]["handle"] == "sokha"
    assert claimed.status_code == 201
    assert claimed.json()["profile"]["handle"] == "sokha"
    assert available.status_code == 200
    assert available.json()["available"] is True
