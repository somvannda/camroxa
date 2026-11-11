#!/usr/bin/env python3
"""Drop the credit-wallet-lot repair snapshot after a clean grace period.

The 2026-11-11 repair kept ``credit_wallet_lots_repair_20261111`` as a rollback
copy. Once the ledger has stayed consistent for a few days that copy is dead
weight, so this drops it — but only after re-proving the invariants the snapshot
exists to protect:

* every wallet equals the sum of its live lots;
* no ``grant`` lot is left without an expiry;
* the pack-lot unique index from migration 197 is present, so the duplicate-lot
  bug that caused the repair cannot silently return.

The table is dropped only when the snapshot is at least ``--min-age-days`` old
and every guard passes. Nothing is dropped without ``--apply``.

Usage (from the repo root, with the platform venv):
    python scripts/ops/drop_credit_repair_snapshot.py                 # dry run
    python scripts/ops/drop_credit_repair_snapshot.py --apply         # drop if safe
    python scripts/ops/drop_credit_repair_snapshot.py --json          # machine-readable

    # snapshot from a different date / shorter grace period
    python scripts/ops/drop_credit_repair_snapshot.py --apply \\
        --created-on 2026-11-01 --min-age-days 3

Cron (daily, after the database backup):
    10 4 * * * cd /opt/camxora/repo && \\
      platform_api/.venv/bin/python scripts/ops/drop_credit_repair_snapshot.py --apply \\
      >> /var/log/camxora/drop-repair-snapshot.log 2>&1

Exit codes: 0 = dropped, already gone, or still within the grace period (the
expected daily outcome); 1 = a guard failed and the snapshot was kept;
2 = error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime, timezone

import asyncpg

DEFAULT_TABLE = "credit_wallet_lots_repair_20261111"
DEFAULT_CREATED_ON = "2026-11-11"
DEFAULT_MIN_AGE_DAYS = 7
UNITS_PER_CREDIT = 10_000

# Same statement the daily credit-invariant alert uses.
WALLET_MISMATCH_SQL = """
SELECT count(*) FROM credit_wallets w
WHERE w.balance <> COALESCE((
  SELECT SUM(l.remaining_units) FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
), 0)
"""

NO_EXPIRY_GRANTS_SQL = """
SELECT count(*) FROM credit_wallet_lots
WHERE tag = 'grant' AND remaining_units > 0 AND expires_at IS NULL
"""

PACK_INDEX_SQL = """
SELECT to_regclass('public.uq_credit_wallet_lots_pack_ref') IS NOT NULL
"""


def _safe_identifier(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
        raise ValueError(f"refusing unsafe table name: {name!r}")
    return name


async def run(
    dsn: str,
    *,
    table: str,
    created_on: date,
    min_age_days: int,
    apply: bool,
    force: bool,
    as_json: bool,
) -> int:
    age_days = (datetime.now(timezone.utc).date() - created_on).days
    report: dict = {
        "table": table,
        "created_on": created_on.isoformat(),
        "age_days": age_days,
        "min_age_days": min_age_days,
        "exists": False,
        "applied": False,
        "guards": {},
        "kept_reason": None,
    }

    conn = await asyncpg.connect(dsn=dsn)
    try:
        exists = bool(await conn.fetchval("SELECT to_regclass($1)::text", f"public.{table}"))
        report["exists"] = exists
        if not exists:
            report["kept_reason"] = "already gone"
            return _emit(report, as_json, "nothing to do: snapshot table is already gone")

        report["guards"] = {
            "wallet_lot_mismatches": int(await conn.fetchval(WALLET_MISMATCH_SQL) or 0),
            "grant_lots_without_expiry": int(await conn.fetchval(NO_EXPIRY_GRANTS_SQL) or 0),
            "pack_ref_index_present": bool(await conn.fetchval(PACK_INDEX_SQL)),
        }

        if not force and age_days < min_age_days:
            report["kept_reason"] = (
                f"snapshot is {age_days} day(s) old; needs {min_age_days}"
            )
            return _emit(report, as_json)
        if force and age_days < min_age_days:
            print(
                f"WARN: --force ignores the {min_age_days}-day grace period "
                f"(snapshot is {age_days} day(s) old)",
                file=sys.stderr,
            )

        broken = [
            name
            for name, ok in (
                ("wallet_lot_mismatches", report["guards"]["wallet_lot_mismatches"] == 0),
                (
                    "grant_lots_without_expiry",
                    report["guards"]["grant_lots_without_expiry"] == 0,
                ),
                ("pack_ref_index_present", report["guards"]["pack_ref_index_present"]),
            )
            if not ok
        ]
        if broken:
            report["kept_reason"] = "guard failed: " + ", ".join(broken)
            return _emit(report, as_json)

        if not apply:
            report["kept_reason"] = "dry run (pass --apply to drop)"
            return _emit(report, as_json)

        await conn.execute(f"DROP TABLE IF EXISTS {table}")
        report["applied"] = True
        return _emit(report, as_json)
    finally:
        await conn.close()


def _emit(report: dict, as_json: bool, note: str | None = None) -> int:
    if as_json:
        print(json.dumps(report, indent=2, default=str))
    else:
        g = report.get("guards") or {}
        print(
            f"snapshot {report['table']}: exists={report['exists']} "
            f"age={report['age_days']}d/{report['min_age_days']}d"
        )
        if g:
            print(
                f"  guards: wallet_mismatches={g['wallet_lot_mismatches']} "
                f"no_expiry_grants={g['grant_lots_without_expiry']} "
                f"pack_ref_index={g['pack_ref_index_present']}"
            )
        if report["applied"]:
            print(f"DROPPED {report['table']}")
        else:
            print(f"  KEPT: {note or report['kept_reason']}")
    if report["applied"]:
        return 0
    reason = str(report.get("kept_reason") or "")
    # A young snapshot or a dry run is the expected daily outcome; only a failed
    # guard (the ledger drifting again) deserves a non-zero exit in cron.
    return 1 if reason.startswith("guard failed") else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument("--table", default=DEFAULT_TABLE, help="snapshot table name")
    parser.add_argument(
        "--created-on",
        default=DEFAULT_CREATED_ON,
        help=f"snapshot date, YYYY-MM-DD (default {DEFAULT_CREATED_ON})",
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=DEFAULT_MIN_AGE_DAYS,
        help=f"grace period in days (default {DEFAULT_MIN_AGE_DAYS})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually drop the table once every guard passes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore the age check (guards are always enforced)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    try:
        table = _safe_identifier(str(args.table))
        created_on = date.fromisoformat(str(args.created_on))
        if args.min_age_days < 0:
            raise ValueError("--min-age-days must be >= 0")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")
    try:
        code = asyncio.run(
            run(
                dsn,
                table=table,
                created_on=created_on,
                min_age_days=args.min_age_days,
                apply=bool(args.apply),
                force=bool(args.force),
                as_json=bool(args.json),
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
