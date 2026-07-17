#!/usr/bin/env python3
"""Create admin user(s) on sandbox VPS and enable open signup."""

from __future__ import annotations

import argparse
import secrets
import string
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def _gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


REMOTE_PY = textwrap.dedent(
    '''
import asyncio
import os
import sys
from uuid import uuid4

import asyncpg
import bcrypt


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def main() -> None:
    emails = sys.argv[1].split(",")
    passwords = sys.argv[2].split(",")
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO system_settings (key, value_type, value, updated_at)
            VALUES ('signup_mode', 'string', 'open', NOW())
            ON CONFLICT (key) DO UPDATE SET value = 'open', updated_at = NOW()
            """
        )
        for email, password in zip(emails, passwords, strict=True):
            email = email.strip().lower()
            if not email:
                continue
            existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
            if existing:
                await conn.execute(
                    "UPDATE users SET role = 'admin', status = 'active', updated_at = NOW() WHERE email = $1",
                    email,
                )
                print(f"PROMOTED {email}")
                continue
            user_id = uuid4()
            pw_hash = hash_password(password)
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, 'admin', 'active', NOW(), NOW())
                    """,
                    user_id,
                    email,
                    pw_hash,
                    email.split("@")[0],
                )
                await conn.execute(
                    "INSERT INTO credit_wallets (user_id, balance, updated_at) VALUES ($1, 0, NOW()) ON CONFLICT DO NOTHING",
                    user_id,
                )
            print(f"CREATED {email} {user_id}")
    finally:
        await conn.close()


asyncio.run(main())
'''
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create sandbox admin users")
    parser.add_argument(
        "emails",
        nargs="*",
        default=["somvannda@gmail.com", "duke@camxora.com"],
        help="Admin emails to create or promote",
    )
    args = parser.parse_args()
    emails = [e.strip().lower() for e in args.emails if e.strip()]
    passwords = [_gen_password() for _ in emails]

    secrets_cfg = load_secrets()
    client = ssh_connect(
        secrets_cfg["VPS_HOST"],
        secrets_cfg["VPS_USER"],
        ensure_deploy_key(),
        None,
    )

    remote_script = "/tmp/camxora_create_admin.py"
    sftp = client.open_sftp()
    with sftp.file(remote_script, "w") as remote_file:
        remote_file.write(REMOTE_PY)
    sftp.close()

    email_arg = ",".join(emails)
    pass_arg = ",".join(passwords)
    cmd = (
        f"sudo -u camxora bash -lc '"
        f"set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
        f"/opt/camxora/repo/platform_api/.venv/bin/python {remote_script} {email_arg!r} {pass_arg!r}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    client.close()

    print(out)
    if err.strip():
        print(err, file=sys.stderr)

    if code != 0:
        return code

    print("\n=== Admin credentials (change after first login) ===")
    for email, password in zip(emails, passwords, strict=True):
        print(f"  {email}")
        print(f"    password: {password}")
    print("\nSignup mode set to: open")
    print("Login: https://app.sandbox.camxora.com/login")
    print("Admin: https://admin.sandbox.camxora.com")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
