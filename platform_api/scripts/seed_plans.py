"""Seed default subscription plans."""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    
    defaults = [
        ("Monthly", 7900, 30, 2, 420, 7),
        ("Yearly", 69900, 365, 4, 840, 7),
        ("Lifetime", 149900, None, 5, None, 7),
    ]
    
    for name, price, cycle, profiles, quota, daily in defaults:
        await conn.execute(
            """
            INSERT INTO plans (name, price_cents, billing_cycle_days, profile_allowance,
                               monthly_song_quota, daily_song_limit_per_channel,
                               is_active, effective_from, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, true, NOW(), NOW(), NOW())
            ON CONFLICT (name) DO NOTHING
            """,
            name, price, cycle, profiles, quota, daily,
        )
    
    rows = await conn.fetch("SELECT name, price_cents, billing_cycle_days, monthly_song_quota FROM plans ORDER BY price_cents")
    print("Plans in database:")
    for r in rows:
        cycle = f"{r['billing_cycle_days']} days" if r['billing_cycle_days'] else "Lifetime"
        quota = str(r['monthly_song_quota']) if r['monthly_song_quota'] else "Unlimited"
        print(f"  {r['name']}: ${r['price_cents']/100:.2f} / {cycle}, {quota} songs/mo")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
