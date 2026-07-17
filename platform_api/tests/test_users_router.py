"""Tests for the users router account endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.routers import users as users_router
from platform_api.routers.users import _get_user_service


USER_ID = uuid4()
USER_CONTEXT = AuthContext(user_id=str(USER_ID), email="boss@example.com", role="user")
ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")


class FakeDbPool:
    """Small fake asyncpg pool for `/users/me` enrichment tests."""

    def __init__(self, *, balance=None, license_row=None, profile_row=None) -> None:
        self._balance = balance
        self._license_row = license_row
        self._profile_row = profile_row

    async def fetchrow(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from credit_wallets" in sql:
            return self._balance
        if "from licenses l" in sql and "join plans p" in sql:
            return self._license_row
        if "from channel_profiles" in sql:
            return self._profile_row
        raise AssertionError(f"Unexpected query: {query}")


class FakeUserDetailDbPool:
    async def fetchrow(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from credit_wallets" in sql:
            return {"balance": 450}
        if "sum(abs(amount))" in sql:
            return {"total": 120}
        if "from licenses l" in sql and "join plans p" in sql:
            return {
                "plan_id": uuid4(),
                "license_status": "active",
                "activated_at": datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
                "expires_at": datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc),
                "plan_name": "Pro",
            }
        if "from suno_tasks" in sql:
            return {"cnt": 7}
        if "from image_jobs" in sql:
            return {"cnt": 11}
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def fetch(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from credit_transactions" in sql:
            return []
        if "from channel_profiles" in sql:
            return [
                {
                    "id": uuid4(),
                    "name": "Boss Primary",
                    "folder_name": "boss-primary",
                    "run_prefix": "BP",
                    "created_at": datetime(2026, 6, 25, 10, 30, tzinfo=timezone.utc),
                    "logo_path": "uploads/logos/boss-primary.png",
                    "video_template_id": "video-template-1",
                    "reel_template_id": "reel-template-1",
                    "output_resolution": "1920x1080",
                    "image_config": {
                        "genre": "Pop",
                        "role": "primary",
                        "cover_paths": ["uploads/covers/cover-1.png"],
                    },
                    "youtube_config": {
                        "description": "Primary channel description",
                        "keywords": ["keyword one", "keyword two"],
                        "tags": ["tag-one"],
                        "visibility": "scheduled",
                        "publish_at": "2026-07-01T09:30:00",
                        "made_for_kids": False,
                        "ai_use": True,
                        "category": "10",
                        "playlist": "playlist-123",
                        "title_template": "Title {n}",
                        "description_template": "Description template",
                    },
                }
            ]
        if "from profile_video_templates" in sql:
            return [
                {
                    "id": "video-template-1",
                    "name": "Boss Neon Drive",
                    "updated_at": datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
                },
                {
                    "id": "reel-template-1",
                    "name": "Boss Reel Stack",
                    "updated_at": datetime(2026, 7, 2, 8, 0, tzinfo=timezone.utc),
                },
            ]
        raise AssertionError(f"Unexpected fetch query: {query}")


def _make_user() -> User:
    return User(
        id=USER_ID,
        email="boss@example.com",
        password_hash="hashed-password",
        display_name="Boss User",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        created_at=datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 24, 13, 30, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_user_service() -> AsyncMock:
    service = AsyncMock()
    service.get_user = AsyncMock(return_value=_make_user())
    return service


@pytest.fixture
def app(mock_user_service: AsyncMock):
    application = create_app()
    application.dependency_overrides[_get_user_service] = lambda: mock_user_service
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestGetMe:
    """Tests for `GET /api/v1/users/me`."""

    async def test_enriches_plan_balance_and_profile_count(
        self,
        client: AsyncClient,
        mock_user_service: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            users_router,
            "get_db_pool",
            lambda: FakeDbPool(
                balance={"balance": 275},
                license_row={"plan_name": "Pro", "profile_allowance": 4},
                profile_row={"cnt": 2},
            ),
        )

        response = await client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "boss@example.com"
        assert data["display_name"] == "Boss User"
        assert data["plan_name"] == "Pro"
        assert data["profile_allowance"] == 4
        assert data["credit_balance"] == 275
        assert data["channel_profile_count"] == 2
        mock_user_service.get_user.assert_awaited_once_with(USER_ID)

    async def test_defaults_when_optional_rows_are_missing(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            users_router,
            "get_db_pool",
            lambda: FakeDbPool(balance=None, license_row=None, profile_row=None),
        )

        response = await client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["plan_name"] is None
        assert data["profile_allowance"] is None
        assert data["credit_balance"] == 0
        assert data["channel_profile_count"] == 0


class TestGetUserFullDetails:
    async def test_returns_extended_channel_profile_sync_fields(
        self,
        app,
        mock_user_service: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: ADMIN_CONTEXT
        monkeypatch.setattr(users_router, "get_db_pool", lambda: FakeUserDetailDbPool())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/users/{USER_ID}/details")

        assert response.status_code == 200
        data = response.json()
        assert data["plan_name"] == "Pro"
        assert data["total_songs_generated"] == 7
        assert data["total_images_generated"] == 11
        assert len(data["channel_profiles"]) == 1
        profile = data["channel_profiles"][0]
        assert profile["name"] == "Boss Primary"
        assert profile["logo_available"] is True
        assert profile["cover_count"] == 1
        assert profile["description"] == "Primary channel description"
        assert profile["keywords"] == ["keyword one", "keyword two"]
        assert profile["tags"] == ["tag-one"]
        assert profile["run_prefix"] == "BP"
        assert profile["output_resolution"] == "1920x1080"
        assert profile["video_template_id"] == "video-template-1"
        assert profile["reel_template_id"] == "reel-template-1"
        assert profile["video_template_name"] == "Boss Neon Drive"
        assert profile["video_template_available"] is True
        assert profile["reel_template_name"] == "Boss Reel Stack"
        assert profile["reel_template_available"] is True
        assert profile["visibility"] == "scheduled"
        assert profile["publish_at"] == "2026-07-01T09:30:00"
        assert profile["made_for_kids"] is False
        assert profile["ai_use"] is True
        assert profile["playlist"] == "playlist-123"
        assert profile["title_template"] == "Title {n}"
        assert profile["description_template"] == "Description template"
