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


def upload_seed(task_id) -> tuple[str | None, str | None]:
    """Upload the seed WAV to the configured S3 stand-in, keyed by task id.

    The playback proxy only signs task-scoped storage keys; without this the seed is
    listable but not streamable (it would hit the encrypted-player guard).
    """
    key_id = os.environ.get("PLATFORM_STREAMING_B2_KEY_ID")
    app_key = os.environ.get("PLATFORM_STREAMING_B2_APPLICATION_KEY")
    bucket = os.environ.get("PLATFORM_STREAMING_B2_BUCKET")
    endpoint = os.environ.get("PLATFORM_STREAMING_B2_ENDPOINT")
    region = os.environ.get("PLATFORM_STREAMING_B2_REGION", "us-east-1")
    if not (key_id and app_key and bucket and endpoint):
        return None, None
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=app_key,
            region_name=region,
        )
        key_ok = f"web-music/{task_id}/seed-ok.wav"
        key_alt = f"web-music/{task_id}/seed-alt.wav"
        for key in (key_ok, key_alt):
            s3.upload_file(WAV_PATH, bucket, key, ExtraArgs={"ContentType": "audio/wav"})
        print("uploaded seed audio to", bucket)
        return key_ok, key_alt
    except Exception as exc:  # noqa: BLE001 - seeding is best effort
        print("upload skipped:", exc)
        return None, None


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
        if existing and "--force" not in sys.argv:
            print("task already exists:", existing)
            return 0
        if existing:
            await conn.execute("delete from suno_tasks where id=$1", existing)
            print("removed old seed task")

        now = datetime.now(timezone.utc)
        workspace_id = await conn.fetchval(
            "select id from web_music_workspaces where user_id=$1 order by is_default desc limit 1",
            user_id,
        )
        task_id = uuid4()
        key_ok, key_alt = upload_seed(task_id)
        await conn.execute(
            """
            insert into suno_tasks (
                id, user_id, request_hash, model, title, lyrics, style, instrumental,
                status, audio_url_ok, downloaded_ok, downloaded_alt, created_at, updated_at,
                source, workspace_id, stream_ready_ok, stream_ready_alt,
                package_status_ok, package_status_alt, duration_ok, duration_alt,
                b2_storage_key_ok, b2_storage_key_alt
            ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24)
            """,
            task_id,
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
            # No encrypted package: the proxy may serve the signed object instead.
            "none",
            "none",
            4.0,
            4.0,
            key_ok,
            key_alt,
        )
        print("inserted Seed Demo Loop ->", key_ok or PUBLIC_URL)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
