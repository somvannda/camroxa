"""Desktop Studio access — paid plan (or admin) required to use the app."""

from __future__ import annotations

import re
from typing import Any

from shared.models.auth import UserMeResponse

DESKTOP_REQUIRES_PAID_PLAN_MESSAGE = (
    "Your account does not have a Desktop Studio plan. "
    "Upgrade in the account portal to Starter, Creator, or Studio, then sign in again."
)

DESKTOP_PLAN_REQUIRED_CODE = "DESKTOP_PLAN_REQUIRED"

_PAID_CATALOG_TIERS = ("starter", "creator", "studio")


def is_paid_catalog_plan_name(name: str | None) -> bool:
    """True for public paid catalog SKUs: Starter, Creator, Studio."""
    normalized = re.sub(r"[_-]+", " ", str(name or "")).strip().lower()
    if not normalized or normalized == "free" or normalized.startswith("free "):
        return False
    return any(tier in normalized for tier in _PAID_CATALOG_TIERS)


def user_can_use_desktop_studio(me: UserMeResponse) -> bool:
    """True when the account may enter the desktop shell.

    Admins may open the studio without a plan. Paid catalog (Starter /
    Creator / Studio) and fulfilled desktop checkout (``onboarding_paid``)
    also qualify. Free daily-credit accounts are blocked.
    """
    role = str(getattr(me, "role", None) or "").strip().lower()
    if role == "admin":
        return True
    if bool(getattr(me, "onboarding_paid", False)):
        return True
    return is_paid_catalog_plan_name(getattr(me, "plan_name", None))


def platform_api_error_code(payload: Any) -> str | None:
    """Read ``error.code`` from a platform_api JSON envelope."""
    if not isinstance(payload, dict):
        return None
    nested = payload.get("error")
    if isinstance(nested, dict):
        code = nested.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
    return None


def is_desktop_plan_required_message(text: str | None) -> bool:
    """True when login/bootstrap copy means 'open the plans popup'."""
    raw = str(text or "").strip()
    if not raw:
        return False
    if raw == DESKTOP_REQUIRES_PAID_PLAN_MESSAGE:
        return True
    lowered = raw.lower()
    return "desktop studio requires a paid plan" in lowered or (
        "starter, creator, or studio" in lowered and "paid plan" in lowered
    )


def is_desktop_plan_required_error(exc: object) -> bool:
    """True for API 403 ``DESKTOP_PLAN_REQUIRED`` (v3 desktop client gate)."""
    payload = getattr(exc, "payload", None)
    if platform_api_error_code(payload) == DESKTOP_PLAN_REQUIRED_CODE:
        return True
    status = getattr(exc, "status", None)
    if status == 403 and is_desktop_plan_required_message(str(exc)):
        return True
    return is_desktop_plan_required_message(str(exc))
