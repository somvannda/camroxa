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
        if "from billing_payments" in sql:
            return None
        raise AssertionError(f"Unexpected query: {query}")


class FakeUserDetailDbPool:
    async def fetchrow(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from credit_wallets" in sql:
            return {"balance": 450}
        if "from credit_transactions" in sql and "sum(" in sql:
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
        if "from music_descriptions" in sql or "from music_structures" in sql:
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
        if "from music_descriptions" in sql or "from music_structures" in sql:
            return []
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
                license_row={
                    "plan_name": "Pro",
                    "profile_allowance": 4,
                    "profile_addon_slots": 0,
                    "profile_addon_pending": 0,
                    "distrokid_enabled": False,
                    "distrokid_expires_at": None,
                },
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
        assert data["credit_balance"] == 0.0275
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
        monkeypatch.setattr(
            users_router,
            "upload_path_exists",
            lambda value: bool(str(value or "").strip()),
        )

        fake_topup = AsyncMock()
        fake_topup.build_period_snapshot = AsyncMock(
            return_value=type(
                "Snap",
                (),
                {
                    "period_start": None,
                    "period_end": None,
                    "plan_name": "Pro",
                    "kinds": {},
                },
            )()
        )
        monkeypatch.setattr(
            "platform_api.dependencies.get_quota_topup_service",
            lambda: fake_topup,
        )
        monkeypatch.setattr(
            "platform_api.services.quota_topup_service.snapshot_to_dict",
            lambda snap: {
                "period_start": None,
                "period_end": None,
                "plan_name": "Pro",
                "kinds": {},
            },
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/users/{USER_ID}/details")

        assert response.status_code == 200
        data = response.json()
        assert data["plan_name"] == "Pro"
        assert data["quota_period"] is not None
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

    async def test_quota_topup_endpoint_grants_and_returns_status(
        self,
        app,
        mock_user_service: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: ADMIN_CONTEXT
        mock_user_service.get_user = AsyncMock(return_value=_make_user())

        grant_result = {
            "id": str(uuid4()),
            "user_id": str(USER_ID),
            "quota_kind": "music",
            "amount": 10,
            "reason": "support",
            "period_start": "2026-07-10",
            "period_end": "2026-08-09",
            "base_limit": 100,
            "topup_extra": 10,
            "effective_limit": 110,
            "used": 5,
            "remaining": 105,
        }
        fake_topup = AsyncMock()
        fake_topup.grant = AsyncMock(return_value=grant_result)
        fake_topup.build_period_snapshot = AsyncMock(
            return_value=type("Snap", (), {})()
        )
        monkeypatch.setattr(
            "platform_api.dependencies.get_quota_topup_service",
            lambda: fake_topup,
        )
        monkeypatch.setattr(
            "platform_api.services.quota_topup_service.snapshot_to_dict",
            lambda snap: {
                "period_start": "2026-07-10",
                "period_end": "2026-08-09",
                "plan_name": "Pro",
                "kinds": {
                    "music": {
                        "quota_kind": "music",
                        "base_limit": 100,
                        "topup_extra": 10,
                        "effective_limit": 110,
                        "used": 5,
                        "remaining": 105,
                    }
                },
            },
        )
        monkeypatch.setattr(
            users_router,
            "get_db_pool",
            lambda: FakeDbPool(balance={"balance": 0}),
        )
        fake_audit = AsyncMock()
        fake_audit.log_event = AsyncMock()
        monkeypatch.setattr(
            "platform_api.dependencies.get_audit_service",
            lambda: fake_audit,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/users/{USER_ID}/quota-topups",
                json={"quota_kind": "music", "amount": 10, "reason": "support"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["quota_kind"] == "music"
        assert data["amount"] == 10
        assert data["effective_limit"] == 110
        assert data["quota_period"]["kinds"]["music"]["topup_extra"] == 10
        fake_topup.grant.assert_awaited_once()
        fake_audit.log_event.assert_awaited_once()


class TestAdminSetPassword:
    async def test_sets_password_and_revokes_tokens(
        self,
        app,
        mock_user_service: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: ADMIN_CONTEXT
        mock_user_service.get_user = AsyncMock(return_value=_make_user())

        fake_repo = AsyncMock()
        fake_repo.update = AsyncMock(return_value=_make_user())
        fake_auth = AsyncMock()
        fake_auth.revoke_tokens = AsyncMock()

        monkeypatch.setattr("platform_api.dependencies.get_user_repo", lambda: fake_repo)
        monkeypatch.setattr("platform_api.dependencies.get_auth_service", lambda: fake_auth)
        monkeypatch.setattr(
            "platform_api.services.auth_service.AuthService.hash_password",
            staticmethod(lambda pwd: f"hashed_{pwd}"),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/users/{USER_ID}/set-password",
                json={"password": "NewPass123"},
            )

        assert response.status_code == 200
        fake_repo.update.assert_awaited_once()
        kwargs = fake_repo.update.await_args.kwargs
        assert kwargs["password_hash"] == "hashed_NewPass123"
        fake_auth.revoke_tokens.assert_awaited_once_with(str(USER_ID))

    async def test_rejects_weak_password(
        self,
        app,
        mock_user_service: AsyncMock,
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: ADMIN_CONTEXT
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/users/{USER_ID}/set-password",
                json={"password": "weakpass"},
            )
        assert response.status_code == 422
