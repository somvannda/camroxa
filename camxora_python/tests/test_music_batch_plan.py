"""Gap-fill and create-retry helpers for multi-day Generate."""

from __future__ import annotations

from shared.lib.music_batch_plan import (
    create_planned_batches,
    existing_batch_slots,
    format_create_batches_summary,
    is_retryable_create_error,
    missing_create_requests,
)
from shared.models.platform import BatchCreateRequest, BatchCreateResponse, MusicHistoryBatch
from shared.services.platform_client import PlatformApiError


def _request(day: str, ok: str, alt: str) -> BatchCreateRequest:
    return BatchCreateRequest(
        ok_profile_id=ok,
        alt_profile_id=alt,
        from_date=day,
        to_date=day,
        song_count=15,
    )


def _history(day: str, ok: str, alt: str, batch_id: str = "b1") -> MusicHistoryBatch:
    return MusicHistoryBatch(
        batch_id=batch_id,
        from_date=day,
        to_date=day,
        ok_profile_id=ok,
        alt_profile_id=alt,
        created_at="2026-08-23T07:34:00Z",
        updated_at="2026-08-23T07:34:00Z",
    )


def _ok_response(day: str) -> BatchCreateResponse:
    return BatchCreateResponse(batch_id=f"new-{day}", status="pending", song_count=15, from_date=day, to_date=day)


def test_missing_requests_match_aug_24_29_gap() -> None:
    drive, vortex, reactor, remixes = "ok-drive", "alt-vortex", "ok-reactor", "alt-remixes"
    planned: list[BatchCreateRequest] = []
    for day in ("2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28", "2026-08-29"):
        planned.append(_request(day, drive, vortex))
        planned.append(_request(day, reactor, remixes))
    existing = [
        _history("2026-08-24", drive, vortex, "1"),
        _history("2026-08-24", reactor, remixes, "2"),
        _history("2026-08-25", drive, vortex, "3"),
        _history("2026-08-25", reactor, remixes, "4"),
        _history("2026-08-26", drive, vortex, "5"),
        _history("2026-08-26", reactor, remixes, "6"),
        _history("2026-08-27", drive, vortex, "7"),
        _history("2026-08-27", reactor, remixes, "8"),
        _history("2026-08-28", drive, vortex, "9"),
    ]
    missing = missing_create_requests(planned, existing)
    assert [(item.from_date, item.ok_profile_id) for item in missing] == [
        ("2026-08-28", reactor),
        ("2026-08-29", drive),
        ("2026-08-29", reactor),
    ]
    assert existing_batch_slots(existing) == {
        ("2026-08-24", drive, vortex),
        ("2026-08-24", reactor, remixes),
        ("2026-08-25", drive, vortex),
        ("2026-08-25", reactor, remixes),
        ("2026-08-26", drive, vortex),
        ("2026-08-26", reactor, remixes),
        ("2026-08-27", drive, vortex),
        ("2026-08-27", reactor, remixes),
        ("2026-08-28", drive, vortex),
    }


def test_create_planned_skips_existing_and_fills_gaps() -> None:
    drive, vortex, reactor, remixes = "ok-drive", "alt-vortex", "ok-reactor", "alt-remixes"
    planned = [
        _request("2026-08-28", drive, vortex),
        _request("2026-08-28", reactor, remixes),
        _request("2026-08-29", drive, vortex),
        _request("2026-08-29", reactor, remixes),
    ]
    created_days: list[str] = []

    def create(request: BatchCreateRequest) -> BatchCreateResponse:
        created_days.append(f"{request.from_date}:{request.ok_profile_id}")
        return _ok_response(f"{request.from_date}-{request.ok_profile_id}")

    result = create_planned_batches(
        create,
        planned,
        existing_batches=[_history("2026-08-28", drive, vortex, "9")],
        skip_existing=True,
        sleep=lambda _seconds: None,
    )
    assert result.skipped == 1
    assert result.created_count == 3
    assert result.failed_count == 0
    assert created_days == [
        "2026-08-28:ok-reactor",
        "2026-08-29:ok-drive",
        "2026-08-29:ok-reactor",
    ]
    assert format_create_batches_summary(result) == "Created 3 batch runs, 1 already existed."


def test_create_planned_continues_and_retries_after_timeout() -> None:
    calls: list[str] = []
    attempts = {"2026-08-28": 0}

    def create(request: BatchCreateRequest) -> BatchCreateResponse:
        calls.append(request.from_date)
        if request.from_date == "2026-08-28":
            attempts["2026-08-28"] += 1
            if attempts["2026-08-28"] < 2:
                raise PlatformApiError(0, "Request timed out contacting the Camxora API.")
        return _ok_response(request.from_date)

    result = create_planned_batches(
        create,
        [
            _request("2026-08-28", "ok-a", "alt-a"),
            _request("2026-08-29", "ok-a", "alt-a"),
        ],
        attempts=3,
        retry_delay_sec=0,
        sleep=lambda _seconds: None,
    )
    assert result.created_count == 2
    assert result.failed_count == 0
    assert calls == ["2026-08-28", "2026-08-29", "2026-08-28"]


def test_create_planned_does_not_retry_validation_errors() -> None:
    calls: list[str] = []

    def create(request: BatchCreateRequest) -> BatchCreateResponse:
        calls.append(request.from_date)
        if request.from_date == "2026-08-28":
            raise PlatformApiError(422, "Choose a valid inclusive date range.")
        return _ok_response(request.from_date)

    result = create_planned_batches(
        create,
        [
            _request("2026-08-28", "ok-a", "alt-a"),
            _request("2026-08-29", "ok-a", "alt-a"),
        ],
        attempts=3,
        sleep=lambda _seconds: None,
    )
    assert calls == ["2026-08-28", "2026-08-29"]
    assert result.created_count == 1
    assert result.failed_count == 1
    assert result.failed[0][0].from_date == "2026-08-28"


def test_timeout_is_retryable_and_quota_is_not() -> None:
    assert is_retryable_create_error(PlatformApiError(0, "Request timed out contacting x."))
    assert is_retryable_create_error(PlatformApiError(429, "Too many requests"))
    assert not is_retryable_create_error(PlatformApiError(401, "Session expired"))
    assert not is_retryable_create_error(PlatformApiError(402, "Insufficient credits"))
    assert not is_retryable_create_error(PlatformApiError(422, "Invalid plan"))


def test_create_planned_reports_skipped_requests() -> None:
    """A day/pair that already exists is reported (not silently dropped)."""
    planned = [_request("2026-10-06", "ok-a", "alt-a")]
    result = create_planned_batches(
        lambda request: _ok_response(request.from_date),
        planned,
        existing_batches=[_history("2026-10-06", "ok-a", "alt-a", "existing-1")],
        skip_existing=True,
        sleep=lambda _seconds: None,
    )
    assert result.skipped == 1
    assert result.created_count == 0
    assert [request.from_date for request in result.skipped_requests] == ["2026-10-06"]
    assert format_create_batches_summary(result) == "1 already existed."


def test_create_planned_creates_by_default_even_when_slot_exists() -> None:
    """Default Generate creates a new batch for a day/pair that already exists."""
    planned = [_request("2026-10-06", "ok-a", "alt-a")]
    calls: list[str] = []

    def create(request: BatchCreateRequest) -> BatchCreateResponse:
        calls.append(request.from_date)
        return _ok_response(request.from_date)

    result = create_planned_batches(
        create,
        planned,
        existing_batches=[_history("2026-10-06", "ok-a", "alt-a", "existing-1")],
        sleep=lambda _seconds: None,
    )
    assert calls == ["2026-10-06"]
    assert result.created_count == 1
    assert result.skipped == 0
    assert result.skipped_requests == []
