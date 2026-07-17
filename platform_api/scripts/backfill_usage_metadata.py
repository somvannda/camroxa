"""Backfill credit_transactions.metadata for legacy llm_draft charges.

Infers purpose, provider, model, and line_items from debit amounts and
optionally links rows to songs/batches when ref_id matches a song UUID.

Usage:
  python platform_api/scripts/backfill_usage_metadata.py
  python platform_api/scripts/backfill_usage_metadata.py --apply
  python platform_api/scripts/backfill_usage_metadata.py --apply --days 30 --user-id <uuid>
  python platform_api/scripts/backfill_usage_metadata.py --apply --link-by-time
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any
from uuid import UUID

import asyncpg

from platform_api.services.usage_transaction_labels import build_legacy_metadata_backfill

DEFAULT_DB = "postgresql://postgres:postgres@localhost:5432/platform_db"

DRAFT_REASONS = ("llm_draft", "draft_generation_failed", "draft_generation_error")


async def _lookup_song_by_ref(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    ref_id: str | None,
) -> dict[str, Any]:
    if not ref_id:
        return {}
    try:
        song_id = UUID(ref_id)
    except ValueError:
        return {}

    row = await conn.fetchrow(
        """
        SELECT id, batch_id, batch_index
        FROM songs
        WHERE id = $1 AND user_id = $2
        """,
        song_id,
        user_id,
    )
    if row is None:
        return {}

    return {
        "source": "batch",
        "song_id": str(row["id"]),
        "batch_id": str(row["batch_id"]),
        "batch_index": int(row["batch_index"]),
    }


async def _lookup_song_by_time(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    created_at: Any,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        SELECT id, batch_id, batch_index
        FROM songs
        WHERE user_id = $1
          AND $2::timestamptz BETWEEN created_at - INTERVAL '1 minute'
              AND updated_at + INTERVAL '2 hours'
        ORDER BY ABS(EXTRACT(EPOCH FROM ($2::timestamptz - updated_at)))
        LIMIT 1
        """,
        user_id,
        created_at,
    )
    if row is None:
        return {}

    return {
        "source": "batch",
        "song_id": str(row["id"]),
        "batch_id": str(row["batch_id"]),
        "batch_index": int(row["batch_index"]),
        "trace_method": "time_match",
    }


def _needs_backfill(metadata: Any) -> bool:
    if metadata is None:
        return True
    if isinstance(metadata, str):
        metadata = metadata.strip()
        if not metadata:
            return True
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return True
    if not isinstance(metadata, dict):
        return True
    if not metadata.get("purpose"):
        return True
    line_items = metadata.get("line_items")
    return not isinstance(line_items, list) or len(line_items) == 0


async def backfill(
    *,
    db_url: str,
    apply: bool,
    days: int,
    user_id: str | None,
    link_by_time: bool,
) -> int:
    conn = await asyncpg.connect(db_url)
    updated = 0
    skipped = 0
    try:
        params: list[Any] = [days, list(DRAFT_REASONS)]
        user_filter = ""
        if user_id:
            user_filter = "AND user_id = $3::uuid"
            params.append(UUID(user_id))

        rows = await conn.fetch(
            f"""
            SELECT id, user_id, amount, direction, reason, ref_id, metadata, created_at
            FROM credit_transactions
            WHERE reason = ANY($2::text[])
              AND created_at >= NOW() - make_interval(days => $1)
              {user_filter}
            ORDER BY created_at ASC
            """,
            *params,
        )

        candidates = [row for row in rows if _needs_backfill(row["metadata"])]
        print(f"Scanned {len(rows)} draft-related rows; {len(candidates)} need metadata backfill.")

        for row in candidates:
            trace = await _lookup_song_by_ref(
                conn,
                user_id=row["user_id"],
                ref_id=row["ref_id"],
            )
            existing = row["metadata"]
            if isinstance(existing, str):
                try:
                    existing = json.loads(existing)
                except json.JSONDecodeError:
                    existing = {}
            if not isinstance(existing, dict):
                existing = {}

            if not trace.get("song_id") and link_by_time and not existing.get("song_id"):
                trace = await _lookup_song_by_time(
                    conn,
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                )

            patch = build_legacy_metadata_backfill(
                amount_units=int(row["amount"] or 0),
                reason=str(row["reason"] or ""),
                trace=trace or None,
            )
            if not patch:
                skipped += 1
                continue

            merged = {**existing, **patch}
            print(
                f"{'UPDATE' if apply else 'DRY-RUN'} {row['id']} "
                f"reason={row['reason']} amount={row['amount']} "
                f"purpose={merged.get('purpose')}"
                + (f" song={merged.get('song_id')}" if merged.get("song_id") else "")
            )

            if apply:
                await conn.execute(
                    """
                    UPDATE credit_transactions
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                    WHERE id = $1
                    """,
                    row["id"],
                    json.dumps(merged),
                )
            updated += 1

        print(f"{'Updated' if apply else 'Would update'}: {updated}; skipped: {skipped}")
        if not apply and updated:
            print("Dry run only. Re-run with --apply to persist changes.")
        return updated
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legacy llm_draft usage metadata")
    parser.add_argument("--db-url", default=DEFAULT_DB, help="PostgreSQL connection URL")
    parser.add_argument("--apply", action="store_true", help="Persist metadata updates")
    parser.add_argument("--days", type=int, default=90, help="Only rows from the last N days")
    parser.add_argument("--user-id", default=None, help="Limit to one user UUID")
    parser.add_argument(
        "--link-by-time",
        action="store_true",
        help="Best-effort song match by created_at proximity when ref_id is not a song UUID",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            backfill(
                db_url=args.db_url,
                apply=args.apply,
                days=max(1, args.days),
                user_id=args.user_id,
                link_by_time=args.link_by_time,
            )
        )
    except Exception as exc:
        print(f"Backfill failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
