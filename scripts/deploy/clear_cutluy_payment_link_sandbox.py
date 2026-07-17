#!/usr/bin/env python3
"""Clear invalid CutLuy payment_link_id on sandbox and restart API."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE_PY = """
import asyncio
import os
import asyncpg

async def main() -> None:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1",
            "billing.cutluy.payment_link_id",
        )
        before = row["value"] if row else ""
        await conn.execute(
            "UPDATE system_settings SET value = '', updated_at = NOW() WHERE key = $1",
            "billing.cutluy.payment_link_id",
        )
        print(f"Cleared payment_link_id (was: {before!r})")
    finally:
        await conn.close()

asyncio.run(main())
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    sftp = client.open_sftp()
    with sftp.file("/tmp/clear_cutluy_link.py", "w") as remote_file:
        remote_file.write(REMOTE_PY)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
        "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/clear_cutluy_link.py' && "
        "systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
