#!/usr/bin/env python3
"""Check stored Suno CDN urls for recent plain tracks + proxy behavior."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r'''
set +e
REPO=/opt/camxora/repo/platform_api
cd $REPO && env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
import asyncio, os
import asyncpg
import httpx

async def main():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    ids = ["6e80e724", "47f1c91e", "8191a430"]
    for prefix in ids:
        row = await pool.fetchrow(
            "SELECT id, status, audio_url_ok, audio_url_alt, external_task_id "
            "FROM suno_tasks WHERE id::text LIKE $1", prefix + "%"
        )
        if not row:
            print(prefix, "NOT FOUND"); continue
        url = row["audio_url_ok"] or row["audio_url_alt"]
        print("\nTASK", row["id"], row["status"], "ext", (row["external_task_id"] or "")[:16])
        print("  url:", (url or "")[:160])
        if not url:
            print("  NO URL"); continue
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(url, headers={"Range": "bytes=0-1023"})
                ct = r.headers.get("content-type", "?")
                cl = r.headers.get("content-length", "?")
                body = r.content[:64]
                print("  HEAD/GET status:", r.status_code, "content-type:", ct, "len:", cl)
                print("  first bytes:", body[:32])
        except Exception as exc:
            print("  GET failed:", type(exc).__name__, str(exc)[:200])
    await pool.close()

asyncio.run(main())
PYEOF
echo URLS_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
