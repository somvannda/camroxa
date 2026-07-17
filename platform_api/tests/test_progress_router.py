"""Progress router helper tests."""

from __future__ import annotations

from datetime import date, datetime, timezone

from platform_api.routers.progress import (
    _batch_run_from_date,
    _batch_run_to_date,
    _format_batch_run_date,
)


def test_format_batch_run_date_uses_planned_dates() -> None:
    batch = {
        "planned_from_date": date(2026, 7, 12),
        "planned_to_date": date(2026, 7, 12),
        "created_at": datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc),
    }
    assert _format_batch_run_date(batch) == "2026-07-12"


def test_format_batch_run_date_shows_planned_range() -> None:
    batch = {
        "planned_from_date": date(2026, 7, 11),
        "planned_to_date": date(2026, 7, 12),
        "created_at": datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
    }
    assert _format_batch_run_date(batch) == "2026-07-11 → 2026-07-12"


def test_coerce_uuid_list_normalizes_postgres_arrays() -> None:
    from platform_api.routers.progress import _coerce_uuid_list
    from uuid import uuid4

    first = uuid4()
    second = uuid4()
    assert _coerce_uuid_list([first, second]) == [str(first), str(second)]
    assert _coerce_uuid_list(None) == []


def test_batch_run_dates_fallback_to_utc_created_at() -> None:
    created = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    batch = {"created_at": created}
    assert _batch_run_from_date(batch) == date(2026, 7, 11)
    assert _batch_run_to_date(batch) == date(2026, 7, 11)
