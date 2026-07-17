#!/usr/bin/env python3
"""Promote a user to admin on the sandbox VPS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else ""
    if not email:
        print("Usage: admin_promote.py user@example.com")
        return 1

    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        None,
    )
    safe_email = email.replace("'", "''")
    sql_list = f"SELECT email, role FROM users;"
    sql_update = f"UPDATE users SET role = 'admin' WHERE email = '{safe_email}';"
    sql_check = f"SELECT email, role FROM users WHERE email = '{safe_email}';"

    for label, sql in [("users", sql_list), ("update", sql_update), ("check", sql_check)]:
        cmd = f"sudo -u postgres psql camxora_platform -c {sql!r}"
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        print(f"=== {label} (exit {code}) ===")
        if out.strip():
            print(out)
        if err.strip() and "could not change directory" not in err:
            print(err)

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
