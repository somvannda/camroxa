"""Seed one playable song for the local Studio sandbox (G12/G16 verification).

Creates a short silent WAV under camxora.com/public/seed/ and inserts a completed
suno_task for the given user so the editor's library has something real to list,
add to a track, and show provenance for.

Local development only.
"""

import asyncio
import math
import os
import struct
import sys
import wave
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg

DB = os.environ.get(
    "PLATFORM_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/camxora_pfm_sandbox"
).replace("postgresql+asyncpg://", "postgresql://")
EMAIL = "somvannda@gmail.com"
WAV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "camxora.com",
    "public",
    "seed",
    "demo-loop.wav",
)
PUBLIC_URL = os.environ.get("STUDIO_SEED_PUBLIC_URL", "http://localhost:3103") + "/seed/demo-loop.wav"


def write_wav(path: str, seconds: float = 4.0, rate: int = 22050) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = bytearray()
        total = int(seconds * rate)
        for i in range(total):
            # A quiet 220 Hz tone so the clip is audible but unobtrusive.
            value = int(1200 * math.sin(2 * math.pi * 220 * i / rate))
            frames += struct.pack("<h", value)
        out.writeframes(bytes(frames))


async def main() -> int:
    write_wav(WAV_PATH)
    print("wav:", WAV_PATH)

    conn = await asyncpg.connect(DB)
    try:
        user_id = await conn.fetchval("select id from users where lower(email)=lower($1)", EMAIL)
        if not user_id:
            print("no user", EMAIL)
            return 1

        existing = await conn.fetchval(
            "select id from suno_tasks where user_id=$1 and title=$2", user_id, "Seed Demo Loop"
        )
        if existing:
            print("task already exists:", existing)
            return 0

        now = datetime.now(timezone.utc)
        workspace_id = await conn.fetchval(
            "select id from web_music_workspaces where user_id=$1 order by is_default desc limit 1",
            user_id,
        )
        await conn.execute(
            """
            insert into suno_tasks (
                id, user_id, request_hash, model, title, lyrics, style, instrumental,
                status, audio_url_ok, downloaded_ok, downloaded_alt, created_at, updated_at,
                source, workspace_id, stream_ready_ok, stream_ready_alt,
                package_status_ok, package_status_alt, duration_ok, duration_alt
            ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
            """,
            uuid4(),
            user_id,
            f"seed-{uuid4().hex[:12]}",
            "v6",
            "Seed Demo Loop",
            "[Instrumental]",
            "downtempo electronic loop, warm analog bass, soft drums, 96 bpm",
            True,
            "complete",
            PUBLIC_URL,
            False,
            False,
            now,
            now,
            # The list endpoint filters on this exact source value and workspace.
            "web_music",
            workspace_id,
            True,
            True,
            "ready",
            "ready",
            4.0,
            4.0,
        )
        print("inserted Seed Demo Loop ->", PUBLIC_URL)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
