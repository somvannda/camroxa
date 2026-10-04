"""Read-only preflight/post-deploy check for web-music credit pricing.

Confirms the database matches the expected state after migrations 127-130:

  - Global Credit Value = 0.005
  - Free plan ($0, 50 credits/month, public)
  - paid tiers: $5/1,000, $10/2,300, $20/5,500, $30/8,800 (monthly)
  - top-up packs: $5/700, $10/1,840, $30/7,920 (active)
  - Camxora Music API: v6 / v6-wild / v6-mini @ 10 credits
  - Suno music: 15 credits price / 12 credits cost

Exits non-zero if any check fails, so it can gate a deploy.

Usage:
  python platform_api/scripts/verify_web_music_pricing.py [DATABASE_URL]
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from typing import Any

import asyncpg

CREDIT_SCALE = 10_000

EXPECTED_GCV = "0.005"
EXPECTED_PAID = {
    "starter_monthly": (500, 1000),
    "creator_monthly": (1000, 2300),
    "pro_monthly": (2000, 5500),
    "studio_monthly": (3000, 8800),
}
EXPECTED_PACKS = {
    "small": (700, 500),
    "medium": (1840, 1000),
    "large": (7920, 3000),
}
EXPECTED_CAMXORA = {"v6", "v6-mini", "v6-wild"}
CAMXORA_UNITS = 10 * CREDIT_SCALE
SUNO_PRICE_UNITS = 15 * CREDIT_SCALE
SUNO_COST_UNITS = 12 * CREDIT_SCALE

_failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        _failures.append(name)


def dsn() -> str:
    if len(sys.argv) > 1:
        value = sys.argv[1]
    else:
        value = os.environ.get("PLATFORM_DATABASE_URL", "")
        if not value:
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            try:
                with open(env_path, encoding="utf-8") as fh:
                    for line in fh:
                        match = re.match(r"\s*PLATFORM_DATABASE_URL\s*=\s*(.+)", line)
                        if match:
                            value = match.group(1).strip().strip('"').strip("'")
                            break
            except OSError:
                pass
    if not value:
        print("No DATABASE_URL provided (arg or PLATFORM_DATABASE_URL).", file=sys.stderr)
        sys.exit(2)
    return value.replace("postgresql+asyncpg://", "postgresql://")


async def run(conn: asyncpg.Connection) -> None:
    gcv = await conn.fetchval("SELECT value FROM system_settings WHERE key = 'global_credit_value'")
    check("GCV = 0.005", str(gcv) == EXPECTED_GCV, f"got {gcv}")

    free = await conn.fetchrow(
        "SELECT price_cents, monthly_credits, is_public, is_active FROM plans "
        "WHERE lower(name) = 'free' ORDER BY updated_at DESC LIMIT 1"
    )
    check(
        "Free plan: $0 / 50 per month / public / active",
        bool(free)
        and int(free["price_cents"]) == 0
        and int(free["monthly_credits"] or 0) == 50
        and bool(free["is_public"])
        and bool(free["is_active"]),
        f"got {dict(free) if free else None}",
    )

    rows = await conn.fetch(
        "SELECT name, price_cents, monthly_credits FROM plans "
        "WHERE plan_type = 'web_music' AND billing_cycle_days = 30 AND price_cents > 0"
    )
    got = {r["name"]: (int(r["price_cents"]), int(r["monthly_credits"] or 0)) for r in rows}
    check("Paid tiers $5/$10/$20/$30 with mirrored credits", got == EXPECTED_PAID, f"got {got}")

    packs = await conn.fetch(
        "SELECT slug, total_credits, price_cents FROM credit_packs "
        "WHERE pack_type = 'web_music' AND is_active"
    )
    got_packs = {r["slug"]: (int(r["total_credits"]), int(r["price_cents"])) for r in packs}
    check("Top-up packs $5/700 - $10/1,840 - $30/7,920", got_packs == EXPECTED_PACKS, f"got {got_packs}")

    camxora = await conn.fetch(
        "SELECT sub_model, credits_per_operation, external_cost_cents FROM credit_pricing "
        "WHERE ai_service = 'camxora_music_api' AND operation_type = 'music'"
    )
    models = {r["sub_model"] for r in camxora}
    units_ok = all(
        int(r["credits_per_operation"]) == CAMXORA_UNITS and int(r["external_cost_cents"]) == CAMXORA_UNITS
        for r in camxora
    )
    check("Camxora Music API v6/v6-wild/v6-mini @ 10 credits", models == EXPECTED_CAMXORA and units_ok, f"got {models}")

    suno = await conn.fetch(
        "SELECT sub_model, credits_per_operation, external_cost_cents FROM credit_pricing "
        "WHERE ai_service = 'suno' AND operation_type = 'music'"
    )
    suno_ok = bool(suno) and all(
        int(r["credits_per_operation"]) == SUNO_PRICE_UNITS and int(r["external_cost_cents"]) == SUNO_COST_UNITS
        for r in suno
    )
    check("Suno music 15 credits / 12 cost", suno_ok, f"{len(suno)} rows")


async def main() -> None:
    connection = await asyncpg.connect(dsn())
    try:
        await run(connection)
    finally:
        await connection.close()
    print()
    if _failures:
        print(f"RESULT: {len(_failures)} check(s) failed.")
        sys.exit(1)
    print("RESULT: all checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
