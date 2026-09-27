#!/usr/bin/env python3
"""READ-ONLY: download prod cutover before/after wallet snapshots and diff."""

from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
OUT_DIR = Path(__file__).resolve().parent / "out"


def download() -> tuple[Path, Path]:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before = OUT_DIR / "credits-snapshot-production-before.csv"
    after = OUT_DIR / "credits-snapshot-production-after.csv"
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.get("/tmp/credits-snapshot-before.csv", str(before))
        sftp.get("/tmp/credits-snapshot-after.csv", str(after))
        sftp.close()
    finally:
        client.close()
    print(f"SAVED {before}")
    print(f"SAVED {after}")
    return before, after


def _d(value: object) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def diff(before: Path, after: Path) -> int:
    def index(path: Path) -> dict[str, dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as handle:
            return {r["user_id"]: r for r in csv.DictReader(handle)}

    b = index(before)
    a = index(after)
    rows = []
    for uid in sorted(set(b) | set(a), key=lambda u: (a.get(u) or b.get(u) or {}).get("email", "")):
        rb = b.get(uid)
        ra = a.get(uid)
        if rb is None or ra is None:
            rows.append((ra or rb, None, None, "NEW" if rb is None else "MISSING"))
            continue
        wb = _d(rb["wallet_credits"])
        wa = _d(ra["wallet_credits"])
        if wa != wb:
            rows.append((ra, wb, wa, ""))
    print(f"=== users with wallet change before->after: {len(rows)} ===")
    print("email,wallet_before,wallet_after,delta,conv_minted,web_remaining,period_grant,debit_after")
    for ra, wb, wa, note in rows:
        if note:
            print(f"{ra.get('email')},{wb},{wa},,{note}")
            continue
        delta = wa - wb
        print(
            f"{ra['email']},{wb},{wa},{delta},"
            f"{ra['quota_conversion_credit_sum']},{ra['web_remaining_credit_sum']},"
            f"{ra['period_grant_credit_sum']},{ra['debit_credit_sum']}"
        )
    print("=== done ===")
    return 0


def main() -> int:
    if "--download" in sys.argv:
        before, after = download()
    else:
        before = OUT_DIR / "credits-snapshot-production-before.csv"
        after = OUT_DIR / "credits-snapshot-production-after.csv"
        if not before.is_file() or not after.is_file():
            raise SystemExit("Run with --download first.")
    return diff(before, after)


if __name__ == "__main__":
    raise SystemExit(main())
