#!/usr/bin/env python3
"""Dump / diff every user's credit wallet around a v3 cutover.

Remote (on the API host):
  python _credits_cutover_snapshot.py dump /tmp/credits-snapshot-before.csv
  python _credits_cutover_snapshot.py dump /tmp/credits-snapshot-after.csv
  python _credits_cutover_snapshot.py diff /tmp/credits-snapshot-before.csv /tmp/credits-snapshot-after.csv

Diff treats leftover conversion, period grant, CutLuy leftover, and pack mints
as expected wallet increases. A Free daily grant may increase by at most
MAX_DAILY_GRANT_CREDITS (50). More than that is the stacked-daily-grant bug.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

MAX_DAILY_GRANT_CREDITS = Decimal("50")
MAX_DAILY_GRANT_TXNS = 1
EPS = Decimal("0.0001")

SNAPSHOT_SQL = r"""
SELECT
  u.id::text AS user_id,
  u.email,
  ROUND(COALESCE(w.balance, 0) / 10000.0, 4) AS wallet_credits,
  ROUND(COALESCE(lot.grant_rem, 0) / 10000.0, 4) AS grant_remaining,
  ROUND(COALESCE(lot.daily_rem, 0) / 10000.0, 4) AS daily_remaining,
  ROUND(COALESCE(lot.conversion_rem, 0) / 10000.0, 4) AS conversion_remaining,
  ROUND(COALESCE(lot.pack_rem, 0) / 10000.0, 4) AS pack_remaining,
  ROUND(COALESCE(lot.admin_rem, 0) / 10000.0, 4) AS admin_remaining,
  COALESCE(tx.daily_grant_n, 0) AS daily_grant_txn_count,
  ROUND(COALESCE(tx.daily_grant_sum, 0) / 10000.0, 4) AS daily_grant_credit_sum,
  ROUND(COALESCE(tx.period_grant_sum, 0) / 10000.0, 4) AS period_grant_credit_sum,
  ROUND(COALESCE(tx.quota_conversion_sum, 0) / 10000.0, 4) AS quota_conversion_credit_sum,
  ROUND(COALESCE(tx.web_remaining_sum, 0) / 10000.0, 4) AS web_remaining_credit_sum,
  ROUND(COALESCE(tx.pack_sum, 0) / 10000.0, 4) AS pack_credit_sum,
  ROUND(COALESCE(tx.debit_sum, 0) / 10000.0, 4) AS debit_credit_sum,
  COALESCE(conv.leftover_packages, 0) AS leftover_packages_applied,
  COALESCE(conv.credits_minted, 0) AS leftover_credits_applied
FROM users u
LEFT JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN LATERAL (
  SELECT
    SUM(remaining_units) FILTER (WHERE tag = 'grant') AS grant_rem,
    SUM(remaining_units) FILTER (WHERE tag = 'daily_grant') AS daily_rem,
    SUM(remaining_units) FILTER (WHERE tag = 'quota_conversion') AS conversion_rem,
    SUM(remaining_units) FILTER (WHERE tag = 'pack') AS pack_rem,
    SUM(remaining_units) FILTER (WHERE tag = 'admin') AS admin_rem
  FROM credit_wallet_lots l
  WHERE l.user_id = u.id
) lot ON true
LEFT JOIN LATERAL (
  SELECT
    COUNT(*) FILTER (WHERE reason = 'v3_daily_grant' AND direction = 'credit') AS daily_grant_n,
    SUM(amount) FILTER (WHERE reason = 'v3_daily_grant' AND direction = 'credit') AS daily_grant_sum,
    SUM(amount) FILTER (WHERE reason = 'v3_period_grant' AND direction = 'credit') AS period_grant_sum,
    SUM(amount) FILTER (WHERE reason = 'v3_quota_conversion' AND direction = 'credit') AS quota_conversion_sum,
    SUM(amount) FILTER (WHERE reason = 'v3_web_remaining' AND direction = 'credit') AS web_remaining_sum,
    SUM(amount) FILTER (WHERE reason = 'v3_pack' AND direction = 'credit') AS pack_sum,
    SUM(amount) FILTER (WHERE direction = 'debit') AS debit_sum
  FROM credit_transactions t
  WHERE t.user_id = u.id
) tx ON true
LEFT JOIN LATERAL (
  SELECT leftover_packages, credits_minted
  FROM billing_conversion_runs r
  WHERE r.user_id = u.id AND r.status = 'applied'
  ORDER BY r.created_at DESC
  LIMIT 1
) conv ON true
ORDER BY u.email
"""


def _d(value: object) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def dump_csv(path: Path) -> None:
    cmd = [
        "sudo",
        "-u",
        "postgres",
        "psql",
        "-d",
        "camxora_platform",
        "-v",
        "ON_ERROR_STOP=1",
        "-A",
        "-F",
        ",",
        "-P",
        "footer=off",
        "-c",
        SNAPSHOT_SQL,
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {path} rows={max(0, len(lines) - 1)}")


def _index(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["user_id"]: row for row in rows}


def diff_csv(before_path: Path, after_path: Path) -> int:
    before = _index(before_path)
    after = _index(after_path)
    failures: list[str] = []
    expected_changes = 0
    unchanged = 0

    all_ids = sorted(set(before) | set(after), key=lambda uid: (after.get(uid) or before[uid])["email"])
    print("email,wallet_before,wallet_after,wallet_delta,expected_delta,status")
    for user_id in all_ids:
        b = before.get(user_id)
        a = after.get(user_id)
        if b is None:
            failures.append(f"NEW_USER {(a or {}).get('email')} {user_id}")
            continue
        if a is None:
            failures.append(f"MISSING_USER {b.get('email')} {user_id}")
            continue

        wallet_delta = _d(a["wallet_credits"]) - _d(b["wallet_credits"])
        conversion_delta = _d(a["quota_conversion_credit_sum"]) - _d(b["quota_conversion_credit_sum"])
        web_delta = _d(a["web_remaining_credit_sum"]) - _d(b["web_remaining_credit_sum"])
        period_delta = _d(a["period_grant_credit_sum"]) - _d(b["period_grant_credit_sum"])
        pack_delta = _d(a["pack_credit_sum"]) - _d(b["pack_credit_sum"])
        debit_delta = _d(a["debit_credit_sum"]) - _d(b["debit_credit_sum"])
        daily_delta = _d(a["daily_grant_credit_sum"]) - _d(b["daily_grant_credit_sum"])
        daily_txn_delta = int(_d(a["daily_grant_txn_count"]) - _d(b["daily_grant_txn_count"]))

        status = "ok"
        if daily_delta < 0 or daily_delta > MAX_DAILY_GRANT_CREDITS + EPS:
            status = "stacked_daily_grant"
            failures.append(
                f"{a['email']} daily grant +{daily_delta} (max {MAX_DAILY_GRANT_CREDITS})"
            )
        elif daily_txn_delta > MAX_DAILY_GRANT_TXNS:
            status = "stacked_daily_grant"
            failures.append(
                f"{a['email']} daily grant txns +{daily_txn_delta} (max {MAX_DAILY_GRANT_TXNS})"
            )

        allowed_daily = min(daily_delta, MAX_DAILY_GRANT_CREDITS) if daily_delta > 0 else Decimal("0")
        expected = conversion_delta + web_delta + period_delta + pack_delta + allowed_daily - debit_delta
        if abs(wallet_delta - expected) > EPS and status == "ok":
            status = "wallet_mismatch"
            failures.append(
                f"{a['email']} wallet {b['wallet_credits']} -> {a['wallet_credits']} "
                f"delta={wallet_delta} expected={expected}"
            )

        if status == "ok" and wallet_delta == 0:
            unchanged += 1
        elif status == "ok":
            expected_changes += 1
        print(
            f"{a['email']},{b['wallet_credits']},{a['wallet_credits']},"
            f"{wallet_delta},{expected},{status}"
        )

    print(
        f"=== SUMMARY users={len(all_ids)} unchanged={unchanged} "
        f"expected_changes={expected_changes} failures={len(failures)} ==="
    )
    for line in failures:
        print(f"FAIL {line}")
    if failures:
        print("CREDITS_CUTOVER_SNAPSHOT_FAIL")
        return 1
    print("CREDITS_CUTOVER_SNAPSHOT_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) >= 2 and args[0] == "dump":
        dump_csv(Path(args[1]))
        return 0
    if len(args) >= 3 and args[0] == "diff":
        return diff_csv(Path(args[1]), Path(args[2]))
    print(
        "Usage:\n"
        "  python _credits_cutover_snapshot.py dump <out.csv>\n"
        "  python _credits_cutover_snapshot.py diff <before.csv> <after.csv>"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
