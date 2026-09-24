#!/usr/bin/env python3
"""Production runner: confirm ensure_period_grant is idempotent for iamduke."""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_PY = DEPLOY / "_verify_period_grant_prod.py"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/verify_period_grant_prod.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        cmd = (
            "if ! ip -4 addr | grep -q '82.197.71.248'; then echo Refusing non-production host; exit 1; fi; "
            "sudo -u camxora bash -lc "
            "'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && "
            "export PYTHONPATH=/opt/camxora/repo && python /tmp/verify_period_grant_prod.py'"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=90)
        sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            sys.stderr.write(err[:2000] + "\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
