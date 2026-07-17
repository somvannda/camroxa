#!/usr/bin/env python3
"""Reset a sandbox user password."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

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
    try:
        salt = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        updated = await conn.execute(
            """
            UPDATE users
            SET password_hash = $1, role = 'admin', status = 'active', updated_at = NOW()
            WHERE email = $2
            """,
            password_hash,
            email,
        )
        print(updated)
    finally:
        await conn.close()


asyncio.run(main())
'''
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset sandbox user password")
    parser.add_argument("email")
    parser.add_argument("password")
    args = parser.parse_args()

    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    remote_script = "/tmp/camxora_reset_password.py"
    remote_payload = "/tmp/camxora_reset_password.json"
    email = args.email.strip().lower()
    password = args.password
    payload = {"email": email, "password": password}

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
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()

    print(out.strip() or "(no stdout)")
    if err.strip():
        print(err, file=sys.stderr)
    if code != 0:
        return code

    # Clear lockouts for this email after reset.
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    clear_cmd = (
        f"redis-cli -n 1 DEL auth:lockout:{email} auth:failures:{email} >/dev/null; echo LOCKOUTS_CLEARED"
    )
    _, stdout, _ = client.exec_command(clear_cmd)
    print(stdout.read().decode("utf-8", errors="replace").strip())
    client.close()
    print(f"Password reset for {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
