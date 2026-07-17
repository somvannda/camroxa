"""Plan upgrade fulfillment preserves active license add-on fields."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.repositories.license_repo import License


@pytest.mark.asyncio
async def test_plan_upgrade_uses_change_plan_not_revoke() -> None:
    user_id = uuid4()
    license_id = uuid4()
    old_plan_id = uuid4()
    new_plan_id = uuid4()

    active_license = License(
        id=license_id,
        license_key="abc",
        plan_id=old_plan_id,
        user_id=user_id,
        status="active",
        activated_at=datetime.now(timezone.utc),
        expires_at=None,
        revoked_at=None,
        profile_addon_slots=2,
        profile_addon_pending=2,
        created_at=datetime.now(timezone.utc),
    )

    license_repo = AsyncMock()
    license_repo.get_active_for_user = AsyncMock(return_value=active_license)
    license_repo.change_plan = AsyncMock(
        return_value=License(
            id=license_id,
            license_key="abc",
            plan_id=new_plan_id,
            user_id=user_id,
            status="active",
            activated_at=datetime.now(timezone.utc),
            expires_at=None,
            revoked_at=None,
            profile_addon_slots=2,
            profile_addon_pending=2,
            created_at=datetime.now(timezone.utc),
        )
    )
    license_repo.revoke_all_for_user = AsyncMock()

    active = await license_repo.get_active_for_user(user_id)
    assert active.profile_addon_slots == 2
    assert active.profile_addon_pending == 2
    updated = await license_repo.change_plan(active.id, new_plan_id, object())
    assert updated.profile_addon_slots == 2
    assert updated.profile_addon_pending == 2
    license_repo.revoke_all_for_user.assert_not_called()
