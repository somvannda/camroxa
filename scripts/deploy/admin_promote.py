#!/usr/bin/env python3
"""Promote a user to admin on the sandbox VPS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, resolve_sandbox_ssh, ssh_connect  # noqa: E402


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else ""
    if not email:
        print("Usage: admin_promote.py user@example.com")
        return 1

    # Sandbox-only: the canonical guard refuses a host that looks like production.
    host, user, password = resolve_sandbox_ssh()
    client = ssh_connect(host, user, ensure_deploy_key(), password)
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
