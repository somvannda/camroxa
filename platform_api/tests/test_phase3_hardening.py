"""Phase 3: paid recurring finite meters + CutLuy signature helpers."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.cutluy_webhook import verify_cutluy_webhook_signature
from platform_api.services.plan_validation import validate_paid_recurring_finite_meters


def test_paid_recurring_rejects_null_monthly_meters() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_paid_recurring_finite_meters(
            price_cents=7900,
            billing_cycle_days=30,
            monthly_song_limit=300,
            monthly_image_limit=None,
            monthly_draft_limit=1260,
            monthly_video_limit=300,
            monthly_merge_limit=30,
            is_active=True,
        )
    assert exc.value.details["error_code"] == "PAID_PLAN_UNLIMITED_FORBIDDEN"


def test_paid_recurring_rejects_null_video_merge_meters() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_paid_recurring_finite_meters(
            price_cents=7900,
            billing_cycle_days=30,
            monthly_song_limit=300,
            monthly_image_limit=120,
            monthly_draft_limit=1260,
            monthly_video_limit=None,
            monthly_merge_limit=30,
            is_active=True,
        )
    assert "monthly_video_limit" in exc.value.details["missing_limits"]


def test_lifetime_or_free_allows_null_meters() -> None:
    validate_paid_recurring_finite_meters(
        price_cents=9900,
        billing_cycle_days=None,
        monthly_song_limit=None,
        monthly_image_limit=None,
        monthly_draft_limit=None,
        monthly_video_limit=None,
        monthly_merge_limit=None,
        is_active=True,
    )
    validate_paid_recurring_finite_meters(
        price_cents=0,
        billing_cycle_days=30,
        monthly_song_limit=None,
        monthly_image_limit=None,
        monthly_draft_limit=None,
        is_active=True,
    )


def test_cutluy_webhook_signature_valid() -> None:
    secret = "whsec_test"
    body = b'{"type":"payment.completed","data":{"payment":{"id":"pay_1","status":"paid"}}}'
    ts = str(int(time.time()))
    digest = hmac.new(
        secret.encode(),
        f"{ts}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    header = f"t={ts},v1={digest}"
    assert (
        verify_cutluy_webhook_signature(
            raw_body=body,
            signature_header=header,
            secret=secret,
            now=float(ts),
        )
        is True
    )


def test_cutluy_webhook_signature_rejects_tamper_and_stale() -> None:
    secret = "whsec_test"
    body = b'{"ok":true}'
    ts = str(int(time.time()))
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert (
        verify_cutluy_webhook_signature(
            raw_body=b'{"ok":false}',
            signature_header=f"t={ts},v1={digest}",
            secret=secret,
            now=float(ts),
        )
        is False
    )
    old_ts = str(int(time.time()) - 10_000)
    old_digest = hmac.new(
        secret.encode(), f"{old_ts}.".encode() + body, hashlib.sha256
    ).hexdigest()
    assert (
        verify_cutluy_webhook_signature(
            raw_body=body,
            signature_header=f"t={old_ts},v1={old_digest}",
            secret=secret,
            now=time.time(),
        )
        is False
    )
