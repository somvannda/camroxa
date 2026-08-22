#!/usr/bin/env python3
"""Run HLS backfill on sandbox packaged tracks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

REMOTE = r"""
sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && unset PLATFORM_CORS_ORIGINS && set +a && PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python - <<"PY"
import asyncio
import os
import sys

sys.path.insert(0, "/opt/camxora/repo")
import asyncpg
from platform_api.services.audio_package_service import AudioPackageService


async def main() -> None:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    try:
        svc = AudioPackageService(pool)
        for _ in range(10):
            result = await svc.backfill_hls(limit=10)
            print("backfill_hls", result)
            if int(result.get("ready") or 0) == 0:
                break
    finally:
        await pool.close()


asyncio.run(main())
PY'
"""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
