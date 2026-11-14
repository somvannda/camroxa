import asyncio

import asyncpg


async def main() -> None:
    conn = await asyncpg.connect(user="postgres", password="postgres", database="sunoapi", host="localhost")
    cols = await conn.fetch(
        """
        select column_name, data_type from information_schema.columns
        where table_schema='public' and table_name='suno_accounts' order by ordinal_position
        """
    )
    print("columns:", ", ".join(f"{c['column_name']}:{c['data_type']}" for c in cols))
    rows = await conn.fetch("select * from suno_accounts limit 3")
    for row in rows:
        data = dict(row)
        for key in list(data):
            value = data[key]
            if isinstance(value, (bytes, memoryview)):
                data[key] = f"<{len(value)} bytes>"
            elif isinstance(value, str) and len(value) > 40:
                data[key] = value[:12] + "…"
        print(data)
    await conn.close()


asyncio.run(main())
