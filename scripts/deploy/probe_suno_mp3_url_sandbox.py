#!/usr/bin/env python3
"""Probe Suno MP3 URL download from sandbox VPS."""

from __future__ import annotations

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
import httpx

async def probe_url(client, url):
    try:
        r = await client.get(url, follow_redirects=True)
        body = r.content
        return {
            "status": r.status_code,
            "content_type": r.headers.get("content-type"),
            "content_length": len(body),
            "url_prefix": url[:100],
        }
    except Exception as exc:
        return {"error": str(exc)[:200], "url_prefix": url[:100]}

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        "SELECT external_task_id, audio_url_ok, audio_url_alt FROM suno_tasks "
        "WHERE batch_id = '6ba527b6-01f1-4a5e-91a4-c9d0daaeaad2' LIMIT 1"
    )
    await conn.close()
    if not row:
        print("no row")
        return
    print("stored ok:", (row["audio_url_ok"] or "")[:120])
    print("stored alt:", (row["audio_url_alt"] or "")[:120])
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Camxora/1.0)",
        "Accept": "*/*",
    }
    async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
        for label, url in [("ok", row["audio_url_ok"]), ("alt", row["audio_url_alt"])]:
            if url:
                print(label, json.dumps(await probe_url(client, url)))

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/probe_suno_url.py"
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
