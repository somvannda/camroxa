#!/usr/bin/env python3
import asyncio
import asyncpg
from pathlib import Path

env = {}
for line in Path("platform_api/.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
dsn = env["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)

async def main():
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(
        "SELECT key, LEFT(value, 300) AS value FROM system_settings WHERE key LIKE 'ai_routing%' ORDER BY key"
    )
    for row in rows:
        print(row["key"], "=>", row["value"])
    await conn.close()

asyncio.run(main())
