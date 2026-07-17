#!/usr/bin/env python3
"""Diagnose users list 500 on sandbox."""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = textwrap.dedent(
    '''
import asyncio
import os
import asyncpg

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('email_verifications','users')"
        )
        print("tables:", [r["tablename"] for r in tables])
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='email_confirmed'"
        )
        print("email_confirmed_col:", bool(cols))
        if any(r["tablename"] == "email_verifications" for r in tables):
            cnt = await conn.fetchval("SELECT COUNT(*) FROM email_verifications")
            print("email_verifications_count:", cnt)
        else:
            print("email_verifications_count: MISSING_TABLE")
    finally:
        await conn.close()

asyncio.run(main())
'''
)


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )
    remote_py = "/tmp/diag_users.py"
    sftp = client.open_sftp()
    with sftp.file(remote_py, "w") as fh:
        fh.write(REMOTE)
    sftp.close()
    _, stdout, stderr = client.exec_command(
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
        f"/opt/camxora/repo/platform_api/.venv/bin/python {remote_py}'"
    )
    print(stdout.read().decode())
    err = stderr.read().decode().strip()
    if err:
        print(err, file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
