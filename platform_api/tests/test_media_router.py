from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.dependencies import set_db_pool


USER_ID = uuid4()
OTHER_USER_ID = uuid4()
PROFILE_ID = uuid4()


class FakePool:
    def __init__(self, row: dict) -> None:
        self._row = row

    async def fetchrow(self, _query: str, *_args):
        return self._row


def _write_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00")


@pytest.fixture
def app():
    application = create_app()
    yield application


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMedia:
    async def test_user_can_fetch_own_logo(self, app, client: AsyncClient):
        logo_rel = os.path.join("uploads", "logos", str(USER_ID), "logo.png")
        logo_abs = Path(logo_rel).resolve()
        _write_file(logo_abs)

        try:
            set_db_pool(FakePool({"id": PROFILE_ID, "user_id": USER_ID, "logo_path": logo_rel, "image_config": {}}))
            app.dependency_overrides[get_current_user] = lambda: AuthContext(user_id=str(USER_ID), email="u@x.com", role="user")

            resp = await client.get(f"/api/v1/media/channel-profiles/{PROFILE_ID}/logo")
            assert resp.status_code == 200
        finally:
            try:
                logo_abs.unlink()
            except Exception:
                pass

    async def test_user_cannot_fetch_other_logo(self, app, client: AsyncClient):
        logo_rel = os.path.join("uploads", "logos", str(OTHER_USER_ID), "logo.png")
        logo_abs = Path(logo_rel).resolve()
        _write_file(logo_abs)

        try:
            set_db_pool(FakePool({"id": PROFILE_ID, "user_id": OTHER_USER_ID, "logo_path": logo_rel, "image_config": {}}))
            app.dependency_overrides[get_current_user] = lambda: AuthContext(user_id=str(USER_ID), email="u@x.com", role="user")

            resp = await client.get(f"/api/v1/media/channel-profiles/{PROFILE_ID}/logo")
            assert resp.status_code == 404
        finally:
            try:
                logo_abs.unlink()
            except Exception:
                pass

    async def test_admin_can_fetch_other_logo(self, app, client: AsyncClient):
        logo_rel = os.path.join("uploads", "logos", str(OTHER_USER_ID), "logo.png")
        logo_abs = Path(logo_rel).resolve()
        _write_file(logo_abs)

        try:
            set_db_pool(FakePool({"id": PROFILE_ID, "user_id": OTHER_USER_ID, "logo_path": logo_rel, "image_config": {}}))
            app.dependency_overrides[get_current_user] = lambda: AuthContext(user_id=str(USER_ID), email="admin@x.com", role="admin")

            resp = await client.get(f"/api/v1/media/channel-profiles/{PROFILE_ID}/logo")
            assert resp.status_code == 200
        finally:
            try:
                logo_abs.unlink()
            except Exception:
                pass

    async def test_cover_index_bounds(self, app, client: AsyncClient):
        cover_rel = os.path.join("uploads", "covers", str(USER_ID), "cover-0.png")
        cover_abs = Path(cover_rel).resolve()
        _write_file(cover_abs)

        try:
            set_db_pool(
                FakePool(
                    {
                        "id": PROFILE_ID,
                        "user_id": USER_ID,
                        "logo_path": None,
                        "image_config": {"cover_paths": [cover_rel]},
                    }
                )
            )
            app.dependency_overrides[get_current_user] = lambda: AuthContext(user_id=str(USER_ID), email="u@x.com", role="user")

            resp = await client.get(f"/api/v1/media/channel-profiles/{PROFILE_ID}/covers/2")
            assert resp.status_code == 404
        finally:
            try:
                cover_abs.unlink()
            except Exception:
                pass
