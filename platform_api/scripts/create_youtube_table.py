import asyncio
import asyncpg


async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS youtube_upload_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            song_id UUID REFERENCES songs(id),
            title VARCHAR(500) NOT NULL,
            description TEXT,
            tags VARCHAR(1000),
            privacy_status VARCHAR(20) NOT NULL DEFAULT 'private',
            youtube_video_id VARCHAR(100),
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_youtube_upload_jobs_user_id ON youtube_upload_jobs(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_youtube_upload_jobs_status ON youtube_upload_jobs(user_id, status)")
    await conn.close()
    print("youtube_upload_jobs table created successfully")


if __name__ == "__main__":
    asyncio.run(main())
