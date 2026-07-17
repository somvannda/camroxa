#!/usr/bin/env python3
"""Probe CutLuy with/without payment_link_id."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    client = ssh_connect(
        load_secrets()["VPS_HOST"],
        load_secrets()["VPS_USER"],
        ensure_deploy_key(),
        None,
    )
    cmd = r"""
API_KEY=$(sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, asyncpg, os
async def main():
    conn=await asyncpg.connect(os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1))
    row=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1","billing.cutluy.secret_key")
    print(row["value"] if row else "")
    await conn.close()
asyncio.run(main())
PY')
echo 'without payment_link_id:'
curl -s -w '\nHTTP:%{http_code}\n' -X POST https://cutluy.com/v1/payments \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d '{"amount":1.0,"reference_id":"diag-no-link-2","metadata":{"test":true}}'
"""
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
