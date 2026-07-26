#!/usr/bin/env python3
"""Fetch decrypted sandbox streaming B2 credentials (KEY=value lines)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r'''
import asyncio
import base64
import os
import asyncpg
from platform_api.services.key_encryption import KeyEncryption

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    master = os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY", "").strip()
    conn = await asyncpg.connect(dsn)
    kid = (await conn.fetchval("SELECT value FROM system_settings WHERE key = 'streaming.b2.key_id'") or "").strip()
    app = (await conn.fetchval("SELECT value FROM system_settings WHERE key = 'streaming.b2.application_key'") or "").strip()
    bucket = (await conn.fetchval("SELECT value FROM system_settings WHERE key = 'streaming.b2.bucket'") or "").strip()
    endpoint = (await conn.fetchval("SELECT value FROM system_settings WHERE key = 'streaming.b2.endpoint'") or "").strip()
    if master and app:
        try:
            raw = base64.urlsafe_b64decode(app.encode("ascii"))
            app = KeyEncryption(master_key=master).decrypt(raw)
        except Exception as exc:
            print("DECRYPT_ERROR=" + str(exc), flush=True)
    print("B2_SRC_KEY_ID=" + kid)
    print("B2_SRC_APPLICATION_KEY=" + app)
    print("B2_SRC_BUCKET=" + bucket)
    print("B2_ENDPOINT=" + endpoint)
    await conn.close()

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/fetch_b2_src_decrypted.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"), end="")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
