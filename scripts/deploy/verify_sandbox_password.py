#!/usr/bin/env python3
"""Verify password hash on sandbox for a user."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

PASSWORD = os.environ["CAMXORA_ADMIN_PASSWORD"]
EMAIL = os.environ.get("CAMXORA_ADMIN_EMAIL", "duke@camxora.com")

REMOTE_PY = textwrap.dedent(
    '''
import asyncio
import json
import os
import sys
from pathlib import Path
import bcrypt
import asyncpg


async def main() -> None:
    payload_path = sys.argv[1]
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    email = str(payload["email"]).strip().lower()
    password = str(payload["password"])
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        "SELECT email, role, status, password_hash FROM users WHERE email = $1",
        email,
    )
    await conn.close()
    if not row:
        print("USER_MISSING")
        return
    ok = bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8"))
    print("email", row["email"])
    print("role", row["role"])
    print("status", row["status"])
    print("hash_prefix", row["password_hash"][:20])
    print("password_matches", ok)


asyncio.run(main())
'''
)


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote_script = "/tmp/camxora_verify_password.py"
    remote_payload = "/tmp/camxora_verify_password.json"
    payload = {"email": EMAIL, "password": PASSWORD}
    sftp = client.open_sftp()
    with sftp.file(remote_script, "w") as remote_file:
        remote_file.write(REMOTE_PY)
    with sftp.file(remote_payload, "w") as remote_file:
        remote_file.write(json.dumps(payload))
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc "
        f"\"set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
        f"/opt/camxora/repo/platform_api/.venv/bin/python {remote_script} {remote_payload}\""
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
