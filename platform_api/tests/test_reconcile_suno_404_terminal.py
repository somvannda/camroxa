"""Aged provider-404 Suno tasks reconcile as terminal failures (not stuck pending).

The reconcile loop used to swallow every poll error, so a task the provider no
longer knows (`check_status` -> 404) sat in `pending` forever — charged, never
finished, never refunded (23 such rows in production). A 404 past a grace window
is terminal: route it into the normal FAILED handling (which refunds).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import platform_api.dependencies as deps
import platform_api.services.suno_audio_resolver as resolver
from platform_api.exceptions import ExternalServiceError
from platform_api.models.enums import TaskStatus
from platform_api.tests.test_batch_service import make_service


def _service():
    return make_service(
        AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    )


def _row(*, age_minutes: int) -> dict:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "song_id": uuid4(),
        "batch_id": uuid4(),
        "external_task_id": "ext-123",
        "status": "pending",
        "audio_url_ok": None,
        "audio_url_alt": None,
        "audio_id_ok": None,
        "audio_id_alt": None,
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
    }


def _wire(service, monkeypatch, row, exc: Exception | None) -> None:
    service._batch_repo.list_stuck_suno_pending_songs = AsyncMock(return_value=[])
    service._batch_repo.list_reconcilable_suno_tasks = AsyncMock(return_value=[row])
    service._batch_repo.update_status = AsyncMock()
    service.handle_suno_task_update = AsyncMock()

    monkeypatch.setattr(deps, "get_db_pool", lambda: object())

    async def _poll(_pool, _ext):
        if exc is not None:
            raise exc
        raise AssertionError("row should not have been polled")

    monkeypatch.setattr(resolver, "poll_suno_generate_with_pool", _poll)


@pytest.mark.asyncio
async def test_aged_404_reconciles_as_terminal_failure(monkeypatch):
    service = _service()
    row = _row(age_minutes=120)
    _wire(
        service,
        monkeypatch,
        row,
        ExternalServiceError("Suno API error 404: check_status", details={"status_code": 404}),
    )

    reconciled = await service.reconcile_pending_suno_tasks(user_id=str(uuid4()), limit=25)

    assert reconciled == 1
    service._batch_repo.update_status.assert_awaited_once()
    assert service._batch_repo.update_status.await_args.kwargs["status"] == TaskStatus.FAILED
    service.handle_suno_task_update.assert_awaited_once()
    assert (
        service.handle_suno_task_update.await_args.kwargs["status"] == TaskStatus.FAILED
    )


@pytest.mark.asyncio
async def test_recent_404_is_not_terminal(monkeypatch):
    """A fresh 404 is propagation lag, not a lost task — leave it pending."""
    service = _service()
    row = _row(age_minutes=5)
    _wire(
        service,
        monkeypatch,
        row,
        ExternalServiceError("Suno API error 404: check_status", details={"status_code": 404}),
    )

    reconciled = await service.reconcile_pending_suno_tasks(user_id=str(uuid4()), limit=25)

    assert reconciled == 0
    service._batch_repo.update_status.assert_not_awaited()
    service.handle_suno_task_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_aged_non_404_error_still_skipped(monkeypatch):
    """Transient errors (timeouts/5xx) must keep the old continue behaviour."""
    service = _service()
    row = _row(age_minutes=120)
    _wire(
        service,
        monkeypatch,
        row,
        ExternalServiceError("Suno API error 500: check_status", details={"status_code": 500}),
    )

    reconciled = await service.reconcile_pending_suno_tasks(user_id=str(uuid4()), limit=25)

    assert reconciled == 0
    service._batch_repo.update_status.assert_not_awaited()


def test_aged_for_terminal_not_found_boundary():
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    assert _aged(now - timedelta(minutes=31), now=now) is True
    assert _aged(now - timedelta(minutes=29), now=now) is False


def _aged(created_at: datetime, *, now: datetime) -> bool:
    from platform_api.services.batch_service import BatchService

    return BatchService._suno_task_aged_for_terminal_not_found(created_at, now=now)
