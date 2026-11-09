"""Route tests for Creator Program workflow endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.routers.admin_creators import _get_program_service as admin_program
from platform_api.routers.creator_studio import _get_program_service as studio_program


class _FakeProgram:
    async def get_status(self, _user_id: str):
        return {"application": None, "verifications": [], "badges": []}

    async def submit_application(self, _user_id: str, _payload: dict):
        return {"application": {"id": str(uuid4()), "status": "submitted"}}

    async def withdraw_application(self, _user_id: str):
        return {"application": {"status": "withdrawn"}}

    async def submit_verification(self, _user_id: str, *, kind: str, evidence_ref: str):
        return {"verification": {"kind": kind, "status": "pending"}}

    async def list_applications(self, **_kwargs):
        return {"items": [], "total": 0, "limit": 50, "offset": 0}

    async def decide_application(self, application_id: str, **_kwargs):
        return {"application": {"id": application_id, "status": "approved"}}

    async def list_pending_verifications(self, **_kwargs):
        return {"items": [], "limit": 50, "offset": 0}

    async def decide_verification(self, verification_id: str, **_kwargs):
        return {"verification": {"id": verification_id, "status": "approved"}}

    async def grant_badge(self, user_id: str, **kwargs):
        return {"badge": {"user_id": user_id, "badge": kwargs["badge"]}}

    async def revoke_badge(self, user_id: str, **kwargs):
        return {"badge": {"user_id": user_id, "badge": kwargs["badge"]}}


@pytest.fixture()
def app():
    application = create_app()
    fake = _FakeProgram()
    application.dependency_overrides[studio_program] = lambda: fake
    application.dependency_overrides[admin_program] = lambda: fake
    application.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id=str(uuid4()), email="creator@example.com", role="user"
    )
    application.dependency_overrides[require_admin] = lambda: AuthContext(
        user_id=str(uuid4()), email="admin@example.com", role="admin"
    )
    return application


@pytest.mark.asyncio
async def test_creator_application_routes(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status = await client.get("/api/v3/creator/application")
        submitted = await client.post(
            "/api/v3/creator/application",
            json={
                "pitch": "I make late-night Khmer pop about the city and the ride home after work.",
                "links": [{"label": "YouTube", "url": "https://youtube.com/@sokha"}],
                "rights_attested": True,
            },
        )
        verification = await client.post(
            "/api/v3/creator/verification",
            json={"kind": "identity", "evidence_ref": "kyc/evidence-123"},
        )

    assert status.status_code == 200
    assert submitted.status_code == 201
    assert submitted.json()["application"]["status"] == "submitted"
    assert verification.status_code == 201
    assert verification.json()["verification"]["status"] == "pending"


@pytest.mark.asyncio
async def test_admin_creator_routes(app) -> None:
    application_id = str(uuid4())
    user_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/v3/admin/creators/applications")
        decision = await client.post(
            f"/api/v3/admin/creators/applications/{application_id}/decision",
            json={"decision": "approve", "reason": "Looks good."},
        )
        badge = await client.post(
            f"/api/v3/admin/creators/{user_id}/badges",
            json={"badge": "verified"},
        )

    assert listing.status_code == 200
    assert listing.json()["total"] == 0
    assert decision.status_code == 200
    assert decision.json()["application"]["status"] == "approved"
    assert badge.status_code == 200
    assert badge.json()["badge"]["badge"] == "verified"
