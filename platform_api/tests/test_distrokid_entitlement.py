"""DistroKid entitlement helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from platform_api.services.distrokid_entitlement_service import (
    DISTROKID_ADDON_PRICE_CENTS,
    DISTROKID_MONTHLY_WAV_LIMIT,
    compute_distrokid_expires_at,
    license_has_active_distrokid,
)


class _Lic:
    def __init__(self, enabled: bool, expires_at: datetime | None) -> None:
        self.distrokid_enabled = enabled
        self.distrokid_expires_at = expires_at


def test_distrokid_price_and_wav_limit_constants() -> None:
    assert DISTROKID_ADDON_PRICE_CENTS == 500
    assert DISTROKID_MONTHLY_WAV_LIMIT == 600


def test_license_has_active_distrokid_requires_enabled() -> None:
    assert license_has_active_distrokid(_Lic(False, None)) is False
    assert license_has_active_distrokid(_Lic(True, None)) is True


def test_license_has_active_distrokid_respects_expiry() -> None:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    past = now - timedelta(days=1)
    future = now + timedelta(days=1)
    assert license_has_active_distrokid(_Lic(True, past), now=now) is False
    assert license_has_active_distrokid(_Lic(True, future), now=now) is True


def test_compute_distrokid_expires_at_capped_by_license() -> None:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    license_end = now + timedelta(days=10)
    expires = compute_distrokid_expires_at(
        now=now,
        license_expires_at=license_end,
        period_days=30,
    )
    assert expires == license_end
