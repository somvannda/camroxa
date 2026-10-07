#!/usr/bin/env python3
"""Admin wallet adjustment (lot-aware) for one user, via the platform's own
`CreditService.admin_adjust`.

Raw SQL would desync the lot-based credit ledger (`credit_wallet_lots`); this
goes through the service so the balance and the `admin_adjustment` row stay
consistent. Dry-run by default.

Usage (on the host, with the platform venv):
    cd /opt/camxora/repo/platform_api && source .venv/bin/activate
    python ../scripts/deploy/refund_credits.py --email user@example.com --credits 990 \
        --reason "refund 99 no-op Suno retries (issue #372)"
    # add --apply to write
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg is required: run with the platform_api venv (source .venv/bin/activate).")
    raise SystemExit(2)

CREDIT_SCALE = 10_000  # 1 display credit = 10_000 units (services/credit_units.py)
ENV_FILE = Path("/opt/camxora/repo/platform_api/.env")


def load_dsn() -> str:
    if not ENV_FILE.is_file():
        raise SystemExit(f"env file not found: {ENV_FILE}")
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("PLATFORM_DATABASE_URL="):
            url = raw.split("=", 1)[1].strip().strip('"').strip("'")
            return url.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("PLATFORM_DATABASE_URL not found in env file")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--credits", type=float, required=True, help="credits to add (negative deducts)")
    p.add_argument("--reason", required=True, help="adjustment reason (recorded as 'admin_adjustment: ...')")
    p.add_argument("--apply", action="store_true", help="write the adjustment (default: dry-run)")
    return p.parse_args()


async def run(args: argparse.Namespace) -> int:
    from platform_api.repositories.credit_repo import CreditRepository
    from platform_api.services.credit_service import CreditService

    units = int(round(args.credits * CREDIT_SCALE))
    if units == 0:
        print("credits must be non-zero")
        return 2

    pool = await asyncpg.create_pool(load_dsn())
    try:
        user_id = await pool.fetchval("SELECT id FROM users WHERE lower(email) = lower($1)", args.email)
        if user_id is None:
            print(f"user not found: {args.email}")
            return 1

        # admin_adjust only touches the credit repo; the other deps are unused here.
        repo = CreditRepository(pool)  # type: ignore[arg-type]
        svc = CreditService(credit_repo=repo, license_repo=None, plan_repo=None)  # type: ignore[arg-type]

        current = await repo.get_balance(user_id)
        new = current + units
        print(f"user:        {args.email} ({user_id})")
        print(f"balance now: {current:,} units ({current / CREDIT_SCALE:,.2f} credits)")
        print(f"adjustment:  {units:+,} units ({args.credits:+,.2f} credits)")
        print(f"new balance: {new:,} units ({new / CREDIT_SCALE:,.2f} credits)")
        print(f"reason:      admin_adjustment: {args.reason}")

        if not args.apply:
            print("dry-run only; pass --apply to write")
            return 0

        result = await svc.admin_adjust(str(user_id), units, args.reason)
        print(f"APPLIED. new balance: {result:,} units ({result / CREDIT_SCALE:,.2f} credits)")
        return 0
    finally:
        await pool.close()


def main() -> int:
    if sys.version_info < (3, 10):
        print("Python 3.10+ required")
        return 2
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
