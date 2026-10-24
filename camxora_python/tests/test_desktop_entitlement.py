"""Desktop Studio paid-plan entitlement helpers."""

from __future__ import annotations

from shared.lib.desktop_entitlement import (
    DESKTOP_REQUIRES_PAID_PLAN_MESSAGE,
    is_desktop_plan_required_error,
    is_desktop_plan_required_message,
    is_paid_catalog_plan_name,
    user_can_use_desktop_studio,
)
from shared.models.auth import UserMeResponse
from shared.services.platform_client import PlatformApiError


def _me(**kwargs: object) -> UserMeResponse:
    base = {
        "id": "u1",
        "email": "user@test.com",
        "email_confirmed": True,
        "display_name": "User",
        "credit_balance": 0,
    }
    base.update(kwargs)
    return UserMeResponse.model_validate(base)


def test_unpaid_user_cannot_use_desktop() -> None:
    assert user_can_use_desktop_studio(_me(onboarding_paid=False)) is False
    assert user_can_use_desktop_studio(_me(desktop_access=False)) is False


def test_pack_access_flag_is_authoritative() -> None:
    # Packs-only billing: the API decides from live, unexpired pack credits.
    assert user_can_use_desktop_studio(_me(desktop_access=True)) is True
    assert (
        user_can_use_desktop_studio(
            _me(desktop_access=False, onboarding_paid=True, plan_name="Starter")
        )
        is False
    )


def test_paid_user_can_use_desktop() -> None:
    assert user_can_use_desktop_studio(_me(onboarding_paid=True)) is True


def test_admin_can_use_desktop_without_plan() -> None:
    assert user_can_use_desktop_studio(_me(onboarding_paid=False, role="admin")) is True


def test_starter_creator_studio_can_use_desktop() -> None:
    for name in ("Starter", "starter_monthly", "creator_yearly", "Studio (Monthly)"):
        assert user_can_use_desktop_studio(_me(onboarding_paid=False, plan_name=name)) is True


def test_free_plan_cannot_use_desktop() -> None:
    assert user_can_use_desktop_studio(_me(onboarding_paid=False, plan_name="Free")) is False
    assert is_paid_catalog_plan_name("Free") is False
    assert is_paid_catalog_plan_name("free_daily") is False


def test_paid_plan_message_is_user_facing() -> None:
    message = DESKTOP_REQUIRES_PAID_PLAN_MESSAGE.lower()
    assert "desktop" in message
    assert "credit pack" in message
    assert "30 days" in message
    assert is_desktop_plan_required_message(DESKTOP_REQUIRES_PAID_PLAN_MESSAGE)


def test_v3_desktop_plan_required_error() -> None:
    exc = PlatformApiError(
        403,
        "Desktop studio requires a paid plan. Choose Starter, Creator, or Studio on the web.",
        payload={"error": {"code": "DESKTOP_PLAN_REQUIRED"}},
    )
    assert exc.error_code == "DESKTOP_PLAN_REQUIRED"
    assert is_desktop_plan_required_error(exc)
    assert is_desktop_plan_required_message(str(exc))
