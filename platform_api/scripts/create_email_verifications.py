import asyncio
import asyncpg


async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            code VARCHAR(6) NOT NULL,
            purpose VARCHAR(20) NOT NULL DEFAULT 'register',
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_email_verifications_user ON email_verifications(user_id, purpose)")
    await conn.close()
    print("email_verifications table created successfully")


if __name__ == "__main__":
    asyncio.run(main())
