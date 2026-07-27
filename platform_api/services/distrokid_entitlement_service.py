"""DistroKid monthly add-on entitlement ($5) — WAV + future DistroKid upload.

Not a profile_addon slot product. Boolean license entitlement with period end.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# CutLuy / portal catalog price for DistroKid add-on.
DISTROKID_ADDON_PRICE_CENTS = 500
DISTROKID_ADDON_NAME = "DistroKid"
DISTROKID_PERIOD_DAYS = 30
# Matches Standard Monthly full burn: 300 Suno packages × 2 tracks.
DISTROKID_MONTHLY_WAV_LIMIT = 600
# Provider COGS seed (~0.4 Suno API credits at $50/10k).
DISTROKID_WAV_COGS_USD = 0.002


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_distrokid_expires_at(
    *,
    now: datetime | None = None,
    license_expires_at: datetime | None = None,
    period_days: int = DISTROKID_PERIOD_DAYS,
) -> datetime:
    """Grant one DistroKid period; do not extend past the subscription end when known."""
    start = now or utc_now()
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    period_end = start + timedelta(days=max(1, int(period_days)))
    if license_expires_at is not None:
        end = license_expires_at
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < period_end:
            return end
    return period_end


def license_has_active_distrokid(license_obj: Any, *, now: datetime | None = None) -> bool:
    """True when DistroKid add-on is enabled and not past expires_at."""
    if not bool(getattr(license_obj, "distrokid_enabled", False)):
        return False
    expires = getattr(license_obj, "distrokid_expires_at", None)
    if expires is None:
        return True
    current = now or utc_now()
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return expires > current


def distrokid_status_payload(license_obj: Any | None) -> dict[str, Any]:
    """Public entitlement snapshot for /users/me and license validate."""
    if license_obj is None:
        return {
            "distrokid_enabled": False,
            "distrokid_active": False,
            "distrokid_expires_at": None,
            "distrokid_monthly_wav_limit": DISTROKID_MONTHLY_WAV_LIMIT,
            "distrokid_price_cents": DISTROKID_ADDON_PRICE_CENTS,
        }
    active = license_has_active_distrokid(license_obj)
    expires = getattr(license_obj, "distrokid_expires_at", None)
    return {
        "distrokid_enabled": bool(getattr(license_obj, "distrokid_enabled", False)),
        "distrokid_active": active,
        "distrokid_expires_at": expires,
        "distrokid_monthly_wav_limit": DISTROKID_MONTHLY_WAV_LIMIT,
        "distrokid_price_cents": DISTROKID_ADDON_PRICE_CENTS,
    }
