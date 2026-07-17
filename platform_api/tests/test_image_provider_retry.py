"""Tests for image provider retry/backoff helpers."""

from __future__ import annotations

from platform_api.exceptions import ExternalServiceError
from platform_api.services.image_provider_retry import (
    compute_retry_delay_seconds,
    provider_max_attempts,
)


def test_provider_max_attempts_prefers_slai_retries() -> None:
    assert provider_max_attempts("slai", slai_retries=5, fallback_retries=1) == 5
    assert provider_max_attempts("fal", slai_retries=5, fallback_retries=1) == 1


def test_compute_retry_delay_uses_retry_after_hint() -> None:
    exc = ExternalServiceError(
        "rate limited",
        is_retryable=True,
        details={"retry_after_seconds": 12},
    )
    delay = compute_retry_delay_seconds(
        exc,
        attempt_index=0,
        base_delay_seconds=5.0,
        max_delay_seconds=45.0,
    )
    assert delay == 12.0


def test_compute_retry_delay_exponential_backoff() -> None:
    exc = ExternalServiceError("timeout", is_retryable=True)
    assert (
        compute_retry_delay_seconds(
            exc,
            attempt_index=0,
            base_delay_seconds=5.0,
            max_delay_seconds=45.0,
        )
        == 5.0
    )
    assert (
        compute_retry_delay_seconds(
            exc,
            attempt_index=2,
            base_delay_seconds=5.0,
            max_delay_seconds=45.0,
        )
        == 20.0
    )
