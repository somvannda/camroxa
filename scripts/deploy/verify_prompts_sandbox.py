#!/usr/bin/env python3
"""Verify music prompt counts on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = r"""
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, asyncpg, os
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    for label, sql in [
        ("music_descriptions_admin", "SELECT COUNT(*) FROM music_descriptions WHERE user_id IS NULL"),
        ("music_structures_admin", "SELECT COUNT(*) FROM music_structures WHERE user_id IS NULL"),
        ("channel_prompts", "SELECT COUNT(*) FROM channel_prompts"),
    ]:
        print(label, await conn.fetchval(sql))
    await conn.close()
asyncio.run(main())
PY'
"""
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
