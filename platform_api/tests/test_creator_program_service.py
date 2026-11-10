"""Tests for applications, verification, and badges (Phase 1b)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import DuplicateError, ValidationError
from platform_api.services.creator_program_service import CreatorProgramService


def _profile(user_id=None):
    return {
        "user_id": user_id or uuid4(),
        "handle": "sokha",
        "display_name": "Sokha Chan",
        "tier": "creator",
        "status": "active",
    }


def _application(user_id=None, status="submitted"):
    return {
        "id": uuid4(),
        "user_id": user_id or uuid4(),
        "version": 1,
        "status": status,
        "requested_tier": "verified",
        "payload": {},
        "submitted_at": datetime.now(timezone.utc),
        "sla_due_at": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "decision_reason": None,
    }


def _payload():
    return {
        "pitch": "I make late-night Khmer pop about the city, the river, and the ride home after work.",
        "links": [{"label": "YouTube", "url": "https://youtube.com/@sokha"}],
        "track_ids": ["task-1"],
        "rights_attested": True,
        "requested_tier": "verified",
    }


@pytest.mark.asyncio
async def test_submit_application_creates_a_submitted_row() -> None:
    profile = _profile()
    application = _application(user_id=profile["user_id"])
    service = CreatorProgramService(AsyncMock())
    service._profiles = AsyncMock()
    service._profiles.get_by_user_id = AsyncMock(return_value=profile)
    service._repo = AsyncMock()
    service._repo.get_open_application = AsyncMock(return_value=None)
    service._repo.get_latest_application = AsyncMock(return_value=None)
    service._repo.insert_application = AsyncMock(return_value=application)

    result = await service.submit_application(str(profile["user_id"]), _payload())

    assert result["application"]["status"] == "submitted"
    service._repo.insert_application.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_application_blocks_a_second_open_application() -> None:
    profile = _profile()
    service = CreatorProgramService(AsyncMock())
    service._profiles = AsyncMock()
    service._profiles.get_by_user_id = AsyncMock(return_value=profile)
    service._repo = AsyncMock()
    service._repo.get_open_application = AsyncMock(return_value=_application())

    with pytest.raises(DuplicateError):
        await service.submit_application(str(profile["user_id"]), _payload())


@pytest.mark.asyncio
async def test_submit_application_requires_rights_attestation() -> None:
    profile = _profile()
    service = CreatorProgramService(AsyncMock())
    service._profiles = AsyncMock()
    service._profiles.get_by_user_id = AsyncMock(return_value=profile)

    payload = _payload()
    payload["rights_attested"] = False
    with pytest.raises(ValidationError) as exc:
        await service.submit_application(str(profile["user_id"]), payload)

    assert "rights_attested" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_approving_an_application_verifies_the_creator() -> None:
    user_id = uuid4()
    application = _application(user_id=user_id)
    service = CreatorProgramService(AsyncMock())
    service._repo = AsyncMock()
    service._repo.get_application = AsyncMock(return_value=application)
    service._repo.set_application_status = AsyncMock(
        return_value={**application, "status": "approved"}
    )
    service._repo.set_profile_tier = AsyncMock(return_value={})
    service._repo.grant_badge = AsyncMock(return_value={})
    service._profiles = AsyncMock()
    service._profiles.get_by_user_id = AsyncMock(return_value=_profile(user_id))

    result = await service.decide_application(
        str(application["id"]),
        decision="approve",
        reviewer_id=str(uuid4()),
        reason="Looks good.",
    )

    assert result["application"]["status"] == "approved"
    service._repo.set_profile_tier.assert_awaited_once()
    assert service._repo.set_profile_tier.await_args.kwargs["tier"] == "verified"
    service._repo.grant_badge.assert_awaited_once()
    assert service._repo.grant_badge.await_args.kwargs["badge"] == "verified"


@pytest.mark.asyncio
async def test_request_changes_requires_a_reason() -> None:
    application = _application()
    service = CreatorProgramService(AsyncMock())
    service._repo = AsyncMock()
    service._repo.get_application = AsyncMock(return_value=application)

    with pytest.raises(ValidationError):
        await service.decide_application(
            str(application["id"]),
            decision="request_changes",
            reviewer_id=str(uuid4()),
        )


@pytest.mark.asyncio
async def test_granting_verified_badge_updates_profile_tier() -> None:
    user_id = uuid4()
    service = CreatorProgramService(AsyncMock())
    service._profiles = AsyncMock()
    service._profiles.get_by_user_id = AsyncMock(return_value=_profile(user_id))
    service._repo = AsyncMock()
    service._repo.grant_badge = AsyncMock(return_value={"badge": "verified"})
    service._repo.set_profile_tier = AsyncMock(return_value={})

    await service.grant_badge(str(user_id), badge="verified", reviewer_id=str(uuid4()))

    service._repo.set_profile_tier.assert_awaited_once()
    assert service._repo.set_profile_tier.await_args.kwargs["tier"] == "verified"


@pytest.mark.asyncio
async def test_revoking_verified_badge_downgrades_profile() -> None:
    user_id = uuid4()
    service = CreatorProgramService(AsyncMock())
    service._repo = AsyncMock()
    service._repo.revoke_badge = AsyncMock(return_value={"badge": "verified"})
    service._repo.set_profile_tier = AsyncMock(return_value={})

    await service.revoke_badge(str(user_id), badge="verified", reason="Policy violation")

    service._repo.set_profile_tier.assert_awaited_once()
    assert service._repo.set_profile_tier.await_args.kwargs["tier"] == "creator"


@pytest.mark.asyncio
async def test_submit_verification_validates_kind_and_evidence() -> None:
    service = CreatorProgramService(AsyncMock())
    service._repo = AsyncMock()
    service._repo.insert_verification = AsyncMock(return_value={"status": "pending"})

    with pytest.raises(ValidationError):
        await service.submit_verification(str(uuid4()), kind="passport", evidence_ref="x")

    with pytest.raises(ValidationError):
        await service.submit_verification(str(uuid4()), kind="identity", evidence_ref="")

    result = await service.submit_verification(
        str(uuid4()), kind="identity", evidence_ref="kyc/evidence-123"
    )
    assert result["verification"]["status"] == "pending"
