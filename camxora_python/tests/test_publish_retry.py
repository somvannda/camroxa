"""Publish retry policy."""

from __future__ import annotations

from shared.lib.publish_retry import MAX_ATTEMPTS, backoff_for, should_retry


def test_transport_and_5xx_are_retried() -> None:
    assert should_retry(0) is True
    assert should_retry(None) is True
    assert should_retry(500) is True
    assert should_retry(503) is True
    assert should_retry(429) is True


def test_client_errors_are_not_retried() -> None:
    for status in (400, 401, 403, 404, 409, 422):
        assert should_retry(status) is False


def test_message_hints_can_trigger_a_retry() -> None:
    assert should_retry(503, "provider temporarily unavailable") is True
    assert should_retry(400, "title is required") is False


def test_backoff_grows_then_caps() -> None:
    assert backoff_for(1) == 2.0
    assert backoff_for(2) == 6.0
    assert backoff_for(3) == 6.0
    assert backoff_for(0) == 0.0


def test_attempt_budget() -> None:
    assert MAX_ATTEMPTS == 3
