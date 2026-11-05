"""Read-only audit: music charges that produced no successful task.

A ``v3_music`` debit is written before the ``suno_tasks`` row exists. Desktop
debits carried ``ref_id = NULL`` before commit c23c7b9b, so they cannot be
joined by key; this service time-correlates each unkeyed debit with the nearest
task for the same user.

A charge is reported when all of these hold:

* it is older than ``min_age_minutes`` (not an in-flight submit);
* the nearest task within ±120s is missing, or failed/error;
* no refund is keyed to the task/song;
* no same-amount refund landed within 10 minutes after the charge.

The last check matters: a failed submit refunds under the song key, which can
fall outside the task window. Without it the audit over-reported ~3.5x.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

UNITS_PER_CREDIT = 10_000

SQL = """
WITH debits AS (
    SELECT ct.id, ct.user_id, ct.created_at, ct.amount
    FROM credit_transactions ct
    WHERE ct.reason = 'v3_music'
      AND ct.direction = 'debit'
      AND ct.ref_id IS NULL
      AND ct.created_at >= now() - ($1 || ' days')::interval
      AND ct.created_at < now() - ($2 || ' minutes')::interval
)
SELECT d.id,
       d.user_id,
       u.email,
       d.created_at,
       d.amount,
       t.id AS task_id,
       t.song_id,
       t.status AS task_status
FROM debits d
JOIN users u ON u.id = d.user_id
LEFT JOIN LATERAL (
    SELECT t.id, t.song_id, t.status
    FROM suno_tasks t
    WHERE t.user_id = d.user_id
      AND t.created_at BETWEEN d.created_at - interval '120 seconds'
                           AND d.created_at + interval '120 seconds'
    ORDER BY abs(extract(epoch FROM (t.created_at - d.created_at)))
    LIMIT 1
) t ON true
WHERE (
        t.id IS NULL
        OR (
             lower(coalesce(t.status, '')) IN ('failed', 'error')
             AND NOT EXISTS (
                 SELECT 1 FROM credit_transactions r
                 WHERE r.user_id = d.user_id
                   AND (r.direction = 'refund' OR r.reason ILIKE '%refund%')
                   AND (r.ref_id = t.id::text OR r.ref_id = t.song_id::text)
             )
        )
      )
  AND NOT EXISTS (
        SELECT 1 FROM credit_transactions r
        WHERE r.user_id = d.user_id
          AND (r.direction = 'refund' OR r.reason ILIKE '%refund%')
          AND r.amount = d.amount
          AND r.created_at >= d.created_at
          AND r.created_at <= d.created_at + interval '10 minutes'
  )
ORDER BY d.created_at;
"""


def _credits(units: object) -> float:
    return float(int(units or 0) / UNITS_PER_CREDIT)


async def collect_unrefunded_music_charges(
    pool: Any,
    *,
    days: int = 30,
    min_age_minutes: int = 15,
) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        SQL,
        str(max(1, int(days))),
        str(max(0, int(min_age_minutes))),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        status = str(row["task_status"] or "").strip().lower()
        out.append(
            {
                "debit_id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "email": str(row["email"] or ""),
                "created_at": row["created_at"].isoformat(),
                "credits": _credits(row["amount"]),
                "task_id": str(row["task_id"]) if row["task_id"] else None,
                "song_id": str(row["song_id"]) if row["song_id"] else None,
                "task_status": status or None,
                "reason": "failed_task" if status in {"failed", "error"} else "no_task",
            }
        )
    return out


def summarize_by_user(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    users: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["user_id"])
        entry = users.setdefault(
            key,
            {
                "user_id": key,
                "email": row["email"],
                "charges": 0,
                "credits": 0.0,
                "first_seen": row["created_at"],
                "last_seen": row["created_at"],
            },
        )
        entry["charges"] += 1
        entry["credits"] += float(row["credits"])
        if row["created_at"] < entry["first_seen"]:
            entry["first_seen"] = row["created_at"]
        if row["created_at"] > entry["last_seen"]:
            entry["last_seen"] = row["created_at"]
    return sorted(users.values(), key=lambda item: -item["credits"])


def refund_command(total_credits: int, *, days: int = 30) -> str:
    """Copy-paste command an operator runs after reviewing the rows."""
    return (
        "python scripts/ops/refund_unkeyed_music_charges.py "
        f"--days {int(days)} --apply --confirm-credits {int(total_credits)}"
    )


__all__ = [
    "collect_unrefunded_music_charges",
    "summarize_by_user",
    "refund_command",
    "UNITS_PER_CREDIT",
]
