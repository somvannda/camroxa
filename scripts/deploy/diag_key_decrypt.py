#!/usr/bin/env python3
"""Tail API logs and test key decryption on sandbox."""

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
journalctl -u camxora-api --since '3 hours ago' --no-pager | tail -100
echo '--- decrypt probe ---'
sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, os
from platform_api.dependencies import get_db_pool
from platform_api.services.key_pool_service import KeyPoolService
from platform_api.repositories.key_pool_repo import KeyPoolRepository

async def main():
    pool = get_db_pool()
    svc = KeyPoolService(KeyPoolRepository(pool=pool))
    for provider in ["deepseek", "openai"]:
        try:
            key = await svc.get_active_key(provider)
            print(provider, "ok", key.label if key else None, "len", len(key.decrypted_value) if key else 0)
        except Exception as exc:
            print(provider, "FAIL", type(exc).__name__, str(exc)[:200])

asyncio.run(main())
PY'
"""
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
