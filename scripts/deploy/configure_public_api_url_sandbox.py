#!/usr/bin/env python3
"""Configure sandbox public API URL for YouTube OAuth redirect + restart API."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

PUBLIC_API = "https://api.sandbox.camxora.com"


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote_py = f"""
import asyncio, asyncpg, os

PUBLIC_API = {PUBLIC_API!r}

async def run():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    await conn.execute(
        '''
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ('platform.public_api_base_url', $1, 'string', NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, value_type = EXCLUDED.value_type, updated_at = NOW()
        ''',
        PUBLIC_API,
    )
    row = await conn.fetchrow("SELECT value FROM system_settings WHERE key = 'platform.public_api_base_url'")
    print("platform.public_api_base_url", row["value"] if row else None)
    await conn.close()

asyncio.run(run())
"""
    sftp = client.open_sftp()
    with sftp.file("/tmp/set_public_api_url.py", "w") as f:
        f.write(remote_py)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        "set +a && /opt/camxora/repo/platform_api/.venv/bin/python /tmp/set_public_api_url.py' && "
        "systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
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
