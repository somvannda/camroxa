import asyncpg, asyncio, os
from dotenv import load_dotenv
load_dotenv()

async def run():
    dsn = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/platform_db')
    if dsn.startswith('postgresql+asyncpg://'):
        dsn = dsn.replace('postgresql+asyncpg://', 'postgresql://', 1)
    conn = await asyncpg.connect(dsn)
    exists = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'channel_prompts')")
    if exists:
        print('Table channel_prompts already exists')
    else:
        await conn.execute("""
            CREATE TABLE channel_prompts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL,
                content TEXT NOT NULL CHECK (char_length(content) BETWEEN 1 AND 5000),
                category VARCHAR(50) NOT NULL,
                genre VARCHAR(100) NOT NULL DEFAULT '',
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(name, category)
            )
        """)
        await conn.execute("CREATE INDEX idx_channel_prompts_category ON channel_prompts(category)")
        await conn.execute("CREATE INDEX idx_channel_prompts_genre ON channel_prompts(genre)")
        print('Table channel_prompts created successfully')
    await conn.close()

asyncio.run(run())
