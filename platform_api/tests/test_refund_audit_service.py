"""Failed-refund audit: mapping, aggregation, and the admin endpoint payload."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from platform_api.routers import admin_refunds
from platform_api.services.refund_audit_service import (
    collect_unrefunded_music_charges,
    refund_command,
    summarize_by_user,
)

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)


class _Pool:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, tuple]] = []

    async def fetch(self, query: str, *args: object) -> list[dict]:
        self.calls.append((query, args))
        return self._rows


@pytest.mark.asyncio
async def test_maps_rows_and_classifies_reason() -> None:
    pool = _Pool(
        [
            {
                "id": "d1",
                "user_id": "u1",
                "email": "a@example.com",
                "created_at": NOW,
                "amount": 100_000,
                "task_id": None,
                "song_id": None,
                "task_status": None,
            },
            {
                "id": "d2",
                "user_id": "u1",
                "email": "a@example.com",
                "created_at": NOW,
                "amount": 100_000,
                "task_id": "t2",
                "song_id": "s2",
                "task_status": "failed",
            },
        ]
    )

    rows = await collect_unrefunded_music_charges(pool, days=30, min_age_minutes=15)

    assert [row["reason"] for row in rows] == ["no_task", "failed_task"]
    assert rows[0]["credits"] == 10.0
    assert rows[0]["task_status"] is None
    assert pool.calls[0][1] == ("30", "15")


def test_summarize_by_user_totals_and_window() -> None:
    rows = [
        {"user_id": "u1", "email": "a@example.com", "credits": 10.0, "created_at": "2026-11-01T00:00:00+00:00"},
        {"user_id": "u1", "email": "a@example.com", "credits": 10.0, "created_at": "2026-11-03T00:00:00+00:00"},
        {"user_id": "u2", "email": "b@example.com", "credits": 30.0, "created_at": "2026-11-02T00:00:00+00:00"},
    ]

    users = summarize_by_user(rows)

    assert [u["user_id"] for u in users] == ["u2", "u1"]
    assert users[1]["charges"] == 2
    assert users[1]["credits"] == 20.0
    assert users[1]["first_seen"] == "2026-11-01T00:00:00+00:00"
    assert users[1]["last_seen"] == "2026-11-03T00:00:00+00:00"


def test_refund_command_is_copy_paste_ready() -> None:
    assert refund_command(820, days=30) == (
        "python scripts/ops/refund_unkeyed_music_charges.py "
        "--days 30 --apply --confirm-credits 820"
    )


@pytest.mark.asyncio
async def test_endpoint_payload_has_totals_and_command(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(
        [
            {
                "id": "d1",
                "user_id": "u1",
                "email": "a@example.com",
                "created_at": NOW,
                "amount": 100_000,
                "task_id": None,
                "song_id": None,
                "task_status": None,
            }
        ]
    )
    monkeypatch.setattr(admin_refunds, "get_db_pool", lambda: pool)

    payload = await admin_refunds.list_failed_refunds(None, days=30, min_age_minutes=15, limit=50)

    assert payload["summary"] == {
        "charges": 1,
        "credits": 10.0,
        "users": 1,
        "no_task": 1,
        "failed_task": 0,
    }
    assert payload["refund_command"].endswith("--confirm-credits 10")
    assert payload["rows"][0]["debit_id"] == "d1"


@pytest.mark.asyncio
async def test_refund_failed_charges_uses_idempotent_orphan_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import refund_audit_service as service

    class _Repo:
        def __init__(self, pool: object) -> None:
            self.calls: list[dict] = []

        async def refund_once(self, user_id, amount, reason, ref_id, metadata):
            self.calls.append(
                {
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason,
                    "ref_id": ref_id,
                    "metadata": metadata,
                }
            )
            return True

    pool = _Pool(
        [
            {
                "id": "d1",
                "user_id": "u1",
                "created_at": NOW,
                "amount": 100_000,
            }
        ]
    )
    monkeypatch.setattr(
        "platform_api.repositories.credit_repo.CreditRepository", _Repo
    )

    result = await service.refund_failed_charges(
        pool,
        user_id="11111111-1111-1111-1111-111111111111",
        debit_ids=["22222222-2222-2222-2222-222222222222"],
        admin_id="33333333-3333-3333-3333-333333333333",
    )

    assert result == {
        "requested": 1,
        "matched": 1,
        "refunded": 1,
        "skipped": 0,
        "failed": 0,
        "credits": 10.0,
    }
    assert pool.calls[0][0].count("orphan:") == 1


@pytest.mark.asyncio
async def test_refund_endpoint_requires_confirmation() -> None:
    from types import SimpleNamespace

    from pydantic import ValidationError as PydanticValidationError

    from platform_api.exceptions import ValidationError

    body = admin_refunds.RefundFailedRequest(
        user_id="11111111-1111-1111-1111-111111111111",
        debit_ids=["22222222-2222-2222-2222-222222222222"],
        confirm="",
    )

    with pytest.raises(ValidationError):
        await admin_refunds.refund_failed(SimpleNamespace(user_id="admin"), body)

    with pytest.raises(PydanticValidationError):
        admin_refunds.RefundFailedRequest(
            user_id="11111111-1111-1111-1111-111111111111",
            debit_ids=[],
            confirm="REFUND",
        )
