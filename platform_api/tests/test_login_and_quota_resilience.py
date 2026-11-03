"""Regression guards for the "unexpected error" reports on music.camxora.com.

Two independent failures shared one symptom — a generic
``An unexpected error occurred.`` payload:

* ``GET /api/v3/users/me`` 500'd after a successful sign-in when the response
  model rejected a dirty row (``display_name``/``products``/``created_at``), so
  the web client showed an error even though the session cookie was already set.
* ``GET /api/v3/web-music/quota`` 500'd when a credit counter arrived as a
  float/Decimal, which left the Create page unable to refresh the balance after
  a top-up.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.routers.users import _coerce_products, _user_to_response
from platform_api.routers.web_music import WebMusicQuotaResponse, _coerce_quota_payload


class TestProfileResponseCoercion:
    def test_products_accepts_every_stored_shape(self) -> None:
        assert _coerce_products(["music_web", "desktop"]) == ["music_web", "desktop"]
        assert _coerce_products('["music_web"]') == ["music_web"]
        assert _coerce_products("music_web") == ["music_web"]
        assert _coerce_products({"music_web": True}) == ["music_web"]
        assert _coerce_products(None) == []
        assert _coerce_products("") == []

    def test_blank_display_name_falls_back_to_email(self) -> None:
        user = User(
            id=uuid4(),
            email="listener@example.com",
            display_name=None,  # type: ignore[arg-type]
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )

        response = _user_to_response(user)

        assert response.display_name == "listener@example.com"
        assert response.email == "listener@example.com"
        assert response.created_at is not None

    def test_missing_created_at_is_defaulted(self) -> None:
        user = User(id=uuid4(), email="a@b.c", display_name="A")
        user.created_at = None  # type: ignore[assignment]

        response = _user_to_response(user)

        assert response.created_at is not None


class TestQuotaResponseCoercion:
    def test_fractional_counters_are_rounded_not_rejected(self) -> None:
        payload = {
            "limit": Decimal("1970.4442"),
            "used": 12.7,
            "remaining": 195.0,
            "credits_remaining": Decimal("1970.4442"),
            "credits_per_song": 10,
            "queue_limit": 2,
            "queue_used": 0,
        }

        response = WebMusicQuotaResponse(**_coerce_quota_payload(payload))

        assert response.limit == 1970
        assert response.used == 13
        assert response.remaining == 195
        assert response.credits_remaining == 1970

    def test_unparseable_counter_becomes_zero(self) -> None:
        cleaned = _coerce_quota_payload({"limit": "n/a", "credits_remaining": None})

        assert cleaned["limit"] == 0
        assert cleaned["credits_remaining"] is None

    def test_payload_is_not_mutated(self) -> None:
        payload = {"limit": 5.5}

        _coerce_quota_payload(payload)

        assert payload["limit"] == 5.5
