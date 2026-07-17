"""Phase 3: refresh token reuse detection (H8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.config import Settings
from platform_api.exceptions import AuthenticationError
from platform_api.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_all_sessions() -> None:
    user_id = uuid4()
    user_repo = AsyncMock()
    refresh_repo = AsyncMock()
    refresh_repo.get_by_hash = AsyncMock(
        return_value={
            "user_id": user_id,
            "revoked_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        }
    )
    refresh_repo.revoke_all_for_user = AsyncMock()
    user_repo.increment_token_version = AsyncMock()

    settings = Settings(
        jwt_secret="x" * 40,
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )
    service = AuthService(
        config=settings,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
    )
    service._decode_token = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(email="user@example.com", type="refresh")
    )
    service._hash_token = MagicMock(return_value="hash")  # type: ignore[method-assign]

    with pytest.raises(AuthenticationError) as exc:
        await service.refresh_token("stolen-refresh-token")

    assert exc.value.details["error_code"] == "REFRESH_TOKEN_REUSE"
    refresh_repo.revoke_all_for_user.assert_awaited_once()
    user_repo.increment_token_version.assert_awaited_once()
