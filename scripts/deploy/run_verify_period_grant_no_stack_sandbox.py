#!/usr/bin/env python3
"""Sandbox: call ensure_period_grant 5 times for duke@test.com; wallet must stay 50."""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

SANDBOX_HOST = "46.250.235.83"
REMOTE_PY = DEPLOY / "_verify_period_grant_no_stack.py"


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/verify_period_grant_no_stack.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        cmd = (
            "if ip -4 addr | grep -q '82.197.71.248'; then echo Refusing production host; exit 1; fi; "
            "sudo -u camxora bash -lc "
            "'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && "
            "export PYTHONPATH=/opt/camxora/repo && python /tmp/verify_period_grant_no_stack.py'"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=60)
        sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            sys.stderr.write(err[:2000] + "\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
