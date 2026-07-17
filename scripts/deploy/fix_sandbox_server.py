#!/usr/bin/env python3
"""Fix nginx HTTPS, API multipart, and reset admin password on sandbox VPS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

NGINX_CONF = Path(__file__).resolve().parent / "nginx-camxora-sandbox.conf"


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else "duke@camxora.com"
    password = sys.argv[2] if len(sys.argv) > 2 else ""

    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        None,
    )

    sftp = client.open_sftp()
    sftp.put(str(NGINX_CONF), "/etc/nginx/sites-available/camxora-sandbox")
    sftp.close()

    reset_py = f"""
import asyncio, os, bcrypt, asyncpg
async def main():
    dsn = os.environ['PLATFORM_DATABASE_URL'].replace('postgresql+asyncpg://','postgresql://',1)
    conn = await asyncpg.connect(dsn)
    salt = bcrypt.gensalt(rounds=12)
    h = bcrypt.hashpw({password!r}.encode(), salt).decode()
    await conn.execute("UPDATE users SET password_hash=$1, role='admin', status='active' WHERE email=$2", h, {email.lower()!r})
    await conn.close()
    print('password updated for', {email.lower()!r})
asyncio.run(main())
"""

    commands = [
        "ln -sf /etc/nginx/sites-available/camxora-sandbox /etc/nginx/sites-enabled/camxora-sandbox",
        "nginx -t && systemctl reload nginx",
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && pip install -q python-multipart'",
        "systemctl restart camxora-api",
    ]

    if password:
        remote_py = "/tmp/camxora_reset_pw.py"
        sftp = client.open_sftp()
        with sftp.file(remote_py, "w") as f:
            f.write(reset_py)
        sftp.close()
        commands.append(
            f"sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
            f"/opt/camxora/repo/platform_api/.venv/bin/python {remote_py}'"
        )

    for cmd in commands:
        print(f">>> {cmd[:80]}...")
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        if out.strip():
            print(out)
        if err.strip() and "could not change directory" not in err:
            print(err, file=sys.stderr)
        if code != 0:
            print(f"FAILED exit {code}", file=sys.stderr)
            client.close()
            return code

    client.close()
    print("Sandbox nginx HTTPS restored (Camxora, not botifyr).")
    if password:
        print(f"Password updated for {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
