"""Read-only audit of billing / CutLuy checkout configuration."""
from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        print("=== ENV (platform_api) ===")
        print(f"cutluy_api_base_url: {settings.cutluy_api_base_url}")
        print(f"cutluy_secret_key configured: {bool(settings.cutluy_secret_key.strip())}")
        print(f"cutluy_payment_link_id: {settings.cutluy_payment_link_id or '(empty)'}")
        print(f"debug mode: {settings.debug}")

        print("\n=== system_settings (billing.*) ===")
        rows = await conn.fetch(
            """
            SELECT key, value
            FROM system_settings
            WHERE key LIKE 'billing.%'
            ORDER BY key
            """
        )
        if not rows:
            print("(no billing settings in DB — using defaults)")
        for row in rows:
            print(f"  {row['key']} = {row['value']}")

        print("\n=== recent billing_payments ===")
        payments = await conn.fetch(
            """
            SELECT provider, status, checkout_url, created_at
            FROM billing_payments
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        if not payments:
            print("(no payments yet)")
        for row in payments:
            print(f"  [{row['provider']}] {row['status']} @ {row['created_at']}")
            print(f"    checkout_url: {row['checkout_url']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
