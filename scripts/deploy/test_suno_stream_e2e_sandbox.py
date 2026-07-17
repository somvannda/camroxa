#!/usr/bin/env python3
"""End-to-end sandbox test: signed Suno callback -> B2 stream upload."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r'''
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

import asyncpg

TEST_MP3 = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
EXTERNAL_TASK_ID = "sandbox-stream-e2e-test"


def sign(body: bytes, secret: str) -> str:
    return hmac.HMAC(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def main() -> int:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    hmac_secret = (os.environ.get("PLATFORM_SUNO_CALLBACK_HMAC_SECRET") or "").strip()
    if not hmac_secret:
        print("ERROR: PLATFORM_SUNO_CALLBACK_HMAC_SECRET is missing")
        return 1

    conn = await asyncpg.connect(dsn)

    print("=== Suno key pool ===")
    rows = await conn.fetch(
        "SELECT provider, status, COUNT(*) AS cnt FROM api_key_entries WHERE provider = 'suno' GROUP BY provider, status"
    )
    if not rows:
        print("WARNING: no suno keys in api_key_entries")
    for row in rows:
        print(dict(row))

    user = await conn.fetchrow(
        "SELECT id, email FROM users WHERE email = 'somvannda@gmail.com' LIMIT 1"
    )
    if not user:
        user = await conn.fetchrow("SELECT id, email FROM users ORDER BY created_at ASC LIMIT 1")
    if not user:
        print("ERROR: no users in database")
        return 1
    user_id = user["id"]
    print(f"Using user: {user['email']} ({user_id})")

    profiles = await conn.fetch(
        "SELECT id, name FROM channel_profiles WHERE user_id = $1 ORDER BY created_at ASC LIMIT 2",
        user_id,
    )
    ok_profile_id = profiles[0]["id"] if len(profiles) >= 1 else None
    alt_profile_id = profiles[1]["id"] if len(profiles) >= 2 else ok_profile_id
    if not ok_profile_id:
        print("ERROR: user has no channel profiles; create profiles before Suno batch tests")
        return 1

    existing = await conn.fetchrow(
        "SELECT id, status FROM suno_tasks WHERE external_task_id = $1",
        EXTERNAL_TASK_ID,
    )

    if existing:
        task_id = existing["id"]
        batch_id = await conn.fetchval("SELECT batch_id FROM suno_tasks WHERE id = $1", task_id)
        song_id = await conn.fetchval("SELECT song_id FROM suno_tasks WHERE id = $1", task_id)
        print(f"Reusing seeded suno_task {task_id}")
        await conn.execute(
            "UPDATE suno_tasks SET status = 'PENDING', audio_url_ok = NULL, audio_url_alt = NULL, updated_at = NOW() WHERE id = $1",
            task_id,
        )
    else:
        batch_id = uuid4()
        song_id = uuid4()
        task_id = uuid4()
        await conn.execute(
            """
            INSERT INTO batches (
                id, user_id, ok_profile_id, alt_profile_id, song_count, status,
                auto_gsuno, auto_gen_image, ok_album, alt_album, ok_run_dir, alt_run_dir
            ) VALUES ($1, $2, $3, $4, 1, 'running', true, false, 'Sandbox Test Album', 'Sandbox Alt Album', '/tmp/sandbox-ok', '/tmp/sandbox-alt')
            """,
            batch_id,
            user_id,
            ok_profile_id,
            alt_profile_id,
        )
        await conn.execute(
            """
            INSERT INTO songs (id, batch_id, batch_index, user_id, title, album, lyrics, status)
            VALUES ($1, $2, 0, $3, 'Sandbox Stream Test', 'Sandbox Test Album', 'Test lyrics', 'suno_pending')
            """,
            song_id,
            batch_id,
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO suno_tasks (
                id, song_id, user_id, batch_id, request_hash, model, title, lyrics, style,
                instrumental, external_task_id, status, output_dir_ok, output_dir_alt
            ) VALUES (
                $1, $2, $3, $4, $5, 'V4', 'Sandbox Stream Test', 'Test lyrics', 'electronic',
                false, $6, 'PENDING', '/tmp/sandbox-ok', '/tmp/sandbox-alt'
            )
            """,
            task_id,
            song_id,
            user_id,
            batch_id,
            hashlib.sha256(b"sandbox-stream-e2e").hexdigest(),
            EXTERNAL_TASK_ID,
        )
        print(f"Seeded batch={batch_id} song={song_id} suno_task={task_id}")

    payload = {
        "task_id": EXTERNAL_TASK_ID,
        "status": "SUCCESS",
        "audio_url_ok": TEST_MP3,
        "audio_url_alt": TEST_MP3,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8100/api/v1/callbacks/suno",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": sign(body, hmac_secret),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Callback response: {resp.status} {resp.read(200).decode()}")
    except urllib.error.HTTPError as exc:
        print(f"Callback failed: HTTP {exc.code} {exc.read(300).decode()}")
        await conn.close()
        return 1

    print("Waiting for async streaming upload...")
    for attempt in range(12):
        time.sleep(2)
        jobs = await conn.fetch(
            "SELECT kind, status, storage_key, error FROM stream_upload_jobs WHERE suno_task_id = $1 ORDER BY created_at",
            task_id,
        )
        if jobs and all(row["status"] in {"success", "failed"} for row in jobs):
            break

    print("\n=== Stream upload jobs ===")
    jobs = await conn.fetch(
        "SELECT id, kind, status, storage_key, error, created_at, updated_at FROM stream_upload_jobs WHERE suno_task_id = $1 ORDER BY created_at",
        task_id,
    )
    if not jobs:
        print("(none created)")
    for row in jobs:
        print(json.dumps({k: (v.isoformat() if hasattr(v, 'isoformat') else (str(v) if v is not None else None)) for k, v in dict(row).items()}, default=str))

    print("\n=== Stream tracks ===")
    tracks = await conn.fetch(
        """
        SELECT t.id, t.title, t.variant, t.storage_key, t.publish_status, t.size_bytes
        FROM stream_tracks t
        WHERE t.suno_task_id = $1
        ORDER BY t.created_at
        """,
        task_id,
    )
    if not tracks:
        print("(none)")
    for row in tracks:
        print(json.dumps(dict(row), default=str))

    task_row = await conn.fetchrow(
        "SELECT status, audio_url_ok IS NOT NULL AS has_ok, downloaded_ok FROM suno_tasks WHERE id = $1",
        task_id,
    )
    print("\n=== Suno task after callback ===")
    print(dict(task_row))

    await conn.close()

    ok_jobs = [row for row in jobs if row["status"] == "success"]
    if not ok_jobs:
        print("\nRESULT: FAIL — streaming upload did not succeed")
        return 1
    if not tracks:
        print("\nRESULT: FAIL — upload jobs succeeded but no stream_tracks rows")
        return 1
    print("\nRESULT: PASS — sandbox uploaded MP3(s) to music stream storage")
    return 0

raise SystemExit(asyncio.run(main()))
'''

def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/test_suno_stream_e2e.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(b"\nSTDERR:\n")
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()

    # Re-probe public catalog
    import json
    import urllib.request

    print("\n=== Public streaming home (after test) ===")
    try:
        with urllib.request.urlopen(
            "https://api.sandbox.camxora.com/api/v1/public/streaming/home",
            timeout=20,
        ) as resp:
            data = json.loads(resp.read().decode())
            featured = data.get("featured_tracks") or data.get("tracks") or []
            print(f"featured_tracks: {len(featured)}")
            for track in featured[:3]:
                print(f"  - {track.get('title')} ({track.get('id')})")
    except Exception as exc:
        print(f"ERR: {exc}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
