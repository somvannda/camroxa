#!/usr/bin/env python3
"""Alert on NEW wallet-vs-ledger drift, ignoring the known historical set.

Some accounts carry gaps older than 2026-11-04: monthly Free-grant cycles that
predated their ledger rows, and lots that expired without a ``v3_grant_expire``
row. The wallets are correct (they equal live lots); the ledger is the incomplete
side. ``drift_baseline.json`` records those so a real new gap is not buried under
64 permanent hits.

Sub-credit differences (< 1 credit) are ignored: the retired web-music ledger
recorded raw credit counts instead of units, leaving 0.01-0.02 residue.

Read-only.

Exit codes: 0 = no new drift, 1 = new or changed drift, 2 = error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

UNITS_PER_CREDIT = 10_000

SQL = """
WITH t AS (
    SELECT user_id,
           sum(CASE WHEN direction IN ('credit','refund') THEN amount ELSE 0 END) AS inflow,
           sum(CASE WHEN direction = 'debit' THEN amount ELSE 0 END) AS outflow
    FROM credit_transactions
    GROUP BY user_id
)
SELECT u.id AS user_id, u.email,
       (w.balance - coalesce(t.inflow - t.outflow, 0)) AS drift_units,
       w.balance
FROM users u
JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN t ON t.user_id = u.id
WHERE abs(w.balance - coalesce(t.inflow - t.outflow, 0)) >= $1
ORDER BY drift_units DESC;
"""


def load_baseline(path: Path) -> dict[str, int]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {str(u["user_id"]): int(u["drift_units"]) for u in doc.get("users", [])}


async def run(dsn: str, baseline_path: Path, as_json: bool) -> int:
    threshold = UNITS_PER_CREDIT
    baseline = load_baseline(baseline_path)

    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(SQL, threshold)
    finally:
        await conn.close()

    new: list[dict[str, object]] = []
    for r in rows:
        uid = str(r["user_id"])
        drift = int(r["drift_units"] or 0)
        known = baseline.get(uid)
        if known is None:
            new.append({"email": r["email"], "drift_credits": drift / UNITS_PER_CREDIT, "kind": "new"})
        elif abs(drift - known) >= threshold:
            new.append(
                {
                    "email": r["email"],
                    "drift_credits": drift / UNITS_PER_CREDIT,
                    "was_credits": known / UNITS_PER_CREDIT,
                    "kind": "changed",
                }
            )

    if as_json:
        print(json.dumps({"new_drift": len(new), "rows": new}, indent=2))
    else:
        print(f"wallet/ledger drift above 1 credit: {len(rows)} account(s); "
              f"baseline {len(baseline)}; new or changed: {len(new)}")
        for item in new:
            if item["kind"] == "new":
                print(f"  NEW      {item['email']:34} {item['drift_credits']:+.2f} credits")
            else:
                print(
                    f"  CHANGED  {item['email']:34} {item['was_credits']:+.2f} -> "
                    f"{item['drift_credits']:+.2f} credits"
                )

    return 1 if new else 0


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument(
        "--baseline",
        default=str(here / "drift_baseline.json"),
        help="known-drift baseline JSON",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(run(dsn, Path(args.baseline), args.json))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
