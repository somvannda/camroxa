#!/usr/bin/env python3
"""Sync platform_api to sandbox and restart API (fast hotfix)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    archive = build_source_tarball()
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api
chown -R camxora:camxora $REPO/platform_api
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, asyncpg, os
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    row=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1","billing.cutluy.payment_link_id")
    print("payment_link_id before:", row["value"] if row else None)
    await conn.execute(
        "UPDATE system_settings SET value = $1, updated_at = NOW() WHERE key = $2",
        "",
        "billing.cutluy.payment_link_id",
    )
    await conn.close()
asyncio.run(main())
PY'
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
echo API_HOTFIX_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
