#!/usr/bin/env python3
"""Full api journal dump for pich's failing window 17:53:00-17:59:00 CEST."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set +e
echo '=== full api journal 17:53:00 -> 17:59:30 ==='
journalctl -u camxora-api --since "2026-09-05 17:53:00" --until "2026-09-05 17:59:30" --no-pager 2>/dev/null | tail -250
echo
echo '=== uvicorn worker restarts in last 1h ==='
journalctl -u camxora-api --since "1 hour ago" --no-pager 2>/dev/null | grep -iE 'Started server process|Finished server process|Waiting for child|died|Shutting down|Application startup complete|Traceback' | tail -30
echo FULL_WINDOW_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
