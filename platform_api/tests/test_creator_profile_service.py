"""Tests for creator identity (Phase 1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import DuplicateError, ValidationError
from platform_api.services.creator_profile_service import (
    CreatorProfileService,
    normalize_handle,
    validate_handle,
)


def _profile(**overrides):
    user_id = uuid4()
    profile = {
        "user_id": user_id,
        "handle": "sokha",
        "display_name": "Sokha Chan",
        "tagline": "Khmer pop for the ride home.",
        "bio": "Late-night Khmer pop.",
        "country_code": "KH",
        "city": "Phnom Penh",
        "avatar_url": "https://cdn.example/avatar.png",
        "banner_url": None,
        "links": '[{"label":"YouTube","url":"https://youtube.com/@sokha"}]',
        "genres": ["Khmer Pop"],
        "influences": [],
        "pronouns": None,
        "ai_disclosure": "ai_assisted",
        "tier": "creator",
        "status": "active",
        "verified_at": None,
        "verification_expires_at": None,
        "follower_count": 12,
        "program_joined_at": datetime.now(timezone.utc),
        "payout_currency": "USD",
        "support_enabled": True,
        "is_sample": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    profile.update(overrides)
    return profile


def test_handle_normalization_and_validation() -> None:
    assert normalize_handle("@Sokha_01") == "sokha_01"
    assert validate_handle("sokha_01") == "sokha_01"

    with pytest.raises(ValidationError):
        validate_handle("1sokha")
    with pytest.raises(ValidationError):
        validate_handle("admin")
    with pytest.raises(ValidationError):
        validate_handle("ab")


@pytest.mark.asyncio
async def test_claim_creates_a_profile() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(side_effect=[None, _profile()])
    pool.fetchval = AsyncMock(return_value=None)

    payload = await CreatorProfileService(pool).claim(
        str(uuid4()),
        {
            "handle": "sokha",
            "display_name": "Sokha Chan",
            "genres": ["Khmer Pop"],
            "links": [{"label": "YouTube", "url": "https://youtube.com/@sokha"}],
        },
    )

    assert payload["profile"]["handle"] == "sokha"
    assert payload["profile"]["badges"] == []
    assert payload["checklist"]["display_name"] is True
    assert payload["checklist"]["first_release"] is False


@pytest.mark.asyncio
async def test_claim_rejects_duplicate_profile() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=_profile())

    with pytest.raises(DuplicateError):
        await CreatorProfileService(pool).claim(str(uuid4()), {"handle": "sokha", "display_name": "Sokha"})


@pytest.mark.asyncio
async def test_handle_change_is_limited_to_once_every_90_days() -> None:
    recent = datetime.now(timezone.utc) - timedelta(days=10)
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=_profile())
    pool.fetchval = AsyncMock(side_effect=[None, recent])

    with pytest.raises(ValidationError) as exc:
        await CreatorProfileService(pool).update(
            str(uuid4()), {"handle": "sokha_new"}
        )

    assert (exc.value.details or {}).get("fields", {}).get("handle") == "cooldown"
    assert "next_allowed_at" in (exc.value.details or {})


@pytest.mark.asyncio
async def test_public_profile_includes_badges_and_stats() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=_profile(tier="verified"))

    payload = await CreatorProfileService(pool).get_public("sokha")

    assert payload is not None
    assert payload["tier"] == "verified"
    assert payload["badges"] == ["verified"]
    assert payload["stats"]["followers"] == 12
    assert payload["links"][0]["label"] == "YouTube"


@pytest.mark.asyncio
async def test_old_handle_resolves_to_redirect() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetchval = AsyncMock(return_value="sokha_new")

    payload = await CreatorProfileService(pool).get_public("sokha_old")

    assert payload == {"redirect": "sokha_new"}


@pytest.mark.asyncio
async def test_availability_rejects_reserved_handles() -> None:
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=None)

    payload = await CreatorProfileService(pool).availability("admin")

    assert payload["available"] is False
    assert payload["reason"] == "reserved"
    assert len(payload["suggestions"]) >= 1
