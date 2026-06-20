import asyncpg, asyncio, os
from dotenv import load_dotenv
load_dotenv()

async def run():
    dsn = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/platform_db')
    if dsn.startswith('postgresql+asyncpg://'):
        dsn = dsn.replace('postgresql+asyncpg://', 'postgresql://', 1)
    conn = await asyncpg.connect(dsn)
    exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='channel_prompts' AND column_name='match_key')")
    if exists:
        print('Column match_key already exists')
    else:
        await conn.execute("ALTER TABLE channel_prompts ADD COLUMN match_key VARCHAR(100)")
        await conn.execute("CREATE INDEX idx_channel_prompts_match_key ON channel_prompts(match_key)")
        print('Column match_key added')
    await conn.close()

asyncio.run(run())
