"""Sandbox-only: zero legacy plan_usage songs_used for open periods."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sql = (
            "UPDATE plan_usage SET songs_used = 0 WHERE period_end > NOW(); "
            "SELECT COUNT(*) AS open_periods_zeroed FROM plan_usage "
            "WHERE songs_used = 0 AND period_end > NOW();"
        )
        cmd = f"sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c {sql!r}"
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=60)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err[-1000:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
