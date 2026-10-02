#!/usr/bin/env python3
"""Poll the pich repro task until it completes / fails."""
from __future__ import annotations

import sys
import time
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
TASK_ID = "1ff7aa0a-7ea6-4bab-9114-dd9f563a91b4"

REMOTE_CMD = r"""
set +e
REPO=/opt/camxora/repo/platform_api
cd $REPO
for i in 1 2 3 4 5 6; do
  sleep 45
  env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
import asyncio, os, sys
sys.path.insert(0, "/opt/camxora/repo")
import asyncpg

async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    row = await pool.fetchrow(
        "SELECT id, status, error_message, audio_url_ok, audio_url_alt, image_url_ok, "
        "title_ok, created_at, updated_at FROM suno_tasks WHERE id = $1",
        "%TASK%",
    )
    if row:
        print("STATUS:", row["status"], "| err:", (row["error_message"] or "")[:200], "| ok_ready:", bool(row["audio_url_ok"]), "| alt_ready:", bool(row["audio_url_alt"]))
    else:
        print("STATUS: NO_ROW")
    await pool.close()

asyncio.run(main())
PYEOF
  echo "--- poll $i done ---"
done
echo POLL_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== poll task {TASK_ID} -> {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = REMOTE_CMD.replace("%TASK%", TASK_ID)
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=420)
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
