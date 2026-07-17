#!/usr/bin/env python3
"""Backfill streaming uploads for sommakara batch after schedule fix."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = '''
import asyncio
import json
import os
from uuid import UUID

import asyncpg

from platform_api.services.streaming_upload_service import StreamingUploadService


async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE email ILIKE '%sommakara%' LIMIT 1"
        )
        if not user:
            print("user not found")
            return
        batch = await conn.fetchrow(
            "SELECT id FROM batches WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            user["id"],
        )
        if not batch:
            print("batch not found")
            return
        tasks = await conn.fetch(
            "SELECT id FROM suno_tasks WHERE batch_id = $1 AND status = 'success'",
            batch["id"],
        )
        print(f"scheduling {len(tasks)} streaming uploads for batch {batch['id']}")
        service = StreamingUploadService(pool)
        for row in tasks:
            task_id = UUID(str(row["id"]))
            service.schedule_suno_streaming_upload(suno_task_id=task_id)
            print("scheduled", task_id)
        await asyncio.sleep(45)
        jobs = await conn.fetch(
            "SELECT id, kind, status, left(error, 100) AS error FROM stream_upload_jobs "
            "WHERE user_id = $1 ORDER BY created_at DESC LIMIT 20",
            user["id"],
        )
        print("\\n=== upload jobs after backfill ===")
        for job in jobs:
            print(json.dumps(dict(job), default=str))
        tracks = await conn.fetch(
            "SELECT id, title, variant, publish_status FROM stream_tracks WHERE user_id = $1 LIMIT 20",
            user["id"],
        )
        print("\\n=== stream tracks ===")
        for track in tracks:
            print(json.dumps(dict(track), default=str))
    finally:
        await pool.close()
        await conn.close()

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/backfill_sommakara_stream.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
