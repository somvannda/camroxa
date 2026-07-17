#!/usr/bin/env python3
"""Deep probe for generate-names 502 on sandbox."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, os, asyncpg
from platform_api.services.key_encryption import KeyEncryption

async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    enc=KeyEncryption(os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY",""))
    rows=await conn.fetch("SELECT provider, label, status, encrypted_key_value FROM api_key_entries ORDER BY provider")
    for row in rows:
        try:
            plain=enc.decrypt(row["encrypted_key_value"])
            print(row["provider"], row["label"], row["status"], "decrypt_ok", len(plain))
        except Exception as exc:
            print(row["provider"], row["label"], row["status"], "decrypt_FAIL", type(exc).__name__, str(exc)[:120])
    for key in [
        "ai.routing.assignments",
        "ai.routing.text_fallback_chain",
        "ai.routing.operation_assignments",
    ]:
        row=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1", key)
        print(key, "present" if row else "missing")
        if row:
            print(" ", row["value"][:240])
    await conn.close()
asyncio.run(main())
PY'
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
