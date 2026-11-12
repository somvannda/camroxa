import asyncio
import asyncpg

DB = "postgresql://postgres:postgres@localhost:5432/camxora_pfm_sandbox"


async def main() -> None:
    conn = await asyncpg.connect(DB)
    try:
        await conn.execute(
            """
            update suno_tasks
               set status = 'success',
                   audio_id_ok = 'sandbox-clip-ok',
                   audio_id_alt = 'sandbox-clip-alt'
             where title = 'Seed Demo Loop'
            """
        )
        row = await conn.fetchrow(
            """
            select title, status, audio_id_ok, audio_id_alt, stream_ready_ok
              from suno_tasks where title = 'Seed Demo Loop'
            """
        )
        print(dict(row))
    finally:
        await conn.close()


asyncio.run(main())
