"""Admin Suno blocklist router tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from platform_api.middleware.auth import AuthContext
from platform_api.routers import suno_blocklist, suno_blocklist_admin
from platform_api.services.suno_blocklist_service import SunoBlocklistService
from platform_api.tests.test_suno_blocklist_service import FakeSunoBlocklistRepo


@pytest.fixture
def admin_ctx() -> AuthContext:
    return AuthContext(user_id="00000000-0000-0000-0000-000000000001", email="boss@example.com", role="admin")


@pytest.fixture
def blocklist_service() -> SunoBlocklistService:
    return SunoBlocklistService(FakeSunoBlocklistRepo())


@pytest.mark.asyncio
async def test_admin_list_blocklist_terms(
    monkeypatch: pytest.MonkeyPatch,
    admin_ctx: AuthContext,
    blocklist_service: SunoBlocklistService,
) -> None:
    monkeypatch.setattr(
        suno_blocklist_admin,
        "get_suno_blocklist_service",
        lambda: blocklist_service,
    )

    result = await suno_blocklist_admin.list_suno_blocklist_terms(admin_ctx, blocklist_service)
    assert len(result.items) >= 1
    assert any(item.term == "lowlight" for item in result.items)


@pytest.mark.asyncio
async def test_admin_create_blocklist_term(
    monkeypatch: pytest.MonkeyPatch,
    admin_ctx: AuthContext,
    blocklist_service: SunoBlocklistService,
) -> None:
    monkeypatch.setattr(
        suno_blocklist_admin,
        "get_suno_blocklist_service",
        lambda: blocklist_service,
    )

    created = await suno_blocklist_admin.create_suno_blocklist_term(
        suno_blocklist_admin.CreateSunoBlocklistRequest(
            term="Skyline",
            replacement="horizon",
            severity="block",
            enabled=True,
        ),
        admin_ctx,
        blocklist_service,
    )
    assert created.term == "skyline"
    assert created.replacement == "horizon"


@pytest.mark.asyncio
async def test_public_runtime_blocklist_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    blocklist_service: SunoBlocklistService,
) -> None:
    monkeypatch.setattr(
        suno_blocklist,
        "get_suno_blocklist_service",
        lambda: blocklist_service,
    )
    ctx = AuthContext(user_id="00000000-0000-0000-0000-000000000002", email="user@example.com", role="user")

    result = await suno_blocklist.get_suno_blocklist_runtime(ctx, blocklist_service)
    assert "lowlight" in result.replacements
    assert "lowlight" in result.block_terms or "lowlight" in result.replacements
