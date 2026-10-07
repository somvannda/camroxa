"""Tests for Suno status message mapping and poll failure handling."""

from __future__ import annotations

import pytest

from platform_api.clients.suno_client import (
    extract_suno_generate_task_id,
    parse_suno_generate_poll,
    parse_suno_lyrics_poll,
)
from platform_api.exceptions import ExternalServiceError
from platform_api.services.suno_status_messages import (
    classify_suno_failure_type,
    is_suno_failure_status,
    suno_api_code_message,
    suno_submit_error_message,
    suno_task_failure_message,
)


def test_is_suno_failure_status_includes_rejected_and_sensitive() -> None:
    assert is_suno_failure_status("REJECTED")
    assert is_suno_failure_status("SENSITIVE_WORD_ERROR")
    assert is_suno_failure_status("CREATE_TASK_FAILED")
    assert not is_suno_failure_status("PENDING")
    assert not is_suno_failure_status("TEXT_SUCCESS")


def test_suno_task_failure_message_rejected() -> None:
    message = suno_task_failure_message(status="REJECTED")
    assert "content policy" in message.lower()


def test_suno_task_failure_message_sensitive_word() -> None:
    message = suno_task_failure_message(status="SENSITIVE_WORD_ERROR")
    assert "sensitive" in message.lower()


def test_suno_api_code_messages() -> None:
    assert "credit" in suno_api_code_message(429).lower()
    assert "rate limit" in suno_api_code_message(430).lower()
    assert "maintenance" in suno_api_code_message(455).lower()


def test_suno_submit_error_message_maps_credits() -> None:
    message = suno_submit_error_message(code=429, msg="Insufficient credits")
    assert "credit" in message.lower()


def test_classify_suno_failure_type_sensitive_word() -> None:
    assert classify_suno_failure_type(status="SENSITIVE_WORD_ERROR") == "SENSITIVE_WORD_ERROR"


def test_classify_suno_failure_type_producer_tag() -> None:
    message = "Your lyrics contain producer tag lowlight - we don't reference specific artists"
    assert classify_suno_failure_type(error_message=message) == "producer_tag"


def test_classify_suno_failure_type_other() -> None:
    assert classify_suno_failure_type(status="CREATE_TASK_FAILED", error_message="timeout") == "other"


def test_suno_task_failure_message_capacity_error() -> None:
    message = suno_task_failure_message(
        status="GENERATE_AUDIO_FAILED",
        error_message=(
            "No paid Suno account is available for this model; "
            "premium models require a paid account."
        ),
    )
    assert "temporarily unavailable" in message.lower()
    # Must not tell the user their prompt was the problem.
    assert "different lyrics" not in message.lower()


def test_classify_suno_failure_type_provider_capacity() -> None:
    assert (
        classify_suno_failure_type(
            status="GENERATE_AUDIO_FAILED",
            error_message="No Suno account with available credits for this model.",
        )
        == "provider_capacity"
    )


def test_parse_suno_generate_poll_rejected_fails() -> None:
    parsed = parse_suno_generate_poll({"code": 200, "data": {"status": "REJECTED"}})
    assert parsed.state == "failed"
    assert parsed.error
    assert "content policy" in parsed.error.lower()


def test_parse_suno_generate_poll_sensitive_word_error_fails() -> None:
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "SENSITIVE_WORD_ERROR",
                "errorMessage": "prompt blocked",
            },
        }
    )
    assert parsed.state == "failed"
    assert "sensitive" in parsed.error.lower()


def test_parse_suno_generate_poll_unknown_status_fails_not_pending() -> None:
    parsed = parse_suno_generate_poll({"code": 200, "data": {"status": "MYSTERY_STATUS"}})
    assert parsed.state == "failed"
    assert parsed.error


def test_parse_suno_generate_poll_pending_stays_pending() -> None:
    for status in ("PENDING", "TEXT_SUCCESS", "FIRST_SUCCESS", "RUNNING"):
        parsed = parse_suno_generate_poll({"code": 200, "data": {"status": status}})
        assert parsed.state == "pending", status


def test_parse_suno_generate_poll_failure_wins_over_partial_audio() -> None:
    # Regression: a job that failed after storing only one of its two clips must
    # not be reported as success, or Version 1 plays while Version 2 is stuck.
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "GENERATE_AUDIO_FAILED",
                "errorMessage": "audio_ingest_failed",
                "response": {
                    "data": [
                        {"id": "clip-ok", "audio_url": "https://b2.example/clip-ok.mp3"},
                        {"id": "clip-alt", "audio_url": ""},
                    ]
                },
            },
        }
    )
    assert parsed.state == "failed"
    assert parsed.audio_url_ok == ""
    assert parsed.audio_url_alt == ""


def test_parse_suno_lyrics_poll_rejected_fails() -> None:
    parsed = parse_suno_lyrics_poll({"code": 200, "data": {"status": "REJECTED"}})
    assert parsed.state == "failed"
    assert parsed.error


def test_extract_suno_generate_task_id_api_error_user_message() -> None:
    with pytest.raises(ExternalServiceError, match="credit"):
        extract_suno_generate_task_id({"code": 429, "msg": "Insufficient credits", "data": {}})

    with pytest.raises(ExternalServiceError, match="maintenance"):
        extract_suno_generate_task_id({"code": 455, "msg": "Maintenance", "data": {}})
