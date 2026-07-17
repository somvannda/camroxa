#!/usr/bin/env python3
"""Probe streaming config and retry one job via localhost admin API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r'''
import asyncio
import json
import os
import asyncpg

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(
        "SELECT key, CASE WHEN key LIKE '%application_key%' THEN '***' ELSE left(value, 40) END AS val "
        "FROM system_settings WHERE key LIKE 'streaming.%' ORDER BY key"
    )
    print("=== streaming system_settings ===")
    for r in rows:
        print(dict(r))
    job = await conn.fetchrow(
        "SELECT id, kind, status, error FROM stream_upload_jobs "
        "WHERE user_id = (SELECT id FROM users WHERE email ILIKE '%sommakara%' LIMIT 1) "
        "ORDER BY created_at LIMIT 1"
    )
    print("sample job:", json.dumps(dict(job) if job else None, default=str))
    await conn.close()

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/probe_stream_cfg.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
