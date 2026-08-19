"""Tests for admin Camxora Music generation browser endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers import admin_user_web_music as admin_web_music


USER_ID = uuid4()
TASK_ID = uuid4()
WORKSPACE_ID = uuid4()
ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
USER_CONTEXT = AuthContext(user_id=str(USER_ID), email="boss@example.com", role="user")


class FakeAdminMusicPool:
    def __init__(self, *, workspaces=None, tasks=None, audio_row=None, lyrics_row=None) -> None:
        self.workspaces = workspaces or []
        self.tasks = tasks or []
        self.audio_row = audio_row
        self.lyrics_row = lyrics_row

    async def fetchrow(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from users" in sql:
            return {"ok": 1} if args and args[0] == USER_ID else None
        if "from web_music_workspaces" in sql and "id =" in sql:
            return {"id": WORKSPACE_ID} if args and args[0] == WORKSPACE_ID else None
        if "from suno_tasks" in sql and "audio_url_ok" in sql and "where id" in sql:
            return self.audio_row
        if "from suno_tasks" in sql and ("lyrics" in sql or "b2_lrc" in sql) and "where id" in sql:
            return self.lyrics_row
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def fetch(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from web_music_workspaces" in sql:
            return self.workspaces
        if "from suno_tasks" in sql:
            return self.tasks
        raise AssertionError(f"Unexpected fetch query: {query}")

    async def fetchval(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "count(*)" in sql and "from suno_tasks" in sql:
            return len(self.tasks)
        raise AssertionError(f"Unexpected fetchval query: {query}")


@pytest.fixture
def app():
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: ADMIN_CONTEXT
    yield application
    application.dependency_overrides.clear()


async def _get(app, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


class TestAdminUserWebMusic:
    async def test_lists_workspaces_and_generations(
        self,
        app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pool = FakeAdminMusicPool(
            workspaces=[
                {
                    "id": WORKSPACE_ID,
                    "name": "My Workspace",
                    "is_default": True,
                    "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
                }
            ],
            tasks=[
                {
                    "id": TASK_ID,
                    "title": "Fire in My Veins",
                    "lyrics": "[00:01.00]One\n[00:04.00]Two",
                    "style": "Modern Khmer R&B Pop",
                    "model": "V5_5",
                    "instrumental": False,
                    "status": "success",
                    "audio_url_ok": "https://cdn.example/ok.mp3",
                    "audio_url_alt": None,
                    "error_message": None,
                    "created_at": datetime(2026, 8, 18, tzinfo=timezone.utc),
                    "negative_tags": "No traditional Khmer instruments",
                    "vocal_gender": "m",
                    "style_weight": 0.5,
                    "weirdness_constraint": 0.5,
                    "audio_weight": 0.5,
                    "b2_storage_key_ok": None,
                    "b2_storage_key_alt": None,
                    "workspace_id": WORKSPACE_ID,
                    "image_url_ok": "https://cdn.example/cover.jpg",
                    "image_url_alt": None,
                    "duration_ok": 187.0,
                    "duration_alt": None,
                }
            ],
        )
        monkeypatch.setattr(admin_web_music, "get_db_pool", lambda: pool)

        workspaces = await _get(app, f"/api/v1/users/{USER_ID}/web-music/workspaces")
        assert workspaces.status_code == 200
        assert workspaces.json()["items"][0]["name"] == "My Workspace"

        generations = await _get(
            app,
            f"/api/v1/users/{USER_ID}/web-music/generations?workspace_id={WORKSPACE_ID}",
        )
        assert generations.status_code == 200
        payload = generations.json()
        assert payload["total"] == 1
        song = payload["items"][0]
        assert song["title"] == "Fire in My Veins"
        assert song["model"] == "V5_5"
        assert song["vocal_gender"] == "m"
        assert song["negative_tags"] == "No traditional Khmer instruments"
        assert song["clips"][0]["ready"] is True
        assert song["clips"][0]["duration_seconds"] == 187.0
        assert song["clips"][1]["ready"] is False
        assert "/audio?variant=ok" in song["clips"][0]["audio_url"]

    async def test_forbids_non_admin(self, app) -> None:
        app.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
        response = await _get(app, f"/api/v1/users/{USER_ID}/web-music/workspaces")
        assert response.status_code == 403

    async def test_streams_mp3_bytes(
        self,
        app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pool = FakeAdminMusicPool()
        monkeypatch.setattr(admin_web_music, "get_db_pool", lambda: pool)

        async def fake_load(*_args, **_kwargs):
            return (b"ID3fake-mp3", "Fire in My Veins-ok.mp3", "audio/mpeg")

        monkeypatch.setattr(admin_web_music, "_load_clip_audio", fake_load)
        response = await _get(
            app,
            f"/api/v1/users/{USER_ID}/web-music/generations/{TASK_ID}/audio?variant=ok",
        )
        assert response.status_code == 200
        assert response.content == b"ID3fake-mp3"
        assert "audio/mpeg" in response.headers["content-type"]

    async def test_unknown_user_is_404(
        self,
        app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pool = FakeAdminMusicPool()
        monkeypatch.setattr(admin_web_music, "get_db_pool", lambda: pool)
        response = await _get(app, f"/api/v1/users/{uuid4()}/web-music/workspaces")
        assert response.status_code == 404
