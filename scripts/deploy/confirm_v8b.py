#!/usr/bin/env python3
"""Confirm marker + packaged still blocked."""
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

REMOTE_CMD = (
    "set +e\n"
    "grep -n 'Prefer the freshly-stored Suno CDN URL' /opt/camxora/repo/platform_api/services/web_music_service.py | head -1\n"
    "grep -n 'return str(stored_url), \"suno\"' /opt/camxora/repo/platform_api/services/web_music_service.py | head -1\n"
    "systemctl show -p ActiveEnterTimestamp camxora-api 2>/dev/null\n"
    "curl -s -o /dev/null -w 'api_health=%{http_code}\\n' -m 8 http://127.0.0.1:8100/health\n"
    "echo DONE2\n"
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-800:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
