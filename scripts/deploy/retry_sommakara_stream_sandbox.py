#!/usr/bin/env python3
"""Retry failed streaming upload jobs for sommakara batch."""

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
    os.chdir("/opt/camxora/repo")
    os.environ.pop("PLATFORM_CORS_ORIGINS", None)
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        user = await pool.fetchrow("SELECT id FROM users WHERE email ILIKE '%sommakara%' LIMIT 1")
        if not user:
            print("user not found")
            return
        jobs = await pool.fetch(
            "SELECT id, kind, status, error FROM stream_upload_jobs "
            "WHERE user_id = $1 AND status = 'failed' ORDER BY created_at",
            user["id"],
        )
        print(f"retrying {len(jobs)} failed jobs")
        service = StreamingUploadService(pool)
        for row in jobs:
            job_id = UUID(str(row["id"]))
            try:
                result = await service.retry_failed_job(job_id)
                print("ok", row["kind"], job_id, result.get("storage_key"))
            except Exception as exc:
                print("fail", row["kind"], job_id, str(exc)[:120])
        await asyncio.sleep(2)
        summary = await pool.fetch(
            "SELECT status, COUNT(*) AS cnt FROM stream_upload_jobs WHERE user_id = $1 GROUP BY status",
            user["id"],
        )
        print("\\n=== job status counts ===")
        for row in summary:
            print(dict(row))
        tracks = await pool.fetch(
            "SELECT title, variant, publish_status FROM stream_tracks WHERE user_id = $1 LIMIT 20",
            user["id"],
        )
        print("\\n=== tracks ===")
        for row in tracks:
            print(json.dumps(dict(row), default=str))
    finally:
        await pool.close()

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/retry_sommakara_stream.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
