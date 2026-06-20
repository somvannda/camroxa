"""Check which tables exist in platform_db."""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    tables = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    )
    print("Tables in platform_db:")
    for t in tables:
        print(f"  - {t['table_name']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
