#!/usr/bin/env python3
"""Grab api journal last 12 min: pich tracebacks for the 500/422/502 attempts."""
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
echo '=== api journal last 12 minutes: generate/traceback/exception lines ==='
journalctl -u camxora-api --since "12 minutes ago" --no-pager 2>/dev/null | grep -iE 'web-music /generate|service\.generate|Traceback|Error|Exception|ExternalServiceError|Validation|5b1673dc' | tail -120
echo
echo '=== LAST 60 raw lines (whole picture, tail) ==='
journalctl -u camxora-api --since "12 minutes ago" --no-pager 2>/dev/null | tail -60
echo GRAB_DONE
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
